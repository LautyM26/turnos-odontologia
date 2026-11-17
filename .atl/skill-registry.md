# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

Project: **Turnos Odontología (SaaS multi-tenant AR)** — Stack: Python + FastAPI + PostgreSQL + React/Vite (DD-08). Roadmap: CHANGES.md (C-01…C-19). Domain KB: knowledge-base/ (11 files). Project skills: `.claude/skills/` (versioned; mirrored to `.github/skills/` and `.opencode/skills/`). MCP integrations: `.mcp.json` (see "MCP Integrations" below; not skills).

> Scoping note: the User Skills table catalogs ALL installed skills (one line each). Compact Rules blocks are provided only for skills in scope for this roadmap (backend PG/FastAPI, auth, React/Vite frontend, testing, docs). Out-of-scope skills are marked `—` and resolved on demand.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Postgres schema/migration/RLS/perf work; ANY change touching PG (C-01…C-19 backend) | supabase-postgres-best-practices | C:\Users\Lautaro\.agents\skills\supabase-postgres-best-practices\SKILL.md |
| Designing/reviewing PG tables, types, constraints, indexes (C-02, C-04, C-05, C-08, C-09, C-11) | postgresql-table-design | C:\Users\Lautaro\.agents\skills\postgresql-table-design\SKILL.md |
| PG-specific features: JSONB, ranges, exclusion constraints, EXPLAIN, pagination (C-05, C-08, C-09) | postgresql-optimization | C:\Users\Lautaro\.agents\skills\postgresql-optimization\SKILL.md |
| Implementing auth, JWT, RBAC, securing APIs (C-03, C-18 admin) | auth-implementation-patterns | C:\Users\Lautaro\.agents\skills\auth-implementation-patterns\SKILL.md |
| React/Vite/TS/Tailwind/Biome/Vitest setup and patterns (C-01, C-07, C-10, C-14) | typescript-dev | C:\Users\Lautaro\.agents\skills\typescript-dev\SKILL.md |
| Writing/reviewing/refactoring React components for performance (C-07, C-10, C-14) | vercel-react-best-practices | C:\Users\Lautaro\.agents\skills\vercel-react-best-practices\SKILL.md |
| Writing frontend unit tests, mocking, coverage (C-07, C-10, C-14) | vitest | C:\Users\Lautaro\.agents\skills\vitest\SKILL.md |
| Verifying a running web app via browser (Playwright): screenshots, logs, UI behavior | webapp-testing | C:\Users\Lautaro\.agents\skills\webapp-testing\SKILL.md |
| PG integration tests with real Docker DBs, pytest + testcontainers (C-02, C-05) | docker-testcontainers | C:\Users\Lautaro\.agents\skills\docker-testcontainers\SKILL.md |
| Any bug, test failure, or unexpected behavior — before proposing fixes | systematic-debugging | C:\Users\Lautaro\.agents\skills\systematic-debugging\SKILL.md |
| Need current docs for FastAPI, SQLAlchemy, WhatsApp QR client (DD-10), Mercado Pago SDK, ARCA/WSFE (tools from the Context7 MCP server) | context7-mcp | C:\Users\Lautaro\.agents\skills\context7-mcp\SKILL.md |
| Reviewing/auditing UI code for guidelines/accessibility/UX compliance | web-design-guidelines | C:\Users\Lautaro\.agents\skills\web-design-guidelines\SKILL.md |
| Append-only clinical history / immutable audit log design (C-09, C-18) | event-store-design | C:\Users\Lautaro\.agents\skills\event-store-design\SKILL.md |
| — (out of scope: Java/Spring stack — this project is FastAPI) | 302-frameworks-spring-boot-rest | C:\Users\Lautaro\.agents\skills\302-frameworks-spring-boot-rest\SKILL.md |
| — (out of scope: Java/Spring) | java-springboot | C:\Users\Lautaro\.agents\skills\java-springboot\SKILL.md |
| — (out of scope: Java/Spring) | spring-boot-crud-patterns | C:\Users\Lautaro\.agents\skills\spring-boot-crud-patterns\SKILL.md |
| — (out of scope: Java/Spring) | spring-boot-event-driven-patterns | C:\Users\Lautaro\.agents\skills\spring-boot-event-driven-patterns\SKILL.md |
| — (out of scope: Java/Spring) | spring-boot-rest-api-standards | C:\Users\Lautaro\.agents\skills\spring-boot-rest-api-standards\SKILL.md |
| — (out of scope: Java/Spring) | spring-boot-security-jwt | C:\Users\Lautaro\.agents\skills\spring-boot-security-jwt\SKILL.md |
| — (out of scope: Java/Spring) | springboot-patterns | C:\Users\Lautaro\.agents\skills\springboot-patterns\SKILL.md |
| — (out of scope: Java/Spring) | springboot-security | C:\Users\Lautaro\.agents\skills\springboot-security\SKILL.md |
| — (out of scope: Java/Spring) | springboot-tdd | C:\Users\Lautaro\.agents\skills\springboot-tdd\SKILL.md |
| — (on demand: animation work only) | animate | C:\Users\Lautaro\.agents\skills\animate\SKILL.md |
| — (on demand: RN/Expo only) | animate-expo | C:\Users\Lautaro\.agents\skills\animate-expo\SKILL.md |
| — (on demand) | animation-vocabulary | C:\Users\Lautaro\.agents\skills\animation-vocabulary\SKILL.md |
| — (on demand) | apple-design | C:\Users\Lautaro\.agents\skills\apple-design\SKILL.md |
| — (on demand: toast library) | ask-sonner | C:\Users\Lautaro\.agents\skills\ask-sonner\SKILL.md |
| — (on demand: stress-test UI with worst-case data) | break-ui | C:\Users\Lautaro\.agents\skills\break-ui\SKILL.md |
| — (on demand: persistent memory) | claudemem | C:\Users\Lautaro\.agents\skills\claudemem\SKILL.md |
| — (on demand: landing/marketing UI) | design-taste-frontend | C:\Users\Lautaro\.agents\skills\design-taste-frontend\SKILL.md |
| — (on demand: UI polish review) | emil-design-eng | C:\Users\Lautaro\.agents\skills\emil-design-eng\SKILL.md |
| — (on demand: find animation candidates, read-only) | find-animation-opportunities | C:\Users\Lautaro\.agents\skills\find-animation-opportunities\SKILL.md |
| — (meta: skill discovery) | find-skills | C:\Users\Lautaro\.agents\skills\find-skills\SKILL.md |
| — (on demand: generative UI direction) | frontend-design | C:\Users\Lautaro\.agents\skills\frontend-design\SKILL.md |
| — (on demand: knowledge graphs) | graphify | C:\Users\Lautaro\.agents\skills\graphify\SKILL.md |
| — (on demand: plan interviews) | grill-me | C:\Users\Lautaro\.agents\skills\grill-me\SKILL.md |
| — (on demand: full UI critique/polish) | impeccable | C:\Users\Lautaro\.agents\skills\impeccable\SKILL.md |
| — (on demand: motion audit, read-only) | improve-animations | C:\Users\Lautaro\.agents\skills\improve-animations\SKILL.md |
| — (on demand: mobile-web feel) | mobile-native | C:\Users\Lautaro\.agents\skills\mobile-native\SKILL.md |
| — (on demand: choose a frontend library) | pick-ui-library | C:\Users\Lautaro\.agents\skills\pick-ui-library\SKILL.md |
| — (on demand: minimal/YAGNI pressure) | ponytail | C:\Users\Lautaro\.agents\skills\ponytail\SKILL.md |
| — (on demand: prompt engineering) | prompt-master | C:\Users\Lautaro\.agents\skills\prompt-master\SKILL.md |
| — (on demand: multi-variant UI picker) | prototype | C:\Users\Lautaro\.agents\skills\prototype\SKILL.md |
| — (on demand: motion code review) | review-animations | C:\Users\Lautaro\.agents\skills\review-animations\SKILL.md |
| — (on demand: SEO) | seo-audit | C:\Users\Lautaro\.agents\skills\seo-audit\SKILL.md |
| — (on demand: Redis/serverless KV — not in stack) | upstash-redis-js | C:\Users\Lautaro\.agents\skills\upstash-redis-js\SKILL.md |
| — (on demand: dense data-UI palettes) | ui-ux-pro-max | C:\Users\Lautaro\.agents\skills\ui-ux-pro-max\SKILL.md |
| — (on demand: Swift — not in stack) | write-swift | C:\Users\Lautaro\.agents\skills\write-swift\SKILL.md |

