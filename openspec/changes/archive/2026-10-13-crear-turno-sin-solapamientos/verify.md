# Verify — crear-turno-sin-solapamientos

Fecha: 2026-10-13. Resultado: **VERDE, listo para archivar** (no se archivó ni se hizo commit).

## Entorno
- Docker Desktop, Server 29.8.2; PostgreSQL `postgres:16-alpine` vía testcontainers (nunca SQLite).
- Python 3.14.7 (venv `C:\Users\math3\AppData\Local\Temp\venv_turnos`), pytest 9.1.1, ruff.
- Windows 11; `docker.exe` no está en PATH: se antepuso `...\DockerDesktop\resources\bin`.

## Comandos (desde la raíz del repo)
```
export PATH="/c/Users/math3/AppData/Local/Programs/DockerDesktop/resources/bin:$PATH"
<venv>/Scripts/python.exe -m pytest backend/tests -q
<venv>/Scripts/python.exe -m ruff check backend
openspec validate crear-turno-sin-solapamientos --strict
```
`python -m pytest backend/tests -q` funciona tal cual desde la raíz (como documenta el README); no hizo falta cambiar la config.

## Resultados
- Primera corrida completa: 4 failed, 526 passed (242 s). Tras los fixes de abajo: **530 passed, 0 failed, 0 skipped** (196 s).
- Tests nuevos del change: **75** (de 530; los 455 restantes son preexistentes).

| Archivo | Tests | Resultado |
|---|---|---|
| unit/test_turno_schemas.py | 14 | passed |
| unit/test_turno_errores.py | 5 | passed |
| integration/test_migracion_005.py | 4 | passed |
| integration/test_turnos_db_constraints.py | 21 (parametrizados) | passed |
| integration/test_turnos_api.py | 29 (parametrizados) | passed |
| integration/test_turnos_concurrencia.py | 2 | passed |

- Concurrencia, 3 corridas consecutivas: `2 passed` / `2 passed` / `2 passed` (~5.4 s c/u). Estable.
- `ruff check backend`: All checks passed.
- `openspec validate crear-turno-sin-solapamientos --strict`: valid.
- Fallas preexistentes ajenas al change: ninguna.

## Fixes durante verify (4 fallas, todas de TEST; el código y el spec no se tocaron)
1. `test_migracion_004.py::test_downgrade_elimina_004_y_reupgrade_restaura`: hacía `downgrade "-1"`, que desde head=005 baja solo la 005 y no la 004. Test obsoleto por la nueva migración head. Ahora `downgrade "003_clinica_catalogo"` (misma aserción, intacta).
2. `test_turnos_api.py::test_inicio_naive_422_sin_fila`: bug de helper (`_post(..., inicio=naive)` pasaba `inicio` dos veces → `TypeError`). Ahora arma el body y reemplaza `inicio` por el valor naive; aserción 422 + sin fila igual.
3. `test_turnos_db_constraints.py::...23514[fin_igual]` y `[fin_menor]`: `_a(..., fin=..., **cambio)` duplicaba el kwarg `fin` (`TypeError`). Se fusionan los dicts.
4. `fin_menor` (fin < inicio): al corregir (3) se vio que Postgres rechaza la fila antes del CHECK, porque la columna generada `rango` (`tstzrange`) falla con sqlstate `22000` ("range lower bound must be less than or equal to range upper bound"). El spec exige que la base rechace `fin <= inicio` sin fijar el código; `fin == inicio` sigue cubierto por el CHECK `23514`. Se separó `fin_menor` en `test_fin_menor_que_inicio_rechazado_por_la_base` que exige `DBAPIError` con sqlstate `22000`. No se debilitó ninguna aserción: la fila se rechaza igual. Además se acortó una línea (ruff E501).

