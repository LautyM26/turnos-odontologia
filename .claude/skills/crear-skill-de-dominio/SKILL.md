---
name: crear-skill-de-dominio
description: Genera una skill dominio-<área> (agenda, caja, clínica, facturación, WhatsApp, etc.) que resume las reglas de negocio RN vigentes de un área de la clínica, filtradas por las decisiones DD vigentes y las reglas duras de AGENTS.md, con matriz de trazabilidad RN → spec → test. Usar cuando se pida "creá la skill del dominio X", "armá la skill de caja/agenda/clínica", y SIEMPRE antes de un /opsx:propose de un change que toca un área que todavía no tiene skill dominio-* propia (por ejemplo C-12 caja, C-15 WhatsApp, C-09 clínica).
---

# crear-skill-de-dominio

Skill creadora propia del proyecto Turnos Odontología. Construida sobre la estructura de `skill-creator` (Anthropic, `github.com/anthropics/skills`) y adaptada a la fundación del repo (KB + CHANGES + OpenSpec + reglas duras).

## 1. Propósito

Generar una skill `dominio-<área>` que un agente pueda leer **en lugar de** los 11 archivos de `knowledge-base/` cuando va a programar un área. La skill generada contiene solo:

- las RN del área, ya filtradas contra las DD vigentes (nunca reglas reemplazadas);
- las reglas duras de `AGENTS.md` que aplican al área;
- la matriz de trazabilidad RN → spec → test, con celdas vacías marcadas como **pendiente**.

Por qué importa: la KB tiene reglas desactualizadas en lugares sueltos (ejemplo real: DD-10 reemplazó "WhatsApp solo API oficial" por QR, pero quedaron textos viejos en otros archivos). Un agente que lee todo sin filtrar puede implementar lo contrario de lo que decidió el equipo.

## 2. Cuándo se activa

- El usuario pide "creá la skill del dominio <X>" o "generá dominio-<x>".
- Antes de `/opsx:propose` de un change cuya área no tiene `.claude/skills/dominio-*` (revisar la matriz Change → Skills de `.atl/skill-registry.md`).
- Cuando cambió una DD o una RN de un área que ya tiene skill: se regenera para que no quede desactualizada.

No se activa para implementar código: esta skill solo produce la skill de dominio. La implementación sigue el flujo OPSX.

## 3. Entradas necesarias

| Entrada | Ejemplo | Si falta |
|---|---|---|
| Prefijo(s) RN del área (uno o más) | `RN-CA` · `RN-AG + RN-TU` | Preguntar. Los prefijos válidos son los encabezados `## Dominio:` de `knowledge-base/05_reglas_de_negocio.md` |
| Nombre del área | `caja` → skill `dominio-caja` | Derivarlo del encabezado del dominio en `05` |
| Change(s) del roadmap que la usan | `C-12` | Buscar en `CHANGES.md` qué changes citan esas RN en "Leer antes" |

## 4. Procedimiento

Ejecutar los pasos en orden. Trabajar desde la raíz del repo.

### Paso 1 — Leer las RN del dominio

```bash
grep -nE "^- \*\*RN-CA-[0-9]+" knowledge-base/05_reglas_de_negocio.md
```

Copiar cada regla con su código exacto. Contar cuántas son: ese número es el total de filas que tendrá la matriz.

### Paso 2 — Filtrar con las DD vigentes

Leer `knowledge-base/09_decisiones_y_supuestos.md` completo. Una DD está **vigente** salvo que su título diga `REEMPLAZADA` o `Histórico`. Para cada RN del paso 1:

- Si la RN dice "(modificada …, ver DD-NN)", usar el texto modificado.
- Si la RN contradice una DD vigente (ejemplo: menciona "WhatsApp oficial" o "plantilla aprobada" cuando DD-10 dice QR con número dedicado), **no copiarla literal**: escribir la versión coherente con la DD, marcar la fila con ⚠️ y anotar en la sección "Conflictos detectados" qué texto de la KB hay que corregir. Así el conflicto queda visible para el equipo en vez de esconderse.
- Si no puede resolverse con la KB, marcar ⚠️ y preguntar al usuario. No inventar decisiones de dominio.

Revisar también los SU/PA abiertos de `09` y `10_preguntas_abiertas.md` que el área usa (timeouts, cuentas MP, etc.): van como "Supuestos abiertos", nunca como reglas cerradas.

### Paso 3 — Sumar las reglas duras de AGENTS.md

Leer la sección "Reglas Duras" de `AGENTS.md` y copiar **solo** las que aplican al área, con su número. Guía rápida:

| Área | Reglas duras que suelen aplicar |
|---|---|
| Agenda/turnos | 6 (fin en servidor), 7 (TIMESTAMPTZ), 8 (exclusion GiST + 409), 9 (testcontainers), 10 (clinica_id), 13 (Promise.all + 409 en front) |
| Caja/cobros | 4 (extra='forbid'), 7 (NUMERIC ARS), 10, 12 (secretos solo backend), 17 (factura solo desde cobro) |
| Clínica/HC | 14, 15 (append-only), 16 (consentimiento + RBAC clínico) |
| WhatsApp | 12, 17 (QR con número dedicado, DD-10) |

La tabla es orientativa: confirmar contra el texto real de `AGENTS.md`.

### Paso 4 — Buscar specs, código y tests existentes

