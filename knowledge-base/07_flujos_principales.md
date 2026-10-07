# Flujos Principales

> Fuente única: `discovery/Discovery Consolidado Turnos Odontologia.pdf` (§§06–09). Todo traza al MVP §09 y a las oportunidades §07. Lo inferido como operatoria mínima se marca **(S)**.

Cada flujo se documenta extremo a extremo, mostrando interacciones entre componentes.

## Flujo 1: Reserva online con seña (IMP)
**Disparador**: paciente nuevo/abierto abre el enlace de reserva.
**Actor**: Paciente.

**Pasos**:
1. [Paciente] abre enlace público, elige prestación → ve huecos reales (profesional + sillón + duración por prestación, con bloqueos aplicados).
2. [Frontend] pide solo DNI + email/teléfono (sin registro ni cuenta).
3. [API] pre-bloquea el horario según política de seña: si el paciente tiene riesgo de ausencia o la prestación lo exige, exige seña por Mercado Pago; si no, reserva directa.
4. [Paciente] paga seña por Mercado Pago (va directo a la cuenta del profesional) — referencia Turnito: el horario se bloquea recién cuando entra la seña.
5. [API] crea Turno en estado `reservado`, crea Cobro (seña) imputado al turno/presupuesto, dispara WhatsApp de confirmación.
6. [API → ARCA] emite factura B/C con CAE y QR desde el cobro (RN-AF-01).

**Diagrama de secuencia** (ASCII):
```
Paciente → Enlace reserva → API → DB (Turno reservado + pre-bloqueo)
Paciente → Mercado Pago → API → DB (Cobro seña + Turno confirmado-bloqueado)
API → ARCA (FE con CAE) → DB (Factura) → WhatsApp (confirmación)
```

**Casos de error**:
- Pago no completado → el pre-bloqueo expira y el hueco se libera (S — operatoria a validar: timeout del pre-bloqueo).
- Sin CUIT configurado → el turno se crea pero la factura queda pendiente (RN-AF-02).
- Solapamiento concurrente (doble clic / dos pacientes) → gana la primera escritura; la segunda recibe "horario no disponible" (anti-solapamiento duro RN-AG-01).

## Flujo 2: Recordatorio y confirmación bidireccional por WhatsApp (IMP)
**Disparador**: cron/tarea programa recordatorios (ventana típica 24 h — (S), a confirmar).
**Actor**: Sistema → Paciente.

**Pasos**:
1. [API] envía plantilla aprobada de WhatsApp Business API oficial (recordatorio con botones Confirmar / Cancelar / Reprogramar).
2. [Paciente] responde (texto o botón).
3. [Meta webhook → API] interpreta la respuesta y actualiza el Turno: `reservado → confirmado | cancelado`.
4. [API] si cancela: libera el hueco y dispara Flujo 4 (lista de espera); si confirma: marca asistencia esperada y registra costo del mensaje en ARS.
5. [API] guarda MensajeWhatsApp (plantilla, dirección, estado, costo).

**Casos de error**:
- Webhook duplicado o fuera de orden → idempotencia por `turno_id + mensaje_id` (S).
- Número bloqueado / plantilla rechazada → el turno queda sin confirmar y se escala a la recepcionista (bandeja de fallos) (S).
- Uso de QR no oficial: explícitamente prohibido (RN-WA-01) — riesgo de bloqueo del número.

## Flujo 3: Reprogramación y chatbot transaccional (IMP)
**Disparador**: paciente pide mover su turno (por WhatsApp o enlace).
**Actor**: Paciente.

**Pasos**:
1. [Paciente] elige "Reprogramar" en WhatsApp o enlace.
2. [API] muestra opciones reales que respetan reglas de agenda (duración, bloqueos, solapamientos, sillón + profesional).
3. [Paciente] elige nuevo horario → [API] mueve el Turno (misma seña imputada, sin cobrar de nuevo salvo diferencia de prestación).
4. [API] confirma por WhatsApp y actualiza la agenda de profesional/sillón.

**Casos de error**:
- Nuevo horario ocupado entre consulta y confirmación → ofrecer alternativas (mismo manejo de concurrencia que Flujo 1).
- Prestación con distinta duración → recalcular fin del turno (RN-AG-02).

## Flujo 4: Cancelación → lista de espera con relleno automático (DIF, candidato a IMP)
**Disparador**: un turno se cancela o queda ausente.
**Actor**: Sistema → pacientes en espera → Recepcionista.

