# Modelo de Datos

> Derivado del MVP §09 y de las reglas de agenda §06–§07 del discovery. Entidades marcadas con **(S)** son inferencia de modelado (necesarias para sostener el MVP), no texto literal del PDF.

## Dominios

- **Agenda:** profesionales, sillones/recursos, turnos, bloqueos, sobreturnos, lista de espera.
- **Clínica:** pacientes, fichas/anamnesis, odontograma FDI, evoluciones, consentimientos, recetas (vía partner).
- **Administrativa:** presupuestos/planes de tratamiento, cobros/señas/saldos, facturas ARCA, caja.
- **Financiadores (etapa 2):** obras sociales, planes, afiliados, cobertura/copago, lotes, RNO.
- **Comunicación:** mensajes WhatsApp (plantillas, estados), recordatorios, riesgo de ausencia.
- **Seguridad/cumplimiento:** usuarios, roles, auditoría HC, respaldo/exportación.

## ERD (textual)

```
Clinica 1──* Profesional 1──* Turno *──1 Paciente 1──1 Ficha
Clinica 1──* Sillon/Recurso 1──* Turno (recurso + profesional + equipo, anti-solapamiento)
Paciente 1──* Odontograma (piezas FDI permanentes y temporales)
Paciente 1──* Evolucion (autor + fecha, append-only) ──* Adjunto
Presupuesto 1──* PlanTratamiento 1──* Turno (presupuesto → turnos; seguimiento no agendado)
Presupuesto 1──* Cobro (seña/saldo, Mercado Pago) 1──1 FacturaARCA (CAE, QR)
Paciente *──* ObraSocial (plan, afiliado; cobertura/copago/lotes en etapa 2)
Paciente 1──* Consentimiento (firma electrónica + constancia: fecha, IP, dispositivo, hash)
Turno 1──* MensajeWhatsApp (recordatorio/confirmación/cancelación/reprogramación)
Turno *──1 ListaEspera (hueco → oferta automática)
Usuario *──* Rol (RBAC) ; Evolucion *──1 Usuario (autor) ; AuditoriaHC registra todo cambio
```

## Entidades

### Clinica (S)
- Atributos: id, nombre, CUIT, domicilio, datos fiscales ARCA, moneda (ARS), política de seña
- Relaciones: 1──* Profesional, Sillon, Paciente, Usuario
- Constraints: CUIT válido; moneda ARS (precio público en ARS, sin packs)

### Profesional
- Atributos: id, clinica_id, nombre, matrícula, especialidad, agenda_activa
- Relaciones: *──* Sillon (habilitación), 1──* Turno, 1──* Evolucion (autor)
- Índices: (clinica_id, activo)

### Sillon/Recurso (recurso de agenda)
- Atributos: id, clinica_id, nombre, tipo (sillón/box/equipo), activo
- Relaciones: 1──* Turno; bloqueos por rango horario
- Constraints: **anti-solapamiento duro**: no hay dos turnos activos con mismo (sillón, rango) ni mismo (profesional, rango). Ver RN-AG-01.

### Turno
- Atributos: id, clinica_id, profesional_id, sillon_id, paciente_id, prestacion, duracion_min (por prestación), inicio, fin, estado (reservado/confirmado/asistido/ausente/cancelado/sobreturno), origen (enlace/mostrador/WhatsApp/lista_espera), seña_exigida, seña_pagada
- Relaciones: *──1 Presupuesto/Plan (cuando nace de un plan), 1──* Cobro, 1──* MensajeWhatsApp
- Constraints: duracion por prestación; sobreturno solo con rol autorizado; transición de estados explícita
- Índices: (profesional_id, inicio), (sillon_id, inicio), (paciente_id, inicio), (estado)

### Paciente
- Atributos: id, clinica_id, nombre, DNI, email, teléfono/WhatsApp, obra_social_id, plan, nro_afiliado, riesgo_ausencia (score), consentimiento_datos
- Relaciones: 1──1 Ficha, 1──* Evolucion/Odontograma/Presupuesto/Consentimiento
- Constraints: DNI + email permiten reservar sin cuenta (reserva sin registro); datos de salud = datos sensibles (Ley 25.326)
- Índices: (dni), (telefono)

### Ficha (anamnesis) + Evolucion + Odontograma
- Ficha: id, paciente_id, anamnesis, alergias, antecedentes; adjuntos
- Evolucion: id, paciente_id, profesional_id (autor), fecha_hora, texto, pieza_relacionada; **append-only, sin edición muda** (Ley 26.529)
- Odontograma: id, paciente_id, fecha, dentición (permanente/temporal/mixta — FDI), piezas/caras/estados, versionado (el versionado fino es posterior; el FDI básico es MVP)
- Adjuntos: radiografías/imágenes simples (DICOM es F2)

### Presupuesto / PlanTratamiento
- Atributos: id, paciente_id, profesional_id, ítems (prestación, pieza, monto ARS), total, estado (borrador/aceptado/rechazado/vencido), monto_recuperable
- Relaciones: 1──* Turno sugerido; seguimiento de lo no agendado y ausentes (recall desde el plan)
- Constraints: montos en ARS; lo aceptado genera secuencia de turnos sugerida

### Cobro / Seña + FacturaARCA + Caja
- Cobro: id, turno_id/presupuesto_id, tipo (seña/saldo), monto ARS, medio (Mercado Pago), estado, id_externo_MP
- FacturaARCA: id, cobro_id, tipo (B/C), CAE, QR, fecha; emitida desde el cobro
- Caja (S): movimientos diarios, arqueo, comisiones a profesionales tercerizados (referencia AgendaPro)
- Constraints: la seña bloquea el horario (referencia Turnito); seña obligatoria solo si riesgo de ausencia lo exige

### ObraSocial / Afiliado (MVP mínimo + etapa 2)
- MVP: obra_social (nombre), plan, nro_afiliado en Paciente
- Etapa 2: cobertura, copago, lotes exportables, RNO generado desde odontograma; luego validación en línea por financiador

### Consentimiento
- Atributos: id, paciente_id, tipo, texto, firma (fecha, IP, dispositivo, hash), documento_bloqueado
- Constraints: firma según Ley 25.506 con constancia (modelo Odonthia)

### Usuario / Rol + AuditoriaHC
- Usuario: id, clinica_id, rol, auth; Rol: permisos por recurso (ver `03_actores_y_roles.md`)
- AuditoriaHC: quién/qué/cuándo por cada escritura clínica; inmutable

### MensajeWhatsApp + ListaEspera
- Mensaje: id, turno_id, plantilla, dirección (entrante/saliente), estado (enviado/entregado/leído), costo ARS
- ListaEspera: id, prestacion/profesional/sillon, paciente, prioridad, oferta_enviada, estado
- Constraints: solo API oficial; costo por mensaje transparente en pesos

## Seed data inicial

- Roles base (admin, odontólogo, recepcionista) + matriz mínima de permisos (4 roles confirmados, granularidad tercerizado/sobreturnos — ronda usuario 1, PA-03).
- Sillón de ejemplo + profesional de ejemplo + prestaciones con duración (fuente: consultorio piloto propio — ronda usuario 1, PA-09; duraciones a cargar desde el piloto).
- Plantillas WhatsApp aprobadas (recordatorio 24 h, confirmación, cancelación, reprogramación, oferta de hueco).
- Textos legales base: política de privacidad y página de cumplimiento (leyes 26.529, 25.326, 25.506) para adaptar con asesoría legal.
- Nomenclador base para RNO (etapa 2).
