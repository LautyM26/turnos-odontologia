---
name: dominio-cumplimiento
description: Reglas vigentes de cumplimiento legal (RN-CU) con trazabilidad a specs y tests. Usar al programar consentimientos con firma electrónica y constancia (fecha, IP, dispositivo, hash SHA-256, documento bloqueado), consentimiento de datos de salud (Ley 25.326), política de privacidad y página pública de cumplimiento (/cumplimiento, /privacidad), respaldo y exportación completa CSV/ZIP del tenant, administración de usuarios y roles, receta electrónica u órdenes de estudios vía partner registrado en ReNaPDiS (FakePartner, 501 sin partner, RECETAS_PARTNER_KEY) (changes C-18 consentimientos-cumplimiento, C-19 recetas-partner-renapdis), y antes de /opsx:propose de cualquier change de cumplimiento, privacidad o recetas.
---

# dominio-cumplimiento

> Generada con `crear-skill-de-dominio` el 2026-11-16 a partir de `knowledge-base/05_reglas_de_negocio.md`, `knowledge-base/09_decisiones_y_supuestos.md` y `AGENTS.md`. Si cambia una RN o DD de esta área, regenerarla.

## 1. Propósito

Cubre las obligaciones legales del consultorio argentino que el producto vende como diferencial: tratamiento de datos de salud como sensibles (Ley 25.326), consentimientos firmados electrónicamente con constancia (Ley 25.506), receta electrónica solo por plataforma registrada en ReNaPDiS (Res. 1959/2024 y 2214/2025), exportación completa sin retención y páginas públicas de privacidad y cumplimiento.

## 2. Cuándo usarla

- Modelos nuevos `Consentimiento` (C-18) y `RecetaExterna` (C-19); flag `Paciente.consentimiento_datos` (C-08, ya existe).
- Endpoints `/api/pacientes/{id}/consentimientos`, `/api/pacientes/{id}/recetas`, `/api/admin/usuarios`, `/api/admin/exportacion`, `/api/public/legal/*`; páginas `/cumplimiento` y `/privacidad` (`frontend/src/pages/CumplimientoPage.tsx`).
- Adapter `app/infrastructure/recetas/` (C-19: puerto, `fake` y factory; partner ReNaPDiS intercambiable).
- Changes del roadmap: C-18 `consentimientos-cumplimiento` y C-19 `recetas-partner-renapdis` (C-18 archivado 2026-11-17 en `openspec/changes/archive/2026-11-17-consentimientos-cumplimiento/`; C-19 archivado 2026-11-17 en `openspec/changes/archive/2026-11-17-recetas-partner-renapdis/`); el gate de consentimiento de datos ya vive en C-08 (archivado) y C-09.

## 3. Reglas vigentes

| Código | Regla (texto vigente) | DD que la condiciona |
|---|---|---|
| RN-CU-01 | Los datos de salud son datos sensibles (Ley 25.326): sin `consentimiento_datos = true` no se cargan datos de salud; la política de privacidad es pública y declara la ubicación de los datos. | DD-09 (nube multi-tenant: la ubicación declarada es la del proveedor cloud elegido) |
| RN-CU-02 | Consentimientos con firma electrónica y constancia: fecha (servidor), IP, dispositivo (user-agent) y hash del texto exacto firmado; una vez firmado el documento queda bloqueado y no hay edición (Ley 25.506). Firma incompleta → inválida, no bloquea, se reintenta. | — (SU-08 / PA-04) |
| RN-CU-03 | Receta electrónica (y órdenes de estudios) solo por plataforma registrada en ReNaPDiS, obligatoria desde 1/1/2025; hasta tener plataforma propia (F2), vía partner registrado. Sin partner configurado no se emite nada. | DD-06 (partner temprano, propia en F2) |
| RN-CU-04 | Respaldo y exportación completa de los datos del tenant sin costo ni retención (CSV/PDF). | — |
| RN-CU-05 | Página de cumplimiento pública (leyes 26.529, 25.326, 25.506, 27.706) con textos a validar con asesoría legal. | — (SU-08 / PA-04) |

### Reglas duras de AGENTS.md que aplican