**Pasos**:
1. [API] detecta hueco liberado (cancelación, ausencia, reprogramación).
2. [API] busca ListaEspera por (prestación / profesional / sillón) en orden de prioridad.
3. [API] envía oferta automática por WhatsApp al primero ("se liberó Jue 16:30 con Dra. X, ¿lo tomás?").
4. [Paciente] acepta con un tap → [API] reasigna el Turno, transfiere/exige seña según política.
5. [API] si rechaza o expira (timeout a definir — S), ofrece al siguiente; la recepcionista ve todo en bandeja.

**Casos de error**:
- Nadie acepta → el hueco queda libre visible en agenda; se registra como hora perdida para métrica de ocupación.
- Doble aceptación simultánea → idempotencia: solo una reasignación efectiva.

## Flujo 5: Atención clínica — ficha, odontograma, evolución (IMP)
**Disparador**: paciente en sillón, turno en estado `confirmado → asistido`.
**Actor**: Odontólogo.

**Pasos**:
1. [Odontólogo] abre ficha: anamnesis, alergias, antecedentes + adjuntos simples.
2. [Odontólogo] marca odontograma FDI (permanentes y temporales, por pieza/cara) — base para presupuestar (referencia Doctocliq/Dentidad).
3. [Odontólogo] redacta evolución con autor + fecha/hora obligatorios; guardado append-only con auditoría (Ley 26.529).
4. [API] registra todo cambio en AuditoriaHC (quién/qué/cuándo, inmutable).

**Casos de error**:
- Intento de guardar evolución sin autor → rechazo duro (RN-CL-01).
- Corrección de una evolución → no edita: crea nueva versión con traza (RN-CL-02).

## Flujo 6: Presupuesto → plan → turnos + seguimiento (IMP + DIF)
**Disparador**: el odontólogo presenta un tratamiento.
**Actor**: Odontólogo → Paciente → Recepcionista.

**Pasos**:
1. [Odontólogo] crea Presupuesto (ítems prestación + pieza + monto ARS → total) desde el odontograma.
2. [Paciente] acepta (en consultorio o vía PDF compartido) → [API] genera la secuencia de Turnos sugerida (RN-PR-01).
3. [Recepcionista/Paciente] agenda cada turno de la secuencia (Flujo 1/3).
4. [API] todo lo aceptado-no-agendado entra a seguimiento con monto visible; todo ausente entra a recuperación (RN-PR-02, RN-TU-04).
5. [API] el recall se dispara desde el odontograma o el plan (no campañas genéricas — RN-CL-04).

**Casos de error**:
- Presupuesto vencido/rechazado → sale del seguimiento activo, queda como no convertido para métrica.
- Cambio de plan a mitad de tratamiento → nuevo presupuesto versionado; turnos ya tomados se re-imputan (S — a validar).

## Flujo 7: Caja, saldo y factura ARCA (IMP)
**Disparador**: cobro de seña/saldo en mostrador o online.
**Actor**: Recepcionista / Sistema.

**Pasos**:
1. [Recepcionista] imputa cobro (seña/saldo, Mercado Pago) al turno/presupuesto.
2. [API → ARCA] emite FE B/C con CAE y QR desde el cobro.
3. [API] guarda Cobro + FacturaARCA, actualiza Caja diaria y comprobantes del paciente.
4. [API] anulaciones solo con rol autorizado y traza (RN-CA-03).

**Casos de error**:
- Caída de ARCA → el cobro queda registrado y la factura en cola de reintento con estado visible (S — a validar).
- Anulación sin rol → rechazo (RBAC).

## Flujo 8: Consentimiento con firma electrónica (DIF)
**Disparador**: tratamiento que requiere consentimiento.
**Actor**: Odontólogo → Paciente.

**Pasos**:
1. [Odontólogo] genera consentimiento desde el plan.
2. [Paciente] firma electrónicamente (fecha, IP, dispositivo, hash — modelo Odonthia, Ley 25.506).
3. [API] bloquea el documento post-firma; guarda constancia auditable.

**Casos de error**:
- Firma incompleta → documento inválido, no bloquea; se reintenta.

## Flujo 9 (etapa 2, fuera del MVP): Obra social y receta
**Disparador**: etapa financiadora / prescripción.
**Actor**: Sistema vía alianzas/partner.

**Pasos (diseño anticipado, no MVP)**:
1. Cálculo de cobertura y copago + RNO generado desde el odontograma → lotes exportables.
2. Validación en línea por financiador vía círculos o Frontini (requiere acuerdo por financiador — barrera de entrada).
3. Receta electrónica vía partner registrado en ReNaPDiS (obligatoria desde 1/1/2025); propia es F2.
