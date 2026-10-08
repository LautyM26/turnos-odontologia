# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **Turnos Odontología (SaaS multi-tenant AR)**.
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**
> Stack decidido (DD-08): backend Python + FastAPI, DB PostgreSQL, frontend React + Vite. Nube multi-tenant (DD-09).
> Fuera del MVP (F2, no se propone): periodontograma, receta propia ReNaPDiS, cobertura/copago/lotes/RNO, liquidación, DICOM, IA clínica, inventario/laboratorio, portal paciente, telemedicina, marketplace, API pública.

---

## Cómo usar este documento

1. Identificar el change a implementar (verificar que sus dependencias están en `openspec/changes/archive/`).
2. Leer los docs de la knowledge-base indicados en "Leer antes".
3. Ejecutar `/opsx:propose <nombre-del-change>`.
4. Al terminar el change, archivarlo con `/opsx:archive <nombre-del-change>`.
5. Marcar el checkbox `[x]` en este archivo.

---

## Árbol de dependencias

```
C-01 foundation-setup
  └── C-02 core-models-multitenancy
        └── C-03 auth-rbac                       ← desbloquea TODO lo demás
              │
              ├── C-04 clinica-catalogo ─────────┐
              │                                   ├─→ C-05 motor-turnos
              ├── C-08 pacientes-ficha ──┐       │     ├── C-06 reserva-online-publica
              │                           ├──────┘     ├── C-07 agenda-frontend
              │                           │            ├── C-15 whatsapp-bidireccional ─┬─→ C-16 lista-espera-relleno
              │                           │            │                                └─→ C-17 chatbot-reprogramacion
              │                           │            └── C-11 presupuesto-plan ─┬─→ C-12 caja-mercadopago ─→ C-13 factura-arca ─→ C-14 comercial-frontend
              │                           │                                       (C-11 requiere C-05 + C-09)
              │                           └── C-09 odontograma-evolucion
              │                                 ├── C-10 clinica-frontend
              │                                 └── C-11 presupuesto-plan (join con C-05)
              │
              ├── C-18 consentimientos-cumplimiento   ← solo necesita C-03 + C-09
              └── C-19 recetas-partner-renapdis       ← solo necesita C-08 + C-09 (temprana vía partner, DD-06)
```

### Paralelismo por fase

> Cada "gate" es un punto de sincronización. Los changes dentro de un grupo pueden ejecutarse en paralelo.

```
GATE 0: ninguna
  → C-01 foundation-setup (solo)

GATE 1: C-01 ✓
  → C-02 core-models-multitenancy (solo)

GATE 2: C-02 ✓
  → C-03 auth-rbac (solo)

GATE 3: C-03 ✓                     ← PRIMER FORK (2 paralelos)
  → C-04 clinica-catalogo          [Agente A — Backend Core]
  → C-08 pacientes-ficha           [Agente B — Backend Aux]

GATE 4: C-04 + C-08 ✓
  → C-05 motor-turnos               [Agente A — requiere ambas ramas]
  → C-09 odontograma-evolucion      [Agente B — solo requería C-08, corre en paralelo a C-05]  ← FORK

GATE 5: C-05 + C-09 ✓              ← GRAN FORK (5 paralelos)
  → C-06 reserva-online-publica     [Agente A — si C-05 ✓]
  → C-07 agenda-frontend            [Agente C — si C-05 ✓]
  → C-10 clinica-frontend           [Agente C — si C-09 ✓, tras C-07 o en paralelo si hay capacidad]
  → C-15 whatsapp-bidireccional     [Agente B — si C-05 ✓]
  → C-11 presupuesto-plan           [Agente A — si C-05 + C-09 ✓, tras C-06 o en paralelo]

GATE 6: C-11 + C-05 ✓
  → C-12 caja-mercadopago           [Agente A]
  → C-16 lista-espera-relleno       [Agente B — si C-15 ✓]
  → C-17 chatbot-reprogramacion     [Agente B — si C-15 ✓, tras C-16 o en paralelo]
  → C-18 consentimientos-cumplimiento [Agente C — si C-09 ✓, independiente de C-11]
  → C-19 recetas-partner-renapdis   [Agente C — si C-08 + C-09 ✓, tras C-18 o en paralelo]

GATE 7: C-12 ✓
  → C-13 factura-arca               [Agente A]

GATE 8: C-11 + C-12 + C-13 ✓
  → C-14 comercial-frontend         [Agente C]
```

### Camino crítico (9 changes — mínimo irreducible)

```
C-01 → C-02 → C-03 → C-04 → C-05 → C-11 → C-12 → C-13 → C-14
```

> C-08 corre en paralelo a C-04 y C-09 en paralelo a C-05; ambas se unen (join) en C-11. Sin ese join el camino crítico aparente sería más corto pero incorrecto: C-11 exige odontograma (C-09) y turnos (C-05). WhatsApp (C-15) y lista de espera (C-16) son DIF/IMP complementarios fuera del camino mínimo: la reserva online funciona sin ellos, pero el producto no compite sin ellos.