## Project Skills (versioned in this repo)

| Trigger | Skill | Purpose | Path |
|---------|-------|---------|------|
| "Creá la skill del dominio X"; before `/opsx:propose` of a change whose area has no `dominio-*` skill; after an RN/DD of an area changes | crear-skill-de-dominio | Generates `dominio-<área>` from KB 05 (RN) filtered by current DDs (09) + hard rules (AGENTS.md), with RN → spec → test traceability matrix | `.claude/skills/crear-skill-de-dominio/SKILL.md` (+ `templates/dominio-template.md`) |
| Turnos, huecos, solapamientos, bloqueos, sobreturnos, estados del turno, reserva online, agenda UI | dominio-agenda | Current RN-AG + RN-TU rules, hard rules 6/7/8/9/10/13, traceability (4 covered · 3 partial · 3 pending) | `.claude/skills/dominio-agenda/SKILL.md` |
| Cobros, seña, saldo, anulaciones, Mercado Pago, score de riesgo | dominio-caja | Current RN-CA rules, hard rules 4/7/10/12/17, open assumptions PA-06/SU-07 | `.claude/skills/dominio-caja/SKILL.md` |
| Historia clínica, ficha, odontograma FDI, evoluciones, correcciones, AuditoriaHC, adjuntos clínicos, RBAC clínico, recall | dominio-clinica | Current RN-CL rules, hard rules 4/7/9/10/14/15/16, open assumption PA-04/SU-08, traceability (1 covered · 1 partial · 3 pending) | `.claude/skills/dominio-clinica/SKILL.md` |
| Consentimientos firmados, constancia/hash, privacidad, página de cumplimiento, exportación/respaldo, usuarios y roles, receta electrónica vía partner ReNaPDiS | dominio-cumplimiento | Current RN-CU rules, hard rules 4/7/9/10/12/14/15/16/17, open assumptions PA-04/PA-08/SU-08, traceability (0 covered · 2 partial · 3 pending) | `.claude/skills/dominio-cumplimiento/SKILL.md` |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### supabase-postgres-best-practices
- Load BEFORE any PG schema/migration/query change, even one-column changes — not just perf work.
- Security & RLS is CRITICAL priority: every tenant-scoped table must have RLS policies + tests proving cross-tenant queries return 0 rows (maps to C-02 isolation tests).
- Prefer partial indexes for hot subsets (e.g. `WHERE estado='activo'`), covering indexes (`INCLUDE`) for index-only scans, expression indexes (`LOWER(email)`) with matching query expressions.
- Connection management is CRITICAL: use pooling (pgbouncer / pooler) for high-concurrency paths (public reserva C-06, webhooks C-12/C-15).
- Diagnose slow queries with `EXPLAIN (ANALYZE, BUFFERS)`; check `pg_stat_statements` for top-time queries; watch lock contention on C-05 turnos writes.
- Read `references/query-*.md` / `security-*.md` rule files inside the skill when the category applies.

