# Turnos Odontología (SaaS multi-tenant AR) — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` (11 archivos) y `CHANGES.md` (19 changes) el 2026-10-08 (skill `agents-md-generator`, modo WRITE, reglas confirmadas interactivamente por el usuario). No editar a mano sin re-sincronizar ambos archivos (`diff AGENTS.md CLAUDE.md` debe quedar vacío).

---

## Stack Tecnológico

Fuente: `knowledge-base/02_descripcion_general.md` §Stack DECIDIDO + `knowledge-base/09_decisiones_y_supuestos.md` §DD-08 (ronda usuario 1, 2026-10-07: PA-01/PA-02 resueltas).

| Capa | Tecnología | Versión mínima |
|------|------------|----------------|
| Frontend | React + Vite + TypeScript | — |
| Backend | Python + FastAPI | — |
| Base de datos | PostgreSQL | 16 (tests: `postgres:16-alpine` vía testcontainers) |
| Migraciones | Alembic (up/down) | — |
| Mensajería | WhatsApp vía QR con número dedicado (DECISIÓN USUARIO 2026-10-08 — ver nota) | — |
| Cobros | Mercado Pago (seña y saldo) | — |
| Facturación | ARCA factura electrónica B/C con CAE y QR, emitida desde el cobro | — |
| Receta electrónica | Vía partner registrado en ReNaPDiS (Res. 1959/2024); propia es F2 | — |
| Despliegue | SaaS web multi-tenant en la nube, un tenant por clínica con datos aislados (DD-09, SU-01) | — |

> **Nota decisión QR 2026-10-08 (prevalece sobre KB/CHANGES hasta actualizarlos):** el usuario abandona la API oficial Meta (DD-02 / RN-WA-01) por considerarla no confiable. WhatsApp se implementa por **QR con número dedicado**: asumir riesgo de bloqueo Meta/ToS, documentar sesión QR, reconexión y backup. Deja sin efecto el "QR prohibido" en C-15/C-17 y en `02 §Integraciones externas` hasta que el orquestador lo documente en fase 5 (KB + CHANGES). Ver regla dura 17.

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---------|---------------|
| [README.md](knowledge-base/README.md) | Índice + resumen ejecutivo + quick start |
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Propósito, alcance MVP v1.0, fuera de alcance F2, métricas |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack DECIDIDO, arquitectura SaaS + integraciones |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | 4 roles, matriz RBAC, rutas públicas |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | 6 dominios, ERD, 12 entidades, seed data |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | 30 reglas RN-AG/TU/WA/CL/PR/CA/AF/OS/CU/GL |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | 17 US en 5 épicas + 6 US-F2 |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | 9 flujos E2E |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | 8 patrones, estructura FastAPI + React/Vite, 12 env vars |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | 9 decisiones DD-01…DD-09 + supuestos SU/PA |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | 16 inconsistencias IN + 12 preguntas PA (⚠️ ver abajo) |

**Quick start para desarrolladores** (desde `knowledge-base/README.md`):

1. Entender el dominio → `01`, `03`
2. Entender los datos → `04`
3. Entender las reglas → `05`
4. Entender la arquitectura → `02`, `08`
5. Implementar → `07`, `06`
6. Antes de codificar → `10`

> ⚠️ Resolver las preguntas de prioridad **Alta** de `10_preguntas_abiertas.md` antes de arrancar el primer change.

---

## Skills Disponibles

Fuente de verdad: `.atl/skill-registry.md` (generado por `skill-registry`; no versionado). Solo las 13 in-scope para este roadmap (backend PG/FastAPI, auth, frontend React/Vite, testing, docs). El resto va on-demand.

| Agente | Rol | Skills que carga |
|--------|-----|------------------|
| **Backend Core** | PG schema/migraciones/RLS, tablas, tipos, constraints, índices (C-02, C-04, C-05, C-08, C-09, C-11) | `supabase-postgres-best-practices`, `postgresql-table-design`, `postgresql-optimization` |
| **Backend Aux** | Auth JWT/RBAC, tests PG con Docker, docs vigentes de APIs (C-03, C-12, C-13, C-15–C-19) | `auth-implementation-patterns`, `docker-testcontainers`, `context7-mcp` |
| **Clínico / Dominio** | Historia clínica append-only + auditoría inmutable (C-09, C-18) | `event-store-design` |
| **Frontend** | React/Vite/TS/Tailwind, componentes, unit tests, guidelines UX (C-01, C-07, C-10, C-14) | `typescript-dev`, `vercel-react-best-practices`, `vitest`, `web-design-guidelines` |
| **QA / E2E** | Verificación en browser local (screenshots, logs, flujos 409/422) | `webapp-testing` |
| **Transversal** | Cualquier bug/fallo antes de proponer fixes | `systematic-debugging` |

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; no versionado — no está en el repo). Esta tabla solo mapea skill→rol.