### Plan óptimo con 3 agentes

```
Paso │ Agente A (Backend Core)      │ Agente B (Backend Aux)         │ Agente C (Frontend)
─────┼──────────────────────────────┼────────────────────────────────┼─────────────────────────────
  1  │ C-01 foundation-setup        │ —                              │ —
  2  │ C-02 core-models             │ —                              │ —
  3  │ C-03 auth-rbac               │ —                              │ —
  4  │ C-04 clinica-catalogo        │ C-08 pacientes-ficha           │ —
  5  │ C-05 motor-turnos            │ C-09 odontograma-evolucion     │ —
  6  │ C-06 reserva-online-publica  │ C-15 whatsapp-bidireccional    │ C-07 agenda-frontend
  7  │ C-11 presupuesto-plan        │ C-16 lista-espera-relleno      │ C-10 clinica-frontend
  8  │ C-12 caja-mercadopago        │ C-17 chatbot-reprogramacion    │ C-18 consentimientos-cumpl.*
  9  │ C-13 factura-arca            │ C-19 recetas-partner-renapdis  │ C-14 comercial-frontend
```

> \* C-18 es full-stack liviano (mayoría backend + página pública de cumplimiento); el Agente C lo toma cuando libera C-10. C-14 va último porque muestra cobros + facturas + seguimiento.

---

## FASE 0 — Cimientos

### [C-01] `foundation-setup`
- **Estado**: `[x]` pendiente
- **Scope**: Scaffolding completo del monorepo + infraestructura base (DD-08, DD-09)
  - Estructura: `backend/app/{domain,application,infrastructure}/`, `frontend/src/{features,shared,pages}/`, `jobs/`, `docs-legales/`
  - `backend/`: Python + FastAPI app mínima con `GET /api/health`, settings por env (`DATABASE_URL`, `APP_BASE_URL`, `RESERVA_PREBLOQUEO_MIN`), logger, handler de excepciones, Alembic inicializado, `docker-compose.yml` con PostgreSQL
  - `frontend/`: React + Vite + TypeScript scaffolding, router, cliente HTTP con tenant header, Tailwind
  - `.env.example` en cada sub-proyecto con las 12 variables de `08` (MP, WhatsApp, ARCA, ReNaPDiS partner, `ARS_PRECIO_MENSAJE`, `RESERVA_PREBLOQUEO_MIN`); ningún secreto en repo
  - CI GitHub Actions: jobs paralelos backend (ruff + pytest smoke) y frontend (tsc + build)
  - Tests: health check, carga de settings sin secretos hardcodeados
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/01_vision_y_objetivos.md` (qué es el sistema y alcance MVP)
  - `knowledge-base/02_descripcion_general.md` §Stack DECIDIDO + §Arquitectura general
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios + §Variables de entorno
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-08 + §DD-09

---

### [C-02] `core-models-multitenancy`
- **Estado**: `[x]` pendiente
- **Scope**: Modelos base multi-tenant + migraciones iniciales + seed mínimo (DD-09, SU-01/SU-02 validados)
  - Modelos: `Clinica` (nombre, CUIT, domicilio, datos fiscales ARCA, moneda ARS, política de seña), `Usuario` (clinica_id, email, hash, activo), `Rol`, `UsuarioRol`
  - `TenantMixin` (clinica_id obligatorio) + `AuditMixin` (`is_active`, `created_at`, `updated_at`, `deleted_at`); aislamiento por tenant a nivel query (scoped session / dependencia FastAPI `require_tenant`)
  - `BaseRepository[T]`, `UnitOfWork`; validador CUIT argentino
  - Migración 001: tablas core + índices `(clinica_id, activo)`
  - Seed mínimo: 1 clínica piloto, 4 roles (admin, odontólogo, recepcionista, paciente-enlace), 1 usuario ADMIN; prestaciones NO (vienen del piloto, PA-09)
  - Tests: aislamiento multi-tenant (query cruzada retorna 0), CUIT inválido rechazado, seed idempotente
- **Dependencias**: C-01
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Clinica + §Usuario / Rol + AuditoriaHC + §Seed data inicial
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones aplicados (SaaS multi-tenant, RBAC)
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-09 + §SU-01 + §SU-02

---

## FASE 1 — Identidad y acceso

### [C-03] `auth-rbac`
- **Estado**: `[ ]` pendiente
- **Scope**: Autenticación JWT + RBAC por recurso (SU-02 validado: 4 roles, tercerizado solo su agenda, sobreturnos admin/recepcionista)
  - `POST /api/auth/login` — JWT access (15 min) + refresh (7 días), rate limit 5/60s por IP+email; `POST /api/auth/refresh` con rotación + blacklist; `POST /api/auth/logout`; `GET /api/auth/me`
  - Claims JWT: `sub`, `tenant_id` (clinica_id), `roles`, `email`, `jti`, `type`, `iat`, `exp`; refresh en cookie HttpOnly (secure, samesite=lax)
  - `PermissionContext`: `require_role()`, `require_admin()`, `require_own_agenda()` (tercerizado); matriz del `03` codificada; anulaciones de caja y sobreturnos chequeados aquí
  - Rutas públicas declaradas: enlace reserva, webhooks (Meta/MP), comprobantes, cumplimiento (resto tras login)
  - Migración 002: blacklist de tokens (`jti`, `exp`)
  - Tests: login OK/KO, token expirado, refresh rotation invalida anterior, tercerizado no ve agenda ajena, rate limit
- **Dependencias**: C-02
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` (matriz completa + §Rutas públicas)
  - `knowledge-base/05_reglas_de_negocio.md` §Dominio: Cumplimiento y seguridad + §Excepciones globales
  - `knowledge-base/07_flujos_principales.md` §Flujo 1 (reserva sin cuenta — qué queda público)
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad

---

## FASE 2 — Núcleo agenda (catálogo, pacientes, motor, reserva)

> C-04 y C-08 corren en paralelo tras C-03. C-05 exige ambas (el turno referencia profesional + sillón + paciente — regla entidad-referenciada-antes).

### [C-04] `clinica-catalogo`
- **Estado**: `[ ]` pendiente
- **Scope**: Catálogo operativo de la clínica: profesionales, sillones/recursos, prestaciones y bloqueos (DD-04, US-001/US-002)
  - Modelos: `Profesional` (clinica_id, nombre, matrícula, especialidad, agenda_activa, tercerizado flag), `SillonRecurso` (nombre, tipo sillón/box/equipo, activo), `Prestacion` (nombre, duracion_min editable, monto ARS referencia, activa), `Bloqueo` (profesional_id/sillon_id nullable, rango inicio-fin, motivo), `ProfesionalSillon` (habilitación *—*)
  - Endpoints admin CRUD: `/api/admin/profesionales`, `/sillones`, `/prestaciones`, `/bloqueos` (paginados, scoped por tenant)
  - Regla de servidor: duraciones y rangos se calculan en backend, nunca se confía en el cliente
  - Migración 003: tablas catálogo + índices `(clinica_id, activo)`
  - Seed: 1 sillón + 1 profesional de ejemplo + 3 prestaciones con duración del piloto (marcados `seed=true`, borrables)
  - Tests: CRUD por tenant, bloqueo impide hueco (chequeado en C-05), duración por prestación no slot fijo (RN-AG-02)
- **Dependencias**: C-03
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Profesional + §Sillon/Recurso + §Seed data inicial
  - `knowledge-base/05_reglas_de_negocio.md` §Dominio: Agenda (RN-AG-01 a RN-AG-04)
  - `knowledge-base/06_funcionalidades.md` §Épica 1 (US-001, US-002)
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-04 + §SU-06/PA-09 (seed desde el piloto)

---

### [C-08] `pacientes-ficha`
- **Estado**: `[ ]` pendiente
- **Scope**: Pacientes + ficha de anamnesis + adjuntos + campos OS mínimos + base de auditoría (US-007, US-017)
  - Modelos: `Paciente` (clinica_id, nombre, DNI, email, teléfono/WhatsApp, obra_social nombre, plan, nro_afiliado, riesgo_ausencia score default 0, consentimiento_datos bool), `Ficha` (paciente_id 1—1, anamnesis, alergias, antecedentes), `Adjunto` (paciente_id/evolucion_id, tipo foto/PDF, storage path), `AuditoriaHC` (actor, acción, entidad_id, diff, timestamp — inmutable, sin endpoint de escritura)
  - Endpoints: `GET/POST /api/pacientes`, `GET/PATCH /api/pacientes/{id}`, `GET/PUT /api/pacientes/{id}/ficha`, `POST /api/pacientes/{id}/adjuntos` (límite tamaño + MIME foto/PDF, RN-CL-05); búsqueda por DNI/teléfono; DNI+email normalizados
  - Sin validación OS en línea en MVP (RN-OS-01); consentimiento_datos exigido antes de cargar datos de salud (Ley 25.326)
  - Migración 004: tablas pacientes + índices `(dni)`, `(telefono)`, `(clinica_id)`
  - Tests: reserva sin cuenta no crea Usuario (solo Paciente), aislamiento por tenant, adjunto no-PDF/imagen rechazado, auditoría registra escritura
- **Dependencias**: C-03
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Paciente + §Ficha (anamnesis) + Evolucion + Odontograma (solo Ficha/Adjuntos) + §Usuario / Rol + AuditoriaHC
  - `knowledge-base/05_reglas_de_negocio.md` §Dominio: Clínica (RN-CL-01, RN-CL-02, RN-CL-05) + §Obras sociales RN-OS-01 + §Cumplimiento RN-CU-01
  - `knowledge-base/06_funcionalidades.md` §Épica 3 US-007 + §Épica 5 US-017
  - `knowledge-base/03_actores_y_roles.md` §RBAC (recepcionista CRUD, odontólogo sus pacientes, sin acceso clínico para recepción salvo contacto/OS)

