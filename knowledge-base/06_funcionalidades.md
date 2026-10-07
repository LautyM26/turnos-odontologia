# Funcionalidades

> Organizadas por épica. Trazan a la tabla MVP §09: IMP = imprescindible, DIF = diferenciador, F2 = etapa posterior. Reglas citadas: ver `05_reglas_de_negocio.md`.

## Épica 1: Agenda y reserva (IMP)

### US-001 — Agenda multisillón día/semana
**Como** recepcionista **Quiero** ver la agenda por profesional y sillón en vista día/semana **Para** asignar turnos sin choques.
**Criterios de aceptación**:
- [ ] Vista día y semana con profesionales y sillones como ejes
- [ ] Bloqueos visibles y no reservables
- [ ] Solapamiento impedido en (sillón, rango) y (profesional, rango)
**Reglas relacionadas**: RN-AG-01, RN-AG-02, RN-AG-03

### US-002 — Reglas de agenda odontológica
**Como** administrador **Quiero** configurar duración por prestación, bloqueos y sobreturnos por rol **Para** que la agenda refleje la operatoria real del sillón.
**Criterios de aceptación**:
- [ ] Duración editable por prestación
- [ ] Sobreturno solo con rol autorizado y motivo registrado
- [ ] Anti-solapamiento duro que nadie puede bypassear desde UI
**Reglas relacionadas**: RN-AG-02, RN-AG-04

### US-003 — Reserva online sin registro
**Como** paciente nuevo **Quiero** reservar por enlace sin crear cuenta **Para** conseguir turno en 1 minuto.
**Criterios de aceptación**:
- [ ] Enlace compartible (redes/QR/Web)
- [ ] Solo pide DNI + email/teléfono; no exige contraseña
- [ ] Horario se bloquea según política de seña (US-010)
**Reglas relacionadas**: RN-AG-05, RN-CA-01

### US-004 — Lista de espera con relleno automático (DIF, candidato a IMP)
**Como** recepcionista **Quiero** que un hueco liberado se ofrezca solo al primero de la lista **Para** recuperar ocupación sin llamar uno por uno.
**Criterios de aceptación**:
- [ ] Cola por prestación/profesional/sillón con prioridad
- [ ] Oferta automática por WhatsApp ante cancelación
- [ ] Reasignación con un tap del paciente
**Reglas relacionadas**: RN-AG-06, RN-WA-01

## Épica 2: WhatsApp oficial (IMP)

### US-005 — Recordatorio y confirmación bidireccional
**Como** paciente **Quiero** confirmar o cancelar mi turno respondiendo el WhatsApp **Para** no tener que llamar.
**Criterios de aceptación**:
- [ ] Plantillas aprobadas (recordatorio 24 h, confirmación, cancelación, reprogramación)
- [ ] La respuesta actualiza el estado del turno en la agenda
- [ ] Costo por mensaje visible en pesos para el consultorio
**Reglas relacionadas**: RN-TU-02, RN-TU-03, RN-WA-01, RN-WA-02

### US-006 — Reprogramación y chatbot transaccional
**Como** paciente **Quiero** reprogramar por WhatsApp sin intervención humana **Para** mover mi turno fuera de horario.
**Criterios de aceptación**:
- [ ] Flujo guiado: ver opciones → elegir → confirmación
- [ ] Respeta reglas de agenda (duración, bloqueos, solapamientos)
**Reglas relacionadas**: RN-TU-03, RN-AG-01

## Épica 3: Historia clínica y odontograma (IMP)

### US-007 — Ficha con anamnesis
**Como** odontólogo **Quiero** ficha con anamnesis y adjuntos por paciente **Para** atender con contexto.
**Criterios de aceptación**:
- [ ] Anamnesis, alergias, antecedentes editables con traza
- [ ] Adjuntos simples (fotos, PDFs)
**Reglas relacionadas**: RN-CL-01, RN-CL-02, RN-CU-01

### US-008 — Odontograma FDI
**Como** odontólogo **Quiero** odontograma FDI con permanentes y temporales **Para** registrar y presupuestar por pieza.
**Criterios de aceptación**:
- [ ] FDI con dentición permanente y temporal
- [ ] Marca por pieza/cara con trazabilidad (referencia Dentidad)
- [ ] Base para generar presupuesto (referencia Doctocliq)
**Reglas relacionadas**: RN-CL-03, RN-PR-01

