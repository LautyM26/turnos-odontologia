# Design — reserva-online-publica (C-06)

## Context

Motivación: ver `proposal.md`. Requisitos: `specs/public-booking`, `specs/public-booking-web`, `specs/appointments`.

Estado observado:

- `turnos.crear_turno(session, clinica_id, datos, ahora)`:
  - aplica pasado → referencias → horario (C-05d) → bloqueos → solapamiento → INSERT, y el 23P01 de la base resuelve las carreras;
  - fija `origen="mostrador"` en duro.
- `turnos.transicionar_turno(...)` inserta `TurnoTransicion` con `actor_usuario_id` **NOT NULL** (FK a usuario).
- `huecos.buscar_huecos(...)` devuelve `inicio`, `fin` y `sillon_ids`; valida la ventana (máximo 7 días) y las referencias (422).
- `horario.SQL_HORARIO_CTE`: un profesional sin franjas no atiende.
- `pacientes`:
  - `paciente_por_dni` y normalizadores (`normalizar_dni`, `normalizar_email`, `normalizar_telefono`, `nombre_busqueda`);
  - `crear_paciente` exige `AuthContext` y audita con `registrar_evento` (actor usuario);
  - `AuditoriaHC` ya admite `actor_tipo='sistema'` sin usuario (CHECK `actor_usuario_requerido`);
  - CHECKs de `Paciente`: nombre y apellido obligatorios, DNI de 7 a 8 dígitos, teléfono E.164, al menos un contacto.
- `auth/ratelimit.py`: un `Limiter` de slowapi con `key_func` IP+email para el login, y el handler de 429 con `Retry-After` en `main.py`.
- Frontend (C-10):
  - `PublicLayout`, router de datos con la ruta pública placeholder `/reservar/:token`;
  - `shared/api/client.ts`, que inyecta `Authorization` y `X-Clinica-Id` cuando hay sesión;
  - componentes `Aviso`, `DialogoConfirmacion`, `EstadoSeccion`, `NoEncontrada`;
  - vitest + jsdom.

## Goals / Non-Goals

**Goals:**

- Que la reserva pública use **exactamente** el mismo motor que el mostrador (`buscar_huecos` y `crear_turno`), así hueco ⇒ 201 vale también en público.
- No filtrar datos de pacientes ni de turnos ajenos por los endpoints sin autenticación.

**Non-Goals:** seña y pre-bloqueo (C-12), notificaciones (C-15), captcha.

## Decisions

### D1 — `clinica.slug` identifica la clínica en el enlace

- `TEXT NOT NULL UNIQUE`, con CHECK `slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(slug) BETWEEN 3 AND 60`.
- La migración completa los existentes con `'clinica-' || id`; `seed_core` fija `clinica-piloto`.
- **Por qué no `clinica_id` en la URL:** un id secuencial permite enumerar clínicas y queda feo en un QR.

### D2 — Token opaco con hash en la base

- Al reservar: `token = secrets.token_urlsafe(32)` (256 bits) y `turno.token_publico_hash = sha256(token).hexdigest()`, con UNIQUE parcial `WHERE token_publico_hash IS NOT NULL`.
- El token en claro se devuelve **una sola vez** en el `201` y vive solo en la URL `/reserva/{token}`. La búsqueda es por hash.
- **Por qué un hash y no el token en claro:** si se filtra la base, no aparecen enlaces válidos para cancelar turnos ajenos. Con 256 bits de entropía basta SHA-256 sin sal, sin bcrypt.

### D3 — Servicio `reserva_publica.py` sobre el motor existente

`reservar(session, slug, datos, ahora) -> (turno, token)`:

1. Clínica activa por slug (404).
2. Profesional "online": activo, `agenda_activa` y con al menos una franja (422). Prestación activa del tenant (422).
3. **Paciente:** `paciente_por_dni` sobre el DNI normalizado.
   - Si existe y está activo, se usa tal cual y no se toca su ficha.
   - Si está dado de baja, `422` genérico ("No se pudo completar la reserva").
   - Si no existe, se inserta con los normalizadores, `consentimiento_datos=false` y auditoría `AuditoriaHC(accion="crear", entidad="paciente", actor_tipo="sistema", diff={"campos": [...], "origen": "enlace"})`.
   - Si dos reservas crean el mismo DNI a la vez, el UNIQUE `(clinica_id, dni)` hace perder a una, que relee y usa la fila ganadora, igual que el patrón de `crear_paciente`.
4. **Tope por DNI:** `count(turno)` del paciente con `origen='enlace'`, estado `reservado`/`confirmado`, `is_active` e `inicio >= ahora`. Si llega a 2, `409` "Límite de reservas online alcanzado". Se cuenta por paciente y no por IP, para no castigar a una familia en la misma red.
5. **Sillón:** se prueba `crear_turno(..., origen="enlace")` con cada sillón habilitado y activo del profesional, en orden de id. Si un `TurnoNoDisponible` se debe a un turno o bloqueo del sillón, se prueba el siguiente. Si se agotan, `409`.
   - Antes de probar sillones se llama una vez a `dentro_de_horario` y a `bloqueos_solapados` sin sillón. Si fallan, `409` directo, sin iterar.
   - Esto se ejecuta dentro de `crear_turno`, que ya commitea o revierte por intento.
6. Se asigna `token_publico_hash` en el mismo INSERT, pasándolo por `datos`.

`crear_turno` suma dos parámetros opcionales con default: `origen: str = "mostrador"` y `token_publico_hash: str | None = None`. El mostrador no cambia.

**El tope por DNI** se evalúa antes del INSERT, sin lock. Dos reservas simultáneas del mismo DNI podrían dejar 3 turnos. Se acepta: es un freno de abuso, no una regla de integridad. Marcado como `ponytail:` en el código, con la mejora posible (`SELECT ... FOR UPDATE` del paciente).

