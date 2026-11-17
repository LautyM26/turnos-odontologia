# Design — whatsapp-bidireccional (C-15)

## Context

Motivación y decisiones del usuario: ver `proposal.md`. Requisitos: `specs/whatsapp-messaging`, `specs/appointments`, `specs/platform-config`, `specs/data-export`. Reglas del área: skill `dominio-whatsapp`.

Estado observado:

- `turnos.transicionar_turno(session, clinica_id, turno_id, destino, actor_id, motivo, ahora, ..., actor_tipo)` hace todo esto:
  - toma `SELECT … FOR UPDATE`;
  - valida contra `TRANSICIONES` (estado ilegal → `ReferenciaInvalida`, 422);
  - inserta `TurnoTransicion`;
  - **hace commit él mismo**.

  `turno_transicion.actor_tipo` tiene un CHECK `IN ('usuario','paciente_enlace')` y `actor_coherente` (usuario ⇔ `actor_usuario_id`).
- `ORIGENES_TURNO` ya incluye `whatsapp` y `lista_espera`. `deps.PUBLIC_PREFIXES` ya declara `/api/webhooks/whatsapp`, cubierto por `test_ruta_publica_sin_token_ok`.
- Precedente de integración externa (C-19):
  - puerto `Protocol` en `infrastructure/recetas/partner_client.py`;
  - `FakePartner` con hook `fallar_con`;
  - `factory.obtener_partner(settings)` que nunca lanza excepciones y devuelve `NoConfigurado`; `fake` queda bloqueado si `ENTORNO=produccion`;
  - secretos como `SecretStr`, con el valor vacío convertido en `None`.
- `Settings(extra="forbid")`. Las variables `WHATSAPP_*` actuales de `.env.example` (`SESSION_DIR`, `RECONNECT`, `BACKUP_DIR`, `PHONE_NUMBER`) **no están declaradas en `Settings`**. Ningún código las lee; solo `test_env_example.py` las exige.
- `Paciente.telefono` se guarda en E.164 (`normalizar_telefono`, con `phonenumbers`: el `15` local pasa a `9` móvil, por ejemplo `+5491100000001`), con índice `(clinica_id, telefono)`.
- `Clinica.zona_horaria` (C-05d), para mostrar fecha y hora local en el texto.
- Jobs: `app/jobs/purga_blacklist.py` se corre por cron del sistema operativo (`python -m app.jobs.…`). No hay scheduler en proceso.
- `exportador.ENTIDADES_EXPORTABLES` exporta todas las columnas del modelo menos `COLUMNAS_EXCLUIDAS`.
- Gateway WAHA (doc vigente consultada con Context7, `/devlikeapro/waha-docs`):
  - `POST /api/sendText {session, chatId, text}` envía un texto;
  - `POST /api/sessions {name, config.webhooks[{url, events, hmac.key}]}` crea la sesión y `POST /api/sessions/{name}/restart` la reinicia;
  - `GET /api/sessions/{name}` (`status`, `me`) y `GET /api/{session}/auth/qr` (JSON `{base64}`), autenticados con `X-Api-Key`;
  - eventos `message` (`id`, `from` `…@c.us`, `fromMe`, `body`), `message.ack` (`id`, `ack` de -1 a 4) y `session.status` (`STOPPED|STARTING|SCAN_QR_CODE|WORKING|FAILED`);
  - HMAC: header `X-Webhook-Hmac` = HMAC-SHA512 hex del cuerpo crudo.

## Goals / Non-Goals

**Goals:**

- Que el dominio no sepa nada de WAHA: cambiar a la plataforma oficial en F2 = un adapter nuevo + un valor de `WHATSAPP_GATEWAY`.
- Una respuesta del paciente mueve el turno por el **mismo** camino que el mostrador (`transicionar_turno`), sin duplicar la tabla de estados.
- Nada se pierde en silencio: todo lo que no se pudo enviar o entender termina en la bandeja.

**Non-Goals:**

