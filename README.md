# Turnos Odontología — SaaS multi-tenant (AR)

Sistema de gestión de turnos para clínicas odontológicas argentinas: agenda con
anti-solapamiento duro, reserva online sin cuenta, odontograma + HC append-only,
presupuesto → plan → turnos, caja con Mercado Pago, factura electrónica ARCA,
WhatsApp por QR con número dedicado y cumplimiento Ley 25.326/26.529.

## Stack (DD-08)

Backend Python + FastAPI · PostgreSQL 16 · Frontend React + Vite + TS · Alembic.

## Quick start (C-01)

```bash
docker compose up db            # PostgreSQL 16 en :5432
uvicorn app.main:app --reload --app-dir backend   # API en :8000
cd frontend && npm install && npm run dev          # UI en :5173
curl http://localhost:8000/api/health             # {"status":"ok"}
```

## Cómo correr los tests

Requisitos: Python 3.12+ y **Docker Desktop corriendo** (los tests de integración levantan
PostgreSQL 16 real con testcontainers; nunca SQLite).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install fastapi uvicorn "pydantic[email]" pydantic-settings sqlalchemy "psycopg[binary]" \
  alembic bcrypt PyJWT slowapi phonenumbers python-multipart \
  pytest httpx "testcontainers[postgres]" ruff
docker version                      # debe mostrar la sección "Server"
python -m pytest backend/tests -q   # unit + integración
ruff check backend
```

Solo los tests del change `crear-turno-sin-solapamientos` (un archivo por grupo de escenarios del spec
`openspec/specs/appointments/spec.md`):

```bash
python -m pytest backend/tests/unit/test_turno_schemas.py backend/tests/unit/test_turno_errores.py \
  backend/tests/integration/test_migracion_005.py backend/tests/integration/test_turnos_db_constraints.py \
  backend/tests/integration/test_turnos_api.py backend/tests/integration/test_turnos_concurrencia.py -v
```

Tests del change C-05b `transiciones-estado-turno` (estados del turno, historial y concurrencia):

```bash
python -m pytest backend/tests/unit/test_turno_transiciones.py backend/tests/integration/test_migracion_006.py   backend/tests/integration/test_turno_transicion_db.py backend/tests/integration/test_turno_transiciones_api.py   backend/tests/integration/test_turno_transiciones_concurrencia.py -v
```

> Si tenés un PostgreSQL instalado en Windows ocupando el puerto 5432, `docker compose up db` no puede usarlo. Los tests no lo necesitan (testcontainers usa un puerto libre); para levantar la API a mano usá otro puerto, por ejemplo `docker run -d -p 55432:5432 -e POSTGRES_USER=turnos -e POSTGRES_PASSWORD=<pass> -e POSTGRES_DB=turnos postgres:16-alpine` y `DATABASE_URL=postgresql+psycopg://turnos:<pass>@localhost:55432/turnos`.

> **¿Vas a continuar el proyecto?** Leé primero [`docs/CONTINUAR.md`](docs/CONTINUAR.md): estado, reparto de changes, entorno y flujo de trabajo.

## Skills propias y MCP

Detalle, investigación y evidencias: [`docs/skills-mcp/`](docs/skills-mcp/) ([ficha](docs/skills-mcp/investigacion.md) · [informe de aplicación](docs/skills-mcp/aplicacion.md)).

### Skills del proyecto

Viven en el repo, no hay nada que instalar:

| Skill | Ubicación | Para qué |
|-------|-----------|----------|
| `crear-skill-de-dominio` | `.claude/skills/crear-skill-de-dominio/` | Genera una skill `dominio-<área>` desde la KB (RN filtradas por DD vigentes + reglas duras + matriz RN → spec → test) |
| `dominio-agenda` | `.claude/skills/dominio-agenda/` | Reglas vigentes RN-AG + RN-TU (turnos, solapamientos, estados) |
| `dominio-caja` | `.claude/skills/dominio-caja/` | Reglas vigentes RN-CA (seña, cobros, Mercado Pago) |

Claude Code las descubre solas desde `.claude/skills/`. GitHub Copilot usa las copias de `.github/skills/` y OpenCode las de `.opencode/skills/` (idénticas: `diff -r -x evals .claude/skills/dominio-caja .github/skills/dominio-caja` no imprime nada).

**Comprobar:** abrir Claude Code en la raíz del repo y pedir *"¿qué skills de proyecto hay?"* o *"creá la skill del dominio clínica (RN-CL) para C-09"*. El agente debe nombrar o cargar `crear-skill-de-dominio`.

