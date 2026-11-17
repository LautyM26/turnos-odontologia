# appointment-rescheduling Specification

## Purpose
Reprogramación autoguiada de turnos (US-006, Flujo 3, RN-TU-03, RN-AG-01/02): el paciente mueve su turno por WhatsApp o por el enlace de su reserva eligiendo entre huecos reales, sin intervención de recepción y con las mismas reglas de agenda que el mostrador.

> Datos sintéticos: clínica A, profesional P, prestación "Control sintético" (30 min), paciente "Sintético 1" con teléfono, turno T `reservado` dentro de 20 h. Timeout de conversación 30 min; anticipación mínima 2 h.

## Requirements

### Requirement: Opciones de reprogramación

El sistema SHALL calcular para un turno `reservado` o `confirmado` que no empezó hasta 3 huecos libres del mismo profesional y prestación, en orden cronológico, desde la anticipación mínima configurada hasta 14 días, con las mismas reglas de horario, bloqueos y solapamiento que el alta de turnos. Un turno no reprogramable (cancelado, ausente, asistido o ya empezado) SHALL NOT tener opciones.

#### Scenario: Tres primeros huecos del mismo profesional

- **GIVEN** P tiene libres mañana a las 10:00, 10:30, 11:00 y 11:30
- **WHEN** se calculan las opciones de T
- **THEN** son 10:00, 10:30 y 11:00 de P, y ninguna de otro profesional.

### Requirement: Inicio del chatbot por WhatsApp

Cuando el paciente responde "reprogramar" a un recordatorio vigente y hay opciones, el sistema SHALL abrir una conversación (una sola abierta por número y clínica), enviarle el texto base `reprogramacion_opciones` con las opciones numeradas y la hora local, y SHALL NOT cambiar el turno. Sin opciones, SHALL dejar el pedido en la bandeja y responder `reprogramacion`.

#### Scenario: "3" abre el chatbot (happy path)

- **WHEN** Sintético 1 responde "3" al recordatorio de T
- **THEN** recibe "1) …, 2) …, 3) …" con los horarios disponibles de P y T sigue `reservado`.

#### Scenario: Sin huecos disponibles

- **GIVEN** P no tiene horarios libres en los próximos 14 días
- **WHEN** Sintético 1 responde "reprogramar"
- **THEN** el pedido queda en la bandeja y recibe el texto base `reprogramacion`.

### Requirement: Elección y confirmación

Con la conversación eligiendo, un número de opción válido SHALL pasarla a confirmando y enviar `reprogramacion_confirmar` con el horario elegido; con la conversación confirmando, "sí" SHALL ejecutar la reprogramación; "0" o "no" en cualquiera de los dos pasos SHALL cerrarla sin cambios y responder `reprogramacion_sin_cambios`. Cualquier otra respuesta SHALL ir a la bandeja sin cambiar la conversación.

#### Scenario: Elegir y confirmar mueve el turno (happy path)

- **GIVEN** a Sintético 1 se le ofrecieron 3 opciones
- **WHEN** responde "2" y después "si"
- **THEN** existe un turno nuevo `reservado` en la opción 2 con el mismo profesional y prestación, T queda `cancelado` con actor `paciente_whatsapp` y motivo de reprogramación, y recibe `reprogramacion_hecha`.

#### Scenario: Arrepentirse

- **GIVEN** la conversación está confirmando
- **WHEN** Sintético 1 responde "no"
- **THEN** T no cambia, la conversación se cierra y recibe `reprogramacion_sin_cambios`.

#### Scenario: Número fuera de rango

- **WHEN** con 3 opciones el paciente responde "7"
- **THEN** el mensaje va a la bandeja y la conversación sigue esperando una opción.

### Requirement: Horario ocupado entre la consulta y la confirmación

Si al confirmar el horario elegido ya no está disponible, el sistema SHALL NOT crear turno ni cancelar T, SHALL recalcular las opciones y volver a ofrecerlas (`reprogramacion_opciones`); sin opciones, SHALL cerrar la conversación con el pedido en la bandeja.

#### Scenario: Hueco tomado en el medio → alternativas

- **GIVEN** Sintético 1 eligió las 10:30 y antes de confirmar recepción da ese horario a otro paciente
- **WHEN** responde "si"
- **THEN** T sigue `reservado`, no hay turno nuevo y recibe nuevas opciones sin las 10:30.

### Requirement: Una sola reprogramación por conversación

Reintentos de la confirmación —el mismo evento repetido o mensajes distintos, aun simultáneos— SHALL producir un único turno nuevo y una única cancelación del turno original.

#### Scenario: Reintento duplicado idempotente (borde)

- **WHEN** llegan a la vez "si" y "SI" de Sintético 1 con la conversación confirmando
- **THEN** existe un solo turno nuevo y T tiene un solo registro de cancelación.

### Requirement: Vencimiento de la conversación

Una conversación sin cerrar cuyo plazo venció SHALL cerrarse ante el siguiente mensaje del paciente sin tocar la agenda, respondiendo `reprogramacion_vencida`; ese mensaje SHALL NOT interpretarse como confirmación ni cancelación del turno.

#### Scenario: "2" tardío no cancela

- **GIVEN** a Sintético 1 se le ofrecieron opciones hace 40 minutos
- **WHEN** responde "2"
- **THEN** T sigue `reservado` y recibe `reprogramacion_vencida`.

### Requirement: Opciones por enlace

El sistema SHALL responder sin autenticación en `GET /api/public/reservas/{token}/opciones` con las opciones del turno de esa reserva, exponiendo solo `inicio` y `fin`. Token inválido SHALL responder `404`; turno no reprogramable, `422`. El endpoint SHALL tener límite de pedidos por IP.

#### Scenario: Consultar opciones

- **GIVEN** una reserva online con token y P con horarios libres
- **WHEN** el paciente pide las opciones con su token
- **THEN** responde `200` con hasta 3 horarios, sin sillones ni datos de otros pacientes.

#### Scenario: Token inválido

- **WHEN** se piden opciones con un token inexistente
- **THEN** responde `404`.

### Requirement: Reprogramación por enlace

El sistema SHALL reprogramar en `POST /api/public/reservas/{token}/reprogramar` a un `inicio` que sea una de las opciones vigentes: turno nuevo con el mismo profesional y prestación, y turno original `cancelado` con actor `paciente_enlace`. Un `inicio` que no es opción SHALL responder `422`; un horario ocupado al confirmar, `409` con las alternativas. El endpoint SHALL tener límite de pedidos por IP.

#### Scenario: Reprogramar por enlace (happy path)

- **GIVEN** una reserva online con token y opciones disponibles
- **WHEN** el paciente pide reprogramar a la primera opción
- **THEN** responde `200` con el turno nuevo y el original queda `cancelado` con actor `paciente_enlace`.

#### Scenario: Inicio que no es una opción

- **WHEN** se pide reprogramar a un horario fuera del horario de atención
- **THEN** responde `422` sin cambios.

#### Scenario: Ocupado al confirmar

- **GIVEN** la opción elegida se ocupó después de consultarla
- **WHEN** se pide reprogramar a ella
- **THEN** responde `409` con las alternativas vigentes y el turno original sigue igual.