- Scheduler en proceso o colas (Celery, Redis).
- Plantillas por clínica.
- Detectar el idioma de la respuesta o interpretarla con NLP.
- Escalado multi-gateway (un WAHA atiende todas las sesiones).

## Decisions

### D1 — Puerto en `infrastructure/whatsapp/`, igual que recetas

- `puerto.py`:
  - `class Mensajeria(Protocol)` con `nombre`, `simulado`, `enviar_texto(sesion, telefono_e164, texto) -> str` (id externo), `estado(sesion) -> EstadoSesion`, `qr(sesion) -> str | None` e `iniciar(sesion, webhook_url, hmac_key) -> EstadoSesion`;
  - excepciones `GatewayNoDisponible` (timeout, 5xx o conexión) y `SesionNoActiva`;
  - `NoConfigurado(mensaje)`.
- `fake.py`: `FakeMensajeria`, que guarda los envíos en memoria, tiene estado configurable y `fallar_con(exc)`, y genera ids `FAKE-<uuid>`.
- `waha.py`: `WahaMensajeria(url, api_key)` sobre `httpx.Client(timeout=10)`. Mapea el estado de WAHA al estado interno:

  | WAHA | Interno |
  |---|---|
  | `WORKING` | `activa` |
  | `SCAN_QR_CODE` | `escanear_qr` |
  | `STARTING` | `iniciando` |
  | `FAILED` | `caida` |
  | `STOPPED` | `detenida` |
  | otro | `desconocido` |

  Con `iniciar` crea la sesión (`POST /api/sessions`, con `start` implícito) y, si ya existe (409/422), la reinicia (`/restart`). Se suscribe a los eventos `message`, `message.ack` y `session.status`.
- `factory.obtener_mensajeria(settings)`: nunca lanza excepciones.
  - `""` → `NoConfigurado`.
  - `fake` → `NoConfigurado` si `ENTORNO=produccion`.
  - `waha` sin URL → `NoConfigurado`.
  - Valor desconocido → `NoConfigurado` + warning.
- **Por qué no `domain/ports/` como dice la ficha de CHANGES:** el repo ya resolvió esto en C-19 dentro de `infrastructure/`. Un segundo estilo de puerto confunde más de lo que aporta. El nombre del puerto en la KB (`MensajeriaPort`) queda como alias en el docstring.
- **Por qué un gateway y no una librería:** las librerías QR maduras son de Node. WAHA es autoalojado, expone HTTP + webhooks y persiste la sesión en un volumen. Decisión del usuario.

### D2 — Una sesión por clínica: `whatsapp_sesion`

- Tabla `whatsapp_sesion` con `clinica_id` como PK y FK a clínica, y `nombre` `UNIQUE`, que es siempre `clinica-{clinica_id}` (estable aunque cambie el `slug`).
- Columnas:
  - `estado`: CHECK con los 6 valores de la spec;
  - `numero`: `me.id` normalizado o `NULL`;
  - `estado_at` (TIMESTAMPTZ del servidor), más `created_at` y `updated_at`.
- La fila se crea perezosamente la primera vez que se reconecta o llega un evento de esa clínica.
- El webhook resuelve la clínica parseando `clinica-(\d+)` y verificando que la clínica exista. Si no matchea o no existe → `200` sin efectos.
- **Alerta:** cuando un `session.status` pasa de `activa` a `caida` o `detenida`, se emite un log `WARNING` estructurado (`evento=whatsapp_sesion_caida`, `clinica_id`). El admin lo ve en `GET /api/whatsapp/sesion` y los recordatorios que fallen van a la bandeja. No hay canal de notificaciones (supuesto del proposal).

### D3 — `mensaje_whatsapp`: un registro por mensaje, mutable solo en estado/entrega

