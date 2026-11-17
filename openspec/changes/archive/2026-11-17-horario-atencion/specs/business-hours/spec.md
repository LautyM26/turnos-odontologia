# Spec Delta — business-hours

## Purpose

Define cuándo atiende cada profesional: franjas semanales en la hora local de la clínica. Los huecos (C-05c) y el alta de turnos normales se limitan a esas franjas; la reserva pública (C-06) hereda el límite.

## ADDED Requirements

### Requirement: Franjas semanales de atención por profesional

El sistema SHALL guardar, por profesional, un conjunto de franjas de atención, cada una con día de la semana (1 = lunes … 7 = domingo, ISO 8601), hora de inicio y hora de fin en formato `HH:MM` de hora local de la clínica, con `inicio < fin`, horas entre `00:00` y `24:00` y sin cruzar la medianoche. Las franjas de un mismo día SHALL NOT superponerse; dos franjas contiguas (una termina donde empieza la otra) SHALL considerarse un único tramo de atención.

#### Scenario: Horario partido de lunes a viernes (happy path)

- **WHEN** el admin hace `PUT /api/admin/profesionales/{P}/horario` con lunes a viernes `09:00–13:00` y `15:00–19:00`
- **THEN** el sistema responde `200` con las 10 franjas ordenadas por día y hora de inicio.

#### Scenario: Franjas superpuestas en el mismo día (error de negocio)

- **WHEN** el admin envía para el lunes `09:00–13:00` y `12:00–16:00`
- **THEN** el sistema responde `422` y el horario anterior de P queda intacto.

#### Scenario: Franja inválida

- **WHEN** el admin envía una franja con `inicio >= fin`, una hora fuera de `00:00–24:00`, un formato distinto de `HH:MM` o un día fuera de 1–7
- **THEN** el sistema responde `422` sin aplicar cambios.

#### Scenario: Día completo

- **WHEN** el admin envía para el sábado `00:00–24:00`
- **THEN** el sistema responde `200` y el profesional atiende todo el sábado.

### Requirement: Reemplazo atómico del horario solo por admin

El sistema SHALL permitir solo al admin reemplazar el horario completo de un profesional de su clínica, en una sola operación todo o nada. Una lista vacía SHALL dejar al profesional sin horario. Un profesional inexistente, dado de baja o de otra clínica SHALL responder `404`; recepción y odontólogo SHALL recibir `403`.

#### Scenario: Reemplazo total

- **GIVEN** P atiende los lunes `09:00–13:00`
- **WHEN** el admin envía solo martes `10:00–14:00`
- **THEN** P deja de atender los lunes y atiende los martes `10:00–14:00`.

#### Scenario: Recepción no edita horarios

- **WHEN** una recepcionista hace `PUT /api/admin/profesionales/{P}/horario`
- **THEN** el sistema responde `403`.

#### Scenario: Profesional de otra clínica

- **WHEN** el admin de A reemplaza el horario de un profesional de B
- **THEN** el sistema responde `404` y el horario del profesional de B no cambia.

### Requirement: Consulta del horario por el staff

El sistema SHALL devolver en `GET /api/catalogo/profesionales/{id}/horario` las franjas del profesional, ordenadas por día y hora de inicio, junto con la `zona_horaria` de la clínica, a cualquier usuario de staff (admin, recepcionista, odontólogo) de la misma clínica. Un profesional sin franjas SHALL devolver una lista vacía; uno inexistente, dado de baja o de otra clínica SHALL responder `404`.

#### Scenario: Recepcionista consulta el horario

- **WHEN** la recepcionista consulta el horario de P
- **THEN** el sistema responde `200` con las franjas y `zona_horaria = "America/Argentina/Buenos_Aires"`.

### Requirement: Zona horaria de la clínica

Cada clínica SHALL tener una zona horaria IANA, por defecto `America/Argentina/Buenos_Aires`, en la que se interpretan sus franjas. La conversión de hora local a instante absoluto SHALL respetar las reglas de la zona para cada fecha, incluido un eventual horario de verano.

#### Scenario: Franja local convertida a UTC

- **GIVEN** la clínica en `America/Argentina/Buenos_Aires` (UTC−3) y P con lunes `09:00–13:00`
- **WHEN** se consultan huecos del lunes 2031-03-10
- **THEN** el primer inicio posible es `2031-03-10T12:00:00Z`.
