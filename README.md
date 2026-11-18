# Turnos Odontología — SaaS multi-tenant (AR)

Sistema de gestión de turnos para clínicas odontológicas argentinas: agenda con
anti-solapamiento duro, reserva online sin cuenta, odontograma + historia clínica append-only,
presupuesto → plan → turnos, caja con Mercado Pago, factura electrónica ARCA,
WhatsApp por QR con número dedicado y cumplimiento Ley 25.326/26.529.

**Stack (DD-08):** Python + FastAPI · PostgreSQL 16 · Alembic · React + Vite + TypeScript.

> **¿Vas a continuar el proyecto?** Leé primero [`docs/CONTINUAR.md`](docs/CONTINUAR.md): estado, reparto de changes, entorno y flujo de trabajo.

## Contenido

1. [Estado: qué está completo y qué falta](#estado-qué-está-completo-y-qué-falta)
2. [Levantar la demo local](#levantar-la-demo-local): requisitos, instalación, configuración, datos ficticios, arranque y Swagger
3. [Qué mirar en la demo](#qué-mirar-en-la-demo)
4. [Configuración de integraciones](#configuración-de-integraciones)
5. [Tests](#tests)
6. [Skills propias y MCP](#skills-propias-y-mcp)
7. [Documentación y estructura](#documentación-y-estructura)

## Estado: qué está completo y qué falta

**16 de 20 changes completos y archivados** (implementados, con tests en verde y `verify.md`).
Detalle en [`CHANGES.md`](CHANGES.md) y `openspec/changes/archive/`.

| Fase | Changes | Estado |
|------|---------|--------|
| 0 — Cimientos | C-01 `foundation-setup`, C-02 `core-models-multitenancy` | ✅ completo |
| 1 — Identidad y acceso | C-03 `auth-rbac` | ✅ completo |
| 2 — Núcleo agenda | C-04 `clinica-catalogo`, C-08 `pacientes-ficha`, C-05 `motor-turnos` (+ C-05b, C-05c), C-05d `horario-atencion`, C-06 `reserva-online-publica`, C-07 `agenda-frontend`, C-20 `rediseno-visual` | ✅ completo |
| 3 — Clínica | C-09 `odontograma-evolucion`, C-10 `clinica-frontend` | ✅ completo |
| 4 — Comercial y fiscal | C-11 `presupuesto-plan`, C-12 `caja-mercadopago`, C-13 `factura-arca`, C-14 `comercial-frontend` | ⬜ **pendiente** |
| 5 — WhatsApp | C-15 `whatsapp-bidireccional`, C-16 `lista-espera-relleno`, C-17 `chatbot-reprogramacion` | ✅ completo |
| 6 — Cumplimiento | C-18 `consentimientos-cumplimiento`, C-19 `recetas-partner-renapdis` | ✅ completo |

**Qué queda pendiente**

- **Fase 4 completa (C-11 a C-14):** presupuestos y planes de tratamiento, caja y cobros con Mercado Pago,
  factura electrónica ARCA y las pantallas comerciales. No hay código de esto todavía.
- **Seña:** la reserva online, la lista de espera y la reprogramación funcionan **sin seña**; la exigencia de
  seña se engancha cuando llegue C-12.
- **Partner de recetas real:** C-19 funciona con un partner **simulado** (`fake`); el adapter de un partner
  real registrado en ReNaPDiS (PA-08) es un change posterior.
- **WhatsApp con número real:** el código está completo y probado con un gateway simulado; conectar un número
  real requiere levantar el gateway QR y escanear la sesión (ver [Configuración de integraciones](#configuración-de-integraciones)).

## Levantar la demo local

> 🔒 **El repo no trae ninguna contraseña ni secreto.** Cada uno elige los suyos en su PC (los `<...>` de
> abajo son lugares para completar). Usuarios, pacientes y turnos de la demo son **ficticios**: nada real
> (regla dura 14).

Los comandos son para bash (Git Bash en Windows). En PowerShell, `export NOMBRE=valor` se escribe `$env:NOMBRE="valor"`.

### 1. Requisitos

| Herramienta | Versión | Para qué |
|-------------|---------|----------|
| Python | 3.12 o superior | Backend |
| Node.js | 20 o superior | Frontend |
| Docker Desktop | corriendo | Base de datos PostgreSQL 16 y tests de integración |
| Git | — | Clonar el repo |

### 2. Instalación

```bash
git clone <url-del-repo> turnos-odontologia && cd turnos-odontologia

# Backend: entorno virtual + dependencias
python -m venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
pip install fastapi uvicorn "pydantic[email]" pydantic-settings sqlalchemy "psycopg[binary]" \
  alembic bcrypt PyJWT slowapi phonenumbers python-multipart httpx

# Frontend: dependencias
cd frontend && npm install && cd ..

# Base de datos: PostgreSQL 16 en Docker
# (puerto 55432 para no chocar con un PostgreSQL instalado en Windows en :5432)
docker run -d --name turnos-demo-pg -p 55432:5432 \
  -e POSTGRES_USER=turnos -e POSTGRES_PASSWORD=<pass-db> -e POSTGRES_DB=turnos postgres:16-alpine
```

### 3. Configuración de ejemplo (sin secretos)

Crear un archivo `.env` **en la raíz del repo** (el backend lo lee desde la carpeta donde se arranca;
`.env` está en `.gitignore`, nunca se commitea). Ejemplo para la demo local:

```dotenv
# Base de datos (la misma <pass-db> del docker run)
DATABASE_URL=postgresql+psycopg://turnos:<pass-db>@localhost:55432/turnos

# Auth: cualquier texto aleatorio de 32+ caracteres, solo para tu PC
JWT_SECRET_KEY=<secreto-largo-de-32-o-mas-caracteres>
COOKIE_SECURE=false            # solo en http local; en producción va true

# Entorno de demo: habilita los adaptadores simulados de abajo
ENTORNO=demo
WHATSAPP_GATEWAY=fake          # WhatsApp simulado (no envía mensajes reales)
RECETAS_PARTNER=fake           # partner de recetas simulado (recetas marcadas "simulada")
```

Todas las variables posibles, con su descripción y valores por defecto, están en
[`backend/.env.example`](backend/.env.example) y en `backend/app/infrastructure/settings.py`.

> ⚠️ El backend rechaza variables que no conoce: las `SEED_*` del paso siguiente **no** van en el `.env`,
> se exportan en la terminal.

### 4. Datos ficticios

```bash
export DATABASE_URL=postgresql+psycopg://turnos:<pass-db>@localhost:55432/turnos
export SEED_DEMO_PASSWORD=<pass-demo>    # contraseña que vas a usar para entrar con los usuarios de demo
export SEED_ADMIN_PASSWORD=<pass-demo>   # idem para el admin (puede ser la misma)

python -m alembic -c backend/alembic.ini upgrade head   # crea las tablas (migraciones)
python backend/scripts/seed_demo_clinica.py             # clínica piloto, 3 usuarios y 3 pacientes demo
python backend/scripts/seed_demo_agenda.py              # 3 sillones, 3 profesionales, 12 pacientes y ~60 turnos de la semana actual
```

Los scripts se pueden repetir sin duplicar datos. Todo lo que crean está marcado como seed y es sintético
(DNI de prueba 98xxxxxx, emails `@clinica-piloto.test`).

### 5. Arranque del backend y del frontend

```bash
# Terminal 1 — API en http://localhost:8000
uvicorn app.main:app --app-dir backend --port 8000

# Terminal 2 — Frontend en http://localhost:5173 (el proxy de Vite manda /api a :8000)
cd frontend && npm run dev
```

Comprobar: `curl http://localhost:8000/api/health` → `{"status":"ok"}` y abrir http://localhost:5173.

### 6. Swagger

La documentación interactiva de la API está en **http://localhost:8000/docs** (Swagger UI) y en
http://localhost:8000/redoc: lista todas las rutas con sus esquemas, y las públicas (health, reserva online,
páginas legales) se prueban directo con **Try it out**.

Las rutas protegidas piden un token. El botón **Authorize** de Swagger no sirve en este proyecto (manda un
formulario y el login acepta JSON), así que el token se obtiene con `POST /api/auth/login` y se usa por curl:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"recepcion@clinica-piloto.test","password":"<pass-demo>"}' | python -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/pacientes
```

**Problemas comunes**

- **Página en blanco o error `Failed to resolve import "..."`:** faltan dependencias del frontend
  (se agregan en algunos changes). Correr `npm install` en `frontend/` y reiniciar `npm run dev`.
- **El puerto 8000 está ocupado:** levantá la API en otro (`--port 8010`) y arrancá el frontend con
  `VITE_PROXY_TARGET=http://localhost:8010 npm run dev`.
- **`pip install -e backend` falla** ("Multiple top-level packages"): es esperable; instalá las
  dependencias con el `pip install` del paso 2.
- **`docker compose up db` no arranca** porque ya hay un PostgreSQL en :5432: usá el `docker run` del paso 2.

### Usuarios de demo

Todos entran con la contraseña que pusiste en `SEED_DEMO_PASSWORD` (el admin, con `SEED_ADMIN_PASSWORD`).
Login: máximo 5 intentos por minuto.

| Usuario | Rol | Qué ve |
|---------|-----|--------|
| `odontologo@clinica-piloto.test` | Odontólogo | Todo lo clínico: ficha, odontograma, evoluciones (alta y corrección), adjuntos |
| `recepcion@clinica-piloto.test` | Recepcionista | Agenda, pacientes y datos administrativos; en lo clínico ve "Sin acceso clínico" |
| `admin@clinica-piloto.test` | Administrador | Historia clínica en solo lectura, usuarios, exportación |

Pacientes de demo: `Sintético, Demo Uno` y `Demo Dos` (con consentimiento) y `Demo Tres` (sin
consentimiento: la escritura clínica queda bloqueada). `seed_demo_agenda.py` suma 12 pacientes ficticios
más (DNI 98xxxxxx), solo con datos de contacto.

## Qué mirar en la demo

| Pantalla | URL | Login | Notas |
|----------|-----|-------|-------|
| Landing | http://localhost:5173/ | No | Botón de tema: Claro / Oscuro / Sistema (C-20) |
| Agenda | http://localhost:5173/agenda | Staff | Día por sillón y semana por profesional; alta y cambios de estado (C-07) |
| Pacientes e historia clínica | http://localhost:5173/pacientes | Staff | Ficha, odontograma, evoluciones y adjuntos (C-10) |
| Reserva online | http://localhost:5173/reservar/clinica-piloto | No | Solo aparecen profesionales con horario cargado (C-05d, C-06) |
| Comprobante / reprogramar | `/reserva/{token}` · `/reprogramar/{token}` | No | El enlace llega al reservar (C-17, C-20) |
| Cumplimiento y privacidad | http://localhost:5173/cumplimiento · `/privacidad` | No | Páginas legales públicas (C-18) |
| API (Swagger) | http://localhost:8000/docs | — | Todas las rutas del backend |

- **Horario de atención:** un profesional sin franjas no tiene huecos ni acepta turnos normales.
  Se carga con `PUT /api/admin/profesionales/{id}/horario` (admin). Los seeds traen lunes a viernes 09–13 y 14–18.
- **Diseño:** el sistema de diseño está en [`design-system/turnos-odontologia/MASTER.md`](design-system/turnos-odontologia/MASTER.md).
  Las capturas de la landing (`frontend/public/landing/`) se regeneran con `E2E_PASSWORD=<pass-demo> python scripts/e2e/capturas_landing.py`.

## Configuración de integraciones

Las variables van en el `.env` del paso 3 (lista completa en `backend/.env.example`). Son solo del backend:
nunca con prefijo `VITE_` y nunca con valores reales en el repo.

Las integraciones externas nunca impiden que el sistema arranque: si una no está configurada, solo esa
función responde `501` con un mensaje de configuración. Los adaptadores simulados (`fake`) funcionan solo con
`ENTORNO` distinto de `produccion` (el default es `produccion`, por seguridad).

### WhatsApp (C-15, C-16, C-17)

| Variable | Valores | Efecto |
|---|---|---|
| `WHATSAPP_GATEWAY` | vacío, `fake`, `waha` | Vacío = no configurado (`501`). `fake` = gateway simulado, para demo y tests. `waha` = gateway QR real. |
| `WHATSAPP_GATEWAY_URL` | URL del gateway | Solo con `waha` (local: `http://127.0.0.1:3000`). |
| `WHATSAPP_GATEWAY_API_KEY` | clave del gateway | Solo env del backend; la misma que usa el contenedor `waha`. |
| `WHATSAPP_WEBHOOK_HMAC_KEY` | secreto HMAC | Firma de los eventos entrantes del gateway. |

Para usar un número real por QR: levantar el gateway con `docker compose --profile whatsapp up -d waha` y
seguir el runbook [`docs/whatsapp-sesion.md`](docs/whatsapp-sesion.md) (sesión QR, reconexión y backup).

### Partner de recetas (C-19)

| Variable | Valores | Efecto |
|---|---|---|
| `RECETAS_PARTNER` | vacío, `fake` | Vacío = no configurado: emitir responde `501` y el resto del sistema sigue funcionando. `fake` = partner simulado. |
| `ENTORNO` | `desarrollo`, `test`, `demo`, `produccion` (default) | Con `produccion`, `fake` queda bloqueado (`501`): una receta simulada nunca puede pasar por válida. |
| `RECETAS_PARTNER_KEY` | credencial del partner real | Solo env/vault del backend; se enmascara en logs y errores. |

`fake` genera ids `FAKE-...` y enlaces `https://partner-simulado.invalid/...`, y marca cada receta `simulada = true`.
El adapter del partner real (PA-08) es un change posterior.

## Tests

**Requisitos:** el entorno de Python del paso 2 más `pip install pytest "testcontainers[postgres]" ruff`, y
**Docker Desktop corriendo**: los tests de integración levantan un PostgreSQL 16 real con testcontainers
(nunca SQLite). No hace falta tener la base de la demo levantada.

```bash
docker version                      # debe mostrar la sección "Server"
python -m pytest backend/tests -q   # backend completo: unit + integración (~20 min)
ruff check backend
cd frontend && npm test             # frontend (vitest)
```

E2E con navegador real (con la demo levantada; requiere `pip install playwright` y
`python -m playwright install chromium`):

```bash
E2E_PASSWORD=<pass-demo> python scripts/e2e/clinica_demo.py      # flujo clínico
python scripts/e2e/rediseno_evidencias.py                         # capturas claro/oscuro, desktop/móvil
```

Cada change archivado tiene en su `verify.md` la corrida completa y el detalle de qué cubre cada test.

<details>
<summary><b>Tests por change</b> (para correr solo un grupo)</summary>

**`crear-turno-sin-solapamientos`** (C-05: alta + anti-solapamiento + bloqueos)

```bash
python -m pytest backend/tests/unit/test_turno_schemas.py backend/tests/unit/test_turno_errores.py \
  backend/tests/integration/test_migracion_005.py backend/tests/integration/test_turnos_db_constraints.py \
  backend/tests/integration/test_turnos_api.py backend/tests/integration/test_turnos_concurrencia.py -v
```

**C-05b `transiciones-estado-turno`** (estados del turno, historial y concurrencia)

```bash
python -m pytest backend/tests/unit/test_turno_transiciones.py backend/tests/integration/test_migracion_006.py \
  backend/tests/integration/test_turno_transicion_db.py backend/tests/integration/test_turno_transiciones_api.py \
  backend/tests/integration/test_turno_transiciones_concurrencia.py -v
```

**C-05c `huecos-y-sobreturnos`** (sobreturno con motivo y `GET /api/agenda/huecos`)

```bash
python -m pytest backend/tests/unit/test_turno_schemas.py backend/tests/integration/test_migracion_011.py \
  backend/tests/integration/test_turnos_db_constraints.py backend/tests/integration/test_sobreturnos_api.py \
  backend/tests/integration/test_huecos_servicio.py backend/tests/integration/test_huecos_api.py -v
```

**C-05d `horario-atencion`** (franjas por profesional; huecos y alta limitados al horario)

```bash
python -m pytest backend/tests/unit/test_horario_schemas.py backend/tests/integration/test_migracion_012.py \
  backend/tests/integration/test_horario_api.py backend/tests/integration/test_horario_concurrencia.py \
  backend/tests/integration/test_horario_turnos.py backend/tests/integration/test_seed_catalogo.py -v
```

**C-06 `reserva-online-publica`** (reserva sin cuenta por enlace; backend + frontend)

```bash
python -m pytest backend/tests/unit/test_reserva_schemas.py backend/tests/integration/test_migracion_013.py \
  backend/tests/integration/test_reserva_publica_servicio.py backend/tests/integration/test_reserva_publica_concurrencia.py \
  backend/tests/integration/test_reserva_publica_api.py -v
cd frontend && npx vitest run tests/reserva-api.test.ts tests/reserva.test.tsx
```

**C-07 `agenda-frontend`** (agenda día/semana, alta y estados; backend + frontend)

```bash
python -m pytest backend/tests/integration/test_agenda_lectura_api.py -v
cd frontend && npx vitest run tests/agenda.test.tsx tests/agenda-tiempo.test.ts tests/ui-componentes.test.tsx tests/app-shell.test.tsx
```

**C-09 `odontograma-evolucion`** (odontograma FDI, evoluciones append-only, historia consolidada)

```bash
python -m pytest backend/tests/unit/test_fdi.py backend/tests/unit/test_clinica_schemas.py \
  backend/tests/unit/test_clinica_errores.py backend/tests/integration/test_migracion_008.py \
  backend/tests/integration/test_clinica_db.py backend/tests/integration/test_odontograma_api.py \
  backend/tests/integration/test_odontograma_concurrencia.py backend/tests/integration/test_evoluciones_api.py \
  backend/tests/integration/test_evoluciones_concurrencia.py backend/tests/integration/test_historia_api.py \
  backend/tests/integration/test_rbac_clinica.py backend/tests/integration/test_clinica_aislamiento.py \
  backend/tests/integration/test_auditoria_writer.py -v
```

**C-18 `consentimientos-cumplimiento`** (consentimientos con firma y constancia, usuarios, exportación, páginas legales)

```bash
python -m pytest backend/tests/unit/test_cumplimiento_hash.py backend/tests/unit/test_cumplimiento_textos.py \
  backend/tests/unit/test_cumplimiento_schemas.py backend/tests/unit/test_cumplimiento_errores.py \
  backend/tests/unit/test_exportacion_csv.py backend/tests/unit/test_usuarios_schemas.py \
  backend/tests/integration/test_migracion_009.py backend/tests/integration/test_cumplimiento_db.py \
  backend/tests/integration/test_auditoria_writer.py backend/tests/integration/test_consentimientos_api.py \
  backend/tests/integration/test_consentimientos_concurrencia.py backend/tests/integration/test_rbac_consentimientos.py \
  backend/tests/integration/test_admin_usuarios_api.py backend/tests/integration/test_usuarios_concurrencia.py \
  backend/tests/integration/test_rbac_admin_cumplimiento.py backend/tests/integration/test_exportacion_api.py \
  backend/tests/integration/test_exportacion_aislamiento.py -v
npm --prefix frontend test -- tests/legal.test.tsx
```

Rutas (ver `/docs`): `POST|GET /api/pacientes/{id}/consentimientos`, `GET .../consentimientos/{cid}`,
`POST .../consentimientos/{cid}/firmar`, `GET|POST /api/admin/usuarios`, `PATCH /api/admin/usuarios/{id}/roles`,
`GET /api/admin/exportacion?formato=csv`. Migración `009_consentimientos_cumplimiento`.

**C-19 `recetas-partner-renapdis`** (receta y órdenes de estudio solo vía partner registrado; partner simulado)

```bash
python -m pytest backend/tests/test_settings.py backend/tests/test_env_example.py backend/tests/test_health.py \
  backend/tests/unit/test_recetas_partner.py backend/tests/unit/test_recetas_schemas.py \
  backend/tests/unit/test_recetas_errores.py backend/tests/integration/test_migracion_010.py \
  backend/tests/integration/test_recetas_db.py backend/tests/integration/test_auditoria_writer.py \
  backend/tests/integration/test_recetas_api.py backend/tests/integration/test_recetas_concurrencia.py \
  backend/tests/integration/test_rbac_recetas.py backend/tests/integration/test_exportacion_api.py \
  backend/tests/integration/test_exportacion_aislamiento.py -v
```

Rutas (ver `/docs`): `POST|GET /api/pacientes/{id}/recetas` y `GET .../recetas/{rid}`. Migración `010_recetas_externas`.

**C-20 `rediseno-visual`** (landing, tema claro/oscuro, reprogramación por enlace; solo frontend)

```bash
cd frontend && npx vitest run tests/landing.test.tsx tests/tema.test.tsx tests/reprogramar.test.tsx tests/reserva.test.tsx tests/ui-componentes.test.tsx
```

C-15, C-16 y C-17 (WhatsApp) se cubren con la suite completa del backend; el detalle está en el `verify.md` de cada uno.

</details>

## Skills propias y MCP

Detalle, investigación y evidencias: [`docs/skills-mcp/`](docs/skills-mcp/) ([ficha](docs/skills-mcp/investigacion.md) · [informe de aplicación](docs/skills-mcp/aplicacion.md)).

### Skills del proyecto

Viven en el repo, no hay nada que instalar:

| Skill | Para qué |
|-------|----------|
| `crear-skill-de-dominio` | Genera una skill `dominio-<área>` desde la KB: reglas de negocio filtradas por las decisiones vigentes + reglas duras + matriz regla → spec → test |
| `dominio-agenda` | Reglas RN-AG + RN-TU: turnos, solapamientos, estados, reserva online, lista de espera |
| `dominio-caja` | Reglas RN-CA: seña, cobros, Mercado Pago |
| `dominio-clinica` | Reglas RN-CL: historia clínica, odontograma, evoluciones append-only, auditoría |
| `dominio-whatsapp` | Reglas RN-WA: sesión QR, recordatorios, respuestas, bandeja de fallos |
| `dominio-cumplimiento` | Reglas RN-CU: consentimientos, privacidad, exportación, recetas vía ReNaPDiS |

Claude Code las descubre solas desde `.claude/skills/`. GitHub Copilot usa las copias de `.github/skills/` y
OpenCode las de `.opencode/skills/` (idénticas salvo `evals/`).

**Comprobar:** abrir Claude Code en la raíz del repo y pedir *"¿qué skills de proyecto hay?"* o
*"creá la skill del dominio X"*. El agente debe nombrar o cargar `crear-skill-de-dominio`.

La skill creadora se construyó con **`skill-creator`** de Anthropic
([github.com/anthropics/skills](https://github.com/anthropics/skills), carpeta `skills/skill-creator`). Solo hace
falta para *modificar* la skill creadora, no para usarla. Para instalarla en otra PC, copiar esa carpeta a
`~/.claude/skills/skill-creator/`.

### MCP: Context7

Integración (no skill) que le da al agente documentación vigente de librerías (FastAPI, SQLAlchemy, Pydantic,
Alembic, Mercado Pago, React).

| Dato | Valor |
|------|-------|
| Servidor | Context7 (Upstash), remoto HTTP: `https://mcp.context7.com/mcp` |
| Configuración | [`.mcp.json`](.mcp.json) en la raíz (scope proyecto, versionado, **sin secretos**) |
| Requisitos | Claude Code + conexión a internet. No necesita Node ni Docker en modo HTTP |
| Credenciales | Ninguna obligatoria. API key opcional y gratuita para más cuota (`CONTEXT7_API_KEY`, **nunca** commitearla) |
| Herramientas | `resolve-library-id` (nombre → id `/org/proyecto`) y `query-docs` (id + pregunta) |

**Usarlo (ya viene configurado en el repo):**

1. Abrir Claude Code en la raíz del repo. La primera vez pregunta si aprobar los servidores de `.mcp.json`: aprobar `context7`.
2. Comprobar la conexión con `/mcp` dentro de Claude Code, o `claude mcp list` en la terminal. Debe decir `context7 … ✔ Connected`.
3. Probar una consulta real, por ejemplo: *"usá Context7 para buscar en la doc de SQLAlchemy cómo bloquear una fila con `with_for_update`"*.

**Con API key (opcional), sin tocar el repo:** se configura en el scope de usuario (`~/.claude.json`, no se versiona):

```bash
claude mcp add --scope user --transport http context7 https://mcp.context7.com/mcp --header "Authorization: Bearer $CONTEXT7_API_KEY"
```

**Solución de problemas**

- `/mcp` muestra `⏸ Pending approval`: correr `claude mcp reset-project-choices`, reabrir Claude Code y aprobar.
- `✘ Failed to connect`: revisar internet o proxy. Alternativa local stdio (requiere Node): `claude mcp add context7 -- npx -y @upstash/context7-mcp` (en Windows puede hacer falta anteponer `cmd /c`).
- Una entrada con `url` pero sin `"type": "http"` se interpreta como stdio y falla: el `type` es obligatorio.
- Los servidores agregados a `.mcp.json` no aparecen en una sesión ya abierta: hay que reiniciar Claude Code.

**Límites de uso:** solo lectura de documentación pública. No enviar en las consultas secretos, tokens, datos de pacientes ni código privado.

## Documentación y estructura

| Carpeta / archivo | Qué hay |
|-------------------|---------|
| `backend/` | API FastAPI, migraciones Alembic, seeds de demo y tests |
| `frontend/` | App React + Vite + TypeScript |
| `design-system/` | Sistema de diseño del frontend |
| `scripts/e2e/` | Pruebas y capturas con navegador real (Playwright) |
| `knowledge-base/` | Base de conocimiento del dominio (fuente de verdad) |
| `CHANGES.md` | Roadmap de 20 changes con dependencias y estado |
| `openspec/` | Specs vigentes (`specs/`) y changes archivados (`changes/archive/`) |
| `AGENTS.md` / `CLAUDE.md` | Reglas para los agentes (17 reglas duras) |
| `docs/discovery/` | Informe de Discovery (`.md` + `.pdf`) y checklist |
| `docs/skills-mcp/` | TP Skills + MCP: investigación, informe de aplicación y evidencias |
| `docs/CONTINUAR.md` | Guía para quien sigue el proyecto |
| `docs/whatsapp-sesion.md` | Runbook de la sesión QR de WhatsApp |
