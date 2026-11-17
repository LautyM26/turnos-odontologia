# Design — chatbot-reprogramacion (C-17)

## Context

Motivación y decisiones del usuario: ver `proposal.md`. Requisitos: `specs/appointment-rescheduling`, `specs/whatsapp-messaging`, `specs/public-booking`, `specs/platform-config`, `specs/data-export`.

Estado observado:

- **Huecos**: `buscar_huecos(session, clinica_id, profesional_id, prestacion_id, desde, hasta, ahora, paso_min)` busca en ventanas de hasta 7 días y devuelve `inicio`, `fin` y `sillon_ids`. El turno propio ocupa su horario, así que nunca se ofrece a sí mismo.
- **Turnos**: `crear_turno(..., origen, token_publico_hash)` hace commit adentro y ante un horario ocupado lanza `TurnoNoDisponible` (409). `transicionar_turno(..., actor_tipo)` admite `paciente_whatsapp` y `paciente_enlace`.
- **Respuestas de WhatsApp**: `procesar_mensaje_entrante` toma el saliente vigente más reciente (recordatorio u oferta). Con "reprogramar" hoy deja el entrante en la bandeja y responde `reprogramacion`. `enviar_texto_base` y `renderizar_texto` aceptan variables explícitas.
- **Reserva pública (C-06)**:
  - `_turno_por_token` busca por `token_publico_hash`, con UNIQUE parcial;
  - los endpoints públicos usan limiters `lectura` y `escritura` por IP;
  - la cancelación por token registra actor `paciente_enlace`.

## Goals / Non-Goals

**Goals:**

- La conversación vive en la base. Sobrevive a reinicios y a varios workers, y siempre se sabe en qué paso está cada paciente.
- Los dos caminos (WhatsApp y enlace) usan el **mismo** servicio `reprogramar(...)`.
- Un número suelto del paciente nunca cancela su turno por error: dentro de la conversación, o con una vencida pendiente de cierre, los números son opciones.

**Non-Goals:**

- Procesamiento de lenguaje natural.
- Conversación sin recordatorio previo.
- Pantalla web.
- Seña.

## Decisions

### D1 — `conversacion_wa`

Columnas (`TenantMixin` + timestamps):

- `id`, `paciente_id`, `telefono`, `turno_id` (el turno a reprogramar);
- `estado` ∈ `eligiendo|confirmando|ejecutando|cerrada`;
- `resultado` ∈ `reprogramado|sin_cambios|vencida|sin_opciones` (nullable, solo con `cerrada`);
- `opciones` JSONB: lista de `{inicio, fin, sillon_ids}` en ISO;
- `elegido` (índice, nullable);
- `turno_nuevo_id` (nullable);
- `expira_at`.

Restricciones:

- FKs compuestas a paciente y turno.
- `UNIQUE (clinica_id, telefono) WHERE estado <> 'cerrada'`: una conversación abierta por número.
- CHECK `(estado = 'cerrada') = (resultado IS NOT NULL)`.

Por qué una tabla y no un campo en `mensaje_whatsapp`: la conversación tiene estado propio y opciones que cambian. Los mensajes son un registro de lo enviado.

### D2 — Opciones (servicio único)

`opciones(session, turno, ahora, settings) -> list[dict]`:

- Si el turno no es reprogramable (`estado ∉ {reservado, confirmado}`, `is_active` falso o `inicio <= ahora`) → `[]`.
- `desde = ahora + REPROGRAMACION_ANTICIPACION_MIN`, redondeado hacia arriba al paso `AGENDA_PASO_MIN` para que los horarios queden "redondos".
- Recorre dos ventanas de 7 días con `buscar_huecos(..., turno.profesional_id, turno.prestacion_id, …)` y corta al llegar a 3.

### D3 — Reprogramar: claim, crear, cancelar

`reprogramar(session, turno, inicio, ahora, settings, actor_tipo, origen) -> Turno`:

1. Valida que `inicio` esté entre las `opciones` **recalculadas ahora**. Si no está y nunca fue una opción → `ReferenciaInvalida` (422). Si estaba en las opciones de la conversación pero ya no → `HorarioOcupado` (409, con las alternativas nuevas).
2. Prueba los `sillon_ids` del hueco en orden con `crear_turno(origen=…)` y se queda con el primero que funcione. Si todos dan 409 → `HorarioOcupado(alternativas)`.
3. Token del enlace (C-06): antes de crear se libera el hash del viejo (`token_publico_hash = NULL`, `flush`) y se pasa el mismo hash a `crear_turno`. Si el alta falla, el `rollback` lo restaura.
4. `transicionar_turno(viejo, 'cancelado', actor_id=None, actor_tipo, motivo=f'reprogramado al turno {nuevo.id}')`.