### D4 — Cancelación con actor de enlace

- Migración: `turno_transicion.actor_usuario_id` pasa a nullable y se agrega `actor_tipo TEXT NOT NULL DEFAULT 'usuario'`, con:
  - CHECK `actor_tipo IN ('usuario','paciente_enlace')`;
  - CHECK `(actor_tipo = 'usuario') = (actor_usuario_id IS NOT NULL)`.
- La tabla es append-only (trigger de la 004). Un `ALTER TABLE` no la muta fila por fila; las filas existentes quedan como `usuario` por el default.
- `transicionar_turno` acepta `actor_id: int | None` y `actor_tipo: str = "usuario"`.
- `cancelar_por_token(session, token, ahora)`:
  1. busca por hash (404);
  2. `transicionar_turno(..., destino="cancelado", actor_id=None, actor_tipo="paciente_enlace")`;
  3. antes, si `ahora >= turno.inicio`, `422`.

  Reutiliza la tabla `TRANSICIONES`: cancelar un turno `asistido` o `cancelado` ya da `422`.

### D5 — API pública y anti-abuso

- Router `backend/app/api/publico.py` (`/api/public`), **sin** `require_tenant_checked` ni JWT. Toda consulta se scopea al `clinica_id` resuelto por slug, o al del turno encontrado por token.
- Rate limit con el mismo `limiter` de slowapi y `key_func=get_remote_address`. Límites por endpoint, configurables por setting con default:
  - `RATE_LIMIT_PUBLICO_LECTURA = "60/minute"` para catálogo, huecos y consulta de la reserva;
  - `RATE_LIMIT_PUBLICO_RESERVA = "5/minute"` para reservar y cancelar.

  Exceder el límite da `429` con `Retry-After`, por el handler existente.
- Schemas con `extra='forbid'`:
  - `ReservaIn`: `dni` normalizado, `nombre`/`apellido` (1 a 100 caracteres), `email`/`telefono` (al menos uno, normalizados) y `acepta_privacidad: Literal[True]`;
  - `ReservaOut` (`token`, `inicio`, `fin`, `estado`, `prestacion`, `profesional`) y `ReservaPublicaOut` (sin token);
  - `HuecoPublicoOut` (`inicio`, `fin`) y `CatalogoPublicoOut`.
- Errores sin filtrar información: `409` "Horario no disponible" igual que el mostrador; un paciente dado de baja recibe el mismo `422` genérico que cualquier dato inválido de negocio.

### D6 — Frontend público

`frontend/src/features/reserva/`:

- `api.ts`: fetch **sin** credenciales ni `X-Clinica-Id`, porque son endpoints públicos. Usa la base de `VITE_API_BASE_URL`, como `client.ts`, y no inyecta el token de sesión aunque el staff esté logueado.
- `ReservarPage.tsx` (`/reservar/:slug`):
  - selects de prestación y profesional, semana con navegación y huecos agrupados por día en hora local (`Intl.DateTimeFormat` con `timeZone` del navegador);
  - formulario accesible, checkbox de privacidad con enlace a `/privacidad`;
  - ante un `409` recarga los huecos y conserva el formulario.
- `ReservaPage.tsx` (`/reserva/:token`): comprobante, `DialogoConfirmacion` para cancelar, región `aria-live` para el estado.
- `router.tsx`: `/reservar/:token` (placeholder de C-01) pasa a `/reservar/:slug`, y se agrega `/reserva/:token`. Ambas van bajo `PublicLayout`.
- Diseño visual: se sigue el sistema existente de C-10 (`PublicLayout` y componentes `shared/ui`) para no romper la identidad. Las skills de diseño se usan para el checklist de UX y accesibilidad y para el motion contenido (transición entre pasos, confirmación), no para inventar otra marca.
- **Por qué no un wizard de varias rutas:** una sola página con pasos visibles evita perder estado entre rutas y simplifica el manejo del 409.

## Risks / Trade-offs

- [El tope por DNI se puede eludir con DNIs inventados] → El DNI no se verifica contra RENAPER (fuera de alcance). El rate limit por IP acota el volumen, y la recepción ve `origen = enlace` en la agenda. Turnstile queda como mejora si aparece abuso real.
- [El rate limit en memoria es por instancia] → Mismo riesgo ya documentado para el login (F2 lo mueve a PG). En el MVP hay una sola instancia.
- [Reutilizar un paciente por DNI permite que alguien reserve "a nombre de" otro] → No se revelan ni se modifican sus datos; el turno aparece en la agenda y el paciente real puede cancelarlo en recepción. Es la opción elegida por el usuario.
- [El 409 por tope de DNI revela que ese DNI tiene reservas online] → Fuga mínima: no dice cuántas ni cuándo. Se acepta frente a un error genérico que confundiría al paciente legítimo.
- [Sin seña, la reserva pública puede generar ausentes] → Es la decisión del usuario; C-12 agrega la seña por score de riesgo (RN-CA-02).

## Migration Plan

1. `013_reserva_online` (`down_revision = "012_horario_atencion"`):
   - `clinica.slug`: se agrega nullable, se completa, se pasa a NOT NULL y se crean UNIQUE y CHECK;
   - `turno.token_publico_hash` con UNIQUE parcial;
   - `turno_transicion`: `actor_usuario_id DROP NOT NULL`, `actor_tipo` y los dos CHECKs.
2. Downgrade:
   - borra los CHECKs y `actor_tipo`;
   - `actor_usuario_id SET NOT NULL`, que **falla** si hay cancelaciones por enlace. Se documenta: para bajar hay que borrar esas filas a mano, porque la tabla es append-only;
   - borra el índice y la columna del token, y `clinica.slug`.