La skill creadora se construyó con **`skill-creator`** de Anthropic ([github.com/anthropics/skills](https://github.com/anthropics/skills), carpeta `skills/skill-creator`). Solo hace falta para *modificar* la skill creadora, no para usarla. En esta PC se usó la copia que trae Claude Code como skill de Anthropic (`anthropic-skills:skill-creator`). Para instalarla en otra PC: `/plugin marketplace add anthropics/skills` y `/plugin install example-skills@anthropic-agent-skills` (que `skill-creator` venga en `example-skills` está **pendiente de verificar**: el README del repo no lo dice). Alternativa sin plugin: copiar la carpeta `skills/skill-creator` del repo a `~/.claude/skills/skill-creator/`.

### MCP: Context7

Integración (no skill) que da al agente documentación vigente de librerías (FastAPI, SQLAlchemy, Pydantic, Alembic, Mercado Pago, React).

| Dato | Valor |
|------|-------|
| Servidor | Context7 (Upstash), remoto HTTP: `https://mcp.context7.com/mcp` |
| Configuración | [`.mcp.json`](.mcp.json) en la raíz (scope proyecto, versionado, **sin secretos**) |
| Requisitos | Claude Code + conexión a internet. No necesita Node ni Docker en modo HTTP |
| Credenciales | Ninguna obligatoria. API key opcional y gratuita para más cuota (context7.com/dashboard) |
| Variable de entorno | `CONTEXT7_API_KEY` (opcional, solo si se usa la key; **nunca** commitearla) |
| Herramientas | `resolve-library-id` (nombre → id `/org/proyecto`) y `query-docs` (id + pregunta) |

**Configurar (ya viene en el repo):**

```json
{
  "mcpServers": {
    "context7": { "type": "http", "url": "https://mcp.context7.com/mcp" }
  }
}
```

1. Abrir Claude Code en la raíz del repo. La primera vez pregunta si aprobar los servidores de `.mcp.json`: aprobar `context7`.
2. Comprobar la conexión: `/mcp` dentro de Claude Code, o `claude mcp list` en la terminal. Debe decir `context7 … ✔ Connected`.
3. Ejecutar una herramienta real, por ejemplo: *"usá Context7 para buscar en la doc de SQLAlchemy cómo bloquear una fila con `with_for_update`"*. El agente llama `resolve-library-id` y después `query-docs`.

**Con API key (opcional), sin tocar el repo:** configurarla en el scope de usuario, que queda en `~/.claude.json` y no se versiona:

```bash
claude mcp add --scope user --transport http context7 https://mcp.context7.com/mcp --header "Authorization: Bearer $CONTEXT7_API_KEY"
```

**Solución de problemas**

- `/mcp` muestra `⏸ Pending approval`: el servidor de `.mcp.json` no fue aprobado. Correr `claude mcp reset-project-choices`, reabrir Claude Code y aprobar.
- `✘ Failed to connect`: revisar internet o proxy. Alternativa local stdio (requiere Node): `claude mcp add context7 -- npx -y @upstash/context7-mcp`. En Windows nativo puede hacer falta anteponer `cmd /c` a `npx`.
- Una entrada con `url` pero sin `"type": "http"` se interpreta como stdio y falla: el `type` es obligatorio.
- Problema encontrado en este repo: los servidores agregados a `.mcp.json` **no aparecen en la sesión que ya estaba abierta**. Hay que reiniciar Claude Code para que cargue `context7`.

**Límites de uso:** solo lectura de documentación pública. No enviar en las consultas secretos, tokens, datos de pacientes ni código privado.

## Documentación del trabajo (Metodología I)

- `docs/discovery/` — informe de Discovery (`.md` + `.pdf`) y checklist de 11 puntos.
- `knowledge-base/` — 10 archivos canónicos · `CHANGES.md` — roadmap · `AGENTS.md`/`CLAUDE.md` — reglas del agente.
- `openspec/changes/archive/` — changes archivados (el del ciclo OPSX de la Etapa 6: `crear-turno-sin-solapamientos`).
- `docs/skills-mcp/` — TP Skills + MCP: ficha de investigación, informe de aplicación y evidencias.

## Estructura

`backend/` · `frontend/` · `jobs/` · `docs-legales/` · `knowledge-base/` ·
`openspec/` · `CHANGES.md` (roadmap de 19 changes) · `AGENTS.md` (17 reglas duras).

## Estado

Archivados: C-01, C-02, C-03, C-04, C-08, `crear-turno-sin-solapamientos` (recorte de C-05) y C-05b `transiciones-estado-turno`. Ver `CHANGES.md` y `openspec/changes/archive/`.