---

### [C-05] `motor-turnos`
- **Estado**: `[ ]` pendiente
- **Scope**: Motor de turnos con anti-solapamiento duro + máquina de estados + sobreturnos por rol (corazón del DD-04, US-001/US-002, Flujo 1)
  - Modelo `Turno` (clinica_id, profesional_id, sillon_id, paciente_id, prestacion_id, inicio, fin calculado = inicio + duracion prestacion, estado reservado/confirmado/asistido/ausente/cancelado/sobreturno, origen enlace/mostrador/WhatsApp/lista_espera, seña_exigida, seña_pagada, motivo_sobreturno)
  - Anti-solapamiento DURO a nivel DB: exclusion constraints PostgreSQL (rango tstzrange) en `(sillon_id, rango)` y `(profesional_id, rango)` solo turnos activos + chequeo de bloqueos en servicio de dominio; doble-clic concurrente → gana primera escritura, segunda recibe 409 "horario no disponible"
  - Máquina de estados explícita `reservado → confirmado → asistido | ausente | cancelado` con transiciones auditadas (RN-TU-01); sobreturno solo rol autorizado + motivo (RN-AG-04); ausente alimenta score de riesgo (RN-TU-04)
  - Endpoints: `GET /api/agenda/huecos?profesional_id&prestacion_id&desde&hasta` (huecos reales con bloqueos aplicados), CRUD `/api/turnos`, `POST /api/turnos/{id}/transicion`
  - Migración 005: tabla turnos + exclusion constraints + índices `(profesional_id, inicio)`, `(sillon_id, inicio)`, `(paciente_id, inicio)`, `(estado)`
  - Tests: solapamiento sillón y profesional rechazados incluso con requests concurrentes, bloqueo impide reserva, sobreturno sin rol → 403, transición ilegal → 422
- **Dependencias**: C-04, C-08
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Turno + §Sillon/Recurso (constraints) + ERD
  - `knowledge-base/05_reglas_de_negocio.md` §Agenda RN-AG-01–04 + §Turnos RN-TU-01 + RN-TU-04
  - `knowledge-base/07_flujos_principales.md` §Flujo 1 + §Casos de error (concurrencia, pre-bloqueo)
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones (Recurso de agenda + anti-solapamiento, Score de riesgo)

---

### [C-06] `reserva-online-publica`
- **Estado**: `[ ]` pendiente
- **Scope**: Enlace público de reserva sin registro con pre-bloqueo y política de seña (US-003, Flujo 1, RN-AG-05 + RN-CA-01/02)
  - Endpoints públicos (sin auth, con rate limit + captcha/Turnstile): `GET /api/public/disponibilidad?prestacion_id&profesional_id`, `POST /api/public/reservas` (DNI + email/teléfono, crea/encuentra Paciente sin Usuario), `GET /api/public/reservas/{token}` (token único por reserva para ver/cancelar)
  - Pre-bloqueo: crea Turno `reservado` con `hold_expires_at = now() + RESERVA_PREBLOQUEO_MIN` (default 15, SU-04 a validar con piloto); job expira holds sin seña y libera hueco; si `seña_exigida` (riesgo alto o prestación lo exige) → el horario se bloquea recién al confirmar pago (callback de C-12), si no → reserva directa
  - Enlace compartible `/{clinica_slug}/reservar/{token}`; validación DNI/email/tel normalizados en servidor
  - Migración 006: `hold_expires_at`, `public_token` único en turnos
  - Tests: reservar sin cuenta OK, pago no completado libera hueco tras timeout, doble reserva concurrente → 1 gana, sin CUIT no bloquea reserva (factura queda pendiente — RN-AF-02)
- **Dependencias**: C-05
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §Épica 1 US-003
  - `knowledge-base/07_flujos_principales.md` §Flujo 1 completo
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AG-05 + §Caja RN-CA-01/02 + §Facturación RN-AF-02
  - `knowledge-base/03_actores_y_roles.md` §Rutas públicas
  - `knowledge-base/10_preguntas_abiertas.md` §PA-06 + §SU-04 (timeouts a validar)

---

### [C-07] `agenda-frontend`
- **Estado**: `[ ]` pendiente
- **Scope**: Agenda día/semana por profesional y sillón + gestión de mostrador (US-001, US-002 lado UI)
  - Páginas: `/agenda` (vista día y semana, ejes profesional × sillón), drawer de turno (crear/editar/cancelar, sobreturno con motivo si rol), overlay de bloqueos no reservables, badge de estado + origen
  - Consume `GET /api/agenda/huecos` y `/api/turnos`; cálculo de fin solo display (la verdad está en servidor); optimistic-lock con manejo 409 ("horario tomado, estos son alternativos")
  - Filtros por profesional/sillón/estado; deep-link desde WhatsApp-reprogramación (preparado para C-17)
  - Tests frontend: render día/semana con datos mock, 409 muestra alternativas, bloqueo no clickeable