> **Nota find-skill 2026-10-08 (confirmado por usuario):** 13 adoptar (las de arriba); resto no/on-demand — Spring/Java fuera de scope (stack es FastAPI), animación/pick-ui/prototype/SEO/Redis/Swift solo on-demand. Gaps de integración sin skill confiable (WhatsApp, Mercado Pago, ARCA, ReNaPDiS partner, FastAPI backend) → `context7-mcp` + docs oficiales (ver "Integration Gaps" del registry).

Cargá la skill correspondiente al contexto ANTES de escribir código (ver matriz Change → Skills del registry).

---

## Roadmap de Changes

El plan de implementación completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 19 changes en 7 fases (FASE 0 cimientos → FASE 6 cumplimiento y cierre).
- **Camino crítico** (9 changes — mínimo irreducible): `C-01 → C-02 → C-03 → C-04 → C-05 → C-11 → C-12 → C-13 → C-14`.
- **Primer change**: `C-01 foundation-setup` (scaffolding monorepo + infra base, sin dependencias, governance BAJO).
- **Joins clave**: C-11 exige C-05 + C-09 (turnos + odontograma); C-08 corre en paralelo a C-04 y C-09 en paralelo a C-05.
- **Gates/paralelismo**: ver "Paralelismo por fase" (GATE 0…8) y "Plan óptimo con 3 agentes" en CHANGES.md.

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá las dependencias del change y los archivos de "Leer antes" de su ficha.

---

## Reglas Duras

> Reglas globales ya definidas en `~/.claude/CLAUDE.md` (orquestador, governance, TDD, engram): el proyecto las hereda. Acá viven solo las reglas **específicas de este proyecto** + las universales que el global no cubra. Son contrato; romperlas es un defecto. Formato `NUNCA X → hacer Y`.

1. NUNCA commitear/pushear sin pedido explícito → solo working tree + git status/diff para revisión.
2. NUNCA buildear/testear pesado sin pedido en fase propose → en propose solo artefactos; build/test en apply.
3. NUNCA commit sin conventional-commits y sin co-autoría IA → feat/fix/chore(scope): mensaje sin Co-Authored-By IA.
4. NUNCA schema Pydantic sin extra='forbid' → rechazar campos no declarados con 422.
5. NUNCA código Python sin snake_case + type hints + ruff limpio → ruff + pytest smoke antes de dar por hecho el change.
6. NUNCA calcular duraciones/fin de turno en cliente → fin = inicio + duracion_prestacion solo en servidor + validación de solapamiento en dominio.
7. NUNCA montos en float/money → SIEMPRE NUMERIC en ARS; tiempo SIEMPRE TIMESTAMPTZ (RN-PR-03).
8. NUNCA anti-solapamiento solo en app → exclusion constraints GiST (sillon_id/profesional_id, tstzrange) + chequeo de bloqueos; doble-clic concurrente → 409.
9. NUNCA test PG con SQLite → integración PG solo con testcontainers-postgres:16-alpine + migraciones Alembic up/down.
10. NUNCA tabla tenant-scoped sin clinica_id + índice (clinica_id, ...) + test aislamiento (query cruzada = 0 filas).
11. NUNCA any ni componentes fuera de PascalCase → tsc estricto + build Vite limpios.
12. NUNCA secreto en browser → solo VITE_-prefixed para base URL/tenant header vía import.meta.env; tokens/keys solo en vault/env backend.
13. NUNCA fetch secuencial de datos independientes de agenda → Promise.all(huecos+turnos+bloqueos) + 409 → mostrar alternativas.
14. NUNCA datos reales de pacientes en repo, seeds, tests ni ejemplos → solo datos sintéticos/marcados seed=true borrables. (Ley 25.326 + secreto profesional)
15. NUNCA historia clínica mutable → Evolución append-only sin PUT/DELETE (corrección = nueva fila corrige_a_id); sin autor profesional → 422; consentimiento firmado = documento bloqueado. (Ley 26.529)
16. NUNCA cargar datos de salud sin consentimiento_datos=true + respetar RBAC clínico (recepción sin acceso clínico salvo contacto/OS) → 403 si no.
17. NUNCA receta fuera de ReNaPDiS → solo vía partner registrado (RN-CU-03); factura ARCA solo desde cobro con CUIT configurado (RN-AF-01/02); WhatsApp por QR con número dedicado (DECISIÓN USUARIO 2026-10-08: se abandona API oficial DD-02/RN-WA-01 por considerarla no confiable — asumir riesgo de bloqueo Meta/ToS, documentar sesión QR, reconexión y backup; deja sin efecto "QR prohibido" en C-15/C-17 hasta actualizar KB/CHANGES).

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias y "Leer antes"
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks (solo artefactos, sin build/test pesado)
4. Implementar las tasks (cargando skills + TDD) → respetando las reglas duras
5. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change
```

Aplicar TODAS las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen.
