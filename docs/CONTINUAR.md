# Cómo continuar el proyecto (traspaso al equipo)

Escrito el 2026-11-16 por Matheo (con Claude Code). Explica el estado actual, cómo levantar el entorno y qué changes puede tomar cada uno **sin depender del trabajo de agenda de Matheo**.

---

## 1. Estado actual

| Change | Estado | Dónde |
|---|---|---|
| C-01, C-02, C-03, C-04, C-08 | ✅ archivados | `openspec/changes/archive/` |
| `crear-turno-sin-solapamientos` (recorte C-05) | ✅ archivado | ídem |
| **C-05b `transiciones-estado-turno`** | ✅ archivado (615 tests en verde) | `openspec/changes/archive/2026-11-16-transiciones-estado-turno/` |
| C-05c `huecos-y-sobreturnos` | ✅ archivado 2026-11-17 (C-05 completo) | `openspec/changes/archive/2026-11-17-huecos-y-sobreturnos/` |
| C-05d `horario-atencion` | ✅ archivado 2026-11-17 | `openspec/changes/archive/2026-11-17-horario-atencion/` |
| **C-09 `odontograma-evolucion`** | ✅ archivado 2026-11-17 (813 tests) | `openspec/changes/archive/2026-11-17-odontograma-evolucion/` |
| **C-10 `clinica-frontend`** | ✅ archivado 2026-11-17 (vitest 202 + E2E Playwright con capturas) | `openspec/changes/archive/2026-11-17-clinica-frontend/` |
| **C-18 `consentimientos-cumplimiento`** | ✅ archivado 2026-11-17 (1057 tests) | `openspec/changes/archive/2026-11-17-consentimientos-cumplimiento/` |
| **C-19 `recetas-partner-renapdis`** | ✅ archivado 2026-11-17 (1184 tests) | `openspec/changes/archive/2026-11-17-recetas-partner-renapdis/` |
| Resto (C-06, C-07, C-11 … C-17) | ⏳ pendientes | `CHANGES.md` |

**TPI:** con 3 integrantes el mínimo es de 6 changes. Ya hay **11 archivados**. Cada change nuevo suma, y todos tenemos que poder explicar el que hicimos.

**Migraciones tomadas:** 008 C-09, 009 C-18, 010 C-19, 011 C-05c, 012 C-05d (head actual: `012_horario_atencion`; la 007 quedó sin usar). La próxima es la 013 con `down_revision` = el head del momento: `python -m alembic -c backend/alembic.ini heads` tiene que mostrar un único head (correrlo desde la raíz).

**Frontend:** C-10 agregó el login, el router de datos (`frontend/src/router.tsx`, ya no existe `App.tsx`) y las rutas protegidas. C-07 (agenda) debe agregar `/agenda` dentro del layout autenticado, reutilizando ese shell. Demo: `backend/scripts/seed_demo_clinica.py` (usuarios `@clinica-piloto.test`, contraseña por `SEED_DEMO_PASSWORD`), ver README §"Demo clínica".

**Skill propia y MCP (obligatorios en el TPI):** ya están hechos y documentados en `docs/skills-mcp/`. Cada uno los usa en su change (ver la sección 4). Eso aporta evidencia de uso para el video.

---

## 2. Reparto propuesto (sin pisarnos)

Matheo sigue con la **cadena de agenda**: C-06 → C-07 (C-05c y C-05d ya archivados). **Ojo C-05d:** un profesional sin horario cargado no acepta turnos normales; cargarlo con `PUT /api/admin/profesionales/{id}/horario`. No toquen `backend/app/domain/agenda/turnos.py`, `huecos.py`, `api/turnos.py` ni `api/agenda.py` sin avisar.

Changes que **no dependen** de C-05c/C-05d y se pueden hacer ya (sus dependencias están archivadas):

| Change | Depende de | Sugerencia | Skill de dominio a generar antes de proponer |
|---|---|---|---|
| ~~C-09, C-10, C-18, C-19~~ | ✅ ya archivados (Lautaro, 2026-11-17) | — | `dominio-clinica` y `dominio-cumplimiento` ya existen |
| **C-15 `whatsapp-bidireccional`** | C-05 (alta + estados ✓) | Integrante B | `dominio-whatsapp` (RN-WA + RN-TU-02/03) |

Notas:

- **C-15** usa las transiciones de C-05b: para confirmar o cancelar por WhatsApp hay que llamar a `transicionar_turno(...)` de `backend/app/domain/agenda/turnos.py`. **No dupliquen la tabla de estados.** No necesita huecos, salvo la opción "reprogramar", que queda para C-17.
- **No tomen todavía** C-11/C-12/C-13/C-14: C-11 genera turnos sugeridos; la consulta de huecos (C-05c, `GET /api/agenda/huecos`) ya existe. C-16 y C-17 dependen de C-15.
- Para C-15, los textos `knowledge-base/04_modelo_de_datos.md:97` y `06_funcionalidades.md:44` todavía dicen "plantillas aprobadas", que contradice DD-10 (WhatsApp por QR). Corríjanlos al generar `dominio-whatsapp`.

---

## 3. Preparar el entorno (una vez por PC)

Requisitos: Git, Python 3.12, Node 22+, **Docker Desktop corriendo** (en Windows necesita WSL2: `wsl --install` como admin y reiniciar) y Claude Code.

