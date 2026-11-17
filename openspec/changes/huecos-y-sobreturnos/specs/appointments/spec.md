# Spec Delta — appointments

## ADDED Requirements

### Requirement: Sobreturno por rol con motivo

El sistema SHALL permitir crear en `POST /api/turnos` un sobreturno enviando `sobreturno: true` y un `motivo_sobreturno` no vacío de hasta 500 caracteres (RN-AG-04). Un sobreturno SHALL quedar exceptuado de los requisitos de no solapamiento por profesional y por sillón, SHALL cumplir las demás validaciones del alta y SHALL quedar marcado con `es_sobreturno = true` y su motivo.

#### Scenario: Recepcionista da un sobreturno sobre un horario ocupado

- **GIVEN** P tiene un turno `reservado` `[10:00, 10:30)` en S1
- **WHEN** la recepcionista crea un turno para P en S1 a las 10:00 con `sobreturno: true` y motivo "urgencia, dolor agudo"
- **THEN** el sistema responde `201` con `estado = "reservado"`, `es_sobreturno = true` y el motivo.

#### Scenario: Sobreturno sin motivo

- **WHEN** se envía `sobreturno: true` sin `motivo_sobreturno` o con texto en blanco
- **THEN** el sistema responde `422` y no persiste el turno.

#### Scenario: Motivo sin sobreturno

- **WHEN** se envía `motivo_sobreturno` sin `sobreturno: true`
- **THEN** el sistema responde `422` y no persiste el turno.

### Requirement: El sobreturno respeta los bloqueos

El sistema SHALL rechazar con `409` "Horario no disponible" un sobreturno cuyo rango se superponga con un bloqueo activo del profesional, del sillón o de toda la clínica (RN-AG-03).

#### Scenario: Sobreturno sobre un feriado (borde)

- **GIVEN** un bloqueo de toda la clínica que cubre el 2031-03-10
- **WHEN** la recepcionista crea un sobreturno ese día
- **THEN** el sistema responde `409` y no persiste el turno.

### Requirement: El sobreturno sigue el ciclo de estados del turno

El sistema SHALL aplicar a un sobreturno las mismas transiciones de estado que a cualquier turno, sin que pasar a `confirmado` o `asistido` lo haga chocar con el turno al que se superpone.

#### Scenario: Sobreturno superpuesto pasa a asistido (borde)

- **GIVEN** un sobreturno superpuesto a un turno `confirmado` del mismo profesional, ambos ya iniciados
- **WHEN** la recepcionista marca ambos como `asistido`
- **THEN** las dos transiciones responden `200`.

## MODIFIED Requirements

### Requirement: Solo los turnos activos ocupan el horario

El sistema SHALL considerar ocupado un rango solo por turnos activos (`reservado`, `confirmado`, `asistido`), no dados de baja y no marcados como sobreturno; un turno `cancelado` o `ausente`, dado de baja lógica o marcado como sobreturno SHALL NOT impedir un nuevo turno en el mismo rango.

#### Scenario: Turno cancelado libera el hueco

- **GIVEN** P tiene en S1 un turno `cancelado` `[10:00, 10:30)`
- **WHEN** la recepcionista crea un turno para P en S1 con `inicio = 10:00`
- **THEN** el sistema responde `201`

#### Scenario: Turno dado de baja libera el hueco

- **GIVEN** S1 tiene un turno `reservado` `[11:00, 11:30)` dado de baja lógica
- **WHEN** la recepcionista crea un turno para Q en S1 con `inicio = 11:00`
- **THEN** el sistema responde `201`

#### Scenario: Un sobreturno no ocupa el horario

- **GIVEN** P tiene en S1 solo un sobreturno `reservado` `[12:00, 12:30)`
- **WHEN** la recepcionista crea un turno normal para P en S1 con `inicio = 12:00`
- **THEN** el sistema responde `201`
