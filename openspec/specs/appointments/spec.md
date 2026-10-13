# appointments Specification

## Purpose
Define el alta de turnos por el staff de la clínica con duración calculada en servidor y prevención dura de solapamientos por profesional y por sillón, respetando los bloqueos de agenda (RN-AG-01, RN-AG-02, RN-AG-03), con RBAC y aislamiento multi-tenant.

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

El sistema SHALL considerar ocupado un rango solo por turnos activos (`reservado`, `confirmado`, `asistido`) y no dados de baja; un turno `cancelado` o `ausente`, o dado de baja lógica, SHALL NOT impedir un nuevo turno en el mismo rango.

#### Scenario: Turno cancelado libera el hueco

- **GIVEN** P tiene en S1 un turno `cancelado` `[10:00, 10:30)`
- **WHEN** la recepcionista crea un turno para P en S1 con `inicio = 10:00`
- **THEN** el sistema responde `201`

#### Scenario: Turno dado de baja libera el hueco

- **GIVEN** S1 tiene un turno `reservado` `[11:00, 11:30)` dado de baja lógica
- **WHEN** la recepcionista crea un turno para Q en S1 con `inicio = 11:00`
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
