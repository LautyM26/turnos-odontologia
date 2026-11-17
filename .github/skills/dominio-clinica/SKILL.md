---
name: dominio-clinica
description: Reglas vigentes de clínica e historia clínica (RN-CL) con trazabilidad a specs y tests. Usar al programar historia clínica (HC), ficha o anamnesis, odontograma FDI (piezas permanentes y temporales, caras, estados, dentición), evoluciones append-only con autor, correcciones con corrige_a_id, auditoría AuditoriaHC, adjuntos clínicos (fotos y PDF), RBAC clínico (recepción sin acceso) o recall desde el odontograma (changes C-08 pacientes-ficha, C-09 odontograma-evolucion, C-10 clinica-frontend, recall de C-11/C-14), y antes de /opsx:propose de cualquier change clínico.
---

# dominio-clinica

> Generada con `crear-skill-de-dominio` el 2026-11-16 a partir de `knowledge-base/05_reglas_de_negocio.md`, `knowledge-base/09_decisiones_y_supuestos.md` y `AGENTS.md`. Si cambia una RN o DD de esta área, regenerarla.

## 1. Propósito

Cubre la historia clínica del paciente: ficha (anamnesis), odontograma FDI, evoluciones y adjuntos, con la garantía legal de que nada se borra ni se edita en silencio (Ley 26.529) y de que solo el personal clínico accede (Ley 25.326). Es la base para presupuestar por pieza (C-11) y para el recall (RN-CL-04).

## 2. Cuándo usarla

- Modelos `FichaVersion`, `Adjunto`, `AuditoriaHC` (C-08) y los nuevos `Odontograma` / `Evolucion` (C-09).
- Endpoints `/api/pacientes/{id}/ficha`, `/adjuntos`, `/auditoria`, `/odontograma`, `/evoluciones`, `/historia`; UI `/pacientes/{id}` (tabs clínicas).
- Changes del roadmap: C-08 `pacientes-ficha` (archivado 2026-10-08), C-09 `odontograma-evolucion` (implementado 2026-11-17; verify.md en `openspec/changes/archive/2026-11-17-odontograma-evolucion/`), C-10 `clinica-frontend`, recall de C-11 `presupuesto-plan` / C-14 `comercial-frontend`; consumen la HC C-18 y C-19.

## 3. Reglas vigentes

| Código | Regla (texto vigente) | DD que la condiciona |
|---|---|---|
| RN-CL-01 | Toda evolución lleva autor (profesional) y fecha/hora; sin autor no se guarda. El autor sale del usuario autenticado y la fecha del servidor, nunca del cliente. | — (SU-08 / PA-04) |
| RN-CL-02 | La HC es append-only con auditoría: ningún cambio borra historia y toda corrección deja traza (Ley 26.529). Corregir = nueva fila que apunta a la corregida, nunca UPDATE/DELETE. | — (SU-08 / PA-04) |
| RN-CL-03 | Odontograma FDI con piezas permanentes (11–48, 32 piezas) y temporales (51–85, 20 piezas) como base del MVP. Dentición mixta fina (seguimiento de recambio), versionado fino y BOP/periodontograma son posteriores (F2). | — |
| RN-CL-04 | El recall se dispara desde el odontograma o el plan, no con campañas genéricas. | — |
| RN-CL-05 | Imágenes simples (foto/PDF) como adjuntos; DICOM y radiología integrada son etapa posterior. | — |

### Reglas duras de AGENTS.md que aplican

- **4**: schemas Pydantic con `extra='forbid'` (campo no declarado → 422; ej. `autor` o `fecha_hora` en el cuerpo).
- **7**: tiempo siempre `TIMESTAMPTZ`, asignado por el servidor.
- **9**: tests de PG solo con testcontainers `postgres:16-alpine` + migraciones up/down.
- **10**: tabla con `clinica_id` + índice `(clinica_id, …)` + test de aislamiento (consulta cruzada = 0 filas).
- **14**: solo datos sintéticos en tests, seeds y ejemplos (nada de pacientes reales).
- **15**: HC inmutable: evolución append-only sin PUT/DELETE, corrección = nueva fila con `corrige_a_id`, sin autor profesional → 422.
- **16**: sin `consentimiento_datos = true` no se cargan datos de salud (403); RBAC clínico: recepción sin acceso clínico salvo contacto/OS (403).

### Supuestos abiertos (no son reglas cerradas)

- **PA-04 / SU-08**: encuadre legal de la HC (26.529, 25.326, 25.506) a validar con asesoría. Lo implementado es el supuesto Sprint 1: append-only + auditoría de escrituras y lecturas clínicas sin PHI en el diff.
- **Vínculo odontólogo–paciente**: hoy rige la regla interina de C-08 (todo paciente de la clínica, lecturas auditadas) vía `set_resolver_vinculo_paciente`; el resolver por turnos no se inyectó todavía.

