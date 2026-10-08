# Tasks — c-03-auth-rbac

## 1. Settings + dependencias base

- [x] 1.1 Añadir env JWT a `settings.py` (`JWT_SECRET_KEY` requerida sin default, `JWT_ALGORITHM`, `JWT_ACCESS_MIN`, `JWT_REFRESH_DAYS`, `COOKIE_SECURE`) + placeholders en `.env.example`, y verificar que el boot falla en claro sin secreto y `pytest tests/test_settings* -q` pasa.
- [x] 1.2 Añadir dependencias `PyJWT` + `slowapi` (bcrypt ya existe vía C-02) a `requirements.txt`, y verificar `ruff check backend` limpio tras el cambio.

## 2. Migración 002 blacklist

- [x] 2.1 Crear `alembic/versions/002_token_blacklist.py` (tabla `token_blacklist`: `jti` PK, `type`, `exp` TIMESTAMPTZ NOT NULL + índice, `revocado_at`, `motivo`; down = drop) y verificar `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` en PG efímero.
- [x] 2.2 Añadir modelo SQLAlchemy `TokenBlacklist` + job `jobs/purga_blacklist.py` (`DELETE WHERE exp < now() - 1h`), y verificar test de purga con `PostgresContainer("postgres:16-alpine")` (fila expirada se borra, vigente persiste).

## 3. Servicio auth (tokens + blacklist + rate-limit)

- [x] 3.1 Implementar `domain/auth/tokens.py` (emisión HS256 con claims `sub/tenant_id/roles/email/jti/type/iat/exp`, verificación firma+exp+tolerancia 60s+type, blacklist lookup) con schemas `extra='forbid'`, y verificar tests unitarios de firma/expiración/`type` cruzado rechazado.
- [x] 3.2 Implementar verificación de password bcrypt en tiempo constante + normalización de email, y verificar test de login-fallo genérico (mismo mensaje para usuario-inexistente vs password-mala).
- [x] 3.3 Implementar rate limit slowapi 5/60s por IP+email en login con `429` + `Retry-After`, y verificar test de 6º intento bloqueado.

## 4. Endpoints /api/auth/*

- [x] 4.1 Implementar `POST /api/auth/login` (set-cookie refresh HttpOnly Secure/SameSite=Lax/Path=/api/auth + access en cuerpo) y `GET /api/auth/me`, y verificar tests login OK (cookie + claims) / KO (401 genérico) / `extra='forbid'` → 422 / `me` sin token → 401.
- [x] 4.2 Implementar `POST /api/auth/refresh` con rotación (nuevo par + blacklist del `jti` anterior) y `POST /api/auth/logout` (blacklist de ambos + limpieza de cookie), y verificar tests de rotación OK, replay del anterior → 401, logout invalida access, token expirado → 401.
- [x] 4.3 Registrar eventos auth en log estructurado (login OK/KO, refresh, logout, rate-limit) sin PII más allá de email/IP, y verificar que los tests 4.1–4.2 emiten los eventos esperados.

## 5. RBAC + cross-check tenant

- [x] 5.1 Implementar `get_current_user` + `require_tenant_checked` (JWT autoritativo, header opcional con cross-check mismatch → 403) + allowlist `PUBLIC_PREFIXES` (public/webhooks-QR/comprobantes/cumplimiento/auth), y verificar tests: sin token → 401, mismatch → 403, JWT ajeno → 0 filas, ruta pública sin token OK, **BREAKING** documentado en respuesta 401.
- [x] 5.2 Implementar `PermissionContext` (`require_role`, `require_admin`, `require_own_agenda` con fallo cerrado sin vínculo Usuario→Profesional) + matriz del `03` codificada, y verificar tests: recepcionista → HC 403, no-admin → `/admin` 403, tercerizado vs agenda ajena 403 / propia OK, sobreturno y anulación sin rol → 403 (contrato que C-05/C-12 invocarán).

## 6. Integración y cierre

- [x] 6.1 Cablear routers en `main.py`, actualizar `deps.py` (reexport compat + remoción del TODO(C-03)), guía frontend (Bearer + `X-Clinica-Id`, nunca `localStorage`) en `frontend/src/shared/apiClient` o nota de contrato, y verificar `ruff + pytest` backend y `tsc --noEmit` frontend en verde.
- [x] 6.2 Verificación E2E por tenant con `PostgresContainer("postgres:16-alpine")`: seed C-02 → login → `me` → refresh → replay 401 → logout 401 → cross-tenant 403, y verificar `openspec validate --strict` del change en verde.

## Workflow follow-up

- Ejecutar `/opsx:apply c-03-auth-rbac` tras revisión humana de los riesgos CRÍTICOS (secretos, CSRF, rate-limit por-instancia, QR).
- Archivar con `/opsx:archive c-03-auth-rbac` y marcar `[x] C-03` en CHANGES.md.
