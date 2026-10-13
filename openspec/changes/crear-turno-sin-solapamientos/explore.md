# Explore: crear-turno-sin-solapamientos (C-05 recortado)

Governance C-05 = CRITICO (CHANGES.md:229) -> propose debe pedir aprobacion humana antes de escribir codigo. Solo lectura; nada modificado en el repo.

## 1. Estado actual del codigo (backend/)
- Migraciones: 001_core_models, 002_token_blacklist, 003_clinica_catalogo, 004_pacientes_ficha. Convencion: `revision="004_pacientes_ficha"`, `down_revision` = anterior (004:18-19). Nueva: `005_turnos` (down=`004_pacientes_ficha`). Helpers `_audit_columns/_pk_identity/_clinica_fk` en 004:24-45 (copiar patron).
- `btree_gist` YA creada en 003:45 y NO se elimina en downgrade (003:207). Usar `CREATE EXTENSION IF NOT EXISTS` igual.
- Modelos agenda `app/domain/agenda/models.py`: Profesional (l.35, UQ clinica_id,id l.44, `agenda_activa`), SillonRecurso (l.76), Prestacion (l.101, `duracion_min` CHECK 5..480), ProfesionalSillon (habilitacion N-M, l.122), Bloqueo (l.141; `rango` columna generada `tstzrange(inicio,fin,'[)')`, GiST parcial por `is_active`). Paciente: `domain/pacientes/models.py:30`, UQ(clinica_id,id) l.41 -> permite FK compuesta.
- Mixins en `infrastructure/persistence/mixins.py` (TenantMixin clinica_id, AuditMixin is_active/created/updated/deleted). PK `BigInteger Identity(always=True)`.
- Duracion: `domain/agenda/duracion.py:8` `calcular_fin(inicio aware, duracion_min)`; ValueError si naive o fuera de 5..480. Contrato explicito para C-05 (regla dura 6).
- Bloqueos: `domain/agenda/bloqueos.py:11` `bloqueos_solapados(session, clinica_id, inicio, fin, profesional_id, sillon_id)`: filtra tenant, is_active, alcance clinica|profesional|sillon, `&&` con `[)`. ValueError si naive o fin<=inicio. REUSAR tal cual.
- Errores de dominio: `domain/agenda/servicio.py:25-50` `CatalogoError(status_code, detail)`; NoEncontrado 404, Conflicto 409, ReferenciaInvalida 422; handler global en `main.py` (`CatalogoError` -> `{detail}`). `_commit()` (servicio.py:53) traduce SQLSTATE 23505 a 409 -> patron a seguir; para exclusion violation el SQLSTATE es **23P01** (caso nuevo).
- Helpers: `obtener(session, Modelo, clinica_id, id)` -> 404 si ajeno/inactivo; `BaseRepository` tenant-scoped (infrastructure/persistence/repository.py); `obtener_paciente(session, tenant, id)`.
- API: patron router `app/api/pacientes.py:41-45` (`Sesion`, `Tenant = Depends(require_tenant_checked)`, `Staff = require_role(...)`). Routers se registran en `main.py` (include_router). deps.py: JWT autoritativo, X-Clinica-Id solo cross-check (403 mismatch).
- RBAC `api/permissions.py`: `require_role(*claves)` (l.37). `require_sobreturno` y `set_resolver_vinculo_paciente` (reemplazo de la regla interina) quedan FUERA del recorte. `require_own_agenda` lee profesional_id de path/query, no sirve para body.
- Tests: `tests/integration/conftest.py`: `postgres_url` (testcontainers postgres:16-alpine + alembic upgrade head, l.14-27), `session_factory`, `auth_data` (clinicas A/B; admin/recep/odonto), `catalogo_data` (l.144: sillones, profesionales P/Q, prestacion A 30 min, datos de B), `make_test_client`, `bearer`, `alta_paciente`. Unit en `tests/unit/` (ej. test_agenda_duracion.py). Estilo: `test_bloqueos_solapados.py` (escenario de modulo, helper `_t(h,m)` UTC).
- Specs vigentes: clinic-catalog, schedule-blocks (Requirement "Consulta de bloqueos que impiden una reserva", l.85), tenant-isolation, access-control, patients... Capability nueva sugerida: `appointments`.