## 4. Cómo aplicarlas

- Código existente: `backend/app/domain/pacientes/models.py` (`FichaVersion`, `Adjunto` con `evolucion_id` sin FK), `backend/app/domain/pacientes/servicios.py`, `backend/app/domain/auditoria/writer.py` (`registrar_evento`, diff con allowlist sin PHI), `backend/app/api/pacientes.py`, migración `backend/alembic/versions/004_pacientes_ficha.py` (`fn_rechazar_mutacion()` + triggers append-only).
- Inmutabilidad: reutilizar `fn_rechazar_mutacion()` con triggers `BEFORE UPDATE OR DELETE` (fila) y `BEFORE TRUNCATE` (sentencia). No crear otra función. El downgrade de una migración nueva no borra la función (es de la 004).
- Permisos: `require_clinico()` (lectura: admin + odontólogo), `require_clinico_escritura()` (escritura: solo odontólogo) y `require_vinculo_paciente` de `backend/app/api/permissions.py`. Escritura clínica sin consentimiento → 403 antes de validar el payload (patrón `paciente_escritura` de `pacientes.py`).
- Orden de respuestas: 401 sin token → 403 rol → 404 paciente de otra clínica → 403 vínculo → 403 consentimiento → 422 payload. Métodos no expuestos (PUT/PATCH/DELETE sobre HC) → 405.
- Auditoría: cada escritura clínica y cada lectura clínica registra un evento en `AuditoriaHC` en la misma transacción; ampliar los CHECK de `entidad`/`accion` y la allowlist del writer en lugar de crear otra tabla de auditoría. Nunca texto clínico en `diff`.
- FKs compuestas por tenant `(clinica_id, x) → tabla(clinica_id, id)` con `ON DELETE RESTRICT`, como en la 004.

## 5. Matriz de trazabilidad RN → spec → test

| Regla | Spec (archivo · requirement) | Test (archivo · función) | Estado |
|---|---|---|---|
| RN-CL-01 | `openspec/specs/clinical-evolutions/spec.md` · "Alta de evolución con autor profesional y hora del servidor", "Evolución sin autor rechazada"; `openspec/changes/archive/2026-11-17-clinica-frontend/specs/evolutions-web/spec.md` · "Alta de evolución" (el cuerpo lleva solo `texto`/`pieza_fdi`, nunca autor ni fecha) | `backend/tests/integration/test_evoluciones_api.py` · `test_alta_201_con_autor_profesional_y_hora_del_servidor`, `test_odontologo_sin_profesional_422_sin_fila`, `test_autor_o_fecha_en_el_cuerpo_422`; `backend/tests/integration/test_clinica_db.py` · `test_insert_sin_autor_o_profesional_falla`; `backend/tests/unit/test_clinica_schemas.py` · `test_autor_o_fecha_en_cuerpo_rechazados`; `frontend/tests/evoluciones.test.tsx` · "envía solo texto y pieza_fdi…", "422 (sin profesional vinculado)…" | cubierta |
| RN-CL-02 | `openspec/specs/clinical-record/spec.md` · "Ficha de anamnesis versionada append-only"; `openspec/specs/clinical-audit/spec.md` · "Toda escritura de datos del paciente queda auditada", "Auditoría inmutable a nivel base de datos", "Auditoría atómica con la operación"; `openspec/specs/clinical-evolutions/spec.md` · "Evoluciones sin edición ni borrado", "Corrección como evolución nueva enlazada", "Solo el autor corrige su evolución"; `openspec/specs/odontogram/spec.md` · "Guardado del odontograma como versión nueva", "Odontograma sin edición ni borrado"; `openspec/changes/archive/2026-11-17-clinica-frontend/specs/evolutions-web/spec.md` · "Historia sin edición ni borrado", "Corrección como evolución nueva", "Quién puede corregir", "Cadena de correcciones visible"; `…/specs/clinical-record-web/spec.md` · "Ficha de anamnesis versionada" | `backend/tests/integration/test_ficha_api.py` · `test_put_crea_v1_y_v2_conservando_la_anterior`, `test_falla_al_auditar_no_deja_version`; `backend/tests/integration/test_append_only_db.py` · `test_update_delete_rechazados_y_fila_persiste`, `test_truncate_rechazado`; `backend/tests/integration/test_auditoria_api.py` · `test_metodos_de_escritura_405_sin_cambiar_el_conteo`; `backend/tests/integration/test_clinica_db.py` · `test_update_delete_rechazados_y_fila_persiste`, `test_truncate_rechazado`; `backend/tests/integration/test_evoluciones_api.py` · `test_autor_corrige_original_intacta_y_corregida_por`, `test_otro_odontologo_intenta_corregir_403`, `test_metodos_de_escritura_405_sin_cambios`, `test_ninguna_ruta_de_odontograma_o_evoluciones_expone_put_patch_delete`; `backend/tests/integration/test_evoluciones_concurrencia.py` · `test_dos_correcciones_simultaneas_un_201_y_un_409`; `backend/tests/integration/test_odontograma_api.py` · `test_nueva_version_conserva_la_anterior`, `test_falla_al_auditar_no_deja_version`; `frontend/tests/evoluciones.test.tsx` · "el código de evoluciones no usa PUT, PATCH ni DELETE", "parte del texto original; el autor corrige y la timeline tiene una entrada más", "solo Corregir sobre evoluciones propias…"; `frontend/tests/ficha.test.tsx` · "409: avisa, conserva lo escrito y recarga solo a pedido" | cubierta |
| RN-CL-03 | `openspec/specs/odontogram/spec.md` · "Piezas FDI válidas según la dentición", "Caras y estados del catálogo MVP", "Odontograma vigente"; `openspec/changes/archive/2026-11-17-clinica-frontend/specs/odontogram-web/spec.md` · "Piezas según la dentición", "Marcado por pieza y por cara", "Guardado como versión nueva", "Conflicto de versión del odontograma" | `backend/tests/unit/test_fdi.py` · `test_conteos_de_piezas`, `test_bordes_validos`, `test_bordes_invalidos`; `backend/tests/unit/test_clinica_schemas.py` · `test_pieza_invalida_en_permanente`, `test_mixta_acepta_limites`, `test_pieza_ausente_o_extraida_sin_caras`; `backend/tests/integration/test_odontograma_api.py` · `test_temporal_85_201`, `test_limites_mixta_201`, `test_pieza_temporal_en_permanente_422`, `test_marcas_validas_por_cara_se_devuelven_tal_cual`; `backend/tests/integration/test_clinica_db.py` · `test_pieza_fdi_invalida_23514`; `frontend/tests/odontograma-modelo.test.ts` · "cantidad de piezas por dentición", "orden de dibujo por arcada…"; `frontend/tests/odontograma-ui.test.tsx` · "permanente: 32 piezas…", "mixta: 52 piezas", "409 conserva el borrador…" | cubierta (backend + UI C-10) |
| RN-CL-04 | — | — | pendiente (C-11/C-14; sin change que lo nombre explícitamente en `CHANGES.md`) |
| RN-CL-05 | `openspec/specs/clinical-record/spec.md` · "Adjuntos limitados a foto o PDF", "Límite de tamaño de adjuntos" | `backend/tests/integration/test_adjuntos_api.py` · `test_jpeg_valido_201_con_metadatos_y_evento_sin_nombre`, `test_png_y_pdf_validos`, `test_tipos_no_permitidos_415_sin_archivo_ni_fila`; `backend/tests/unit/test_archivos_firma.py` · `test_firmas_rechazadas` | cubierta |