- **Dependencias**: C-05
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §Épica 1 US-001 + US-002
  - `knowledge-base/07_flujos_principales.md` §Flujo 1 + §Flujo 3 (reprogramación vista)
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura frontend (features/agenda, features/reserva)
  - `knowledge-base/05_reglas_de_negocio.md` §Agenda RN-AG-01–04

---

## FASE 3 — Clínica (odontograma, evolución, UI)

### [C-09] `odontograma-evolucion`
- **Estado**: `[ ]` pendiente
- **Scope**: Odontograma FDI + evolución append-only con auditoría inmutable (US-008/US-009, Ley 26.529)
  - Modelos: `Odontograma` (paciente_id, fecha, dentición permanente/temporal/mixta, piezas/caras/estados JSONB versionado básico), `Evolucion` (paciente_id, profesional_id autor obligatorio, fecha_hora, texto, pieza_relacionada nullable — SIN update ni delete; corrección = nueva fila con `corrige_a_id`), `AuditoriaHC` extendida a evoluciones/odontograma
  - Endpoints: `GET/POST /api/pacientes/{id}/odontograma`, `GET /api/pacientes/{id}/odontograma/actual`, `GET/POST /api/pacientes/{id}/evoluciones` (autor = usuario logueado profesional, 403 si no; 422 sin autor); `GET /api/pacientes/{id}/historia` (ficha + odontograma actual + evoluciones ordenadas)
  - Reglas duras: guardar evolución sin autor → 422 (RN-CL-01); edición muda imposible (sin endpoint PUT/DELETE, RN-CL-02); FDI básico MVP (mixta fina y BOP son F2, RN-CL-03)
  - Migración 007: tablas odontograma/evolución + auditoría trigger/función
  - Tests: evolución sin autor rechazada, intento de PUT → 405, historia ordenada, tenant aislado
- **Dependencias**: C-08
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Ficha (anamnesis) + Evolucion + Odontograma
  - `knowledge-base/05_reglas_de_negocio.md` §Clínica RN-CL-01–05
  - `knowledge-base/06_funcionalidades.md` §Épica 3 US-008 + US-009
  - `knowledge-base/07_flujos_principales.md` §Flujo 5
  - `knowledge-base/10_preguntas_abiertas.md` §PA-04 (encuadre legal HC a validar con asesoría)

---

### [C-10] `clinica-frontend`
- **Estado**: `[ ]` pendiente
- **Scope**: UI clínica: ficha + odontograma FDI interactivo + evoluciones (US-007/008/009 lado UI)
  - Páginas: `/pacientes`, `/pacientes/{id}` (tabs Ficha / Odontograma / Evoluciones / Adjuntos / Presupuestos-link), odontograma SVG clickeable por pieza/cara (permanente + temporal, selector de dentición), timeline de evoluciones append-only (sin botón editar, solo "corregir" = nueva), upload de adjuntos
  - La marca por pieza/cara es trazable (guarda quién/cuándo) y enlaza a "generar presupuesto" (prepara C-11)
  - Tests frontend: odontograma render 32+20 piezas, corrección crea entrada nueva, adjunto inválido muestra error
- **Dependencias**: C-09
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §Épica 3 (US-007, US-008, US-009)
  - `knowledge-base/07_flujos_principales.md` §Flujo 5
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura frontend (features/clinica)
  - `knowledge-base/04_modelo_de_datos.md` §Ficha + Odontograma

---

## FASE 4 — Comercial y fiscal (presupuesto, caja MP, ARCA, UI)

### [C-11] `presupuesto-plan`
- **Estado**: `[ ]` pendiente
- **Scope**: Presupuesto por ítems → plan de tratamiento → secuencia de turnos sugerida + seguimiento (US-010, US-013 base, Flujo 6)
  - Modelos: `Presupuesto` (paciente_id, profesional_id, estado borrador/aceptado/rechazado/vencido, total ARS calculado, vencimiento), `PresupuestoItem` (prestación_id, pieza FDI, monto ARS), `PlanTratamiento` (presupuesto_id, secuencia ordenada de turnos sugeridos con prestación/profesional/duración)
  - Endpoints: CRUD `/api/presupuestos`, `POST /api/presupuestos/{id}/aceptar` (genera Plan + turnos sugeridos vía motor C-05 respetando bloqueos/solapamientos), `GET /api/seguimiento/no-convertidos|no-agendados|inactivos` (con monto recuperable visible — alimenta C-14)
  - Presupuesto vencido/rechazado sale del seguimiento activo (métrica no-convertido); cambio de plan = nuevo presupuesto versionado (`version`, `reemplaza_a_id`), turnos tomados se re-imputan
  - Montos SIEMPRE ARS, precio público sin packs (RN-PR-03)
  - Migración 008: tablas presupuesto/plan + índices `(paciente_id, estado)`
  - Tests: aceptado genera N turnos sugeridos sin solaparse, no-agendado aparece en seguimiento con monto, versionado re-imputa
