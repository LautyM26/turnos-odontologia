# Verify — huecos-y-sobreturnos (C-05c)

Fecha: 2026-11-17. Resultado: **VERDE, revisado y archivado** el 2026-11-17.

## Entorno

- Windows 11, Docker Desktop sobre WSL2; PostgreSQL `postgres:16-alpine` vía testcontainers (nunca SQLite).
- Python 3.12.10 (venv `.venv` en la raíz del repo), pytest 9.2.0, ruff 0.17.5.
- Diseño D1–D6 aprobado por el usuario el 2026-11-17, antes del apply (governance CRÍTICO).
- Base: `main` en `453695c`, que ya incluye C-09, C-10, C-18 y C-19 del equipo.

## Cambio respecto del diseño: migración 011 en lugar de 007

El diseño reservaba `007_sobreturno_huecos` con `down_revision = "006_turno_transicion"`. Al hacer el pull, C-09/C-18/C-19 ya habían encadenado `006 → 008 → 009 → 010`. Insertar una 007 en el medio haría que una base que ya está en la 010 la diera por aplicada sin crear las columnas. Por eso la migración quedó al final de la cadena como **`011_sobreturno_huecos`** (`down_revision = "010_recetas_externas"`). `proposal.md`, `design.md`, `tasks.md`, `CHANGES.md` y `docs/CONTINUAR.md` se actualizaron. El comportamiento es el mismo.

Efecto colateral: dos tests del equipo fijaban el head en `010_recetas_externas`. Se ajustaron sin cambiar su intención:

- `test_migracion_010.py::test_un_unico_head_y_encadenado_a_la_009` ahora exige **un único head**.
- `test_exportacion_api.py::test_manifest_con_clinica_fecha_con_zona_esquema_y_excluidas` compara `version_esquema` con el head real de Alembic.

## Comandos (desde la raíz del repo)

```
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/ruff check backend
openspec validate huecos-y-sobreturnos --strict
```

## Resultados

- Suite completa: **1232 passed, 0 failed, 0 skipped** (15 min 25 s).
- `ruff check backend`: limpio.
- `openspec validate --strict`: válido.
- Después de la suite se agregó `MATERIALIZED` a los CTEs de huecos (ver EXPLAIN). Los archivos afectados se volvieron a correr: huecos, migraciones 010/011 y exportación, **46 passed**.
- Tests nuevos: **48**.

| Archivo | Tests nuevos | Escenarios de la spec que cubre |
|---|---|---|
| unit/test_turno_schemas.py | 10 | contrato D4: motivo sii sobreturno, blanco, >500, `sobreturno` no booleano |
| test_settings.py | 3 | `AGENDA_PASO_MIN` fuera de 5–60 (y default 15 en un test existente) |
| integration/test_migracion_011.py | 3 | columnas, CHECKs, predicado `NOT es_sobreturno`, downgrade a 010 + re-upgrade, único head |
| integration/test_turnos_db_constraints.py | 3 (+1 ajustado) | sobreturno `asistido` superpuesto sin 23P01; CHECK de coherencia 23514 |
| integration/test_sobreturnos_api.py | 8 | "Recepcionista da un sobreturno sobre un horario ocupado", "Sobreturno sin motivo", "Motivo sin sobreturno", "Sobreturno sobre un feriado", "Un sobreturno no ocupa el horario", "Sobreturno superpuesto pasa a asistido", odontólogo → 403 |
| integration/test_huecos_servicio.py | 11 | "Día libre devuelve huecos cada paso", "Turno del profesional ocupa el hueco" (contiguo), "Bloqueo de clínica", bloqueo de profesional y de sillón, "Un sillón ocupado deja el otro", "Turno cancelado o sobreturno no restan", "Ventana que empieza en el pasado", paso configurable, ventana inválida, **propiedad**: todo hueco devuelto acepta `crear_turno` en cada sillón listado |
| integration/test_huecos_api.py | 10 | 200 con `fin` y sillones, lista vacía `[]`, "Ventana mayor a 7 días", `hasta <= desde`, fecha sin zona, "Prestación inactiva", "Profesional de otra clínica", "Odontólogo consulta su agenda", "Odontólogo consulta otra agenda", "Sin autenticación" |

