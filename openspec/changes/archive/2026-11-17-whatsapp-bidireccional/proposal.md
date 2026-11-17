# Proposal — whatsapp-bidireccional (C-15)

## Why

US-005 y el Flujo 2: el paciente recibe un recordatorio por WhatsApp y su respuesta **mueve la agenda** (RN-TU-02/03). Hoy confirmar o cancelar exige que recepción llame o que el paciente use el enlace de C-06. Por DD-10 el canal es una **sesión QR con número dedicado**, no la API oficial de Meta: hay que absorber el riesgo de caída/bloqueo con monitoreo, reconexión, backup y una bandeja de fallos. C-05 (alta + transiciones) ya está archivado y C-16/C-17 dependen de este change.

## What Changes

- **Puerto de mensajería** (`MensajeriaPort`) con dos adapters, elegidos por `WHATSAPP_GATEWAY`:
  - `waha`: habla por HTTP con un **gateway QR autoalojado** (WAHA) que mantiene la sesión de WhatsApp Web; el gateway nos manda sus eventos a `POST /api/webhooks/whatsapp`.
  - `fake`: simulado para tests y demo (bloqueado en `ENTORNO=produccion`), igual que el partner de recetas de C-19.
  - Sin gateway configurado la API arranca igual; los endpoints de sesión responden `501` y los recordatorios quedan como fallos en la bandeja.
- **Una sesión por clínica** (un número dedicado por tenant). La sesión se llama `clinica-{id}`, así el webhook sabe de qué clínica es cada evento.
- **Recordatorio**: job `python -m app.jobs.recordatorios` (cron). Envía un recordatorio por turno `reservado` que empieza dentro de las próximas `WHATSAPP_RECORDATORIO_HORAS` (24 por defecto, SU-04). Respeta un límite de envíos por minuto y reintenta hasta `WHATSAPP_MAX_INTENTOS`.
- **Respuestas del paciente** (por número o palabra): `1`/`SI`/`CONFIRMO` → `confirmado`; `2`/`NO`/`CANCELO` → `cancelado`; `3`/`REPROGRAMAR` → pedido a la bandeja (el chatbot es C-17). Cualquier otra respuesta va a la bandeja sin tocar el turno. Las transiciones reutilizan `transicionar_turno` (C-05b) con actor `paciente_whatsapp`. Después de confirmar o cancelar, el sistema le responde al paciente con el texto base que corresponda.
- **Webhook** público con firma HMAC-SHA512 del gateway (`WHATSAPP_WEBHOOK_HMAC_KEY`; inválida → `401`) e idempotencia por id de mensaje: un evento duplicado no repite la transición.
- **Mensajes y costos** (RN-WA-02/03): cada mensaje guarda texto base (`plantilla`), dirección, estado (`pendiente → enviado → entregado → leido`, o `error`) y costo en ARS `NUMERIC` (`ARS_PRECIO_MENSAJE` al enviar; los entrantes cuestan 0).
- **Endpoints autenticados**:
  - `GET /api/whatsapp/sesion`: estado de la sesión y QR si hay que escanear.
  - `POST /api/whatsapp/sesion/reconectar`: solo admin.
  - `GET /api/whatsapp/fallos` y `POST /api/whatsapp/fallos/{id}/resolver`: bandeja de recepción.
  - `GET /api/whatsapp/costos?desde&hasta`.
  - `GET /api/whatsapp/mensajes?turno_id`.
- **Fallback manual** (decisión del usuario): sesión caída, número bloqueado, paciente sin teléfono o respuesta no entendida → la bandeja. Recepción avisa a mano y marca el fallo como resuelto. No se envía email.
- **Textos base**: 5 textos en es_AR, sembrados por la migración (recordatorio 24 h, confirmación, cancelación, reprogramación y oferta de hueco), sin aprobación de Meta.
- **Operación**:
  - servicio `waha` en `docker-compose.yml` (perfil `whatsapp`);
  - runbook `docs/whatsapp-sesion.md`: riesgo de bloqueo/ToS, escaneo del QR, reconexión, backup y restauración cifrada del volumen de sesión, y migración a la plataforma oficial en F2.