- Columnas:
  - `id`, `clinica_id`;
  - `turno_id` y `paciente_id` (nullable, FK compuestas `(clinica_id, …)`);
  - `plantilla` (FK a `plantilla_wa.clave`, nullable para entrantes);
  - `direccion` ∈ `saliente|entrante`;
  - `telefono` E.164;
  - `texto` (≤ 2000; el entrante se guarda para la bandeja);
  - `estado` ∈ `pendiente|enviado|entregado|leido|error|recibido`;
  - `intencion` ∈ `confirmar|cancelar|reprogramar|desconocida` (solo entrantes);
  - `id_externo`;
  - `intentos` (`int`, default 0);
  - `motivo_error` ∈ `sin_telefono|no_configurado|sesion_no_activa|gateway_no_disponible|otro`;
  - `costo_ars NUMERIC(12,2) NOT NULL DEFAULT 0`, con `CHECK >= 0`;
  - `requiere_atencion` (bool), `resuelto_at`, `resuelto_por` (FK usuario);
  - `created_at`, `updated_at`.
- Índices:
  - `(clinica_id, turno_id, estado)`, el de la ficha de CHANGES;
  - `(clinica_id, created_at)`, para costos;
  - `(clinica_id, telefono, created_at DESC) WHERE direccion='saliente' AND plantilla='recordatorio_24h'`, para asociar respuestas;
  - parcial `(clinica_id) WHERE requiere_atencion AND resuelto_at IS NULL`, para la bandeja.
- Unicidad:
  - `UNIQUE (clinica_id, id_externo) WHERE id_externo IS NOT NULL`: es la idempotencia de eventos;
  - `UNIQUE (clinica_id, turno_id) WHERE direccion='saliente' AND plantilla='recordatorio_24h'`: un recordatorio por turno; los reintentos actualizan la misma fila.
- **Bandeja** = `requiere_atencion AND resuelto_at IS NULL`. Un solo flag cubre los dos casos (saliente en error, entrante que no movió la agenda), sin dos tablas.
- **Por qué no append-only:** no es historia clínica (regla 15 no aplica). El estado de entrega avanza por los acuses y la bandeja se resuelve. El historial que importa (el cambio del turno) ya es inmutable en `turno_transicion`.

### D4 — `plantilla_wa` global, sembrada por la migración

- Columnas: `clave` PK (los 5 valores), `idioma` (`es_AR`), `texto` y `variables` (`TEXT[]`).
- Sin `clinica_id`, igual que `rol`: es catálogo de plataforma, no dato del tenant, así que la regla dura 10 no aplica. El downgrade la elimina.
- Render con `str.format_map` y un dict de variables calculadas en el servidor: `paciente_nombre`, `fecha` (`dd/mm`), `hora` (`HH:MM` en `clinica.zona_horaria`), `profesional` y `clinica`. Una variable faltante es un bug: falla el test, no se manda texto roto.
- Personalizar textos por clínica: YAGNI hasta que el piloto lo pida.

### D5 — Recordatorios: job de cron, "claim" por UNIQUE, ritmo con `sleep`

`app/jobs/recordatorios.py::enviar_recordatorios(session, mensajeria, settings, ahora, dormir=time.sleep)` hace esto:

1. Elige los candidatos: turnos `reservado`, `is_active`, con `ahora < inicio <= ahora + WHATSAPP_RECORDATORIO_HORAS` y sin fila de recordatorio. Más las filas de recordatorio en `error` con motivo transitorio, `intentos < WHATSAPP_MAX_INTENTOS` y turno todavía `reservado` y futuro.
2. Si el paciente no tiene teléfono, crea la fila en `error`/`sin_telefono` con `requiere_atencion` y no la reintenta.
3. Para el resto, `INSERT … ON CONFLICT DO NOTHING` de la fila `pendiente` + `commit`. Ese es el claim: dos corridas solapadas no envían dos veces. Después llama a `enviar_texto`:
   - si sale bien: `enviado`, `id_externo`, `intentos += 1`, `costo_ars = settings.ars_precio_mensaje`;
   - si falla: `error`, motivo, `intentos += 1`, `requiere_atencion = true`.
4. Antes de cada envío llama a `dormir(60 / WHATSAPP_ENVIOS_POR_MINUTO)` (se salta antes del primero). `dormir` se inyecta: los tests pasan una función que registra los intervalos.
5. Si la mensajería es `NoConfigurado`, todos los candidatos quedan en `error`/`no_configurado`. Este motivo es transitorio: se reintenta cuando se configure.