## Trazabilidad escenario → test (29 escenarios del spec)
| # | Requirement / Scenario | Test(s) |
|---|---|---|
| 1 | Alta / Recepcionista crea turno (happy path) | api: `test_recepcionista_crea_turno_201_con_fin_calculado_y_get`, `test_inicio_con_offset_se_normaliza_y_admin_tambien_crea`; unit: `test_turno_schemas.py` |
| 2 | Alta / Cliente intenta fijar fin o duración | api: `test_fin_o_duracion_en_body_422_sin_fila`; unit schemas (extra forbid) |
| 3 | Alta / Inicio sin zona horaria | api: `test_inicio_naive_422_sin_fila`; unit schemas |
| 4 | Alta / Turno en el pasado | api: `test_turno_en_el_pasado_422_e_inicio_igual_a_ahora_201` |
| 5 | Prof. / Profesional ocupado en otro sillón | api: `test_profesional_ocupado_en_otro_sillon_409`; db: `test_superpuesto_por_profesional_en_otro_sillon_23P01` |
| 6 | Sillón / Sillón ocupado por otro profesional | api: `test_sillon_ocupado_por_otro_profesional_409`; db: `test_superpuesto_por_sillon_con_otro_profesional_23P01` |
| 7 | Semiabiertos / Empieza justo cuando termina otro | api: `test_turno_contiguo_201`; db: `test_turnos_contiguos_no_se_superponen`, `test_rango_generado_es_semiabierto` |
| 8 | Semiabiertos / Termina justo cuando empieza un bloqueo | api: `test_bloqueo_del_profesional_409_y_contiguo_201` |
| 9 | Activos / Turno cancelado libera el hueco | api: `test_turno_no_activo_libera_el_hueco_201` (param); db: `test_turno_no_activo_no_ocupa_el_horario`, `test_sobreturno_puede_superponerse_a_un_turno_activo` |
| 10 | Activos / Turno dado de baja libera el hueco | api: `test_turno_no_activo_libera_el_hueco_201` (is_active=false) |
| 11 | Bloqueos / del profesional | api: `test_bloqueo_del_profesional_409_y_contiguo_201` |
| 12 | Bloqueos / del sillón | api: `test_bloqueo_del_sillon_409` |
| 13 | Bloqueos / de clínica | api: `test_bloqueo_de_clinica_409_para_cualquier_recurso` |
| 14 | Bloqueos / de otro profesional no impide | api: `test_bloqueo_de_otro_profesional_o_inactivo_no_impide` |
| 15 | Concurrencia / Doble clic concurrente | conc: `test_cinco_pedidos_identicos_un_201_y_cuatro_409`, `test_dos_pedidos_que_compiten_solo_por_el_sillon` |
| 16 | Persistencia / Inserción directa superpuesta por profesional | db: `test_superpuesto_por_profesional_en_otro_sillon_23P01` |
| 17 | Persistencia / Inserción directa superpuesta por sillón | db: `test_superpuesto_por_sillon_con_otro_profesional_23P01` |
| 18 | Referencias / Paciente dado de baja | api: `test_referencias_invalidas_422_sin_persistir[paciente_inactivo]` |
| 19 | Referencias / Prestación inactiva | api: `...[prestacion_inactiva]` |
| 20 | Referencias / Profesional con agenda inactiva | api: `...[agenda_inactiva]` |
| 21 | Referencias / Profesional no habilitado en el sillón | api: `...[no_habilitado]` |
| 22 | Referencias / Referencia de otra clínica | api: `...[profesional_de_B]`, `[sillon_de_B]`, `[paciente_de_B]`, `[prestacion_de_B]`, `test_referencia_inexistente_422`; db: `test_fk_compuesta_rechaza_referencias_de_otra_clinica_23503` |
| 23 | Rol / Admin crea un turno | api: `test_inicio_con_offset_se_normaliza_y_admin_tambien_crea` |
| 24 | Rol / Odontólogo no crea turnos | api: `test_odontologo_403_aun_con_body_invalido_y_sin_fila` (lectura permitida: `test_odontologo_puede_leer_un_turno`) |
| 25 | Rol / Sin autenticación | api: `test_sin_token_401`, `test_turnos_no_es_ruta_publica` |
| 26 | Tenant / Mismo horario en otra clínica | api: `test_misma_hora_en_otra_clinica_201_y_get_ajeno_404`; db: `test_mismo_rango_en_otra_clinica_es_valido` |
| 27 | Tenant / Lectura de un turno ajeno | api: `test_misma_hora_en_otra_clinica_201_y_get_ajeno_404` |
| 28 | Tenant / Consulta cruzada sin filas | db: `test_repositorio_de_otra_clinica_no_ve_turnos_ajenos` |
| 29 | Esquema / Upgrade y downgrade limpios | mig: `test_upgrade_head_crea_turno_exclusiones_indices_y_uq_prestacion`, `test_exclusiones_son_gist_sobre_rango_y_solo_turnos_activos`, `test_columnas_de_tiempo_son_timestamptz`, `test_downgrade_elimina_005_y_reupgrade_restaura`; `test_migrations_smoke.py` |

## Notas para archive
- C-05 en CHANGES.md queda parcial (no marcar `[x]`): faltan transiciones, sobreturnos, huecos, reprogramar/cancelar.
- Warnings de deprecación (alembic `path_separator`, starlette cookies) preexistentes, sin relación.
