# appointments Specification

## Purpose
Define el alta de turnos por el staff de la clínica con duración calculada en servidor y prevención dura de solapamientos por profesional y por sillón, respetando los bloqueos de agenda (RN-AG-01, RN-AG-02, RN-AG-03), y el ciclo de vida del turno con transiciones de estado explícitas y auditadas (RN-TU-01), con RBAC y aislamiento multi-tenant.

> Datos de los escenarios 100 % sintéticos: clínicas A y B, profesionales P y Q, sillones S1 y S2 (P y Q habilitados en ambos salvo que se indique), prestación "Control sintético" de 30 min, paciente "Paciente Sintético 1". Fecha de referencia `2031-03-10`, horas en UTC.

## Requirements

### Requirement: Alta de turno con duración calculada en servidor

El sistema SHALL permitir crear un turno en `POST /api/turnos` indicando profesional, sillón, paciente, prestación e `inicio` con zona horaria. El sistema SHALL calcular `fin = inicio + duración de la prestación` exclusivamente en el servidor (RN-AG-02), SHALL guardar la duración aplicada como parte del turno, SHALL crear el turno en estado `reservado` con origen `mostrador` y SHALL responder `201` con el turno creado. El sistema SHALL rechazar con `422` un `inicio` sin zona horaria y cualquier campo no declarado en el contrato, incluidos `fin`, `duracion_min`, `estado` y `clinica_id`. El sistema SHALL rechazar con `422` un turno cuyo `inicio` sea anterior al instante actual del servidor (UTC).

#### Scenario: Recepcionista crea un turno (happy path)

- **GIVEN** la clínica A sin turnos para P ni S1 el `2031-03-10`
- **WHEN** la recepcionista de A crea un turno para P en S1, paciente "Paciente Sintético 1", prestación "Control sintético" (30 min), `inicio = 2031-03-10T10:00:00Z`
- **THEN** el sistema responde `201` con `estado = reservado`, `origen = mostrador`, `duracion_min = 30` y `fin = 2031-03-10T10:30:00Z`

#### Scenario: El cliente intenta fijar el fin o la duración

- **GIVEN** el mismo pedido válido del happy path
- **WHEN** el cuerpo incluye además `fin = 2031-03-10T11:00:00Z` o `duracion_min = 60`
- **THEN** el sistema responde `422` y no persiste ningún turno

#### Scenario: Inicio sin zona horaria

- **GIVEN** un pedido por lo demás válido
- **WHEN** se envía `inicio = 2031-03-10T10:00:00` sin offset
- **THEN** el sistema responde `422` y no persiste ningún turno

#### Scenario: Turno en el pasado

- **GIVEN** el instante actual del servidor es `2031-03-10T12:00:00Z` y P y S1 están libres
- **WHEN** la recepcionista crea un turno para P en S1 con `inicio = 2031-03-10T11:00:00Z`
- **THEN** el sistema responde `422` "No se pueden crear turnos en el pasado" y no persiste ningún turno

### Requirement: Sin solapamiento de turnos por profesional

El sistema SHALL impedir que un profesional tenga dos turnos activos cuyos rangos `[inicio, fin)` se superpongan, aunque estén en sillones distintos (RN-AG-01), y SHALL responder `409` "Horario no disponible" sin exponer datos del paciente ni del turno en conflicto.

#### Scenario: Profesional ocupado en otro sillón

- **GIVEN** P tiene un turno `reservado` en S1 `[10:00, 10:30)`
- **WHEN** la recepcionista crea un turno para P en S2 con `inicio = 10:15` (30 min)
- **THEN** el sistema responde `409` y P conserva un solo turno en ese rango

### Requirement: Sin solapamiento de turnos por sillón

El sistema SHALL impedir que un sillón/recurso tenga dos turnos activos cuyos rangos `[inicio, fin)` se superpongan, aunque sean de profesionales distintos (RN-AG-01), y SHALL responder `409` "Horario no disponible".

#### Scenario: Sillón ocupado por otro profesional

- **GIVEN** S1 tiene un turno `reservado` de P `[10:00, 10:30)`
- **WHEN** la recepcionista crea un turno para Q en S1 con `inicio = 09:45` (30 min, rango `[09:45, 10:15)`)
- **THEN** el sistema responde `409` y S1 conserva un solo turno en ese rango

### Requirement: Rangos semiabiertos permiten turnos contiguos

El sistema SHALL tratar el rango de cada turno como semiabierto `[inicio, fin)`: un turno que empieza exactamente cuando termina otro turno o un bloqueo, o que termina exactamente cuando empieza un bloqueo, SHALL NOT considerarse superpuesto.