- **Backoff:** es la periodicidad del cron (sugerido cada 15 min, en el runbook) × intentos. No hay timers propios.
- **Por qué no APScheduler o BackgroundTasks:** el proyecto ya usa cron del sistema operativo para jobs. Un scheduler en proceso se duplica con varios workers de uvicorn.
- `ARS_PRECIO_MENSAJE` se agrega a `Settings` como `Decimal` (`condecimal(ge=0, max_digits=12, decimal_places=2)`), default `0.00`.

### D6 — Webhook: HMAC, parseo defensivo y validación estricta de lo que usamos

`POST /api/webhooks/whatsapp` lee `request.body()` crudo y procesa así:

1. Sin `WHATSAPP_WEBHOOK_HMAC_KEY` → `503`.
2. Compara con `hmac.compare_digest(hmac.new(key, body, sha512).hexdigest(), header)`. Si no coincide → `401`.
3. Hace `json.loads` del cuerpo y extrae solo los campos que usamos a modelos Pydantic **propios** con `extra="forbid"` (regla dura 4), construidos campo a campo. El sobre de WAHA no es nuestro contrato y suma campos por versión o engine. Validarlo entero con `forbid` rompería en cada upgrade del gateway. Datos mal formados → `422`.
4. Despacha según `event`: `message` (solo si `fromMe` es false), `message.ack` o `session.status`. Cualquier otro → `200` sin efectos.

- **Por qué HMAC y no un token en la URL:** WAHA lo soporta de forma nativa y firma el cuerpo, así que un replay con el cuerpo alterado no pasa. `WHATSAPP_WEBHOOK_VERIFY` de la KB (`08`) se reemplaza por `WHATSAPP_WEBHOOK_HMAC_KEY`: corregir `08` al archivar.
- El `chatId` `5491100000001@c.us` se convierte a `+5491100000001` con `normalizar_telefono`. Ids que no sean `@c.us` (grupos, `@lid`) → se ignoran con un log.

### D7 — Procesar una respuesta: insert-first y una sola transacción

`procesar_mensaje_entrante(session, clinica_id, evento, ahora, mensajeria)` hace esto:

1. `INSERT mensaje_whatsapp(direccion='entrante', estado='recibido', id_externo, telefono, texto, costo 0, intencion)` + `flush`.
   - Si choca con `UniqueViolation` en `id_externo` → `rollback` y retorna "duplicado" sin efectos.
   - Ante dos entregas simultáneas, la segunda espera en el índice único hasta que la primera hace commit y después falla. Así se cumple "evento duplicado no repite efectos" sin locks propios.
2. Busca el último recordatorio saliente a ese teléfono en esa clínica cuyo turno sigue activo y con `inicio > ahora`, y fija `turno_id`/`paciente_id`. Si no hay ninguno → `requiere_atencion`.
3. Según la intención:
   - `confirmar` o `cancelar`: `transicionar_turno(..., actor_id=None, actor_tipo='paciente_whatsapp', motivo='respuesta WhatsApp')`. Ese commit incluye el mensaje entrante: es atómico.
     - Si lanza `ReferenciaInvalida` (por ejemplo, confirmar un cancelado): `rollback`, se reinserta el entrante con `requiere_atencion` y se hace commit, sin transición.
     - Un "SI" repetido con **otro** id sobre un turno ya `confirmado` es `confirmado→confirmado`, ilegal → bandeja. Es aceptable: recepción ve que el paciente insistió.
   - `reprogramar`: `requiere_atencion` + commit.
   - `desconocida`: `requiere_atencion` + commit, sin respuesta automática. Se evitan bucles con contestadores automáticos y se suma riesgo de bloqueo cero.
4. **Después del commit**, la respuesta al paciente (`confirmacion`, `cancelacion` o `reprogramacion`) se envía como un saliente más (`pendiente` → `enviado` o `error` + bandeja). Si falla, el turno igual quedó actualizado, y el webhook responde `200` para que WAHA no reintente y duplique.

