# Design — lista-espera-relleno (C-16)

## Context

Motivación y decisiones del usuario: ver `proposal.md`. Requisitos: `specs/waitlist`, `specs/whatsapp-messaging`, `specs/platform-config`, `specs/data-export`. Reglas: skills `dominio-agenda` (RN-AG-06, RN-TU-04) y `dominio-whatsapp`.

Estado observado:

- **`turnos.py`**:
  - `crear_turno(session, clinica_id, datos, ahora, origen)` aplica pasado → referencias → horario → bloqueos → solapamiento → INSERT. **Hace commit**, y el 23P01 de la base se traduce a `TurnoNoDisponible` (409).
  - `transicionar_turno(..., actor_id=None, actor_tipo='paciente_whatsapp')` existe desde C-15 y también hace commit.
  - El pre-chequeo `_hay_turno_solapado`, `bloqueos_solapados` y `dentro_de_horario` son privados o de otros módulos.
  - `ORIGENES_TURNO` ya incluye `lista_espera`.
- **WhatsApp (C-15)**:
  - `despachar(session, mensajeria, msg, precio)` envía un saliente ya persistido y deja estado, costo y bandeja.
  - `renderizar(session, clinica_id, clave, turno_id)` toma las variables **del turno**: paciente, profesional, fecha y hora locales en SQL.
  - `procesar_mensaje_entrante` asocia la respuesta solo al último **recordatorio** vigente.
  - El texto base `oferta_hueco` ya está sembrado ("¿Lo tomás? Respondé 1 para aceptar o 2 para rechazar").
- **Jobs**: patrón cron del sistema operativo (`app/jobs/recordatorios.py`, con un claim por UNIQUE y `dormir` inyectable).
- **Exportación**: `ENTIDADES_EXPORTABLES`.

## Goals / Non-Goals

**Goals:**

- Que el hueco ofrecido se reserve por el **mismo** camino que el mostrador (`crear_turno`). El 409 sigue siendo la última palabra.
- Exactamente una reasignación por oferta, aun con mensajes repetidos o simultáneos.
- No tocar el camino caliente de cancelación (los endpoints de turnos de Matheo): la lista consume cancelaciones, no las intercepta.

**Non-Goals:**

- Eventos de dominio en proceso o colas.
- Ofertas en paralelo a varios pacientes por el mismo hueco.
- UI.

## Decisions

### D1 — Huecos detectados por el job (cron), no por un hook en la cancelación

`app/jobs/lista_espera.py::procesar_lista_espera(session, mensajeria, settings, ahora)`, cron cada 5 min:

1. **Vencer**: hace `UPDATE oferta SET estado='expirada' WHERE estado='pendiente' AND expira_at <= ahora RETURNING lista_espera_id` y devuelve esas entradas a `en_cola`.
2. **Huecos liberados**: busca turnos `cancelado`, `is_active`, `NOT es_sobreturno`, con `inicio >= ahora + anticipación`, sin oferta `pendiente` y con `horario_libre(...)` (D9). Los recorre por `inicio`.
3. Para cada hueco elige un candidato (D3), arma la oferta (D4) y la envía. Si el envío falla, anula la oferta y corta la corrida (spec "Fallo del canal no consume la cola").

Por qué un job y no un hook en `transicionar_turno` o en los endpoints de cancelación:

- Hay 3 caminos que cancelan (mostrador, enlace de C-06, WhatsApp de C-15) y C-17 suma otro. El job los cubre a todos sin tocarlos.
- El vencimiento de ofertas necesita un proceso periódico de todas formas.
- Si el gateway está caído, el próximo ciclo reintenta solo.

Costo: hasta 5 min de demora para la primera oferta, chico frente a la ventana de 30 min de cada oferta.

Que el hueco se cancele por adelantar un turno (D6) no requiere nada especial: es otro turno cancelado y lo levanta la corrida siguiente. Así sale la cascada que pidió el usuario.

### D2 — Modelo

**`lista_espera`** (`TenantMixin` + timestamps):

- Columnas:
  - `id`, `paciente_id`, `prestacion_id`;
  - `profesional_id` y `sillon_id` (nullable);
  - `turno_a_adelantar_id` (nullable);
  - `prioridad` `int` 0–10 (default 0);
  - `estado` ∈ `en_cola|ofertado|aceptado|salido`.
- FKs compuestas `(clinica_id, x)` a paciente, prestación, profesional, sillón y turno.
- `UNIQUE (clinica_id, paciente_id, prestacion_id) WHERE estado IN ('en_cola','ofertado')`: una entrada activa por paciente y prestación (409).
- Índice `(clinica_id, prestacion_id, estado, prioridad DESC, id)`: el `(prestacion_id, estado, prioridad)` de la ficha, con prefijo de tenant (regla 10).