### postgresql-table-design
- PKs: `BIGINT GENERATED ALWAYS AS IDENTITY`; UUID only for opaque/global IDs (public tokens like reserva `public_token` → UUID/opaque random, never sequential).
- Money ALWAYS `NUMERIC`, never float/money type (ARS montos C-11/C-12); time ALWAYS `TIMESTAMPTZ`; strings `TEXT` (+ `CHECK(length)`); evolving business states → `TEXT + CHECK`, not ENUM.
- Normalize to 3NF first; denormalize only for measured read pain. `NOT NULL` everywhere semantically required.
- PG does NOT auto-index FK columns — create indexes manually on every FK + `(clinica_id, ...)` composite prefixes per CHANGES.md.
- `UNIQUE` allows multiple NULLs — use `NULLS NOT DISTINCT` (PG15+) where a single NULL must be unique.
- Anti-solapamiento C-05: `EXCLUDE USING gist (sillon_id WITH =, rango WITH &&)` / `(profesional_id WITH =, rango WITH &&)` on `tstzrange`, active-states-only via partial predicate; needs GiST-capable range type.
- JSONB (odontograma piezas C-09) over JSON, with GIN index; identifiers `snake_case` unquoted; `now()` = txn start, `clock_timestamp()` = wall clock.

### postgresql-optimization
- Odontograma JSONB (C-09): GIN index + containment operators (`@>`, `?`); never `data::text LIKE`.
- Turnos overlap checks (C-05): range operator `&&` on `tstzrange`; GiST index on range columns; exclusion constraint is the hard guard, app check is best-effort.
- Pagination: cursor-based (`WHERE id > $last ORDER BY id LIMIT n`), never large `OFFSET` (admin lists, seguimiento C-11/C-14).
- Seguimiento/aggregation queries (C-11/C-14 tableros): partial indexes per estado + `EXPLAIN ANALYZE` before shipping.
- DNI/teléfono search (C-08): `pg_trgm` trigram indexes for fuzzy match; `unaccent` for Spanish names.
- Always parameterized queries; enable RLS where tenant isolation required; monitor unused indexes via `pg_stat_user_indexes`.