- **4**: schemas Pydantic con `extra='forbid'` (ej. `ip`, `fecha` o `hash` en el cuerpo de la firma → 422).
- **7**: tiempo siempre `TIMESTAMPTZ`, asignado por el servidor (fecha de firma, de emisión, de exportación).
- **9**: tests de PG solo con testcontainers `postgres:16-alpine` + migraciones up/down.
- **10**: tabla con `clinica_id` + índice `(clinica_id, …)` + test de aislamiento (consulta cruzada = 0 filas); la exportación nunca incluye otro tenant.
- **12**: la credencial del partner (`RECETAS_PARTNER_KEY`) solo en env/vault del backend; nunca en el repo ni en el browser.
- **14**: solo datos sintéticos en tests, seeds, textos de ejemplo y recetas de demo.
- **15**: consentimiento firmado = documento bloqueado (sin endpoint de edición; trigger en DB).
- **16**: sin `consentimiento_datos = true` → 403; RBAC clínico: recepción sin acceso clínico (403).
- **17**: receta solo vía partner registrado en ReNaPDiS (RN-CU-03).

### Supuestos abiertos (no son reglas cerradas)

- **PA-04 / SU-08**: encuadre legal (26.529, 25.326, 25.506, 27.553 + DNU 345/2024, Res. 1959/2024 y 2214/2025, 27.706) a validar con asesoría. Los textos legales del seed son placeholders marcados "a validar con asesoría legal"; la firma implementada es firma electrónica simple con constancia, no firma digital con certificado.
- **PA-08 / SU-08**: partner de recetas no elegido (Farmalink, Innovamed u otro) ni alcance de órdenes de estudios. Se programa contra un puerto con adapter fake; el adapter real es un change posterior.

## 4. Cómo aplicarlas

- Código existente a reutilizar: `backend/app/api/permissions.py` (`require_admin()`, `require_clinico()`, `require_clinico_escritura()`, `require_vinculo_paciente`), `backend/app/api/pacientes.py` (dependencias `paciente_lectura` / `paciente_escritura`, que ya devuelven 403 sin consentimiento), `backend/app/domain/auditoria/writer.py` (`registrar_evento`, allowlist sin PHI), `backend/app/infrastructure/settings.py` (`extra="forbid"`: toda env var nueva se declara ahí con default seguro).
- Inmutabilidad: reutilizar `fn_rechazar_mutacion()` de `backend/alembic/versions/004_pacientes_ficha.py`. Para el consentimiento, preferir documento y firma como filas append-only separadas (firmar = INSERT de la constancia, nunca UPDATE; `documento_bloqueado` se deriva de que exista la firma). Si se usara un flag mutable, el trigger debe rechazar toda mutación una vez bloqueado.
- Hash: SHA-256 en servidor sobre los bytes UTF-8 del texto exacto versionado que se mostró; el cliente nunca manda el hash ni la fecha.
- Auditoría: `auditoria_hc` exige `paciente_id`; los eventos por paciente (consentimiento, receta) van ahí ampliando los CHECK de `entidad`/`accion`. Eventos sin paciente (exportación, usuarios) necesitan otro registro append-only.
- Partner de recetas: puerto + adapters (`fake` para tests/demo, ninguno = no configurado → 501 claro). El boot nunca falla por falta de credencial.
- Migraciones: 007 reservada (C-05c), 008 = C-09, 009 = C-18, 010 = C-19. `alembic heads` debe mostrar un único head.

## 5. Matriz de trazabilidad RN → spec → test