- **Dependencias**: C-09, C-05
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Presupuesto / PlanTratamiento
  - `knowledge-base/05_reglas_de_negocio.md` §Presupuesto RN-PR-01–03 + §Turnos RN-TU-04
  - `knowledge-base/06_funcionalidades.md` §Épica 4 US-010 + US-013
  - `knowledge-base/07_flujos_principales.md` §Flujo 6

---

### [C-12] `caja-mercadopago`
- **Estado**: `[ ]` pendiente
- **Scope**: Caja con seña/saldo por Mercado Pago + webhooks idempotentes + score de riesgo (US-011, Flujo 7 parcial)
  - Modelos: `Cobro` (turno_id/presupuesto_id, tipo seña/saldo, monto ARS, medio MP, estado pendiente/aprobado/rechazado/reembolsado, id_externo_MP único), `CajaMovimiento` (clinica_id, fecha, concepto, monto, usuario), `RiesgoAusencia` (paciente_id, score, causas: ausencias/cancelaciones tardías)
  - Endpoints: `POST /api/cobros/preferencia` (crea preferencia MP imputada a turno/presupuesto), `POST /api/webhooks/mercadopago` (firma `MP_WEBHOOK_SECRET`, idempotencia por `id_externo_MP`), `POST /api/cobros/{id}/anular` (solo rol autorizado + traza, RN-CA-03), `GET /api/caja/resumen?fecha`
  - Seña bloquea horario (callback confirma Turno reservado); seña obligatoria solo si score alto o prestación lo exige (RN-CA-02); política de reembolso ante cancelación según SU-07/PA-06 (documentar supuesto elegido)
  - Migración 009: tablas cobro/caja/riesgo + constraint único `id_externo_MP`
  - Tests: webhook duplicado no duplica cobro, firma inválida → 401, anulación sin rol → 403, score sube tras ausencia
- **Dependencias**: C-05, C-11
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Cobro / Seña + FacturaARCA + Caja
  - `knowledge-base/05_reglas_de_negocio.md` §Caja RN-CA-01–03
  - `knowledge-base/07_flujos_principales.md` §Flujo 1 (pasos 3–5) + §Flujo 7
  - `knowledge-base/10_preguntas_abiertas.md` §PA-06 + §SU-07 (cuenta MP y reembolsos, supuesto Sprint 1)
  - `knowledge-base/02_descripcion_general.md` §Integraciones externas (Mercado Pago)

---

### [C-13] `factura-arca`
- **Estado**: `[ ]` pendiente
- **Scope**: Factura electrónica ARCA B/C con CAE + QR emitida desde el cobro, con cola de reintentos (US-012, DD-01)
  - Modelo `FacturaARCA` (cobro_id 1—1, tipo B/C según régimen del piloto, CAE, QR payload, estado emitida/pendiente/error, intentos, ultimo_error)
  - Servicio `infrastructure/fiscal/arca_client` (WSFE homologación primero): `emitir_desde_cobro(cobro_id)`; sin CUIT configurado → 422 y factura `pendiente` (RN-AF-02); ante caída ARCA → `pendiente` + job con backoff y estado visible (PA-07 a validar)
  - Endpoints: `POST /api/cobros/{id}/facturar`, `GET /api/facturas`, `GET /api/facturas/{id}/pdf` (comprobante con QR)
  - Job `jobs/reintentos_arca.py` + bandeja visible de pendientes/errores
  - Migración 010: tabla facturas + índice `(estado)`
  - Tests: sin CUIT → 422, cobro emite 1 factura (idempotente), caída ARCA simulada → pendiente + reintento OK
- **Dependencias**: C-12
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Cobro / Seña + FacturaARCA + Caja
  - `knowledge-base/05_reglas_de_negocio.md` §Facturación RN-AF-01/02
  - `knowledge-base/06_funcionalidades.md` §Épica 4 US-012
  - `knowledge-base/07_flujos_principales.md` §Flujo 7 + §Casos de error (caída ARCA)
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-01 + §PA-07 (CUIT/régimen del piloto)

---

### [C-14] `comercial-frontend`
- **Estado**: `[ ]` pendiente
- **Scope**: UI comercial: presupuesto → plan → turnos, caja, facturas y tableros de recupero (US-010/011/012/013 lado UI)
  - Páginas: `/presupuestos` (editor por ítems prestación+pieza+monto, total ARS vivo, aceptar → muestra turnos sugeridos), `/caja` (cobrar seña/saldo MP, anular con rol, resumen diario + arqueo), `/facturas` (lista, estado CAE, PDF con QR, cola de pendientes), `/seguimiento` (no convertidos / no agendados / inactivos / ausentes con monto y botón recall)
  - Comprobantes compartibles por link público (prepara firma de links con expiración)
  - Tests frontend: total recalcula al editar ítem, factura pendiente muestra reintentar, tablero muestra montos