- `interpretar(texto) -> intencion`: función pura. Usa `normalizar_texto` de pacientes (minúsculas y sin tildes), quita los signos y compara la **primera palabra** contra tres conjuntos fijos (spec). La "primera palabra" hace que "si, confirmo" funcione y que "no se" quede en `cancelar`. Por eso la respuesta automática siempre dice qué se hizo y recepción puede revertirlo desde el mostrador.
- `message.ack`: `UPDATE … SET estado = nuevo WHERE clinica_id AND id_externo AND orden(estado) < orden(nuevo)`, con `1→enviado`, `2→entregado` y `3|4→leido`. `-1` → `error` + `requiere_atencion` solo si estaba `pendiente`/`enviado`. Monótono por construcción.

### D8 — Turno: `actor_tipo` ampliado, sin tocar la lógica

- Se agrega `'paciente_whatsapp'` al CHECK `actor_tipo_valido` y `actor_coherente` pasa a `(actor_tipo = 'usuario') = (actor_usuario_id IS NOT NULL)`. Ya cubre los dos tipos de paciente: no cambia.
- Cambio en `turnos.py`: solo el string del CHECK espejo. `transicionar_turno` ya acepta `actor_tipo`.

### D9 — API y RBAC

Router `api/whatsapp.py`:

| Endpoint | Roles | Notas |
|---|---|---|
| `GET /api/whatsapp/sesion` | admin, recepcionista | 501 si `NoConfigurado`. Consulta el estado en vivo al gateway (y lo persiste); si falla, devuelve el último conocido con `"en_vivo": false`. QR solo si `escanear_qr` |
| `POST /api/whatsapp/sesion/reconectar` | admin | `iniciar(nombre, APP_BASE_URL + "/api/webhooks/whatsapp", hmac_key)`; 501/503 según configuración o gateway caído |
| `GET /api/whatsapp/fallos` | admin, recepcionista | Bandeja paginada (`limit` ≤ 100), orden `created_at DESC`, con nombre del paciente e inicio del turno (datos de contacto, no clínicos) |
| `POST /api/whatsapp/fallos/{id}/resolver` | admin, recepcionista | 404 si es ajeno, no está en la bandeja o ya se resolvió |
| `GET /api/whatsapp/costos` | admin, recepcionista | `desde`/`hasta` como `date`; total con `SUM(costo_ars)` en SQL, serializado como string decimal |
| `GET /api/whatsapp/mensajes?turno_id=` | admin, recepcionista | 404 si el turno es ajeno |
| `POST /api/webhooks/whatsapp` | público (ya declarado) | D6 |

- Roles con `require_role(...)`. Todos los schemas de entrada y salida con `extra="forbid"`.
- Si el odontólogo necesita ver la mensajería de sus turnos: se agrega cuando lo pida C-07.

### D10 — Configuración (reemplaza las 4 variables muertas)

Nuevas en `Settings`:

| Variable | Tipo | Default | Notas |
|---|---|---|---|
| `whatsapp_gateway` | `str` | `""` | normalizada a minúsculas |
| `whatsapp_gateway_url` | `str` | `""` | |
| `whatsapp_gateway_api_key` | `SecretStr \| None` | — | vacío → `None` |
| `whatsapp_webhook_hmac_key` | `SecretStr \| None` | — | ídem |
| `whatsapp_recordatorio_horas` | `int` | 24 | rango 1–72 |
| `whatsapp_max_intentos` | `int` | 3 | rango 1–10 |
| `whatsapp_envios_por_minuto` | `int` | 20 | rango 1–60 |
| `ars_precio_mensaje` | `Decimal` | `0.00` | |

- `.env.example` y `test_env_example.py` se actualizan. La docstring del test sobre "contradice DD-02" se reescribe.
- `docker-compose.yml`: servicio `waha` con `profiles: [whatsapp]`, imagen `devlikeapro/waha` con tag fijo (se elige y anota en apply), volumen `waha_sessions` para `/app/.sessions` y `WHATSAPP_API_KEY` desde env. No arranca con `docker compose up` normal.

