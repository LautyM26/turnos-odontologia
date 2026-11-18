# reschedule-web Specification

## Purpose
Pantalla pública para que el paciente reprograme su turno con el enlace privado (el del chatbot de WhatsApp o el del comprobante), sobre la API de C-17.

## Requirements

### Requirement: Opciones de reprogramación

La página `/reprogramar/{token}` SHALL mostrar, sin sesión, el turno actual (clínica, profesional, prestación, fecha y hora en la zona de la clínica) y las opciones de horario que devuelve `GET /api/public/reservas/{token}/opciones`. Si no hay opciones, SHALL indicarlo con una salida para volver al comprobante.

#### Scenario: Paciente ve opciones (happy path)

- **WHEN** el paciente abre `/reprogramar/{token}` de un turno futuro
- **THEN** ve su turno actual y hasta 3 horarios para elegir.

#### Scenario: Turno que no se puede reprogramar

- **WHEN** la API responde `422` (turno pasado, cancelado o cerrado)
- **THEN** la página explica que el turno ya no se puede reprogramar online.

#### Scenario: Enlace inválido

- **WHEN** la API responde `404`
- **THEN** la página muestra "Reserva no encontrada".

### Requirement: Confirmar el nuevo horario

Al elegir un horario y confirmar, la página SHALL enviar `POST /api/public/reservas/{token}/reprogramar` con el inicio elegido y, con `200`, SHALL mostrar el turno reprogramado con acceso al comprobante. Ante un `409`, SHALL avisar que el horario se ocupó y ofrecer las `alternativas` de la respuesta para elegir otra vez.

#### Scenario: Reprogramación confirmada

- **WHEN** el paciente elige el jueves a las 10:30 y confirma
- **THEN** ve "Turno reprogramado" con el nuevo horario.

#### Scenario: Horario ocupado al confirmar (borde)

- **WHEN** la API responde `409` con alternativas
- **THEN** la página avisa y muestra esas alternativas, sin perder el contexto del turno.

#### Scenario: Demasiados pedidos

- **WHEN** la API responde `429`
- **THEN** la página pide esperar un minuto antes de reintentar.