## 2. Reglas de negocio aplicables (KB)
- RN-AG-01 (05:7): sin dos turnos activos solapados en (sillon, rango) NI (profesional, rango); prevencion dura.
- RN-AG-02 (05:8): turno hereda duracion de la prestacion. RN-AG-03 (05:9): bloqueos impiden reservas.
- RN-TU-01 (05:16): estados reservado->confirmado->asistido|ausente|cancelado (transiciones fuera del recorte; solo se NACE en `reservado`).
- KB04 Turno (l.47-51): atributos y indices (profesional_id,inicio),(sillon_id,inicio),(paciente_id,inicio),(estado).
- KB03 RBAC (l.24-25): Recepcionista CRUD turnos; Admin todo; Odontologo "Lectura + bloqueos propios" (NO crea turnos).
- KB07 Flujo 1 l.29: concurrente -> gana la primera, la segunda "horario no disponible". KB08 l.58: fin calculado en servidor.
- Reglas duras CLAUDE.md: 4 (extra=forbid), 6, 7 (TIMESTAMPTZ), 8 (GiST + 409), 9 (testcontainers, Alembic up/down), 10 (clinica_id + indice + test aislamiento), 14 (datos sinteticos).

## 3. Decisiones de diseno para propose (con recomendacion)
D1 Rango semiabierto: columna `rango tstzrange GENERATED ALWAYS AS (tstzrange(inicio, fin, '[)')) STORED` (igual que Bloqueo) -> `[10:00,10:30)` y `[10:30,11:00)` NO solapan. REC: si.
D2 Dos exclusion constraints (btree_gist): `EXCLUDE USING gist (clinica_id WITH =, sillon_id WITH =, rango WITH &&) WHERE (is_active AND estado IN ('reservado','confirmado','asistido','ausente'?...))`. REC: activos = reservado, confirmado, asistido (ausente/cancelado liberan hueco; sobreturno excluido del WHERE porque por diseno SI se solapa). Idem con `profesional_id`. Incluir clinica_id en la clave. Alembic con SQL crudo.
D3 Concurrencia: la DB arbitra. Servicio hace pre-chequeo amigable pero no confiable; INSERT+commit; `IntegrityError` con `orig.sqlstate == '23P01'` -> `Conflicto("Horario no disponible")` 409. Sin SELECT FOR UPDATE ni advisory locks. Distinguir cual constraint saltó por `orig.diag.constraint_name` para mensaje (profesional vs sillon).
D4 Bloqueos: no entran en exclusion (otra tabla) -> chequeo en servicio con `bloqueos_solapados` antes del INSERT, misma transaccion -> 409. TOCTOU residual (bloqueo creado entre check e insert) aceptado y documentado; trigger = sobreingenieria.
D5 Columnas minimas Turno (005): id, clinica_id, profesional_id, sillon_id, paciente_id, prestacion_id, duracion_min (snapshot), inicio, fin, rango (generada), estado (CHECK con enum completo KB, default 'reservado'), origen (CHECK, default 'mostrador'), audit. FKs compuestas (clinica_id, x)->tabla(clinica_id,id) como ProfesionalSillon. CHECK `fin > inicio`. OMITIR sena_*, motivo_sobreturno. Indices (clinica_id, profesional_id, inicio), (clinica_id, sillon_id, inicio), (clinica_id, paciente_id, inicio), (clinica_id, estado).
D6 API: `POST /api/turnos` body {profesional_id, sillon_id, paciente_id, prestacion_id, inicio aware}; `extra='forbid'` -> `fin`/`duracion_min` en body = 422; `inicio` naive = 422. fin = `calcular_fin(inicio, prestacion.duracion_min)`. 201 con TurnoOut. Opcional GET /api/turnos/{id} (404 cross-tenant) para verificar aislamiento; lista solo si hace falta.
D7 Referencias (todas en tenant): profesional activo y `agenda_activa`, sillon activo, prestacion activa, paciente activo; inexistente/ajeno/inactivo = 422 `ReferenciaInvalida` (patron crear_bloqueo C-04). Habilitacion `ProfesionalSillon`: REC exigirla (422); pregunta abierta si el equipo quiere recortarla.
D8 RBAC: `require_role("admin","recepcionista")`; odontologo 403; sin token 401. Orden: 401 -> 403 -> 422 payload -> 422 referencias -> 409.
D9 Codigos: 201; 401; 403; 404 solo GET por id ajeno; 409 solape profesional / sillon / bloqueo (mensajes distintos, sin exponer PII del turno en conflicto); 422 validacion/referencias/fin en body.
D10 Capa: `domain/agenda/turnos.py` (modelo + `crear_turno`), schemas, `api/turnos.py`; `TurnoError` hereda `CatalogoError` -> reutiliza el handler (solo include_router en main.py).
D11 Auditoria de transiciones fuera de alcance; created_at basta.