### auth-implementation-patterns
- Access tokens short-lived (15 min per C-03); refresh rotation with blacklist (`jti`); refresh in HttpOnly cookie (`secure`, `samesite=lax`) — never JWT in localStorage.
- Hash passwords with bcrypt/argon2; rate-limit auth endpoints (5/60s per IP+email per C-03); log security events (logins, failures).
- Enforce AuthZ server-side on every route: `require_role()` / `require_admin()` / `require_own_agenda()` per KB matriz RBAC; client-side checks are display-only.
- JWT claims: `sub`, `tenant_id`, `roles`, `email`, `jti`, `type`, `iat`, `exp` — `tenant_id` drives ALL query scoping.
- Declare public routes explicitly (reserva link, Meta/MP webhooks, comprobantes, cumplimiento); everything else behind login.
- Validate all input (email format, password strength); rotate secrets; MFA when possible.

### typescript-dev
- Stack pins: Vite 8 (Rolldown default), React 19.2 + Compiler 1.0, TS 6.0 strict, Tailwind v4 CSS-first, Biome (`biome check` / `biome ci` single command), Vitest 4.
- No `useMemo`/`useCallback`/`memo` — React Compiler memoizes; no `forwardRef` — `ref` is a regular prop.
- Tailwind v4: NO `tailwind.config.js` — config lives in CSS (`@theme`); style with semantic tokens (`bg-primary`), never raw palette or dynamic `bg-${x}` classnames.
- TS 6.0: `strict` on by default; `types: []` default (add `["node"]` if needed); `module: preserve` + `moduleResolution: bundler` for Vite apps; `@/*` paths, no `baseUrl`.
- Vite plugin order: framework/router plugin first, `react()` last; secrets never reach browser — only `VITE_`-prefixed env via `import.meta.env` (tenant header + API base URL OK, tokens/secrets NEVER).
- Backend is FastAPI (not Hono) — ignore Hono RPC sections; frontend talks to FastAPI via typed HTTP client with tenant header (per C-01).
- Tests run through `vite.config.ts` (aliases shared); `vitest run` in CI.

### vercel-react-best-practices
- Fetch in parallel (`Promise.all`) — never sequential awaits for independent data (agenda huecos + turnos + bloqueos on `/agenda`).
- Import directly, avoid barrel files; lazy-load heavy components (odontograma SVG editor, PDF viewer) with dynamic imports.
- Never define components inside components; derive state during render, not in effects; `startTransition`/`useDeferredValue` for non-urgent renders (agenda week view, seguimiento tableros).
- Subscribe to derived booleans/primitives, not raw objects, in effect deps; functional `setState` for stable callbacks.
- `content-visibility` for long lists (pacientes, facturas); hoist static JSX; ternary over `&&` for conditionals.
- Server-side rules (RSC cache/serialization) do NOT apply — this is a Vite SPA; apply only client/bundle/render/js rules.