```powershell
git clone https://github.com/LautyM26/turnos-odontologia.git
cd turnos-odontologia
git pull                                    # traer la rama/merge con lo último
npm i -g @fission-ai/openspec               # CLI de OpenSpec (lo usan /opsx:*)
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn "pydantic[email]" pydantic-settings sqlalchemy "psycopg[binary]" alembic bcrypt PyJWT slowapi phonenumbers python-multipart pytest httpx "testcontainers[postgres]" ruff
docker version                              # tiene que mostrar "Server"
python -m pytest backend/tests -q           # ~8 min; tiene que dar 615 passed
ruff check backend                          # All checks passed!
```

Problemas conocidos:

- **PostgreSQL de Windows en el puerto 5432:** si tienen uno instalado, `docker compose up db` no puede usar ese puerto. Los tests no lo necesitan. Para levantar la API a mano, ver `README.md` (base en el puerto 55432).
- **MCP Context7:** al abrir Claude Code en la carpeta del repo, aprobar `context7` (viene en `.mcp.json`) y verificar con `/mcp`. Si `claude mcp list` desde otra terminal dice "Pending approval", es normal: se aprueba desde la sesión interactiva.

---

## 4. Flujo para cada change (el mismo que usamos en C-05b)

1. **Generar la skill de dominio del área**, si no existe. En Claude Code:
   `creá la skill del dominio clínica (RN-CL) para C-09`
   - Se activa `crear-skill-de-dominio` y genera `.claude/skills/dominio-clinica/`, con copias e índices.
   - Verificar con: `python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-clinica RN-CL` → `RESULTADO: OK`.
2. **Leer** la ficha del change en `CHANGES.md` (dependencias y "Leer antes") y la skill generada.
3. **`/opsx:propose <nombre-del-change>`**.
   - Si una regla es ambigua, el agente pregunta. Decidan y que quede justificado en `design.md`.
   - Usar **Context7** para la doc de librerías (ej. "usá Context7 para la doc de SQLAlchemy JSONB" en C-09).
   - La spec necesita al menos un escenario feliz, uno de error de negocio y uno de borde.
4. **Revisar y aprobar `design.md`.** Los changes CRÍTICOS (C-09, C-18…) requieren aprobación humana antes de codificar.
5. **`/opsx:apply <nombre>`** con TDD: primero los tests y después el código. Integración solo con testcontainers (nunca SQLite).
6. **Verificar:**
   - suite completa + `ruff check backend` en verde;
   - prueba manual en Swagger (`/docs`);
   - dejar todo en `verify.md` dentro del change.
   - Consejo de C-05b: hagan una prueba de mutación (romper a propósito la línea clave y ver que algún test falle). Así encontramos un test que no detectaba nada.
7. **`/opsx:archive <nombre>`**, actualizar la matriz de la skill de dominio y marcar `[x]` en `CHANGES.md`.
8. **Commits:** conventional commits, **sin** co-autoría de IA (regla dura 3), en una rama propia. Para el TPI conviene que cada uno commitee lo suyo con su usuario.

Las 17 reglas duras están en `AGENTS.md` (= `CLAUDE.md`). Las más fáciles de olvidar: 4 (`extra='forbid'`), 7 (montos en NUMERIC y tiempos en TIMESTAMPTZ), 10 (`clinica_id` + índice + test de aislamiento), 14 (solo datos ficticios) y 15 (HC append-only).

---

## 5. Migraciones: evitar choques

Cada change con backend suma una migración Alembic en cadena (`down_revision`). Si dos personas crean "la siguiente" a la vez, quedan **dos heads** y `alembic upgrade head` falla.

- **Tomado:** `012_horario_atencion` (C-05d, Matheo, `down_revision = "011_sobreturno_huecos"`).
- **Tomado:** `011_sobreturno_huecos` (C-05c, Matheo, `down_revision = "010_recetas_externas"`). La 007 quedó sin usar: no insertar migraciones en medio de la cadena, porque una base que ya está más adelante las da por aplicadas.
- Quien cree una migración nueva usa el número siguiente al head (hoy 013) y pone como `down_revision` el head **del momento en que mergea**. Antes de mergear: `cd backend && alembic heads` tiene que mostrar un único head. Si hay dos, actualizar el `down_revision` de su migración para colgarla de la otra.
- Avisen en el grupo qué número toman.

---

## 6. Memoria del proyecto (engram)

`.engram/` (`manifest.json` + `chunks/`) es la memoria persistente del agente. Se sincroniza con commits `chore(engram): sync project memory`. Hagan `git pull` antes de empezar para tener la última versión. Si su agente usa engram, va a ver las decisiones de esta sesión.

**Fuente de verdad:** `CHANGES.md`, `knowledge-base/`, `openspec/` y `docs/skills-mcp/`. Engram es un complemento.

---

## 7. Pedido sugerido para arrancar (copiar en Claude Code)

```
Leé docs/CONTINUAR.md, AGENTS.md y la ficha de <C-09 odontograma-evolucion> en CHANGES.md.
Primero creá la skill del dominio <clínica (RN-CL)> con crear-skill-de-dominio y verificala.
Después hacé /opsx:propose <odontograma-evolucion> usando esa skill y Context7 para la doc
de las librerías. Preguntame las reglas ambiguas antes de decidir. No hagas commit.
```
