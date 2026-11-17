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
- Atributos: id, nombre, CUIT, domicilio, datos fiscales ARCA, moneda (ARS), política de seña, zona_horaria (IANA, default America/Argentina/Buenos_Aires; C-05d)
- Relaciones: 1──* Profesional, Sillon, Paciente, Usuario
- Constraints: CUIT válido; moneda ARS (precio público en ARS, sin packs)

### Profesional
- Atributos: id, clinica_id, nombre, matrícula, especialidad, agenda_activa
- Relaciones: *──* Sillon (habilitación), 1──* Turno, 1──* Evolucion (autor), 1──* FranjaHoraria (horario de atención)
- Índices: (clinica_id, activo)

### FranjaHoraria (C-05d)
- Atributos: id, clinica_id, profesional_id, dia_semana (1 = lunes … 7 = domingo), inicio_min, fin_min (minutos desde la medianoche local; 1440 = 24:00)
- Semántica: horario semanal de atención en la zona de la clínica; franjas contiguas forman un tramo. Sin franjas el profesional no atiende (sin huecos ni turnos normales); el sobreturno queda exceptuado. Feriados = bloqueos de clínica.
- Constraints: 0 ≤ inicio_min < fin_min ≤ 1440; sin superposición en el mismo día (validada al reemplazar el horario completo)
- Índices: (clinica_id, profesional_id, dia_semana)

### Sillon/Recurso (recurso de agenda)
- Atributos: id, clinica_id, nombre, tipo (sillón/box/equipo), activo
- Relaciones: 1──* Turno; bloqueos por rango horario
- Constraints: **anti-solapamiento duro**: no hay dos turnos activos con mismo (sillón, rango) ni mismo (profesional, rango). Ver RN-AG-01.

### Turno
- Atributos: id, clinica_id, profesional_id, sillon_id, paciente_id, prestacion, duracion_min (por prestación), inicio, fin, estado (reservado/confirmado/asistido/ausente/cancelado; el valor `sobreturno` queda en desuso desde C-05c), es_sobreturno + motivo_sobreturno (marca, C-05c), origen (enlace/mostrador/WhatsApp/lista_espera), seña_exigida, seña_pagada
- Relaciones: *──1 Presupuesto/Plan (cuando nace de un plan), 1──* Cobro, 1──* MensajeWhatsApp
- Constraints: duracion por prestación; sobreturno solo con rol autorizado y con motivo (marca `es_sobreturno`, exceptuada del anti-solapamiento pero no de los bloqueos, C-05c); transición de estados explícita
- Índices: (profesional_id, inicio), (sillon_id, inicio), (paciente_id, inicio), (estado)

### Paciente
- Atributos: id, clinica_id, nombre, DNI, email, teléfono/WhatsApp, obra_social_id, plan, nro_afiliado, riesgo_ausencia (score), consentimiento_datos
- Relaciones: 1──1 Ficha, 1──* Evolucion/Odontograma/Presupuesto/Consentimiento
- Constraints: DNI + email permiten reservar sin cuenta (reserva sin registro); datos de salud = datos sensibles (Ley 25.326)
- Índices: (dni), (telefono)