#### Scenario: Turno que empieza justo cuando termina otro

- **GIVEN** P tiene un turno `reservado` en S1 `[10:00, 10:30)`
- **WHEN** la recepcionista crea un turno para P en S1 con `inicio = 10:30` (30 min)
- **THEN** el sistema responde `201` con `fin = 11:00`

#### Scenario: Turno que termina justo cuando empieza un bloqueo

- **GIVEN** P tiene un bloqueo `[13:00, 14:00)`
- **WHEN** la recepcionista crea un turno para P en S1 con `inicio = 12:30` (30 min)
- **THEN** el sistema responde `201` con `fin = 13:00`

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

### Requirement: Los bloqueos impiden reservas

El sistema SHALL rechazar con `409` "Horario no disponible" un turno cuyo rango se superponga con un bloqueo activo que aplique al profesional, al sillón o a toda la clínica (RN-AG-03), y SHALL ignorar bloqueos inactivos, de otros profesionales, de otros sillones y de otras clínicas.

#### Scenario: Bloqueo del profesional

- **GIVEN** P tiene un bloqueo "Almuerzo" `[13:00, 14:00)`
- **WHEN** la recepcionista crea un turno para P en S1 con `inicio = 13:30`
- **THEN** el sistema responde `409` y no persiste el turno

#### Scenario: Bloqueo del sillón

- **GIVEN** S1 tiene un bloqueo "Mantenimiento" `[09:00, 10:00)`
- **WHEN** la recepcionista crea un turno para Q en S1 con `inicio = 09:30`
- **THEN** el sistema responde `409`

#### Scenario: Bloqueo de clínica

- **GIVEN** la clínica A tiene un bloqueo de clínica "Feriado" para todo el `2031-03-10`
- **WHEN** la recepcionista crea un turno para cualquier profesional y sillón de A ese día
- **THEN** el sistema responde `409`

#### Scenario: Bloqueo de otro profesional no impide

- **GIVEN** Q tiene un bloqueo `[15:00, 16:00)`
- **WHEN** la recepcionista crea un turno para P en S2 con `inicio = 15:00`
- **THEN** el sistema responde `201`

### Requirement: Concurrencia sobre el mismo hueco

Ante pedidos simultáneos que compiten por el mismo profesional o sillón en rangos superpuestos, el sistema SHALL aceptar exactamente uno (gana la primera escritura confirmada) y SHALL responder `409` a los demás, sin dejar turnos duplicados (KB07 Flujo 1, doble clic).

#### Scenario: Doble clic concurrente

- **GIVEN** P y S1 libres de `10:00` a `10:30`
- **WHEN** se envían 5 pedidos simultáneos idénticos para P en S1 con `inicio = 10:00`
- **THEN** exactamente uno recibe `201`, los otros cuatro reciben `409` y existe un solo turno activo en ese rango

### Requirement: Garantía de no solapamiento en la capa de persistencia

La prevención de solapamientos entre turnos activos por profesional y por sillón SHALL sostenerse en la propia base de datos, de modo que una escritura que no pase por la API (script, migración de datos, bug de la aplicación) tampoco pueda persistir un turno activo superpuesto dentro de la misma clínica (regla dura 8).

#### Scenario: Inserción directa superpuesta por profesional

- **GIVEN** P tiene un turno `reservado` `[10:00, 10:30)` en S1
- **WHEN** se inserta directamente en la base de datos un turno `reservado` de P en S2 `[10:15, 10:45)`
- **THEN** la base de datos rechaza la inserción por violación de exclusión

#### Scenario: Inserción directa superpuesta por sillón

- **GIVEN** S1 tiene un turno `reservado` de P `[10:00, 10:30)`
- **WHEN** se inserta directamente un turno `reservado` de Q en S1 `[10:00, 10:30)`
- **THEN** la base de datos rechaza la inserción por violación de exclusión

### Requirement: Referencias válidas del tenant

El sistema SHALL exigir que profesional, sillón, paciente y prestación existan, estén activos y pertenezcan a la clínica del JWT; que el profesional tenga la agenda activa; y que el profesional esté habilitado en el sillón indicado. Cualquier incumplimiento SHALL responder `422` sin persistir el turno.

#### Scenario: Paciente dado de baja

- **GIVEN** "Paciente Sintético 2" dado de baja lógica en A
- **WHEN** la recepcionista crea un turno para ese paciente
- **THEN** el sistema responde `422`

#### Scenario: Prestación inactiva