**`oferta_lista_espera`** (`TenantMixin` + timestamps):

- Columnas:
  - `id`, `lista_espera_id`, `turno_liberado_id` (el cancelado de origen);
  - `inicio`, `fin`, `profesional_id`, `sillon_id`, `prestacion_id`: copiados del hueco; inmutables y auditables;
  - `estado` ∈ `pendiente|aceptada|rechazada|expirada|anulada`;
  - `expira_at`, `respondida_at`;
  - `mensaje_id` (FK `mensaje_whatsapp`), `turno_creado_id` (FK turno).
- `UNIQUE (clinica_id, turno_liberado_id) WHERE estado='pendiente'`: una oferta en curso por hueco. También resuelve la carrera entre el job y la oferta manual (409).
- `UNIQUE (clinica_id, lista_espera_id) WHERE estado='pendiente'`: una oferta en curso por entrada.
- `UNIQUE (clinica_id, lista_espera_id, turno_liberado_id)`: el mismo hueco nunca dos veces a la misma entrada. Es lo que hace avanzar la rotación.
- CHECK `turno_creado_id IS NULL OR estado='aceptada'`. No se exige la vuelta (aceptada ⇒ turno), porque el claim marca `aceptada` antes de crear el turno (D6).

La migración `015_lista_espera` además amplía el CHECK `plantilla_wa.clave_valida` y siembra `oferta_aceptada` y `oferta_no_disponible`. El downgrade los borra solo si ningún mensaje los usa, con un error claro si alguno los usa (mismo criterio que la 014).

### D3 — Elección del candidato: una consulta

Entradas de la clínica del hueco que cumplen todo esto:

- `estado='en_cola'` y `prestacion_id = hueco.prestacion_id`;
- `profesional_id IS NULL OR = hueco.profesional_id`, y lo mismo con `sillon_id`;
- `NOT EXISTS` oferta de ese hueco para esa entrada;
- paciente activo con `telefono`;
- `turno_a_adelantar_id IS NULL` o ese turno sigue activo con `inicio > hueco.inicio`.

Orden: `prioridad DESC, created_at, id`, `LIMIT 1`.

### D4 — Oferta y render con variables explícitas

`renderizar` se divide en dos funciones:

- `variables_horario(session, clinica_id, paciente_id, profesional_id, inicio) -> dict`: la misma SQL de fecha y hora locales.
- `renderizar_texto(session, clave, variables)`.

`renderizar(…, turno_id)` queda como envoltorio. La oferta usa el paciente **de la entrada**, no el del turno cancelado: el texto nunca nombra al paciente que canceló.

Orden de los pasos:

1. Se crea la oferta `pendiente` (con el UNIQUE como claim) y la entrada pasa a `ofertado`.
2. Se crea el saliente `oferta_hueco` (`turno_id = NULL`, `paciente_id` = el de la entrada) y se guarda `oferta.mensaje_id`. Commit.
3. `despachar`. Si devuelve False: oferta `anulada`, entrada `en_cola` y fin de la corrida.

### D5 — Asociación de la respuesta (extiende C-15)

`_recordatorio_vigente` pasa a ser `_contexto_vigente`: toma el último saliente a ese número en la clínica que sea:

- un `recordatorio_24h` con turno activo y futuro, o
- un `oferta_hueco` cuya oferta tiene hueco futuro (en cualquier estado: así una respuesta tardía recibe `oferta_no_disponible`).

Gana el más reciente. Si es una oferta, `procesar_mensaje_entrante` registra el entrante (insert-first, la idempotencia de C-15 intacta) con `paciente_id` y sin `turno_id`, y delega en `lista_espera.servicios.responder_oferta(...)`:

| Intención | Acción |
|---|---|
| confirmar | `aceptar_oferta` |
| cancelar | `rechazar_oferta` |
| otra | bandeja |

Esa delegación se hace con un import diferido dentro de la función, para evitar el ciclo whatsapp ↔ lista_espera. La lista depende de WhatsApp (`despachar`, `renderizar_texto`) y no al revés en el import del módulo.

### D6 — Aceptar: primero el claim, después crear el turno

`aceptar_oferta(session, oferta_id, ahora, mensajeria, precio)`:

1. `UPDATE oferta SET estado='aceptada', respondida_at=ahora WHERE id=:id AND estado='pendiente' AND expira_at > ahora RETURNING …` + commit. Ese es el claim: de dos aceptaciones simultáneas, gana solo una.
2. Si no ganó y la oferta ya estaba `aceptada` → no-op, sin respuesta. Cualquier otro estado → respuesta `oferta_no_disponible`.
3. `crear_turno(datos del hueco + paciente de la entrada, origen='lista_espera', ahora)`.
   - Si lanza `TurnoNoDisponible` o `ReferenciaInvalida`: oferta `anulada`, entrada `en_cola`, respuesta `oferta_no_disponible`.
   - Si sale bien: `turno_creado_id`, entrada `aceptado`. Si había turno a adelantar todavía cancelable: `transicionar_turno(…, 'cancelado', actor_id=None, actor_tipo='paciente_whatsapp', motivo='adelantado por lista de espera')`. Respuesta `oferta_aceptada` (variables del turno nuevo).

Por qué el claim va antes de `crear_turno`: este hace commit adentro y soltaría cualquier lock de fila. Con el estado como claim, la segunda aceptación ve `aceptada` y no hace nada, sin lock largo ni carrera.

`rechazar_oferta`: `UPDATE … SET estado='rechazada' WHERE estado='pendiente'`; la entrada vuelve a `en_cola`; sin respuesta.

### D7 — Oferta manual

`POST /api/lista-espera/{id}/ofertar {turno_liberado_id}` usa las mismas validaciones del hueco (D1.2) y la coincidencia de D3 contra esa entrada puntual, sin tener en cuenta la prioridad:

- falla una regla → 422;
- el hueco tiene oferta pendiente → 409 (por el UNIQUE);
- el envío falla → 502 con la oferta anulada.

### D8 — API y RBAC

Router `api/lista_espera.py`. Todo con `require_role("admin","recepcionista")` y tenant del JWT. Schemas con `extra='forbid'`.

| Endpoint | Respuesta |
|---|---|
| `POST /api/lista-espera` | 201 / 409 / 422 |
| `GET /api/lista-espera?prestacion_id` | activas ordenadas |
| `PATCH /api/lista-espera/{id}` | prioridad y preferencias; solo entradas activas |
| `DELETE /api/lista-espera/{id}` | 204: `salido` + anula la oferta pendiente |
| `POST /api/lista-espera/{id}/ofertar` | D7 |
| `GET /api/lista-espera/bandeja?limit` | ofertas recientes con paciente y hueco |
| `GET /api/lista-espera/metricas?desde&hasta` | liberados / recuperados / perdidos por fecha local del hueco; rango > 366 días → 422 |

### D9 — `horario_libre` en `turnos.py` (avisar a Matheo)

Función pública nueva de una línea de lógica: `not bloqueos_solapados(...) and not _hay_turno_solapado(...) and dentro_de_horario(...)`. No cambia nada existente y evita duplicar el predicado de "activo".

### D10 — Configuración, exportación y cron

- `Settings`: `lista_espera_oferta_min` (30, rango 5–240) y `lista_espera_anticipacion_min` (120, rango 0–1440).
- `.env.example` y `test_env_example.py` actualizados.
- `ENTIDADES_EXPORTABLES` suma `lista_espera` y `ofertas_lista_espera`.
- `docs/whatsapp-sesion.md` §4 suma el cron `*/5 … python -m app.jobs.lista_espera`.

## Risks / Trade-offs

- **[Demora de hasta 5 min hasta la primera oferta]** → Es aceptable frente a la ventana de 30 min. Si molesta, el cron puede correr cada minuto: es idempotente.
- **[Paciente con recordatorio y oferta a la vez]** → Gana el saliente más reciente, y los textos dicen claramente a qué responder. El caso se cubre con un test (spec whatsapp-messaging).
- **[Recepción llena el hueco a mano mientras hay una oferta]** → Al aceptar, `crear_turno` da 409 y el paciente recibe `oferta_no_disponible`. Ninguna oferta deja el hueco reservado: el hueco nunca se bloquea por una oferta.
- **[La cascada por adelantar turnos genera muchos mensajes]** → Cada hueco produce una oferta por vez, con el límite de ritmo del gateway de C-15. La cascada se corta sola cuando nadie es elegible.
- **[Métrica aproximada]** → "Perdido" no distingue a quien recepción llenó a mano; queda documentado en el proposal.

## Migration Plan

1. `015_lista_espera` (`down_revision = "014_whatsapp"`). Verificar un único `alembic heads` al mergear.
2. Deploy: variables nuevas (opcionales) y el cron `*/5`.
3. Rollback: sin el cron, la lista no oferta nada. Los datos quedan. El downgrade borra las tablas y los textos nuevos si no se usaron.