### Ficha (anamnesis) + Evolucion + Odontograma
- Ficha: id, paciente_id, anamnesis, alergias, antecedentes; adjuntos
- Evolucion: id, paciente_id, autor_usuario_id, profesional_id (autor profesional), fecha_hora (TIMESTAMPTZ del servidor), texto (1–10 000), pieza_fdi (opcional, FDI), corrige_a_id + motivo_correccion (corrección); **append-only, sin edición muda** (Ley 26.529). Corregir = fila nueva con `corrige_a_id` (una sola corrección por evolución; `corregida_por_id` se calcula en la lectura, la original nunca se toca). Triggers + FKs compuestas por tenant (C-09)
- Odontograma: id, paciente_id, version, dentición (permanente/temporal/mixta — FDI), piezas (JSONB), autor_usuario_id, created_at. **Snapshot completo y append-only por versión** (la vigente = mayor `version`; `UNIQUE (clinica_id, paciente_id, version)`). Forma de `piezas`: objeto disperso por código FDI → `{"16": {"estado": {"codigo", "registro"}, "caras": {"V|L|M|D|O": {"codigo", "registro"}}}}`; `registro` = `existente` | `a_realizar`; estados de pieza `ausente|extraida|extraccion_indicada|corona|endodoncia|implante`, de cara `caries|obturacion|sellador|fractura`; GIN `jsonb_path_ops` para recall/presupuesto (C-11/C-14). El versionado fino (por marca) es posterior (C-09 lo resuelve por snapshot)
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
- Dos tablas append-only (C-18): **`consentimiento`** (documento: id, clinica_id, paciente_id, `tipo` ∈ catálogo cerrado `tratamiento_general|extraccion|endodoncia|implante|anestesia`, `texto` exacto, `texto_version`, `texto_hash` SHA-256 hex, autor_usuario_id, created_at) y **`consentimiento_firma`** (constancia: `firmado_en` TIMESTAMPTZ del servidor, `ip`, `dispositivo` = user-agent, `texto_hash`, firmante_nombre, firmante_dni 7–8 dígitos, asistido_por_usuario_id).
- `estado` (`pendiente`/`firmado`) y `documento_bloqueado` se **derivan** de que exista la constancia; firmar = INSERT, nunca UPDATE. `UNIQUE (clinica_id, consentimiento_id)` → una sola firma por documento; triggers `fn_rechazar_mutacion()` + FKs compuestas por tenant.
- Constraints: firma según Ley 25.506 con constancia (modelo Odonthia); firma electrónica simple, PA-04 abierto

### RecetaExterna
- Tabla append-only (C-19, RN-CU-03): **`receta_externa`** (id, clinica_id, paciente_id, `evolucion_id` obligatoria — evolución propia del odontólogo —, `tipo` ∈ `receta|orden_estudio`, `partner`, `simulada`, `id_externo`, `pdf_url` https del partner, `diagnostico` ≤ 500, `items` JSONB 1..10, `clave_idempotencia` UUID, `huella_solicitud` SHA-256, autor_usuario_id, profesional_id, `emitida_en` TIMESTAMPTZ del servidor).
- Se emite solo vía partner registrado en ReNaPDiS; se guarda el enlace al PDF del partner, no el binario. `UNIQUE (clinica_id, clave_idempotencia)` y `UNIQUE (clinica_id, partner, id_externo)`; FK compuesta a `evolucion` (no se vincula una evolución de otro paciente o clínica); triggers `fn_rechazar_mutacion()`. AuditoriaHC suma la entidad `receta`.

### Usuario / Rol + AuditoriaHC + AuditoriaAdmin
- Usuario: id, clinica_id, rol, auth; Rol: permisos por recurso (ver `03_actores_y_roles.md`). Administración por API (C-18): alta, listado y reemplazo de roles (`usuario_rol` con `is_active`); la clínica nunca queda sin admin activo
- AuditoriaHC: quién/qué/cuándo por cada escritura clínica; inmutable. C-18 suma la entidad `consentimiento` y la acción `firmar`
- AuditoriaAdmin (C-18): eventos sin paciente — `usuario_crear`, `usuario_roles`, `exportar` —; id, clinica_id, actor_usuario_id, accion, entidad_id (nullable), diff (sin email ni contraseña), ip, created_at; inmutable

### MensajeWhatsApp + ListaEspera
- Mensaje: id, turno_id, plantilla, dirección (entrante/saliente), estado (enviado/entregado/leído), costo ARS
- ListaEspera: id, prestacion/profesional/sillon, paciente, prioridad, oferta_enviada, estado
- Constraints: canal WhatsApp por QR con número dedicado (DD-10); costo por mensaje transparente en pesos; estado de sesión QR registrado

## Seed data inicial

- Roles base (admin, odontólogo, recepcionista) + matriz mínima de permisos (4 roles confirmados, granularidad tercerizado/sobreturnos — ronda usuario 1, PA-03).
- Sillón de ejemplo + profesional de ejemplo + prestaciones con duración (fuente: consultorio piloto propio — ronda usuario 1, PA-09; duraciones a cargar desde el piloto).
- Plantillas WhatsApp aprobadas (recordatorio 24 h, confirmación, cancelación, reprogramación, oferta de hueco).
- Textos legales base: política de privacidad y página de cumplimiento (leyes 26.529, 25.326, 25.506) para adaptar con asesoría legal.
- Nomenclador base para RNO (etapa 2).