Resumen: 5 reglas · 4 cubiertas · 0 parciales · 1 pendiente (RN-CL-04, recall en C-11/C-14). Ningún test cita el código RN: la trazabilidad se hizo por significado (requirement → escenario → test).

Reglas duras ya cubiertas en C-08 (referencia): 16 en `openspec/specs/access-control/spec.md` · "Lectura clínica solo admin y odontólogo" / `backend/tests/integration/test_rbac_pacientes.py` · `test_recepcion_recibe_403_en_todo_endpoint_clinico_sin_auditar`; consentimiento en `backend/tests/integration/test_ficha_api.py` · `test_put_sin_consentimiento_403_sin_version`.

### Conflictos detectados

- **Dentición mixta**: RN-CL-03 dice que la dentición mixta es posterior, pero `knowledge-base/04_modelo_de_datos.md` (Odontograma) lista "permanente/temporal/mixta" y la ficha C-09 de `CHANGES.md` dice "mixta fina y BOP son F2". No contradice ninguna DD; es una ambigüedad interna de la KB. Lectura adoptada: en el MVP un odontograma puede registrar piezas de ambos sets FDI (lo que cubre al paciente con dentición mixta), y lo "fino" (recambio pieza temporal → permanente, estadios de erupción) es F2. Confirmado por el usuario el 2026-11-16 (DC-4 de C-09): `mixta` = unión de ambos sets.
- Ninguna RN-CL contradice una DD vigente.

## 6. Criterios de revisión

Antes de dar por terminado un change de esta área:

- [ ] Cada regla de la sección 3 que el change toca tiene escenario en la spec del change.
- [ ] Cada escenario nuevo tiene un test y la fila correspondiente de la matriz se actualizó (regenerar esta skill).
- [ ] Ninguna implementación contradice una DD vigente.
- [ ] Se respetaron las reglas duras 4, 7, 9, 10, 14, 15 y 16 (sin PUT/DELETE de HC; 403 para recepción; 0 filas cross-tenant).
- [ ] Solo datos sintéticos en tests, seeds y ejemplos (regla dura 14).
