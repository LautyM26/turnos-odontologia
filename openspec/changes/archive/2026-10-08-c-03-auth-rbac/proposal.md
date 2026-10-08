# Proposal — c-03-auth-rbac

## Why

C-02 dejó el multi-tenant sin frontera real de autenticación: `require_tenant` confía en el header manual `X-Clinica-Id` con un `TODO(C-03)` explícito de cross-check contra JWT. Sin auth, cualquier cliente puede spoofear el tenant y no hay RBAC que desbloquee el resto del roadmap (C-04→C-19 dependen de identidad + roles). Este change cierra ese riesgo CRÍTICO.

## What Changes

- `POST /api/auth/login` — valida email + password (bcrypt del seed C-02), emite JWT access (15 min) + refresh (7 días). Rate limit 5 intentos/60s por par IP+email. Respuestas de fallo genéricas (no enumerar usuarios). Schemas Pydantic con `extra='forbid'`.
- `POST /api/auth/refresh` — acepta refresh vía cookie HttpOnly, rota el par (emite nuevo jti, blacklista el anterior) y rechaza tokens ya rotados/revocados.
- `POST /api/auth/logout` — blacklista access + refresh vigentes (por `jti`), limpia cookie de refresh.
- `GET /api/auth/me` — retorna identidad (`sub`, `email`, `tenant_id`, `roles`) desde el access vigente.
- Claims JWT: `sub` (usuario_id), `tenant_id` (clinica_id — gobierna todo scoping), `roles` (lista de claves), `email`, `jti`, `type` (`access`|`refresh`), `iat`, `exp`. Algoritmo HS256 con secreto solo en env backend (`JWT_SECRET_KEY` + `JWT_REFRESH_SECRET_KEY` o uno solo con `type` discriminante — decisión en design). Access via `Authorization: Bearer`; refresh **solo** en cookie HttpOnly (`Secure`, `SameSite=Lax`, `Path=/api/auth`).
- `PermissionContext`: dependencias `require_role(*roles)`, `require_admin()`, `require_own_agenda()` (tercerizado solo ve su agenda; admin/recepcionista gestionan sobreturnos según matriz `03`). Matriz RBAC del `03_actores_y_roles.md` codificada en servidor; cliente solo display. Anulaciones de caja y sobreturnos se chequean a través de este contexto (aplicación en C-05/C-12, contrato aquí).
- Cross-check tenant: `require_tenant` pasa a exigir JWT válido y a fallar cerrado ante mismatch `JWT.tenant_id != X-Clinica-Id` (401 sin token / 403 mismatch). Se elimina el spoofing manual. Rutas públicas declaradas quedan exentas de este chequeo.
- Rutas públicas explícitas (sin login): enlace reserva (`/api/public/*`, C-06), webhooks Mercado Pago + WhatsApp-QR (sesión local con número dedicado — decisión 2026-10-08, ya no Cloud API oficial), comprobantes/facturas por token, páginas `/cumplimiento` + `/privacidad`. Resto tras login. **BREAKING**: todo endpoint scoped existente/futuro sin token pasa a 401 (antes solo pedía header).
- Migración Alembic 002: tabla `token_blacklist` (`jti` único, `type`, `exp` TIMESTAMPTZ para purga, `revocado_at`, `motivo`). Job/tarea de purga de expirados.
- Observabilidad mínima: loguear eventos auth (login OK/KO, refresh, logout, rate-limit hits) sin PII sensible más allá de email hash/IP.
- Tests (testcontainers `postgres:16-alpine`, Alembic up/down 002, nunca SQLite): login OK/KO, token expirado → 401, refresh rotation invalida el anterior (replay → 401), tercerizado no ve agenda ajena (403), rate limit 6º intento → 429, cross-tenant con JWT ajeno → 403/0 filas, blacklist se respeta.

## Capabilities

### New Capabilities

- `auth`: ciclo de vida de sesión JWT — login/refresh/logout/me, claims, expiraciones, transporte (Bearer + cookie HttpOnly), rate limit, blacklist y eventos auditados.
- `access-control`: RBAC por recurso — `PermissionContext` (`require_role`, `require_admin`, `require_own_agenda`), matriz de permisos del `03` codificada, rutas públicas declaradas, reglas transversales (sobreturnos y anulaciones de caja chequeados aquí).

### Modified Capabilities

- `tenant-isolation`: el requisito "Resolución de tenant por request" cambia — el `tenant_id` autoritativo pasa a ser el claim JWT; el header `X-Clinica-Id` se mantiene como afirmación del cliente sujeta a cross-check (mismatch → 403). Sin token → 401 salvo ruta pública declarada.

## Impact

- Código: nuevo `backend/app/domain/auth/` (servicio tokens, blacklist, rate-limit), `backend/app/api/auth.py` + `backend/app/api/permissions.py` (PermissionContext), refactor `backend/app/api/deps.py` (`require_tenant` + `get_current_user`), `backend/app/infrastructure/settings.py` (nuevas env JWT), migración `002_token_blacklist.py`, seed/admin sin cambios de schema (reusa hash bcrypt C-02).
- APIs: 4 endpoints nuevos bajo `/api/auth/*`; contrato de auth para todos los endpoints scoped futuros (C-04+); frontend `shared/apiClient` deberá enviar Bearer + `X-Clinica-Id` y no guardar JWT en `localStorage`.
- Dependencias: `pyjwt` (o `python-jose`) + `passlib[bcrypt]` (ya en C-02 para seed) + limitador (slowapi o middleware propio — decisión en design). Sin cambios de infra.
- Sistemas: desbloquea GATE 3 (C-04 + C-08 en paralelo). Riesgo si no se hace: spoofing de tenant abierto.