## Prueba de mutación

Se quitó `NOT es_sobreturno AND` de `_ACTIVO_011` en la migración 011 y se corrieron los tests de constraints, sobreturnos y migración: **7 failed, 28 passed**. Fallaron:

- `test_turno_no_activo_no_ocupa_el_horario[sobreturno]`
- `test_sobreturno_puede_superponerse_a_un_turno_activo`
- `test_recepcionista_da_un_sobreturno_sobre_un_horario_ocupado`
- `test_un_sobreturno_no_ocupa_el_horario`
- `test_sobreturno_superpuesto_pasa_a_asistido`
- los 2 tests de predicado de `test_migracion_011.py`

Después se restauró la migración.

## EXPLAIN ANALYZE (ventana de 7 días, paso 15, prestación de 30 min)

Base de desarrollo (`postgres:16-alpine`, seed sintético: 1 profesional habilitado en 1 sillón), 671 candidatos:

- Primera versión (CTEs inlineados): el subplan de sillones se ejecutaba una vez por candidato (`loops=671`). Planning 24 ms, **Execution 9,5 ms**.
- Con `libre_prof`/`libre_sillon AS MATERIALIZED`: cada CTE se ejecuta una vez (`loops=1`), con `Index Scan using ex_turno_sillon_rango` y `ix_bloqueo_clinica_activo`. Planning 14 ms, **Execution 3,8 ms**.

## Prueba manual (uvicorn + API real, base de desarrollo en la 011)

Script con `urllib` contra `http://localhost:8000`. Admin seed, paciente sintético (`paciente.manual@ejemplo.test`), prestación de 30 min, turno a 2 minutos en el futuro:

```
1) huecos antes: 200 ["18:06", "18:21", "18:36"]
2) turno normal: 201 {"estado": "reservado", "es_sobreturno": false}
3) huecos con turno: 200 ["18:36"]
4) mismo horario sin sobreturno: 409 {"detail": "Horario no disponible"}
5) sobreturno: 201 {"estado": "reservado", "es_sobreturno": true, "motivo_sobreturno": "urgencia sintética"}
6) huecos con sobreturno (igual que 3): 200 ["18:36"]
7) confirmar normal: 200 {"estado": "confirmado"}
   (espera hasta el inicio del turno)
8) asistido normal: 200 {"estado": "asistido", "es_sobreturno": false}
8) asistido sobreturno: 200 {"estado": "asistido", "es_sobreturno": true}
```

El sobreturno no consume el hueco (paso 6 = paso 3), y los dos turnos superpuestos pasan a `asistido` sin chocar con la constraint.

## Trazabilidad

- KB `04_modelo_de_datos.md` §Turno: marca `es_sobreturno`/`motivo_sobreturno` y estado `sobreturno` en desuso.
- README: comando de tests del change. `AGENTS.md`/`CLAUDE.md` no se tocaron.
- `dominio-agenda`: RN-AG-04 pasa a **cubierta** y RN-AG-03 suma los tests de huecos (resumen: 5 cubiertas · 2 parciales · 3 pendientes). Las copias en `.github/skills` y `.opencode/skills` son idénticas.
- `verificar.py dominio-agenda RN-AG RN-TU`: **OK** después del archive (la spec `schedule-availability` nació en el sync; antes era la única ruta inexistente).

## Archivo

- Revisado por el usuario el 2026-11-17 y archivado con `openspec archive` como `2026-11-17-huecos-y-sobreturnos`: `appointments` +3 requirements y 1 modificado; `schedule-availability` creada con 5 requirements. `openspec validate --specs`: 26/26.