- **GIVEN** una prestación sintética inactiva en A
- **WHEN** la recepcionista crea un turno con esa prestación
- **THEN** el sistema responde `422`

#### Scenario: Profesional con agenda inactiva

- **GIVEN** Q con `agenda_activa = false`
- **WHEN** la recepcionista crea un turno para Q
- **THEN** el sistema responde `422`

#### Scenario: Profesional no habilitado en el sillón

- **GIVEN** P no está habilitado en el sillón S3
- **WHEN** la recepcionista crea un turno para P en S3
- **THEN** el sistema responde `422`

#### Scenario: Referencia de otra clínica

- **GIVEN** un profesional, sillón, paciente o prestación de la clínica B
- **WHEN** la recepcionista de A crea un turno usando ese id
- **THEN** el sistema responde `422` y no persiste el turno

### Requirement: Alta de turnos restringida por rol

El sistema SHALL permitir crear turnos solo a los roles `admin` y `recepcionista` de la clínica (matriz RBAC `03`: odontólogo "Lectura + bloqueos propios"), SHALL responder `403` a `odontologo` y SHALL responder `401` sin token válido. La autorización SHALL evaluarse antes de validar el cuerpo y las referencias.

#### Scenario: Admin crea un turno

- **GIVEN** un usuario `admin` de A
- **WHEN** crea un turno válido
- **THEN** el sistema responde `201`

#### Scenario: Odontólogo no crea turnos

- **GIVEN** un usuario `odontologo` de A vinculado a P
- **WHEN** intenta crear un turno para P
- **THEN** el sistema responde `403` y no persiste el turno

#### Scenario: Sin autenticación

- **GIVEN** un pedido sin token
- **WHEN** se llama a `POST /api/turnos`
- **THEN** el sistema responde `401`

### Requirement: Aislamiento multi-tenant de turnos

Los turnos SHALL estar aislados por clínica: los solapamientos SHALL evaluarse solo dentro de la misma clínica, y un turno de otra clínica SHALL ser invisible (`404` en `GET /api/turnos/{id}`, 0 filas en consultas scoped por tenant).

#### Scenario: Mismo horario en otra clínica

- **GIVEN** la clínica A tiene un turno `reservado` `[10:00, 10:30)`
- **WHEN** la recepcionista de B crea un turno con profesional, sillón, paciente y prestación de B con `inicio = 10:00`
- **THEN** el sistema responde `201`

#### Scenario: Lectura de un turno ajeno

- **GIVEN** un turno creado en la clínica A
- **WHEN** un usuario de B pide `GET /api/turnos/{id}` con ese id
- **THEN** el sistema responde `404`

#### Scenario: Consulta cruzada sin filas

- **GIVEN** turnos en A y B
- **WHEN** se consultan turnos scoped a la clínica B
- **THEN** la consulta no devuelve ningún turno de A

### Requirement: Esquema de turnos reversible e indexado por tenant

La estructura de persistencia de turnos SHALL poder aplicarse y revertirse sin residuos (upgrade/downgrade), SHALL guardar tiempos con zona horaria y SHALL indexar las búsquedas de agenda con prefijo de clínica (profesional+inicio, sillón+inicio, paciente+inicio, estado).

#### Scenario: Upgrade y downgrade limpios

- **GIVEN** la base en la revisión de pacientes (`004`)
- **WHEN** se aplica la revisión de turnos, se revierte y se vuelve a aplicar
- **THEN** la tabla de turnos y sus restricciones existen tras cada upgrade, no quedan tras el downgrade y las tablas previas permanecen intactas

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

### Requirement: Transiciones del paciente por enlace

El historial de transiciones SHALL registrar el tipo de actor de cada transición: `usuario` (con `actor_usuario_id` obligatorio) o `paciente_enlace` (sin usuario). Un turno reservado por enlace SHALL quedar con `origen = "enlace"`; uno creado en el mostrador, con `origen = "mostrador"`. La base SHALL rechazar una transición de tipo `usuario` sin `actor_usuario_id` y una de tipo `paciente_enlace` con usuario.

#### Scenario: Cancelación por enlace en el historial

- **WHEN** el paciente cancela su turno con el token
- **THEN** el historial guarda `desde = "reservado"`, `hacia = "cancelado"`, `actor_tipo = "paciente_enlace"` y `actor_usuario_id` nulo.

#### Scenario: Coherencia del actor

- **WHEN** se intenta insertar una transición `actor_tipo = "usuario"` sin `actor_usuario_id`
- **THEN** la base la rechaza (`23514`).