- **Dependencias**: C-11, C-12, C-13
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §Épica 4 (US-010–013)
  - `knowledge-base/07_flujos_principales.md` §Flujo 6 + §Flujo 7
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura frontend (features/presupuesto, features/caja)
  - `knowledge-base/05_reglas_de_negocio.md` §Presupuesto + §Caja + §Facturación

---

## FASE 5 — Comunicación WhatsApp (oficial, bidireccional)

> Solo API oficial Meta (DD-02, RN-WA-01). QR prohibido. Costo ARS transparente (RN-WA-02). Supuestos BSP/plantillas en PA-05/SU-07.

### [C-15] `whatsapp-bidireccional`
- **Estado**: `[ ]` pendiente
- **Scope**: Recordatorio/confirmación/cancelación bidireccional por WhatsApp oficial + costos + bandeja de fallos (US-005, Flujo 2)
  - Modelos: `MensajeWhatsApp` (turno_id, plantilla, dirección entrante/saliente, estado enviado/entregado/leído/error, costo ARS), `PlantillaWA` (nombre, idioma es_AR, variables, estado aprobada)
  - Servicio `infrastructure/whatsapp/meta_client` (env `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_ID`): envío de plantillas (recordatorio 24 h — ventana SU-04 a confirmar, confirmación, cancelación); `POST /api/webhooks/whatsapp` (verificación `WHATSAPP_WEBHOOK_VERIFY`, idempotencia `turno_id + mensaje_id`, interpreta Confirmar/Cancelar/Reprogramar → actualiza Turno + registra costo)
  - Job `jobs/recordatorios.py` (cron 24 h antes, reintentos con backoff); respuestas actualizan agenda de verdad (RN-TU-03); fallo (bloqueado/plantilla rechazada) → bandeja de fallos para recepcionista + endpoint `GET /api/whatsapp/fallos`, `GET /api/whatsapp/costos?desde&hasta`
  - Seed: 5 plantillas (recordatorio 24 h, confirmación, cancelación, reprogramación, oferta de hueco)
  - Migración 011: tablas mensajes/plantillas + índice `(turno_id, estado)`
  - Tests: respuesta "SI" confirma turno, duplicado de webhook no duplica transición, costo registrado en ARS
- **Dependencias**: C-05
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §MensajeWhatsApp + ListaEspera + §Seed (plantillas)
  - `knowledge-base/05_reglas_de_negocio.md` §WhatsApp RN-WA-01–03 + §Turnos RN-TU-02/03
  - `knowledge-base/06_funcionalidades.md` §Épica 2 US-005
  - `knowledge-base/07_flujos_principales.md` §Flujo 2 completo
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-02 + §SU-07/PA-05 (BSP y costos)

---

### [C-16] `lista-espera-relleno`
- **Estado**: `[ ]` pendiente
- **Scope**: Lista de espera con oferta automática del hueco liberado y reasignación en un tap (US-004 DIF candidato a IMP, Flujo 4)
  - Modelo `ListaEspera` (clinica_id, prestacion_id, profesional_id/sillon_id preferidos, paciente_id, prioridad, oferta_enviada_a, oferta_expira_at, estado en_cola/ofertado/aceptado/expirado/salido)
  - Servicio: ante cancelación/ausencia/reprogramación (evento de dominio desde C-05) → busca cola por (prestación/profesional/sillón) en prioridad → envía oferta por WA (C-15) "Jue 16:30 con Dra. X, ¿lo tomás? [Sí/No]" → Sí con un tap reasigna Turno (transfiere/exige seña según política) → si expira (timeout SU-04 a definir) ofrece al siguiente; nadie acepta → hueco libre + métrica hora-perdida
  - Endpoints: CRUD `/api/lista-espera`, `POST /api/lista-espera/{id}/ofertar`, bandeja recepcionista `GET /api/lista-espera/bandeja`
  - Idempotencia: doble aceptación simultánea → una sola reasignación efectiva (lock por turno)
  - Migración 012: tabla lista_espera + índice `(prestacion_id, estado, prioridad)`
  - Tests: cancelación dispara oferta al primero, aceptar reasigna, expirar pasa al siguiente, doble aceptar → 1 efectivo
- **Dependencias**: C-05, C-15
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §MensajeWhatsApp + ListaEspera
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AG-06 + §RN-TU-04
  - `knowledge-base/06_funcionalidades.md` §Épica 1 US-004
  - `knowledge-base/07_flujos_principales.md` §Flujo 4 completo
  - `knowledge-base/01_vision_y_objetivos.md` §Métricas de éxito (ocupación, huecos recuperados)

