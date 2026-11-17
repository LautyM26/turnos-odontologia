# schedule-availability Specification

## Purpose
Permite al staff consultar los huecos libres reales de un profesional para una prestación dentro de una ventana de tiempo, respetando turnos, bloqueos y habilitaciones profesional–sillón (Flujo 1, DD-04).

## Requirements

### Requirement: Huecos libres dentro de una ventana

El sistema SHALL responder en `GET /api/agenda/huecos` con `profesional_id`, `prestacion_id`, `desde` y `hasta` la lista ordenada de inicios, alineados a múltiplos de `AGENDA_PASO_MIN` minutos desde `desde`, en los que un turno normal de esa prestación entraría completo dentro de la ventana y dentro del horario de atención del profesional. Cada hueco SHALL incluir `inicio`, `fin` (inicio + duración de la prestación) y los sillones habilitados libres.

#### Scenario: Día libre devuelve huecos cada paso (happy path)

- **GIVEN** el profesional P con horario que cubre el 2031-03-10 de 09:00 a 10:00, sin turnos ni bloqueos, habilitado en S1 y S2, una prestación de 30 min y `AGENDA_PASO_MIN = 15`
- **WHEN** la recepcionista consulta `desde = 09:00`, `hasta = 10:00`
- **THEN** el sistema responde `200` con los inicios 09:00, 09:15 y 09:30, cada uno con `fin` 30 min después y sillones `[S1, S2]`; 09:45 no aparece porque terminaría después de `hasta`.

### Requirement: Turnos y bloqueos restan huecos

El sistema SHALL excluir los inicios cuyo rango se superponga con un turno activo no marcado como sobreturno del profesional, con un bloqueo del profesional o de toda la clínica, o, por sillón, con un turno activo o un bloqueo de ese sillón. Un inicio SHALL aparecer si al menos un sillón habilitado queda libre. Los rangos son semiabiertos `[inicio, fin)`.

#### Scenario: Turno del profesional ocupa el hueco

- **GIVEN** P tiene un turno `reservado` `[09:15, 09:45)` en S1
- **WHEN** se consultan huecos de 30 min entre 09:00 y 10:30
- **THEN** no aparecen 09:00, 09:15 ni 09:30, y sí aparecen 09:45 y 10:00 (contiguo al fin del turno).

#### Scenario: Bloqueo de clínica

- **GIVEN** un bloqueo de toda la clínica `[12:00, 13:00)`
- **WHEN** se consultan huecos de 30 min entre 11:30 y 13:30
- **THEN** solo aparecen 11:30 y 13:00.

#### Scenario: Un sillón ocupado deja el otro

- **GIVEN** Q tiene un turno activo en S1 `[09:00, 09:30)` y P está habilitado en S1 y S2
- **WHEN** se consultan huecos de P entre 09:00 y 09:30
- **THEN** aparece 09:00 con sillones `[S2]`.

#### Scenario: Turno cancelado o sobreturno no restan

- **GIVEN** P tiene un turno `cancelado` y un sobreturno activo en la ventana
- **WHEN** se consultan huecos
- **THEN** esos rangos aparecen como libres.

### Requirement: Huecos no se ofrecen en el pasado

El sistema SHALL omitir los inicios anteriores al instante actual del servidor (UTC).

#### Scenario: Ventana que empieza en el pasado

- **GIVEN** el reloj del servidor en 2031-03-10 10:05
- **WHEN** se consultan huecos de 30 min entre 09:00 y 11:00
- **THEN** el primer inicio devuelto es 10:15.

### Requirement: Ventana y referencias válidas

El sistema SHALL responder `422` si `desde` o `hasta` no tienen zona horaria, si `hasta <= desde`, si la ventana supera 7 días, o si el profesional (o su agenda) o la prestación son inexistentes, inactivos o de otra clínica.

#### Scenario: Ventana mayor a 7 días (error de negocio)

- **WHEN** se consultan huecos entre 2031-03-01 y 2031-03-09
- **THEN** el sistema responde `422` sin calcular huecos.

#### Scenario: Prestación inactiva

- **WHEN** se consultan huecos para una prestación dada de baja
- **THEN** el sistema responde `422`.

#### Scenario: Profesional de otra clínica

- **WHEN** una recepcionista de A consulta huecos de un profesional de B
- **THEN** el sistema responde `422`.

### Requirement: Consulta de huecos por rol

El sistema SHALL permitir la consulta a `admin` y `recepcionista` para cualquier profesional de su clínica, y al `odontologo` solo para el profesional vinculado a su usuario (`403` en otro caso). Sin autenticación SHALL responder `401`.

#### Scenario: Odontólogo consulta su agenda

- **WHEN** el odontólogo vinculado a P consulta huecos de P
- **THEN** el sistema responde `200`.

#### Scenario: Odontólogo consulta otra agenda

- **WHEN** el odontólogo vinculado a P consulta huecos de Q
- **THEN** el sistema responde `403`.

#### Scenario: Sin autenticación

- **WHEN** se consultan huecos sin token
- **THEN** el sistema responde `401`.

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