Riesgo conocido: el turno nuevo queda commiteado antes de cancelar el viejo. Si la cancelación falla, por ejemplo porque recepción lo marcó asistido en ese instante, el paciente queda con dos turnos activos. En ese caso el sistema deja un fallo en la bandeja de WhatsApp para que recepción lo resuelva. Es un caso de muy baja probabilidad y no vale una transacción distribuida.

### D4 — Máquina de la conversación (WhatsApp)

**Rama nueva en `procesar_mensaje_entrante`**. Antes de buscar recordatorio u oferta, busca la conversación de ese número que no esté `cerrada`. Si existe, registra el entrante (insert-first idempotente, sin `intencion` de agenda: `requiere_atencion` solo si no se entiende) y llama a `chatbot.responder(...)`:

| Estado y texto | Acción |
|---|---|
| vencida (`expira_at <= ahora`) | `cerrada/vencida` + `reprogramacion_vencida` |
| `eligiendo` + número `1..n` | `confirmando` (elegido, expira renovado) + `reprogramacion_confirmar` |
| `eligiendo`/`confirmando` + `0`/`no`/`cancelar` | `cerrada/sin_cambios` + `reprogramacion_sin_cambios` |
| `confirmando` + `si`/`confirmo`/`1` | claim `UPDATE … SET estado='ejecutando' WHERE estado='confirmando' RETURNING`; si no lo gana → `sin_efecto` |
| ganó el claim → `reprogramar` OK | `cerrada/reprogramado` + `reprogramacion_hecha` (variables del turno nuevo) |
| ganó el claim → `HorarioOcupado` con alternativas | `eligiendo` con las opciones nuevas + `reprogramacion_opciones` ("Ese horario se ocupó.") |
| ganó el claim → `HorarioOcupado` sin alternativas | `cerrada/sin_opciones` + bandeja + `reprogramacion` |
| otro texto | bandeja; la conversación no cambia |

**Inicio**. El camino "reprogramar" de C-15 (recordatorio vigente + intención `reprogramar`) llama a `chatbot.iniciar(...)`:

- con opciones → crea la conversación `eligiendo` (`expira_at = ahora + CHATBOT_TIMEOUT_MIN`) y envía `reprogramacion_opciones`;
- sin opciones → hace lo de hoy: bandeja + `reprogramacion`.

Si ya había una conversación abierta, el UNIQUE lo impide. En ese caso se reenvían las opciones de la existente.

Por qué el claim con estado `ejecutando`: `crear_turno` hace commit adentro. Es el mismo patrón de C-16 D6.

**Texto de opciones**. `{opciones}` es una lista "1) jue 12/03 10:00" en hora local de la clínica. La calcula PostgreSQL con `timezone()` y `to_char`, igual que `variables_horario`. `{intro}` va vacío, o "Ese horario se ocupó." cuando se reofrece.

### D5 — Endpoints públicos

En `api/publico.py`, con el patrón de C-06:

| Endpoint | Limiter | Respuestas |
|---|---|---|
| `GET /reservas/{token}/opciones` | `lectura` | 200 `[{inicio, fin}]` / 404 / 422 |
| `POST /reservas/{token}/reprogramar {inicio}` | `escritura` | 200 comprobante / 404 / 422 / 409 `{detail, alternativas}` |

Schemas con `extra='forbid'`. El servicio es `reprogramar(..., actor_tipo='paciente_enlace', origen='enlace')`.

### D6 — Migración, configuración y exportación

- **Migración `016_reprogramacion`**:
  - crea `conversacion_wa`;
  - amplía el CHECK de `plantilla_wa` y siembra los 5 textos nuevos;
  - el downgrade borra los textos si no se usaron (mismo criterio que la 015).
- **`Settings`**:
  - `chatbot_timeout_min`: 30, rango 5–240;
  - `reprogramacion_anticipacion_min`: 120, rango 0–1440.
- **`ENTIDADES_EXPORTABLES`**: suma `conversaciones_whatsapp`.

## Risks / Trade-offs

- **[El paciente responde a un recordatorio viejo mientras hay una conversación abierta]** → La conversación gana. Los números son opciones y el "0" sale sin cambios. Lo cubre un escenario de la spec.
- **[Dos turnos activos si la cancelación del viejo falla]** → Fallo en la bandeja (D3). Es raro y queda visible.
- **[Opciones calculadas con 30 min de vida]** → Al confirmar se recalculan siempre. Un 409 ofrece alternativas.
- **[Texto de opciones largo]** → Son 3 líneas como máximo, muy lejos del límite de 2000 caracteres de `mensaje_whatsapp.texto`.

## Migration Plan

1. `016_reprogramacion` (`down_revision = "015_lista_espera"`). Verificar que haya un único head.
2. Configuración opcional. No hay cron nuevo.
3. Rollback: la tabla y los textos se borran con el downgrade si no se usaron.
