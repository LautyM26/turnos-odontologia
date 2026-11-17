# Spec Delta — appointments

## ADDED Requirements

### Requirement: El turno normal respeta el horario de atención

El sistema SHALL rechazar con `409` "Horario no disponible", sin persistir, el alta de un turno normal cuyo rango `[inicio, fin)` no quede completamente dentro del horario de atención del profesional (franjas en la zona horaria de la clínica; franjas contiguas forman un tramo único). Un profesional sin franjas SHALL NOT aceptar turnos normales. El sobreturno SHALL quedar exceptuado de este requisito, pero no de los bloqueos.

#### Scenario: Turno dentro del horario (happy path)

- **GIVEN** P atiende el lunes 2031-03-10 de `09:00–13:00` hora local
- **WHEN** la recepcionista crea un turno de 30 min para P a las `12:30` locales
- **THEN** el sistema responde `201`.

#### Scenario: Turno que termina fuera del horario (error de negocio)

- **GIVEN** P atiende el lunes de `09:00–13:00`
- **WHEN** la recepcionista crea un turno de 30 min a las `12:45` locales
- **THEN** el sistema responde `409` "Horario no disponible" y no persiste el turno.

#### Scenario: Profesional sin horario

- **GIVEN** P no tiene franjas cargadas
- **WHEN** la recepcionista crea un turno normal para P
- **THEN** el sistema responde `409` y no persiste el turno.

#### Scenario: Sobreturno fuera del horario (borde)

- **GIVEN** P atiende el lunes de `09:00–13:00` y no hay bloqueos
- **WHEN** la recepcionista crea un sobreturno con motivo a las `13:15` locales
- **THEN** el sistema responde `201` con `es_sobreturno = true`.