| Regla | Spec (archivo · requirement) | Test (archivo · función) | Estado |
|---|---|---|---|
| RN-CU-01 | `openspec/specs/clinical-record/spec.md` · "Gate de consentimiento para datos de salud"; `openspec/specs/patients/spec.md` · "Registro del consentimiento de datos"; `openspec/specs/legal-pages/spec.md` · "Política de privacidad pública", "Textos legales sin datos reales"; `openspec/specs/informed-consents/spec.md` · "RBAC y consentimiento de datos en consentimientos" | `backend/tests/integration/test_ficha_api.py` · `test_put_sin_consentimiento_403_sin_version`; `backend/tests/integration/test_adjuntos_api.py` · `test_sin_consentimiento_403_sin_archivo`; `backend/tests/integration/test_pacientes_api.py` · `test_consentimiento_otorgar_setea_fecha_y_usuario_y_audita`, `test_consentimiento_revocar_audita_y_conserva_datos`; `backend/tests/integration/test_rbac_consentimientos.py` · `test_sin_consentimiento_de_datos_403_antes_de_validar_el_cuerpo`; `frontend/tests/legal.test.tsx` · `/privacidad`: ubicación de los datos y aviso, marcadores `[A completar`, sin números tipo DNI | cubierta |
| RN-CU-02 | `openspec/specs/informed-consents/spec.md` · "Generación de consentimiento con texto versionado", "Hash del texto exacto", "Firma electrónica con constancia", "Firma incompleta reintentable", "Documento firmado bloqueado", "Consentimientos aislados por clínica"; `openspec/specs/clinical-audit/spec.md` · "Consentimientos auditados en la auditoría clínica" | `backend/tests/unit/test_cumplimiento_hash.py` · `test_espacios_y_acentos_cuentan`; `backend/tests/unit/test_cumplimiento_schemas.py` · `test_faltantes_completa_y_multiples`; `backend/tests/integration/test_consentimientos_api.py` · `test_firma_completa_201_con_constancia_y_documento_bloqueado`, `test_firma_incompleta_422_reintentable_sin_constancia_ni_evento`, `test_hash_distinto_409_y_sigue_pendiente`, `test_segunda_firma_409_y_constancia_intacta`, `test_metodos_de_edicion_405_y_documento_intacto`, `test_firmar_audita_sin_datos_del_firmante`; `backend/tests/integration/test_consentimientos_concurrencia.py` · `test_dos_firmas_simultaneas_un_201_y_un_409`; `backend/tests/integration/test_cumplimiento_db.py` · `test_update_delete_rechazados_y_fila_persiste`, `test_segunda_firma_del_mismo_consentimiento_23505`; `backend/tests/integration/test_rbac_consentimientos.py` · `test_recepcionista_403_en_las_4_rutas_sin_auditar` | cubierta |
| RN-CU-03 | `openspec/specs/prescriptions/spec.md` · "Emisión vía partner registrado", "Datos del paciente y del profesional desde el servidor", "Vínculo con una evolución propia", "Partner no configurado", "Errores del partner", "Emisión idempotente", "Receta inmutable", "Consulta de recetas", "RBAC y consentimiento de datos en recetas", "Recetas auditadas", "Recetas aisladas por clínica y exportadas"; `openspec/specs/platform-config/spec.md` · "Configuración del partner de recetas" | `backend/tests/unit/test_recetas_partner.py` · `test_factory_vacio_no_configurado_nombra_variable`, `test_factory_fake_en_produccion_bloqueado_con_warning`; `backend/tests/unit/test_recetas_errores.py` · `test_sanear_enmascara_credencial`; `backend/tests/unit/test_recetas_schemas.py` · `test_extras_de_servidor_rechazados`; `backend/tests/test_settings.py` · `test_settings_recetas_key_con_valor_no_aparece_en_repr`; `backend/tests/integration/test_recetas_api.py` · `test_receta_201_simulada_con_datos_del_servidor`, `test_partner_recibe_datos_de_la_base_no_del_cuerpo`, `test_evolucion_de_otro_odontologo_422_evolucion_propia`, `test_sin_partner_501_nombra_variable_y_sin_filas`, `test_fake_en_produccion_501`, `test_partner_caido_502_reintentable_sin_fila_ni_evento`, `test_misma_clave_y_contenido_200_misma_receta_una_emision`, `test_metodos_de_edicion_405`; `backend/tests/integration/test_recetas_db.py` · `test_update_delete_truncate_rechazados_y_fila_persiste`; `backend/tests/integration/test_recetas_concurrencia.py` · `test_dos_emisiones_simultaneas_misma_clave_una_fila`; `backend/tests/integration/test_rbac_recetas.py` · `test_recepcionista_403_en_las_3_rutas_sin_partner_ni_auditoria`, `test_sin_consentimiento_403_antes_del_cuerpo_y_del_501`; `backend/tests/integration/test_exportacion_aislamiento.py` · `test_la_exportacion_de_a_no_contiene_nada_de_b` | cubierta (partner real = change posterior, PA-08) |
| RN-CU-04 | `openspec/specs/data-export/spec.md` · "Exportación completa en ZIP de CSV", "Manifest de la exportación", "Exportación sin secretos y segura para planillas", "Exportación aislada por clínica y solo admin", "Exportación auditada" | `backend/tests/unit/test_exportacion_csv.py` · `test_csv_utf8_con_bom_conserva_caracteres_especiales`, `test_textos_peligrosos_se_prefijan_con_apostrofo`; `backend/tests/integration/test_exportacion_api.py` · `test_exportacion_200_zip_con_un_csv_por_entidad_y_conteos_de_la_db`, `test_formato_no_soportado_422_sin_evento`, `test_ningun_csv_tiene_columnas_de_secretos`, `test_exportacion_exitosa_deja_evento_con_conteos_sin_datos_de_pacientes`; `backend/tests/integration/test_exportacion_aislamiento.py` · `test_la_exportacion_de_a_no_contiene_nada_de_b`; `backend/tests/integration/test_rbac_admin_cumplimiento.py` · `test_no_admin_403_en_todas_las_rutas_sin_efectos` | cubierta (CSV/ZIP; PDF diferido, DT-3) |
| RN-CU-05 | `openspec/specs/access-control/spec.md` · "Rutas públicas declaradas"; `openspec/specs/legal-pages/spec.md` · "Página pública de cumplimiento", "Política de privacidad pública", "Textos legales sin datos reales" | `frontend/tests/legal.test.tsx` · `/cumplimiento`: título, versión y cuatro leyes; aviso "Texto base a validar con asesoría legal" y enlace a `/privacidad`; `/privacidad` es una ruta pública | cubierta (textos a validar con asesoría legal, PA-04) |

