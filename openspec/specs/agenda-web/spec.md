# agenda-web Specification

## Purpose
Pantalla de agenda del staff (US-001, US-002 lado UI): ver el día por sillón y la semana por profesional, dar turnos en el mostrador y gestionar su estado, con la base visual del sistema de diseño.

## Requirements

### Requirement: Vista día por sillón

La página `/agenda` SHALL mostrar por defecto el día actual con una columna por sillón activo y un eje de horas. Cada turno SHALL aparecer en su sillón, con la altura proporcional a su duración, y mostrar la hora, el paciente, la prestación, un badge de estado con texto y la marca "Sobreturno" si corresponde. Un filtro de profesional SHALL limitar los turnos mostrados. El fin del turno SHALL mostrarse tal como lo devuelve el servidor.

#### Scenario: Día con turnos (happy path)

- **WHEN** la recepcionista abre `/agenda`
- **THEN** ve una columna por sillón con los turnos del día en su lugar, cada uno con hora, paciente y estado.

#### Scenario: Cancelados atenuados

- **WHEN** hay un turno `cancelado`
- **THEN** se muestra atenuado y tachado, y su hueco se puede volver a usar.

### Requirement: Vista semana por profesional

La vista **Semana** SHALL mostrar 7 columnas (lunes a domingo) del profesional elegido, con la misma representación de turnos, y SHALL navegar a la semana anterior o siguiente. En la vista semana, elegir un profesional SHALL ser obligatorio.

#### Scenario: Cambio a semana

- **WHEN** la recepcionista elige "Semana" y el profesional P
- **THEN** ve los 7 días de P y la URL refleja `vista=semana&profesional=P`.

### Requirement: Bloqueos y fuera de horario no reservables

Los bloqueos SHALL dibujarse sobre su rango (toda la grilla si son de clínica, la columna si son de sillón y los turnos del profesional si son de profesional) con un patrón distinguible y su motivo, y SHALL NOT permitir crear un turno sobre ellos. Las franjas fuera del horario de atención SHALL verse sombreadas.

#### Scenario: Bloqueo no clickeable (borde)

- **GIVEN** un bloqueo de clínica de 13:00 a 14:00
- **WHEN** la recepcionista hace clic a las 13:15
- **THEN** no se abre el alta y el bloqueo muestra su motivo.

### Requirement: Alta de turno desde la agenda

Para admin y recepción, hacer clic en un hueco libre SHALL abrir un panel de alta con fecha, hora, sillón y profesional precargados. El panel SHALL permitir buscar un paciente por nombre o DNI, darlo de alta rápido si no existe (nombre, apellido, DNI y contacto), elegir la prestación y marcar sobreturno con motivo obligatorio. Al crear, el turno SHALL aparecer en la grilla sin recargar la página.

#### Scenario: Alta con paciente existente (happy path)

- **WHEN** la recepcionista hace clic en S1 a las 10:00, busca "Sintético", elige al paciente y la prestación, y confirma
- **THEN** el turno se crea (`201`) y aparece en S1 a las 10:00.

#### Scenario: Alta rápida de paciente

- **WHEN** la búsqueda no encuentra el DNI y la recepcionista completa el alta rápida
- **THEN** se crea el paciente y queda elegido para el turno.

#### Scenario: Horario tomado, con alternativas (error de negocio)

- **WHEN** la API responde `409` al crear
- **THEN** el panel avisa que el horario ya no está disponible, la agenda se recarga y se ofrecen hasta 6 huecos alternativos del mismo profesional y día, que al elegirlos actualizan la hora.

#### Scenario: El odontólogo no da turnos

- **WHEN** el odontólogo hace clic en un hueco libre de su agenda
- **THEN** no se abre el alta (crear turnos es de admin y recepción, como en `POST /api/turnos`).

### Requirement: Detalle y transiciones de estado

Hacer clic en un turno SHALL abrir su detalle con paciente, prestación, horario, sillón, profesional, origen y estado, y SHALL ofrecer solo las transiciones permitidas para su estado y para el rol: admin y recepción pueden confirmar, cancelar (con motivo opcional), marcar asistido o ausente; el odontólogo solo asistido o ausente, y únicamente desde el inicio. El resultado SHALL reflejarse en la grilla.

#### Scenario: Confirmar un turno

- **WHEN** la recepcionista confirma un turno `reservado`
- **THEN** el badge pasa a "Confirmado".

#### Scenario: Transición rechazada

- **WHEN** la API responde `422`
- **THEN** el detalle muestra el motivo y el turno no cambia.

### Requirement: Datos frescos y deep-link

La agenda SHALL cargar en paralelo turnos, bloqueos y horarios, SHALL recargarse al volver a la pestaña y cada 60 segundos, y SHALL reflejar en la URL la fecha, la vista y el profesional, de modo que un enlace abra la misma agenda. El odontólogo SHALL ver fija su propia agenda.

#### Scenario: Turno creado por la reserva online

- **GIVEN** la agenda abierta
- **WHEN** un paciente reserva online y pasan 60 segundos (o la recepcionista vuelve a la pestaña)
- **THEN** el turno aparece con el origen "Enlace".

#### Scenario: Deep-link

- **WHEN** se abre `/agenda?fecha=2033-09-05&vista=dia`
- **THEN** la agenda muestra ese día.

### Requirement: Accesibilidad de la agenda

Cada turno SHALL ser un control con nombre accesible (hora, paciente y estado). La grilla SHALL ser navegable con teclado. Los paneles SHALL atrapar el foco y cerrarse con Escape. Los resultados de crear o cambiar de estado SHALL anunciarse en una región `aria-live`. Las animaciones SHALL respetar `prefers-reduced-motion`.

#### Scenario: Turno con nombre accesible

- **WHEN** un lector de pantalla recorre la grilla
- **THEN** cada turno se anuncia como "10:00 a 10:30, Sintético, Ana, Confirmado".