### US-009 — Evolución con auditoría
**Como** odontólogo **Quiero** evolución con autor y fecha inmutable **Para** cumplir Ley 26.529.
**Criterios de aceptación**:
- [ ] Autor + timestamp obligatorios
- [ ] Append-only: ediciones dejan auditoría visible
**Reglas relacionadas**: RN-CL-01, RN-CL-02

## Épica 4: Presupuesto, caja y factura (IMP + DIF)

### US-010 — Presupuesto y plan de tratamiento
**Como** odontólogo **Quiero** presupuesto por ítems que genere el plan y sus turnos **Para** no re-cargar nada a mano.
**Criterios de aceptación**:
- [ ] Ítems (prestación, pieza, monto ARS) → total
- [ ] Aceptado ⇒ secuencia de turnos sugerida
- [ ] Lo no agendado entra a seguimiento con monto visible
**Reglas relacionadas**: RN-PR-01, RN-PR-02, RN-PR-03

### US-011 — Caja con seña por Mercado Pago
**Como** recepcionista **Quiero** cobrar seña y saldo por Mercado Pago imputados al turno **Para** asegurar el cobro.
**Criterios de aceptación**:
- [ ] Seña como condición de reserva online; bloquea horario
- [ ] Seña obligatoria solo ante riesgo de ausencia (score)
- [ ] Saldo contra el mismo presupuesto/turno
**Reglas relacionadas**: RN-CA-01, RN-CA-02, RN-CA-03

### US-012 — Factura ARCA desde el cobro (IMP, decisión DD-01)
**Como** administrador **Quiero** factura B/C con CAE emitida al cobrar **Para** no facturar en otro sistema.
**Criterios de aceptación**:
- [ ] FE con CAE y QR generada desde el cobro
- [ ] Sin CUIT configurado no permite emitir
**Reglas relacionadas**: RN-AF-01, RN-AF-02

### US-013 — Seguimiento y recall (DIF)
**Como** recepcionista **Quiero** tableros de no convertidos, no agendados e inactivos **Para** recuperar ingresos.
**Criterios de aceptación**:
- [ ] Presupuestos no convertidos con monto
- [ ] Ausentes con recupero desde el plan
- [ ] Recall disparado desde odontograma/plan
**Reglas relacionadas**: RN-TU-04, RN-CL-04, RN-PR-02

## Épica 5: Cumplimiento y administración (IMP + DIF)

### US-014 — Roles, respaldo y exportación (IMP)
**Como** administrador **Quiero** roles y exportación completa **Para** operar y salir sin retención.
**Criterios de aceptación**:
- [ ] RBAC por recurso (ver `03_actores_y_roles.md`)
- [ ] Respaldo y exportación CSV/PDF sin costo
**Reglas relacionadas**: RN-CU-04

### US-015 — Privacidad y página de cumplimiento (IMP)
**Como** dueño **Quiero** política de privacidad y página de cumplimiento **Para** vender cumplimiento como diferencial.
**Criterios de aceptación**:
- [ ] Textos base adaptados con asesoría legal (26.529, 25.326, 25.506)
- [ ] Página pública de cumplimiento
**Reglas relacionadas**: RN-CU-01, RN-CU-05

### US-016 — Consentimientos firmados (DIF)
**Como** odontólogo **Quiero** consentimiento firmado con constancia **Para** respaldar cada tratamiento.
**Criterios de aceptación**:
- [ ] Firma electrónica con fecha, IP, dispositivo y hash
- [ ] Documento bloqueado post-firma
**Reglas relacionadas**: RN-CU-02

### US-017 — Datos de OS del paciente (IMP mínimo)
**Como** recepcionista **Quiero** registrar obra social, plan y afiliado **Para** preparar la etapa financiadora.
**Criterios de aceptación**:
- [ ] Campos OS/plan/afiliado en ficha del paciente
- [ ] Sin validación en línea en MVP (etapa 2)
**Reglas relacionadas**: RN-OS-01

## Etapa posterior (F2 — no entra al MVP)

- US-F2-01 Periodontograma (BOP/NIC) y dentición mixta avanzada.
- US-F2-02 Receta electrónica propia ReNaPDiS (temprano vía partner).
- US-F2-03 Cobertura/copago/lotes + RNO desde odontograma; validación OS en línea.
- US-F2-04 Liquidación a profesionales y a OS.
- US-F2-05 Imágenes/DICOM, inventario, laboratorio, multisucursal avanzada.
- US-F2-06 IA clínica (dictado al odontograma, CDSS), portal paciente, telemedicina, marketplace, API pública.