- **Configuración**: las variables `WHATSAPP_*` de `.env.example` se reemplazan por las del gateway. **BREAKING (solo `.env`)**: `WHATSAPP_SESSION_DIR`, `WHATSAPP_RECONNECT`, `WHATSAPP_BACKUP_DIR` y `WHATSAPP_PHONE_NUMBER` dejan de existir; ningún código las leía.
- **Exportación** (RN-CU-04): el ZIP suma `mensajes_whatsapp.csv` y `whatsapp_sesiones.csv`.
- Migración `014_whatsapp` (`down_revision = "013_reserva_online"`).

### Decisiones tomadas con el usuario (2026-11-17)

1. Gateway HTTP autoalojado (WAHA) detrás de `MensajeriaPort`, con adapter falso para tests y demo.
2. Respuestas por número o palabra (1/2/3). "Reprogramar" y lo no entendido van a la bandeja.
3. Fallback = bandeja manual. El email queda como mejora futura.
4. Una sesión QR (número dedicado) por clínica.

### Supuestos (registrados, de bajo impacto)

- El recordatorio sale solo para turnos `reservado` (uno `confirmado` no necesita confirmación) con paciente con teléfono. Que el turno exista basta como base para un aviso administrativo. No es un dato de salud, así que no se exige `consentimiento_datos`.
- Los textos base son globales de la plataforma, como `rol`: personalizarlos por clínica queda para después.
- Una respuesta se asocia al **último recordatorio enviado a ese número** en esa clínica cuyo turno todavía no empezó.
- La "alerta al admin" ante una sesión caída es el estado visible en `GET /api/whatsapp/sesion`, un log `WARNING` y los fallos en la bandeja. No hay canal de notificaciones.

## Non-goals

- Chatbot de reprogramación y huecos por WhatsApp (C-17). Oferta de lista de espera (C-16; el texto base queda sembrado).
- Pantallas de bandeja, sesión y costos (las consume C-07/C-14). Este change es solo API.
- Email/SMS de respaldo, avisos iniciados por el staff (por ejemplo "la clínica canceló tu turno") y la API oficial de Meta (F2).

## Capabilities

### New Capabilities

- `whatsapp-messaging`: canal WhatsApp por sesión QR, que incluye:
  - puerto y adapters;
  - sesión por clínica: estado, QR y reconexión;
  - recordatorios con reintentos y límite de ritmo;
  - webhook firmado e idempotente, con interpretación de respuestas que mueve la agenda;
  - registro de mensajes y costos en ARS;
  - bandeja de fallos con fallback manual;
  - RBAC y aislamiento por clínica.

### Modified Capabilities

- `appointments`: el historial de transiciones admite el actor `paciente_whatsapp`, sin usuario.
- `platform-config`: configuración del gateway de WhatsApp (sin impedir el boot; secretos enmascarados; `fake` bloqueado en producción).
- `data-export`: la exportación incluye los mensajes y sesiones de WhatsApp del tenant.

## Impact

- **Código nuevo**:
  - `backend/app/domain/whatsapp/`: modelos, servicios, interpretación y schemas;
  - `backend/app/infrastructure/whatsapp/`: puerto, `fake`, `waha` y factory;
  - `backend/app/api/whatsapp.py`;
  - `backend/app/jobs/recordatorios.py`;
  - `backend/alembic/versions/014_whatsapp.py`;
  - `docs/whatsapp-sesion.md`.
- **Código modificado**:
  - `turnos.py` (`actor_tipo` admite `paciente_whatsapp`);
  - `settings.py`;
  - `main.py` (`include_router`);
  - `exportador.py`;
  - `backend/.env.example` y `test_env_example.py`;
  - `docker-compose.yml`;
  - `pyproject.toml` (`httpx` pasa de dev a runtime; ya está instalado, no es una dependencia nueva).
- **DB**:
  - tablas `whatsapp_sesion`, `mensaje_whatsapp` y `plantilla_wa` (global);
  - índice `(clinica_id, turno_id, estado)`;
  - UNIQUE parcial por `id_externo` y por recordatorio de turno;
  - CHECK de `turno_transicion.actor_tipo` ampliado.
- **Governance**: ALTO (webhook público, datos de contacto de pacientes, riesgo ToS asumido). El apply requiere aprobar el diseño.
