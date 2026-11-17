# Spec Delta — appointments

## ADDED Requirements

### Requirement: Transición de estado explícita

El sistema SHALL permitir cambiar el estado de un turno en `POST /api/turnos/{id}/transicion` indicando el estado destino, solo según esta tabla (RN-TU-01): `reservado → confirmado | cancelado | asistido | ausente` y `confirmado → asistido | ausente | cancelado`. El sistema SHALL responder `200` con el turno actualizado.

#### Scenario: Recepcionista confirma un turno reservado (happy path)

- **GIVEN** un turno `reservado` de la clínica del usuario
- **WHEN** un recepcionista envía `{"estado": "confirmado"}`
- **THEN** el sistema responde `200` con `estado = "confirmado"` y el resto de los datos del turno sin cambios.

#### Scenario: Turno confirmado pasa a asistido

- **GIVEN** un turno `confirmado` cuyo inicio ya pasó
- **WHEN** un recepcionista envía `{"estado": "asistido"}`
- **THEN** el sistema responde `200` con `estado = "asistido"`.

#### Scenario: Turno reservado sin confirmar pasa a ausente

- **GIVEN** un turno `reservado` cuyo inicio ya pasó
- **WHEN** un recepcionista envía `{"estado": "ausente"}`
- **THEN** el sistema responde `200` con `estado = "ausente"`.

### Requirement: Transiciones no permitidas rechazadas

El sistema SHALL rechazar con `422` toda transición fuera de la tabla, incluidas las que parten de un estado terminal (`asistido`, `ausente`, `cancelado`), las que repiten el estado actual y los destinos `reservado` o `sobreturno`. El sistema SHALL dejar el turno sin cambios y SHALL rechazar con `422` campos no declarados en el cuerpo.

#### Scenario: Turno cancelado no puede confirmarse (error de negocio)

- **GIVEN** un turno `cancelado`
- **WHEN** un recepcionista envía `{"estado": "confirmado"}`
- **THEN** el sistema responde `422` y el turno sigue `cancelado`.

#### Scenario: Asistido no vuelve a reservado

- **GIVEN** un turno `asistido`
- **WHEN** un recepcionista envía `{"estado": "reservado"}`
- **THEN** el sistema responde `422` y el turno sigue `asistido`.

#### Scenario: Campo extra en el cuerpo

- **WHEN** el cuerpo incluye un campo no declarado, por ejemplo `inicio`
- **THEN** el sistema responde `422` y el turno no cambia.

### Requirement: Asistencia y ausencia solo desde el inicio del turno

El sistema SHALL rechazar con `422` las transiciones a `asistido` o `ausente` cuando el instante actual del servidor (UTC) es anterior al `inicio` del turno, y SHALL aceptarlas desde el instante de inicio inclusive. Confirmar y cancelar SHALL estar permitidos en cualquier momento.

#### Scenario: Ausente antes de la hora (borde)

- **GIVEN** un turno `confirmado` que empieza dentro de una hora
- **WHEN** un recepcionista envía `{"estado": "ausente"}`
- **THEN** el sistema responde `422` y el turno sigue `confirmado`.

#### Scenario: Asistido exactamente a la hora de inicio (borde)

- **GIVEN** un turno `reservado` y el reloj del servidor exactamente en su `inicio`
- **WHEN** un recepcionista envía `{"estado": "asistido"}`
- **THEN** el sistema responde `200` con `estado = "asistido"`.

### Requirement: Historial de transiciones auditado e inmutable

El sistema SHALL registrar cada transición aceptada en un historial con turno, estado anterior, estado nuevo, usuario que la hizo, motivo opcional y fecha/hora TIMESTAMPTZ del servidor, en la misma transacción que el cambio de estado. El sistema SHALL impedir modificar o borrar ese historial a nivel base de datos.

#### Scenario: Transición registrada en el historial

- **WHEN** un recepcionista cancela un turno `reservado` con motivo "paciente avisó por teléfono"
- **THEN** existe exactamente una fila de historial `reservado → cancelado` con el id del recepcionista, el motivo y la fecha/hora del servidor.

#### Scenario: Transición rechazada no deja historial

- **WHEN** una transición es rechazada con `403` o `422`
- **THEN** no se agrega ninguna fila al historial.

#### Scenario: Historial inmutable

- **WHEN** se intenta un `UPDATE` o `DELETE` directo sobre una fila del historial
- **THEN** la base de datos rechaza la operación.

### Requirement: Cancelado y ausente liberan el hueco

El sistema SHALL considerar libre el horario de un turno que pasó a `cancelado` o `ausente`, de modo que pueda crearse otro turno en el mismo profesional, sillón y rango.

#### Scenario: Reservar el hueco de un turno cancelado

- **GIVEN** un turno `reservado` cancelado mediante una transición
- **WHEN** un recepcionista crea un turno con el mismo profesional, sillón e inicio
- **THEN** el sistema responde `201`.

### Requirement: Transiciones concurrentes sobre el mismo turno

El sistema SHALL serializar las transiciones simultáneas sobre un mismo turno, de modo que cada una se evalúe contra el estado que dejó la anterior y nunca se pierda ni se duplique un cambio.

#### Scenario: Dos cancelaciones simultáneas (borde)

- **GIVEN** un turno `reservado`
- **WHEN** dos pedidos concurrentes envían `{"estado": "cancelado"}`
- **THEN** exactamente uno recibe `200`, el otro recibe `422`, el turno queda `cancelado` y hay exactamente una fila de historial.

### Requirement: Transiciones restringidas por rol

El sistema SHALL permitir a `admin` y `recepcionista` cualquier transición de la tabla. El sistema SHALL permitir al `odontologo` solo transiciones a `asistido` o `ausente` en turnos de su propia agenda, y SHALL responder `403` en cualquier otro caso. Sin autenticación SHALL responder `401`.

#### Scenario: Odontólogo marca asistido en su agenda

- **GIVEN** un turno `confirmado` ya iniciado del profesional vinculado al odontólogo
- **WHEN** el odontólogo envía `{"estado": "asistido"}`
- **THEN** el sistema responde `200`.

#### Scenario: Odontólogo intenta confirmar

- **WHEN** un odontólogo envía `{"estado": "confirmado"}` sobre un turno de su agenda
- **THEN** el sistema responde `403` y el turno no cambia.

#### Scenario: Odontólogo sobre la agenda de otro profesional

- **WHEN** un odontólogo envía `{"estado": "ausente"}` sobre un turno de otro profesional de su clínica
- **THEN** el sistema responde `403` y el turno no cambia.

#### Scenario: Sin autenticación

- **WHEN** se llama al endpoint sin token
- **THEN** el sistema responde `401`.

### Requirement: Transiciones aisladas por clínica

El sistema SHALL responder `404` ante una transición sobre un turno de otra clínica o inexistente, sin revelar su existencia ni modificarlo.

#### Scenario: Turno de otra clínica

- **WHEN** un recepcionista de la clínica A envía una transición sobre un turno de la clínica B
- **THEN** el sistema responde `404` y el turno de la clínica B no cambia.