Las specs y los tests rara vez citan el código RN. La trazabilidad se hace **por significado**, siguiendo el hilo spec → requirement → test:

```bash
# a) citas explícitas del código RN
grep -rnE "RN-CA-[0-9]+" openspec/specs backend/app backend/tests frontend 2>/dev/null
# b) requirements de las specs vigentes que tratan el tema
grep -n "### Requirement" openspec/specs/*/spec.md
# c) tests que implementan esos escenarios (los verify.md/tasks.md archivados listan qué test cubre cada escenario)
grep -rn "def test_" backend/tests | grep -iE "<palabra-clave>"
cat openspec/changes/archive/*/verify.md
```

Reglas para llenar la matriz:

- **Spec**: ruta del `spec.md` + nombre exacto del `Requirement`. Solo si el requirement realmente exige la regla.
- **Test**: archivo + nombre exacto de la función `test_*`. Solo si el test comprueba la regla, no solo si la menciona.
- Celda sin evidencia → `—` y la columna Estado dice **pendiente**. Nunca completar una celda "porque seguro existe": una celda inventada es peor que una vacía, porque esconde trabajo pendiente.
- Estado: `cubierta` (spec y test), `parcial` (falta uno, o cubre solo una parte), `pendiente` (ninguno).

### Paso 5 — Escribir la skill

Copiar `templates/dominio-template.md` (en la carpeta de esta skill) a `.claude/skills/dominio-<área>/SKILL.md` y completarla. Requisitos:

- `description` con las palabras que usa la gente para pedir trabajo de esa área (ej. caja: caja, seña, cobro, saldo, Mercado Pago, webhook, anulación) y los changes que la usan. Es lo único que el agente lee para decidir activarla.
- Una fila por cada RN del paso 1, aunque esté vacía.
- Menos de ~200 líneas: es un resumen, no una copia de la KB. Para el detalle, citar el archivo de la KB.
- Datos sintéticos únicamente (regla dura 14). Sin nombres, DNI ni teléfonos reales.

### Paso 6 — Copiar y registrar

1. Copias idénticas:
   ```bash
   for d in .github/skills .opencode/skills; do mkdir -p "$d/dominio-<área>"; cp .claude/skills/dominio-<área>/SKILL.md "$d/dominio-<área>/"; done
   ```
2. `AGENTS.md` **y** `CLAUDE.md`: agregar la fila en la tabla "Skills del proyecto" con la misma edición en los dos archivos.
3. `.atl/skill-registry.md`: agregar la fila en "Project Skills" y en la matriz Change → Skills (columna "Skill de dominio").

## 5. Resultado esperado

- `.claude/skills/dominio-<área>/SKILL.md` con frontmatter y las 6 secciones de la plantilla, incluida la matriz de trazabilidad.
- Copias idénticas en `.github/skills/` y `.opencode/skills/`.
- La skill registrada en `AGENTS.md`, `CLAUDE.md` y `.atl/skill-registry.md`.
- Un resumen al usuario: cantidad de RN, cuántas cubiertas/parciales/pendientes y la lista de conflictos ⚠️ detectados con la KB.

## 6. Criterios de revisión

Cada criterio se cumple o no. Correr el comando y reportar el resultado al usuario.

| # | Criterio | Cómo verificarlo |
|---|---|---|
| 1 | Cada RN del dominio aparece en la matriz, aunque sea con celdas vacías | Comparar `grep -cE "^- \*\*RN-XX-" knowledge-base/05_reglas_de_negocio.md` con la cantidad de filas `\| RN-XX-` de la matriz |
| 2 | Ninguna regla contradice una DD vigente (ej. no dice "QR prohibido" ni "API oficial" para WhatsApp) | `grep -niE "QR prohibido\|API oficial\|plantilla aprobada" .claude/skills/dominio-<área>/SKILL.md` solo puede aparecer dentro de "Conflictos detectados" |
| 3 | Toda ruta de archivo citada existe | Extraer las rutas citadas y probar `test -e` para cada una (ver script abajo) |
| 4 | La `description` usa las palabras con las que se pide ese trabajo | Leer el frontmatter: debe nombrar el área, sus sustantivos clave y el/los change(s) |
| 5 | Registrada en todos los índices y `AGENTS.md` = `CLAUDE.md` | `grep -l dominio-<área> AGENTS.md CLAUDE.md .atl/skill-registry.md` devuelve los 3 y `diff AGENTS.md CLAUDE.md` no imprime nada; `diff -r` entre las 3 copias tampoco |
| 6 | No incluye datos reales de pacientes (regla dura 14) | Revisión manual: solo datos sintéticos o ninguno |

Atajo: `scripts/verificar.py` (en la carpeta de esta skill) chequea los criterios 1, 2, 3 y 5 y muestra lo necesario para revisar 4 y 6 a mano. Sale con código 1 si algo falla:

```bash
python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-agenda RN-AG RN-TU
```

Script manual para el criterio 3 (si no hay Python):

```bash
f=.claude/skills/dominio-<área>/SKILL.md
grep -oE '`(backend|frontend|openspec|knowledge-base|docs|\.atl|\.claude)/[^` ]+`' "$f" | tr -d '`' | sort -u \
  | while read -r p; do [ -e "$p" ] && echo "OK  $p" || echo "FALTA $p"; done
```

Si un criterio falla, corregir la skill y volver a correr la verificación antes de darla por terminada.
