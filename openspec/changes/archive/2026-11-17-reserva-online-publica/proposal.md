# Proposal — reserva-online-publica (C-06)

## Why

US-003 y el Flujo 1 son el diferenciador frente a Bilog (RN-AG-05): un paciente nuevo reserva desde un enlace compartible (redes, QR, web) sin crear cuenta, eligiendo un hueco real. Hoy los turnos solo se crean desde el mostrador con usuario y rol. C-05/C-05c/C-05d ya garantizan que un hueco ofrecido es reservable (anti-solapamiento, bloqueos y horario), así que falta la puerta pública.

## What Changes

- **Enlace por clínica:** `clinica.slug` (único). La página pública es `/reservar/{slug}`.
- **API pública, sin autenticación**, bajo `/api/public`:
  - `GET /clinicas/{slug}`: nombre de la clínica, prestaciones activas y profesionales que atienden online (agenda activa y con horario cargado).
  - `GET /clinicas/{slug}/huecos?profesional_id&prestacion_id&desde&hasta`: huecos reales (reutiliza `buscar_huecos`), sin exponer sillones.
  - `POST /clinicas/{slug}/reservas`: crea el turno `reservado` con `origen = "enlace"`.
    - Recibe DNI, nombre, apellido, email y/o teléfono y `acepta_privacidad: true`.
    - El servidor elige el sillón.
    - Devuelve un **token** de un solo uso de lectura: se muestra una vez y en la base se guarda solo su hash.
  - `GET /reservas/{token}`: ver la reserva. `POST /reservas/{token}/cancelar`: cancelarla antes del inicio.
- **Paciente:** si el DNI ya existe en la clínica, se reutiliza **sin modificar sus datos** y la respuesta no revela si existía. Si no existe, se crea sin usuario (RN-AG-05, sin contraseña) y sin consentimiento de datos de salud (regla dura 16: no se cargan datos de salud).
- **Anti-abuso** (decisión del usuario):
  - rate limit por IP con slowapi en huecos, reservas y cancelación;
  - **máximo 2 turnos futuros activos por DNI** reservados por enlace (`409`).
  - Sin captcha.
- **Seña:** **no** en C-06 (decisión del usuario). La reserva es directa. La rama "seña exigida" (pre-bloqueo, expiración y webhook de Mercado Pago, RN-CA-01/02) queda para C-12.
- **Historial de transiciones:** la cancelación por enlace no tiene usuario. `turno_transicion` admite `actor_tipo = 'paciente_enlace'` sin `actor_usuario_id`.
- **Frontend público:**
  - `/reservar/{slug}`: elegir prestación y profesional, ver huecos por día de la semana, cargar datos, confirmar; ante un `409` se recargan los huecos y se ofrecen alternativas.
  - `/reserva/{token}`: comprobante y cancelación.
- Migración `013_reserva_online` (`down_revision = "012_horario_atencion"`).

### Decisiones tomadas con el usuario (2026-11-17)

1. Reserva directa, sin seña ni pre-bloqueo; la seña va en C-12.
2. Anti-abuso: rate limit por IP + tope de 2 turnos futuros activos por DNI; sin Turnstile.
3. DNI existente: se reutiliza el paciente sin tocar sus datos y sin revelar que existía.
4. Alcance: API + pantalla pública.

### Supuestos (registrados, de bajo impacto)

- El formulario pide **nombre y apellido** además de DNI y contacto, porque `Paciente` los exige (CHECK). US-003 dice "solo DNI + email/teléfono"; lo esencial del criterio es "sin cuenta ni contraseña", y eso se cumple.
- Se ofrecen todas las prestaciones activas y los profesionales con `agenda_activa` y horario cargado. No hay una marca "visible online" por prestación.
- Ventana de búsqueda pública de hasta 7 días (igual que C-05c), no antes de "ahora".
- La cancelación por enlace se permite hasta el inicio del turno. La KB no fija una antelación mínima.

## Non-goals

- Seña, pre-bloqueo, Mercado Pago y factura (C-12/C-13).
- Confirmación o recordatorio por WhatsApp o email (C-15).
- Reprogramar por enlace (C-17), lista de espera (C-16) y captcha.
- Editar el `slug` por API (C-14); la migración lo genera y el seed lo fija.

## Capabilities

### New Capabilities

- `public-booking`: reserva pública sin cuenta (catálogo público, huecos, alta con paciente reutilizado o nuevo, token, consulta y cancelación, anti-abuso).
- `public-booking-web`: pantallas públicas de reserva y comprobante.

### Modified Capabilities

- `appointments`: el historial de transiciones admite cancelaciones del paciente por enlace, sin usuario.

## Impact

- Código nuevo:
  - `backend/app/domain/agenda/reserva_publica.py`;
  - `backend/app/api/publico.py`;
  - schemas públicos;
  - `backend/alembic/versions/013_reserva_online.py`;
  - `frontend/src/features/reserva/` (páginas, API y tests).
- Código modificado:
  - `turnos.py`: `crear_turno` acepta `origen`; `transicionar_turno` acepta un actor de enlace;
  - `core/models.py`: `Clinica.slug`;
  - `main.py`: `include_router`;
  - `ratelimit.py`: límites públicos;
  - `seed_core.py`: slug del piloto;
  - `router.tsx`: reemplaza el placeholder `/reservar/:token`.
- DB:
  - `clinica.slug` (UNIQUE NOT NULL);
  - `turno.token_publico_hash` (UNIQUE parcial);
  - `turno_transicion.actor_usuario_id` pasa a nullable, con `actor_tipo` y un CHECK de coherencia.
- Dependencias: ninguna nueva.
- Governance: ALTO (endpoints públicos sin autenticación); el apply requiere aprobar el diseño.