---

### [C-17] `chatbot-reprogramacion`
- **Estado**: `[ ]` pendiente
- **Scope**: Reprogramación autoguiada por WhatsApp + enlace con las mismas reglas de agenda (US-006, Flujo 3)
  - Flujo conversacional con estado en servidor (máquina: menu → ver_opciones → elegir → confirmar): muestra hasta 3 huecos reales (motor C-05: duración, bloqueos, solapamientos, sillón+profesional), mueve el Turno conservando seña imputada (recobra solo diferencia si cambia prestación), confirma por WA y actualiza agenda
  - Mismo flujo servido por enlace web (`/reprogramar/{token}` reutiliza token de C-06) para quien prefiere web
  - Concurrencia: hueco ocupado entre consulta y confirmación → ofrece alternativas (mismo 409 de C-05); cambio de duración recalcula fin (RN-AG-02)
  - Tests: reprogramar por WA mueve turno y mantiene seña, hueco tomado en el medio → alternativas, reintento duplicado idempotente
- **Dependencias**: C-05, C-15
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §Épica 2 US-006
  - `knowledge-base/07_flujos_principales.md` §Flujo 3 completo
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-03 + §RN-AG-01/02
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones (Webhooks + idempotencia)

---

## FASE 6 — Cumplimiento y cierre

### [C-18] `consentimientos-cumplimiento`
- **Estado**: `[ ]` pendiente
- **Scope**: Consentimientos con firma electrónica + páginas legales + respaldo/exportación (US-014/015/016, Leyes 25.326/25.506/26.529)
- Modelo `Consentimiento` (paciente_id, tipo, texto versionado, firma: fecha/IP/dispositivo/hash, documento_bloqueado bool, pdf_path); endpoint `POST /api/pacientes/{id}/consentimientos/{cid}/firmar` (registra constancia, bloquea documento — sin endpoint de edición post-firma, RN-CU-02); firma incompleta → 422 reintentable (Flujo 8)
  - Admin: `GET/POST /api/admin/usuarios`, `PATCH /api/admin/usuarios/{id}/roles` (RBAC de C-03 aplicado), `GET /api/admin/exportacion?formato=csv|pdf` (respaldo completo sin costo, RN-CU-04)
  - Páginas públicas: `/cumplimiento` + `/privacidad` (textos base de seed legal de `04`, a adaptar con asesoría — PA-04/SU-08)
  - Migración 013: tabla consentimientos + índice `(paciente_id, tipo)`
  - Tests: firmado no editable, firma incompleta → 422, exportación incluye HC/agenda/caja del tenant y nada de otros
- **Dependencias**: C-03, C-09
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Consentimiento + §Seed (textos legales)
  - `knowledge-base/05_reglas_de_negocio.md` §Cumplimiento RN-CU-01/02/04/05
  - `knowledge-base/06_funcionalidades.md` §Épica 5 (US-014, US-015, US-016)
  - `knowledge-base/07_flujos_principales.md` §Flujo 8
  - `knowledge-base/10_preguntas_abiertas.md` §PA-04 + §SU-08 (asesoría legal Sprint 1)

---

### [C-19] `recetas-partner-renapdis`
- **Estado**: `[ ]` pendiente
- **Scope**: Receta electrónica y órdenes de estudios vía partner registrado ReNaPDiS (DD-06, Flujo 9 anticipado — prescripción obligatoria desde 1/1/2025)
  - Servicio `infrastructure/recetas/partner_client` con adapter intercambiable (Farmalink / Innovamed / otro — elección en PA-08/SU-08): `emitir_receta(evolucion_id, fármacos, firma profesional)`, `emitir_orden_estudio(...)`, guarda `receta_id_externo` + PDF del partner; sin partner configurado → endpoint responde 501 con mensaje de configuración (no bloquea el resto)
  - Modelo `RecetaExterna` (paciente_id, evolucion_id, partner, id_externo, tipo receta/orden, estado, pdf_path)
  - Endpoints: `POST /api/pacientes/{id}/recetas`, `GET /api/pacientes/{id}/recetas` (lista con links a PDF del partner)
  - Credencial `RECETAS_PARTNER_KEY` solo en vault/env; ningún secreto en repo
  - Migración 014: tabla recetas_externas
  - Tests: sin partner → 501 claro, con mock de partner → receta vinculada a evolución, credencial ausente no tumba boot
- **Dependencias**: C-08, C-09
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/02_descripcion_general.md` §Integraciones externas (ReNaPDiS / partner)
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CU-03
  - `knowledge-base/07_flujos_principales.md` §Flujo 9 (diseño anticipado)
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-06 + §SU-08/PA-08
  - `knowledge-base/08_arquitectura_propuesta.md` §Variables de entorno (`RECETAS_PARTNER_KEY`)

---