## 4. Escenarios de spec propuestos (capability `appointments`)
1. Happy path: recepcionista crea turno prestacion 30 min inicio 10:00Z -> 201, estado reservado, fin=10:30Z calculado en servidor.
2. `fin`/`duracion_min` enviado por cliente -> 422; `inicio` sin zona horaria -> 422.
3. Overlap profesional: P ocupado 10:00-10:30, otro sillon, inicio 10:15 -> 409.
4. Overlap sillon: S1 ocupado, otro profesional, rango parcial -> 409.
5. Bloqueo clinica / profesional / sillon cubre el rango -> 409; bloqueo de OTRO profesional no impide -> 201.
6. Edge contiguo: existente [10:00,10:30), nuevo inicio 10:30 (mismo prof y sillon) -> 201; turno que termina justo cuando empieza un bloqueo -> 201.
7. Turno cancelado (o is_active=false) en el mismo rango no bloquea -> 201 (valida el WHERE).
8. Concurrencia: 2..5 requests simultaneos al mismo hueco -> exactamente un 201, resto 409, una sola fila.
9. DB-level: INSERT SQL directo solapado (sin servicio) viola exclusion (23P01) por profesional y por sillon (regla 8).
10. Aislamiento: clinica B mismo horario -> 201 sin chocar con A; ids de A con token de B -> 422/404 y 0 filas; query cruzada = 0 filas (regla 10).
11. RBAC: odontologo 403, sin token 401, admin y recepcionista 201.
12. Referencias invalidas (paciente inactivo, prestacion inactiva, profesional agenda_activa=false, sillon no habilitado) -> 422.
13. Migracion 005 up/down limpia (patron test_migracion_004.py / test_migration_003.py).
Unit: schema (extra forbid, naive datetime); mapeo 23P01 -> 409 con IntegrityError simulado.

## 5. Riesgos / incognitas
- Docker NO instalado: tests de integracion (testcontainers) no corren localmente; solo unit. Instalar Docker Desktop/WSL2 antes de apply o la evidencia queda pendiente.
- Concurrencia en tests: ThreadPoolExecutor + Barrier; el override de get_session (conftest:117-124) da sesion nueva por request, OK.
- Bloqueo TOCTOU (D4). Habilitacion profesional-sillon: decision del equipo.
- Si el C-05 completo agrega sobreturnos, quedan fuera del WHERE de las exclusiones (ya contemplado en D2), sin migrar de nuevo.
- Regla interina de vinculo odontologo-paciente (permissions.py `_vinculo_interino`) no se toca.
- KB10 preguntas abiertas Altas no revisadas en detalle; verificar que ninguna afecte turnos.
- git status tiene .pyc staged como borrados (ruido ajeno al change).
