# Informe de aplicación — Skill propia + MCP

Proyecto Turnos Odontología · TP Skills + MCP (Metodología I) · 2026-11-16 · Estado: **terminado**. Skill propia integrada, MCP operativo y change C-05b preparado (sin implementar).

## 1. Resultados

| Entregable | Estado | Dónde |
|---|---|---|
| Skill creadora propia `crear-skill-de-dominio` (hecha con `skill-creator` de Anthropic) | ✅ | `.claude/skills/crear-skill-de-dominio/` |
| Skills generadas `dominio-agenda` (RN-AG + RN-TU) y `dominio-caja` (RN-CA) | ✅ los 6 criterios pasan | `.claude/skills/dominio-*/`, [evidencia E2](evidencias/README.md#e2--ejecución-de-crear-skill-de-dominio-genera-dominio-agenda-y-dominio-caja) |
| Copias para Copilot y OpenCode | ✅ idénticas (`diff -r`) | `.github/skills/`, `.opencode/skills/` |
| Activación automática de las skills | ✅ 9/9 | [evidencia E3](evidencias/README.md#e3--prueba-de-activación-el-agente-encuentra-y-usa-las-skills-solo) |
| MCP Context7 configurado, conectado y usado | ✅ `resolve-library-id` + `query-docs` | `.mcp.json`, `README.md` §Skills propias y MCP, [evidencia E4](evidencias/README.md#e4--herramienta-real-del-mcp-context7-preparación-de-c-05b) |
| Change C-05b `transiciones-estado-turno` preparado con skill + MCP | ✅ 8 requisitos, 18 escenarios, `openspec validate --strict` OK; después implementado, verificado (615 tests) y archivado | `openspec/changes/archive/2026-11-16-transiciones-estado-turno/`, [evidencia E5](evidencias/README.md#e5--uso-de-dominio-agenda-en-la-preparación-de-c-05b) |

Aporte al change:

- `dominio-agenda` fijó el alcance: RN-TU-01 estaba parcial. También señaló el código a reutilizar y expuso 3 reglas ambiguas que el usuario resolvió (`design.md` D1–D3).
- Context7 aportó la decisión D5: `with_for_update()` + `populate_existing` para el escenario borde de transiciones concurrentes.
- La spec tiene escenarios de los tres tipos pedidos:
  - funcionamiento esperado: "Recepcionista confirma un turno reservado";
  - error de negocio: "Turno cancelado no puede confirmarse";
  - borde: "Ausente antes de la hora", "Asistido exactamente a la hora de inicio" y "Dos cancelaciones simultáneas".
- Cada escenario tiene en `tasks.md` el test que lo verificará.

Trazabilidad que muestran las skills: **Agenda** tiene 3 reglas cubiertas, 4 parciales y 3 pendientes. **Caja** tiene 0 cubiertas, 1 parcial y 2 pendientes. En agenda, RN-TU-01 (transiciones de estado) está parcial, y eso justifica el alcance de C-05b.

## 2. Archivos modificados y motivo

| Archivo | Cambio | Motivo |
|---|---|---|
| `.claude/skills/crear-skill-de-dominio/**` (nuevo) | Skill, plantilla, script de verificación y casos de prueba | Skill propia pedida por la consigna |
| `.claude/skills/dominio-{agenda,caja}/SKILL.md` (nuevos) | Skills generadas | Demostración: validación (agenda) y uso hacia adelante (caja) |
| `.github/skills/…`, `.opencode/skills/…` (nuevos) | Copias idénticas, sin `evals/` | Que Copilot y OpenCode encuentren las skills (misma convención que `openspec-*`) |
| `.mcp.json` (nuevo) | Servidor Context7 por HTTP, sin secretos | Configuración reproducible del MCP en el scope del proyecto |
| `AGENTS.md` = `CLAUDE.md` | Tabla "Skills del proyecto", sección "Integraciones MCP"; "9 decisiones" → 10; "30 reglas" → 37; el registry figuraba "no versionado" y sí lo está | Integrar las incorporaciones y corregir conteos desactualizados |
| `.atl/skill-registry.md` | Project Skills, compact rules, columna "Domain skill" en la matriz Change → Skills (con C-05b), sección MCP Integrations; quitado "QR prohibido" y la referencia a "Meta Cloud API"; Project Conventions apunta a AGENTS/CLAUDE | Registro pedido por la consigna + contradicciones con DD-10 |
| `knowledge-base/05_reglas_de_negocio.md` | RN-TU-02 reescrita según DD-10, con nota de qué decía antes | Conflicto detectado por la skill (ver §3) |
| `knowledge-base/09_decisiones_y_supuestos.md` | Nota en los trade-offs de DD-08 ("WhatsApp oficial" → DD-10) | Mismo conflicto, en otro archivo |
| `knowledge-base/README.md` | Puntero a las skills `dominio-*` en el quick start | Que quien entra a la KB sepa que existe el resumen por área |
| `README.md` | Sección "Skills propias y MCP" (requisitos, config, verificación, troubleshooting, límites) | Reproducibilidad pedida por la consigna |
| `docs/skills-mcp/**` (nuevo) | Ficha, este informe y evidencias | Entregables |
| `CHANGES.md` | Entrada nueva C-05b (propósito, alcance, exclusiones, dependencias, qué adelanta de C-05) y línea de estado de C-05 | Roadmap actualizado según la convención; el change queda `[ ]` pendiente |
| `openspec/changes/archive/2026-11-16-transiciones-estado-turno/**` (nuevo) | proposal, design, tasks y delta de `specs/appointments` | Preparación SDD del change (paso 7) |

No se regeneró la fundación ni se marcó ningún change como implementado.

## 3. Revisión crítica

**a) Error en resultados previos de agentes, detectado por la skill (antes/después).** La fundación fue generada por agentes (`skill-registry`, `agents-md-generator`) y tenía reglas contrarias a la decisión vigente DD-10.

- **Cómo se detectó:** el paso 2 de `crear-skill-de-dominio` (filtrar las RN contra las DD vigentes) al generar `dominio-agenda`.
- **Fuente que permitió corregirlo:** DD-10 en `09`.

| | Antes | Después |
|---|---|---|
| `05` RN-TU-02 | "el recordatorio sale por WhatsApp oficial (plantilla aprobada)…" | "(modificada 2026-11-16, ver DD-10): …WhatsApp (sesión QR con número dedicado, texto base interno)…" |
| `.atl/skill-registry.md` | "Constraints: solo API oficial (DD-02, RN-WA-01), QR prohibido" | "Constraints (DD-10…): QR session with a dedicated number behind `MensajeriaPort`…" |
| `AGENTS.md` | "9 decisiones DD-01…DD-09" · "30 reglas" | "10 decisiones DD-01…DD-10" · "37 reglas" |

**b) Sugerencia inadecuada en la propuesta (hecha con ayuda de IA).** La propuesta decía: "en Caja, todas [las filas] vacías". Al trazar por significado, la skill encontró que **RN-CA-03 ya está parcialmente cubierta**: `require_anulacion_caja()` en `backend/app/api/permissions.py`, el requirement "Sobreturnos y anulaciones chequeados por rol" de `openspec/specs/access-control/spec.md` y `test_anulacion_caja_solo_admin`.

- **Cómo se detectó:** grep del código RN en `backend/app` (paso 4 de la skill) y lectura del test.
- **Corrección:** la fila quedó como **parcial**, no vacía.
- **Precisión sobre la afirmación "ninguna RN aparece en los tests":** es verdadera para el código RN literal, pero 8 reglas tienen tests por significado (7 de agenda y RN-CA-03).

**c) Límite observado en la activación.** En la prueba E3, un pedido sobre WhatsApp también cargó `dominio-caja`. El resultado final fue correcto (se activó la skill creadora), pero muestra que una skill de dominio puede cargarse como "ejemplo" fuera de su área. Mitigación posible si se repite: aclarar en la `description` de cada `dominio-*` que es solo para su área.

**d) Omisión de la skill: solo filtra las RN.** Durante la preparación de C-05b apareció otro texto contrario a DD-10 que la skill **no** detectó, porque su paso 2 solo filtra `05` contra `09`:

- `knowledge-base/06_funcionalidades.md:44` (US-005: "Plantillas aprobadas…");
- `knowledge-base/04_modelo_de_datos.md:97` (seed: "Plantillas WhatsApp aprobadas…");
- el plan de validación de SU-07 en `09` ("definir BSP…").

Cómo se detectó: `grep -i "plantillas aprobadas\|BSP"` sobre la KB al revisar el Flujo 2. No se corrigió en este change porque es del dominio WhatsApp (C-15): queda para cuando se genere `dominio-whatsapp`. Mejora propuesta para la skill: extender el paso 2 a `04`, `06` y `07`.

**e) Problemas de compatibilidad resueltos.**

- `run_eval.py` de skill-creator no corre en Windows (`select.select` sobre pipes). Se reemplazó por `evidencias/activacion.py`.
- `claude.cmd` reescapa los argumentos al pasar por `cmd.exe`. El script llama directamente a `claude.exe`.
- La documentación no confirma en qué plugin viene `skill-creator` (queda pendiente en la ficha).

## 4. Limitaciones

- Los casos de prueba de la skill creadora se corrieron en la misma sesión que la escribió, con contexto. No hubo corridas aisladas ni comparación sin skill (baseline). Se pueden repetir con `claude plugin eval`.
- La trazabilidad "por significado" depende de leer bien specs y tests. El script verifica que las rutas existan, no que el test realmente compruebe la regla: eso sigue siendo revisión humana.
- Los tests que cita la matriz se re-ejecutaron el 2026-11-16, después de instalar Docker Desktop + WSL2: `python -m pytest backend/tests -q` → **530 passed** (7 min 47 s) y `ruff check backend` → *All checks passed!* (baseline previo a C-05b).
- `claude mcp list` desde una terminal externa muestra Context7 "Pending approval" aunque la sesión interactiva ya lo use. La aprobación de servidores de `.mcp.json` es por sesión interactiva.
- C-05b se implementó y archivó después de la preparación (fuera del alcance de este TP, que pedía solo prepararlo). Cuenta para el mínimo del TPI.