### D11 — Exportación

- `ENTIDADES_EXPORTABLES` suma `"mensajes_whatsapp": MensajeWhatsApp` y `"whatsapp_sesiones": WhatsappSesion`.
- `plantilla_wa` no se exporta: es global, no del tenant.

## Risks / Trade-offs

- **[Bloqueo del número por Meta (ToS)]** → Número dedicado, límite de ritmo, mensajes solo a pacientes con turno, sin difusión y sin respuesta a mensajes no entendidos. Fallback manual por la bandeja. Migración a la plataforma oficial detrás del puerto (F2). Riesgo asumido por DD-10 y documentado en el runbook.
- **[Sesión caída sin que nadie mire]** → Los recordatorios fallidos aparecen en la bandeja que recepción usa todos los días, más el log WARNING. Un canal de alertas activo (email al admin) queda fuera, por decisión del usuario.
- **[Formato de número argentino: WhatsApp usa `549…` para celulares]** → Se envía y se compara siempre en E.164 normalizado con `phonenumbers` (que ya agrega el `9`). Si un paciente responde desde un id `@lid` o un formato distinto, el mensaje cae en la bandeja "sin turno": no se pierde y recepción lo resuelve. Verificar con el piloto.
- **[La "primera palabra" puede malinterpretar ("no sé" → cancelar)]** → La respuesta automática confirma qué se hizo y recepción revierte desde el mostrador. Los conjuntos de palabras son chicos y explícitos (tests de tabla).
- **[Dos recordatorios si dos crons se pisan]** → El claim por UNIQUE parcial lo impide a nivel base de datos.
- **[El webhook espera el envío de la respuesta al paciente (latencia hasta 10 s)]** → WAHA tolera la latencia. Si el envío falla, igual responde `200` (el turno ya cambió) y el fallo va a la bandeja.
- **[Backup de sesión]** → La sesión vive en el volumen de WAHA, no en nuestra base. El runbook documenta backup y restauración cifrada del volumen (`tar` + `age`/`gpg`, clave fuera del repo) y la rotación. No es código de la app.
- **[Ningún test toca un WhatsApp real]** → El adapter `waha` se prueba con `httpx.MockTransport` (contrato de requests y mapeo de estados). La prueba end-to-end con un teléfono es manual y queda en `verify.md`.

## Migration Plan

1. `014_whatsapp` (`down_revision = "013_reserva_online"`). Verificar con `alembic heads` que haya un único head **al momento de mergear**: C-11/C-12 también toman números.
   - Crea `plantilla_wa` y le siembra los 5 textos.
   - Crea `whatsapp_sesion` y `mensaje_whatsapp`, con sus CHECKs, índices y FKs compuestas.
   - Hace DROP y ADD del CHECK `turno_transicion.actor_tipo_valido`.
2. Downgrade:
   - borra las tres tablas;
   - si hay filas `paciente_whatsapp`, el downgrade falla con un mensaje claro. No se borra historial inmutable para poder bajar;
   - si no hay, restaura el CHECK original.
3. Deploy:
   - actualizar `.env` con las variables nuevas y borrar las 4 viejas;
   - `docker compose --profile whatsapp up -d waha`;
   - el admin pide `POST /api/whatsapp/sesion/reconectar` y escanea el QR desde `GET /api/whatsapp/sesion`;
   - agregar el cron `*/15 * * * * python -m app.jobs.recordatorios`.
4. Rollback funcional sin bajar la migración: `WHATSAPP_GATEWAY=` vacío. El sistema sigue andando y los recordatorios quedan como fallos visibles.

## Open Questions

- Tag exacto de la imagen de WAHA y engine (`WEBJS` o `NOWEB`): se fija en apply, al levantar el contenedor. No cambia la API usada.
- Frecuencia final del cron y ventana de 24 h (SU-04): ya son configuración. Se ajustan con el piloto.