### vitest
- Vite-native runner: shares `vite.config.ts` (aliases, plugins) — no separate transform config.
- `vi.mock()` for modules, `vi.spyOn()` for methods, fake timers for timeout logic (reserva hold expiry SU-04, lista-espera offer expiry).
- jsdom/happy-dom for component tests (agenda render, odontograma 32+20 piezas, total recalculation); `vitest run` in CI per C-01.
- Coverage via V8 provider; filter by name/file patterns for focused runs; test.extend fixtures for tenant-aware API mocks.

### webapp-testing
- Use Playwright against the LOCAL running app (frontend `vite dev` + backend API) to verify behavior end-to-end.
- Capture screenshots for agenda/odontograma/caja UI verification; read browser console logs for client errors.
- Debug UI behavior (409 alternatives flow, 422 validation messages) in the real browser, not by guessing from code.

### docker-testcontainers
- Python: `testcontainers.postgres.PostgresContainer("postgres:16-alpine")` as module-scoped pytest fixture for PG integration tests.
- REQUIRED for: C-02 tenant-isolation tests, C-05 concurrent double-booking tests (real exclusion-constraint behavior can't be faked with SQLite — never substitute SQLite for PG tests).
- Singleton/reuse containers across the session for speed; CI must support Docker-in-Docker (Ryuk); test Alembic migrations up/down against the container.

### systematic-debugging
- IRON LAW: no fixes without root-cause investigation — reproduce first, read full stack traces, note files/lines/codes.
- Especially under time pressure or when a "quick fix" seems obvious; if a previous fix failed, re-investigate instead of stacking guesses.
- Four phases in order: reproduce → isolate root cause → fix → verify (tests + regression check).

### context7-mcp
- Use for CURRENT library docs whenever touching: FastAPI (deps, background jobs, validation), SQLAlchemy/Alembic, Mercado Pago SDK (preferencias, webhooks), ARCA WSFE (homologación, CAE/QR), the WhatsApp QR-session client chosen for C-15 (DD-10; Meta Cloud API docs only as F2 migration reference).
- Flow: `resolve-library-id` first (exact `/org/project`), then `query-docs` with one scoped concept per call (max 3 calls/question). These tools come from the **Context7 MCP server** configured in `.mcp.json` (see MCP Integrations); this skill only describes how to use them.
- Prefer over web search for API syntax/config/migration questions; never send secrets/keys in queries.
- No ecosystem skill exists for Mercado Pago / ARCA / ReNaPDiS partner — Context7 + official docs are the source of truth (see Integration Gaps).

### web-design-guidelines
- Audit clinical UIs (agenda, odontograma, caja, seguimiento) against guidelines: accessibility (keyboard nav, focus states, contrast), error states, empty states, loading states.
- Data-dense screens first: agenda día/semana, ficha/odontograma tabs, presupuestos editor — clarity over decoration.

### crear-skill-de-dominio
- Inputs: RN prefix(es) + roadmap change. Steps: read RN (05) → filter by current DDs (09; skip titles with REEMPLAZADA/Histórico) → add applicable hard rules (AGENTS.md) → trace by meaning spec requirement → test function → write from template → copy to `.github/skills` + `.opencode/skills` → register in AGENTS.md, CLAUDE.md and this registry.
- Never invent traceability: empty cell = `—` + estado `pendiente`. RN that contradicts a current DD → rewrite coherently, mark ⚠️, list under "Conflictos detectados".
- Done only when its 6 review criteria pass (see SKILL.md §6, each with a command).

### dominio-agenda
- Active turn = `reservado|confirmado|asistido`; `cancelado`/`ausente` free the slot; `sobreturno` is outside the GiST exclusions on purpose (RN-AG-04, `require_sobreturno()`).
- Overlap/blocked → 409 "Horario no disponible" without leaking the other turn; invalid/foreign refs → 422; wrong role → 403; other tenant → 404.
- WhatsApp reminders/confirmations = QR session with dedicated number (DD-10), never "official API/approved templates".
- Timeouts (SU-04) are config, never constants.

### dominio-caja
- Money `NUMERIC` ARS; MP credentials backend-only; webhook = public route, signature with `MP_WEBHOOK_SECRET` (invalid → 401), idempotent by unique `id_externo_MP`.
- Anulación only via `require_anulacion_caja()` (admin) with trace; seña only when risk score demands it (threshold undefined in KB → ask).
- MP account/refund policy is an open assumption (PA-06/SU-07): document the chosen assumption in design.md.

### dominio-clinica
- HC append-only: no PUT/PATCH/DELETE on evoluciones (405); correction = new row with `corrige_a_id`; author = authenticated odontólogo, timestamp = server (no author → 422).
- Reuse `fn_rechazar_mutacion()` (migration 004) triggers and extend `AuditoriaHC` CHECKs + writer allowlist; never clinical text in `diff`.
- RBAC: read `require_clinico()` (admin+odontólogo), write `require_clinico_escritura()` (odontólogo only), `require_vinculo_paciente`; recepción → 403; no consent → 403.
- FDI MVP: permanent 11–48 (32) + temporary 51–85 (20); fine mixed dentition/BOP are F2.

### dominio-cumplimiento
- Signed consent = locked document: constancia = server timestamp + IP + user-agent + SHA-256 of the exact versioned text (client never sends hash/date; extra='forbid' → 422); no edit endpoint; DB trigger rejects mutation once `documento_bloqueado`; incomplete signature → 422 retryable, stays pending.
- No `consentimiento_datos` → 403; recepción → 403 on clinical/consent/receta routes; export and every list = only the caller's tenant (cross-tenant = 0 rows).
- Receta only via ReNaPDiS-registered partner behind a port/adapter (DD-06): fake adapter for tests/demo, not configured → 501 with clear message; boot never fails without `RECETAS_PARTNER_KEY`; secrets backend env only.
- Legal texts are seed placeholders marked "a validar con asesoría legal" (PA-04/SU-08). Migrations: 009 = C-18, 010 = C-19, single `alembic heads`.

### event-store-design
- Evolución (C-09) is append-only: no UPDATE/DELETE endpoints; corrections are new rows with `corrige_a_id` — same pattern as event-sourced logs.
- `AuditoriaHC` is an immutable event log (actor, acción, entidad_id, diff, timestamp) with no write endpoint; extend to evoluciones/odontograma via DB trigger/function.
- Consentimientos firmados (C-18) follow the same immutability: post-firma document is blocked, no edit endpoint.

## Change → Skills Matrix

| Change | Skills to resolve into sub-agent prompt | Domain skill (project) |
|--------|------------------------------------------|------------------------|
| C-01 foundation-setup | typescript-dev, docker-testcontainers, vitest | — (archived) |
| C-02 core-models-multitenancy | supabase-postgres-best-practices, postgresql-table-design, docker-testcontainers | — (archived) |
| C-03 auth-rbac | auth-implementation-patterns, supabase-postgres-best-practices (RLS tests), docker-testcontainers | — (archived) |
| C-04 clinica-catalogo | postgresql-table-design, supabase-postgres-best-practices | — (archived) |
| C-05 motor-turnos | postgresql-table-design (EXCLUDE), postgresql-optimization (ranges), docker-testcontainers (concurrency), systematic-debugging | dominio-agenda |
| C-05b transiciones-estado-turno | docker-testcontainers (concurrency), systematic-debugging; Context7 MCP (SQLAlchemy row locking) | dominio-agenda |
| C-06 reserva-online-publica | auth-implementation-patterns (public routes/rate-limit), postgresql-optimization, vitest | dominio-agenda, dominio-caja (seña) |
| C-07 agenda-frontend | typescript-dev, vercel-react-best-practices, vitest, webapp-testing, web-design-guidelines | dominio-agenda |
| C-08 pacientes-ficha | postgresql-table-design, postgresql-optimization (trgm search), auth-implementation-patterns (RBAC clínico) | — (archived; covered by dominio-clinica) |
| C-09 odontograma-evolucion | postgresql-optimization (JSONB), event-store-design, docker-testcontainers; Context7 MCP (SQLAlchemy JSONB / Alembic) | dominio-clinica |
| C-10 clinica-frontend | typescript-dev, vercel-react-best-practices, vitest, webapp-testing | dominio-clinica |
| C-11 presupuesto-plan | postgresql-table-design, postgresql-optimization (tableros) | — (generate with crear-skill-de-dominio before propose) |
| C-12 caja-mercadopago | context7-mcp (MP SDK), auth-implementation-patterns (webhook firma/idempotencia), docker-testcontainers | dominio-caja |
| C-13 factura-arca | context7-mcp (WSFE), postgresql-table-design | — (generate with crear-skill-de-dominio before propose) |
| C-14 comercial-frontend | typescript-dev, vercel-react-best-practices, vitest, webapp-testing | dominio-caja (/caja) |
| C-15 whatsapp-bidireccional | context7-mcp (WhatsApp QR client, DD-10), docker-testcontainers (webhook idempotencia) | — (generate with crear-skill-de-dominio before propose) |
| C-16 lista-espera-relleno | postgresql-optimization, context7-mcp, docker-testcontainers | dominio-agenda |
| C-17 chatbot-reprogramacion | context7-mcp, postgresql-optimization | dominio-agenda |
| C-18 consentimientos-cumplimiento | event-store-design, auth-implementation-patterns (admin RBAC), docker-testcontainers; Context7 MCP (FastAPI StreamingResponse / zipfile) | dominio-cumplimiento |
| C-19 recetas-partner-renapdis | context7-mcp, auth-implementation-patterns (vault/env, 501 sin partner) | dominio-cumplimiento |

## MCP Integrations (not skills)

| Server | Config | Tools | Use for | Limits |
|--------|--------|-------|---------|--------|
| Context7 | `.mcp.json` → `https://mcp.context7.com/mcp` (HTTP, API key optional) | `resolve-library-id`, `query-docs` | Current docs of FastAPI, SQLAlchemy, Pydantic, Alembic, Mercado Pago, React/Vite | Read-only public docs; never send secrets, tokens, patient data or private code |

## Integration Gaps (no trustworthy skill available)

Verified via `npx skills find` (2026-10-07). Do NOT install low-install-count (<100) skills for these — use Context7 + official docs instead.
- **WhatsApp**: no dedicated skill ≥1K installs (only `gokapso/observe-whatsapp` 3.2K = observability, not integration; rest <150). Constraints (DD-10, RN-WA-01 modified 2026-10-08): QR session with a dedicated number behind `MensajeriaPort` (official API only as F2 migration), session monitoring/reconnect/backup, internal ARS cost `ARS_PRECIO_MENSAJE` (RN-WA-02). Docs of the chosen QR client via Context7. *(Corrected 2026-11-16: this line previously required the official API only and forbade the QR session, superseded by DD-10.)*
- **Mercado Pago**: zero skills found. Source of truth: MP SDK docs via context7-mcp. Constraints: firma `MP_WEBHOOK_SECRET`, idempotencia por `id_externo_MP` (C-12).
- **ARCA WSFE**: zero skills found. Source of truth: ARCA docs. Constraints: homologación primero, CAE+QR, cola con backoff (C-13, DD-01, PA-07).
- **ReNaPDiS partner**: zero skills found. Adapter intercambiable (Farmalink/Innovamed/otro, PA-08); sin partner → 501 claro (C-19, DD-06).
- **FastAPI/Python backend**: best match `sickn33/python-fastapi-development` (525 installs, below 1K trust threshold) — NOT installed. Backend guidance covered by PG + auth + debugging skills above; use context7-mcp for FastAPI specifics.

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| AGENTS.md | `AGENTS.md` | Agent instructions: 17 hard rules, skills, MCP integrations, workflow. Must stay identical to CLAUDE.md. |
| CLAUDE.md | `CLAUDE.md` | Copy of AGENTS.md read by Claude Code (`diff AGENTS.md CLAUDE.md` must be empty). |
| Domain KB | `knowledge-base/` | 11 files; per-area digests in `.claude/skills/dominio-*`. |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.