Resumen: 5 reglas · 5 cubiertas · 0 parciales · 0 pendientes. C-19 cubre RN-CU-03 con el puerto y el adapter `fake`; el adapter del partner real es un change posterior (PA-08). C-19 archivado 2026-11-17: sus specs ya están en `openspec/specs/` (prescriptions y platform-config). Ningún test cita el código RN: la trazabilidad se hizo por significado (requirement → escenario → test). Al archivar C-18, las specs delta pasan a `openspec/specs/` (informed-consents, user-administration, data-export, admin-audit, legal-pages): regenerar las rutas.

### Conflictos detectados

- **Flujo 9 vs. DD-06**: `knowledge-base/07_flujos_principales.md` titula el Flujo 9 "etapa 2, fuera del MVP" y mete la receta junto con obras sociales, pero DD-06 y `CHANGES.md` (C-19) la anticipan vía partner. Lectura adoptada: la receta vía partner entra temprano (DD-06 vigente); lo que queda en etapa 2 es cobertura/RNO de obras sociales y la receta propia.
- **CSV/PDF**: RN-CU-04 y US-014 dicen "CSV/PDF". No contradice una DD; el alcance de PDF se decide (y registra) en el `design.md` de C-18.
- **Plantillas en el seed**: `knowledge-base/04_modelo_de_datos.md` §Seed todavía lista "Plantillas WhatsApp aprobadas", texto previo a DD-10. No afecta a esta área; corregirlo en la KB (corresponde a C-15).
- Ninguna RN-CU contradice una DD vigente.

## 6. Criterios de revisión

Antes de dar por terminado un change de esta área:

- [ ] Cada regla de la sección 3 que el change toca tiene escenario en la spec del change.
- [ ] Cada escenario nuevo tiene un test y la fila correspondiente de la matriz se actualizó (regenerar esta skill).
- [ ] Ninguna implementación contradice una DD vigente (DD-06: receta solo vía partner).
- [ ] Se respetaron las reglas duras 4, 7, 9, 10, 12, 14, 15, 16 y 17 (firmado sin edición; recepción → 403; 0 filas cross-tenant; sin secretos en repo).
- [ ] Solo datos sintéticos en tests, seeds y ejemplos (regla dura 14); textos legales marcados "a validar con asesoría legal".
