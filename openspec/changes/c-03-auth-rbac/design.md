# Design — c-03-auth-rbac

## Context

Ver `proposal.md` (Why). Estado actual (C-02 archivado): `require_tenant` en `backend/app/api/deps.py` resuelve tenant desde `X-Clinica-Id` con `TODO(C-03)` de cross-check JWT; modelos `Clinica/Usuario/Rol/UsuarioRol` + `TenantMixin/AuditMixin` + `BaseRepository/UoW` existen; seed crea 1 clínica + 4 roles + 1 admin con hash bcrypt; settings solo tiene `DATABASE_URL/APP_BASE_URL/RESERVA_PREBLOQUEO_MIN`; app solo monta `health_router`. Specs main: `tenant-isolation` (resolución por header), `core-models`, `platform-health`, `platform-config`. Este change introduce la primera frontera de seguridad real y el contrato que todo C-04+ consume.

## Goals / Non-Goals

**Goals:**
- Cerrar el spoofing de tenant (JWT autoritativo + cross-check cerrado).
- Dejar el contrato auth/RBAC que C-04+ importa sin re-diseñar (endpoints, claims, PermissionContext, rutas públicas).
- Blacklist persistente con rotación que sobrevive reinicios (tabla, no memoria).

**Non-Goals:**
- No UI de login (eso es C-07/C-10/C-14); solo contrato API + cookies.
- No MFA/OTP, no OAuth social, no recuperación de password (F2).
- No toca motor de turnos ni caja (solo deja los hooks `require_own_agenda`/roles que C-05/C-12 aplicarán).
- No migra a API oficial Meta: webhooks WA quedan diseñados para sesión QR local (decisión 2026-10-08).

## Decisions

1. **JWT con PyJWT, HS256, `type` discriminante.**
   - Access 15 min + refresh 7 días; claims `sub/tenant_id/roles/email/jti/type/iat/exp`. Un solo `JWT_SECRET_KEY` (256-bit, solo env) + claim `type` distingue usos; alternativa de dos secretos (`JWT_ACCESS_SECRET`/`JWT_REFRESH_SECRET`) descartada por duplicar rotación sin ganancia en MVP (revisitar si se exige rotación independiente).
   - Alternativa `python-jose` descartada: mantenimiento irregular; PyJWT es mínimo y auditable.
2. **Refresh solo en cookie HttpOnly (`Secure`, `SameSite=Lax`, `Path=/api/auth`, 7 días); access solo en `Authorization: Bearer`.**
   - Nunca JWT en `localStorage` (regla dura 12 + XSS). `Secure` se relaja solo en dev http local por flag `COOKIE_SECURE=false`; prod exige `true`. CSRF sobre `/refresh` mitigado por `SameSite=Lax` + método POST + scope de path; sin token CSRF adicional en MVP (documentado como riesgo aceptado).
3. **Password con `passlib[bcrypt]` (reusa C-02), cost 12; comparación en tiempo constante; fallos genéricos.**
   - Email normalizado a minúsculas antes de lookup (consistente con `UsuarioCreate`). Sin enumeración: mismo mensaje/tiempo para usuario-inexistente vs password-mala.
4. **Rate limit 5/60s por IP+email en `/login` vía slowapi (memoria en MVP).**
   - Alternativa middleware propio en PG descartada por complejidad; alternativa Redis descartada (sin Redis en stack). Límite documentado como por-instancia: con >1 réplica se subestima el ataque → F2 mueve el contador a PG/`token_blacklist`-adyacente o Redis. Respuesta `429` con `Retry-After`.
5. **Blacklist en PG: tabla `token_blacklist(jti TEXT PK, type TEXT, exp TIMESTAMPTZ NOT NULL, revocado_at TIMESTAMPTZ default now(), motivo TEXT)`.**
   - Verificación en cada request protegido: firma + `exp` + `SELECT 1 FROM token_blacklist WHERE jti=?`. Índices: PK sobre `jti`, btree sobre `exp` para purga. Purga por job/cron (`DELETE WHERE exp < now() - interval '1h'`). Logout inserta ambos `jti`; refresh inserta el `jti` anterior con motivo `rotated`.
6. **`require_tenant` refactorizado a `get_current_user` + `require_tenant_checked`.**
   - `get_current_user: Depends(oauth2 Bearer)` → decodifica, valida firma/exp/type=access, chequea blacklist, carga `Usuario` activo + roles (join `UsuarioRol→Rol`), retorna `AuthContext(sub, tenant_id, roles, email, jti)`. `require_tenant_checked(AuthContext, X-Clinica-Id opcional)` → si hay header y `!= tenant_id` → `403`; si no hay header, usa `tenant_id` del JWT (el header pasa a ser opcional/compat, no autoritativo). Rutas públicas usan dependencias separadas sin auth.
