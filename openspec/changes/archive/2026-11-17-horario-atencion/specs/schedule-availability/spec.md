# Spec Delta — schedule-availability

## ADDED Requirements

### Requirement: Huecos solo dentro del horario de atención

El sistema SHALL ofrecer solo inicios cuyo turno completo `[inicio, inicio + duración)` quede dentro del horario de atención del profesional para esa fecha (franjas en la zona horaria de la clínica; franjas contiguas forman un tramo único). Un profesional sin franjas SHALL NOT tener huecos.

#### Scenario: Horario partido recorta los huecos

- **GIVEN** P atiende el lunes 2031-03-10 de `09:00–11:00` y `15:00–16:00` (hora local), sin turnos ni bloqueos, prestación de 30 min, paso 15
- **WHEN** la recepcionista consulta de `08:00` a `17:00` locales
- **THEN** los inicios son de 09:00 a 10:30 cada 15 min y de 15:00 a 15:30; 10:45 no aparece porque terminaría a las 11:15.

#### Scenario: Turno que cruza dos franjas contiguas

- **GIVEN** P atiende el lunes `09:00–10:00` y `10:00–11:00`
- **WHEN** se consultan huecos de 30 min de `09:00` a `11:00`
- **THEN** 09:45 aparece, porque el turno `[09:45, 10:15)` cae dentro del tramo continuo.

#### Scenario: Profesional sin horario (borde)

- **GIVEN** P no tiene franjas cargadas
- **WHEN** se consultan huecos de P en cualquier ventana válida
- **THEN** el sistema responde `200` con `[]`.

## MODIFIED Requirements

### Requirement: Huecos libres dentro de una ventana

El sistema SHALL responder en `GET /api/agenda/huecos` con `profesional_id`, `prestacion_id`, `desde` y `hasta` la lista ordenada de inicios, alineados a múltiplos de `AGENDA_PASO_MIN` minutos desde `desde`, en los que un turno normal de esa prestación entraría completo dentro de la ventana y dentro del horario de atención del profesional. Cada hueco SHALL incluir `inicio`, `fin` (inicio + duración de la prestación) y los sillones habilitados libres.

#### Scenario: Día libre devuelve huecos cada paso (happy path)

- **GIVEN** el profesional P con horario que cubre el 2031-03-10 de 09:00 a 10:00, sin turnos ni bloqueos, habilitado en S1 y S2, una prestación de 30 min y `AGENDA_PASO_MIN = 15`
- **WHEN** la recepcionista consulta `desde = 09:00`, `hasta = 10:00`
- **THEN** el sistema responde `200` con los inicios 09:00, 09:15 y 09:30, cada uno con `fin` 30 min después y sillones `[S1, S2]`; 09:45 no aparece porque terminaría después de `hasta`.