7. **PermissionContext como dependencias finas, no middleware global.**
   - `require_role(*claves)`, `require_admin()` (= `require_role("admin")`), `require_own_agenda(profesional_id)` (lee `profesional_id` del path/query y lo compara con el `profesional_id` vinculado al usuario — binding `Usuario→Profesional` se resuelve en C-04; hasta entonces compara `sub` contra mapa/lookup y falla cerrado si no hay vínculo). Sobreturnos/anulaciones no son endpoints aquí: este change solo deja el chequeo unit-testeado que C-05/C-12 invocarán.
8. **Rutas públicas como allowlist explícita.**
   - Prefijos exentos: `/api/public/*`, `/api/webhooks/mercadopago`, `/api/webhooks/whatsapp` (firma `MP_WEBHOOK_SECRET` / secreto de sesión QR local — no `WHATSAPP_API_TOKEN` Cloud), `/api/comprobantes/*` (token opaco), `/cumplimiento`, `/privacidad`, `/api/auth/*`. Implementado como `PUBLIC_PREFIXES` + test que falla si una ruta nueva scoped nace sin auth por defecto (convención: todo router nuevo incluye `Depends(get_current_user)` salvo allowlist).
9. **Nuevas env (solo backend, nunca `VITE_`): `JWT_SECRET_KEY` (requerida, sin default), `JWT_ALGORITHM=HS256`, `JWT_ACCESS_MIN=15`, `JWT_REFRESH_DAYS=7`, `COOKIE_SECURE=true`, `RATE_LIMIT_LOGIN=5/60s`.**
   - Boot falla en claro si falta `JWT_SECRET_KEY` (no default sintético). `.env.example` solo placeholders.
10. **Schemas `LoginIn(email, password)`, `RefreshIn` vacío (cookie), `TokenOut(access, token_type, expires_in)`, `MeOut(sub, email, tenant_id, roles)` — todos `extra='forbid'`.**
11. **Tests con `PostgresContainer("postgres:16-alpine")` + Alembic up/down 002.**
   - Casos: login OK/KO, expirado, replay de refresh, tercerizado vs agenda ajena, rate-limit, cross-tenant 403, blacklist. Reloj manipulado vía `exp` firmados a mano en tests (no `freezegun` sobre el servidor).

## Risks / Trade-offs

- [Riesgo] Robo de access en memoria XSS → Mitigación: access corto (15 min), sin persistencia, HttpOnly para refresh; frontend no guarda nada sensible.
- [Riesgo] CSRF contra `/refresh` con cookie → Mitigación: `SameSite=Lax` + POST + path restringido; documentado, sin token CSRF en MVP.
- [Riesgo] Rate limit por-instancia subestima ataque distribuido → Mitigación: documentado; F2 a contador PG/Redis. Tests unitarios contra una instancia.
- [Riesgo] `COOKIE_SECURE=false` en dev filtra a prod por error → Mitigación: default `true`; dev lo desactiva explícito; test de settings falla si prod arranca sin secure.
- [Riesgo] `require_own_agenda` sin binding Usuario→Profesional (C-04) queda parcial → Mitigación: falla cerrado (403) si no hay vínculo; C-04 completa el join.
- [Riesgo] QR de WhatsApp (no oficial) bloquea número → Mitigación: fuera de este change salvo diseño de webhook local con secreto propio + allowlist; documentar backup/reconexión en C-15.
- [Trade-off] Blacklist en PG agrega 1 lookup por request → aceptado (PK por `jti`, latencia despreciable frente a cierre de replay); alternativa stateless (solo `exp` corto) descartada porque no permite logout/rotación real.

## Migration Plan

- Alembic `002_token_blacklist.py` (up: crea tabla + índices; down: drop). Sin migración de datos; despliegue sin downtime (tabla nueva, ningún endpoint viejo la toca). Rollback: `downgrade -1` + redeploy previo (endpoints `/auth` 404, resto sigue con header — degradado conocido, no silencioso).
- Orden: migrar 002 → desplegar backend (nuevas env) → frontend adopta Bearer (sin `localStorage`) en changes siguientes.

## Open Questions

- ¿Un solo `JWT_SECRET_KEY` o par access/refresh separado para rotación independiente? (Propuesta: uno solo + `type`; reversible sin cambiar specs.)
- ¿Access 15 min confirmado o 30 min por UX de mostrador? (No cambia specs: constante env.)
- ¿Purga de blacklist como cron del SO, APScheduler o job `jobs/`? (Propuesta: `jobs/purga_blacklist.py` invocado por cron; C-15/C-13 reutilizan el patrón.)
