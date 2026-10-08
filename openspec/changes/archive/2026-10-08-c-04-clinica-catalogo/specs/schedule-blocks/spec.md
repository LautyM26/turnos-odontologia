# Spec Delta — schedule-blocks

## Purpose

Define los bloqueos de agenda (almuerzo, administrativos, feriados) por profesional, sillón o clínica entera, validados en servidor, y la consulta de solapamiento que el motor de turnos usa para impedir reservas en esos rangos (RN-AG-03).

## ADDED Requirements

### Requirement: Alcance del bloqueo

El sistema SHALL registrar cada bloqueo con un motivo no vacío y un único alcance: un profesional, un sillón/recurso, o la clínica entera (ambos nulos). Indicar profesional y sillón a la vez SHALL responder `422`, igual que referir un profesional o sillón que no pertenezca a la clínica del JWT.

#### Scenario: Feriado de clínica

- **WHEN** el admin crea un bloqueo sin profesional ni sillón con motivo "Feriado"
- **THEN** el bloqueo aplica a todos los profesionales y sillones de la clínica.

#### Scenario: Profesional y sillón a la vez

- **WHEN** el admin crea un bloqueo indicando profesional P y sillón S1
- **THEN** el sistema responde `422`.

#### Scenario: Profesional de otra clínica

- **WHEN** el admin de A crea un bloqueo referido a un profesional de B
- **THEN** el sistema responde `422` y no persiste el bloqueo.

### Requirement: Rango validado en servidor

El sistema SHALL aceptar el rango del bloqueo como inicio y fin con zona horaria, SHALL almacenarlo como rango semiabierto `[inicio, fin)` en tiempo absoluto, SHALL exigir `fin > inicio` y una extensión máxima de 31 días, y SHALL responder `422` ante cualquier violación.

#### Scenario: Fin anterior o igual al inicio

- **WHEN** se crea un bloqueo con `fin <= inicio`
- **THEN** el sistema responde `422`.

#### Scenario: Fecha sin zona horaria

- **WHEN** se envía `inicio = 2026-10-08T13:00:00` sin offset
- **THEN** el sistema responde `422`.

#### Scenario: Bloqueo demasiado largo

- **WHEN** se crea un bloqueo de 40 días
- **THEN** el sistema responde `422`.

#### Scenario: Rango contiguo no se superpone

- **WHEN** existe un bloqueo `[12:00, 13:00)` y se consulta el rango `[13:00, 13:30)`
- **THEN** el bloqueo no se considera superpuesto.

### Requirement: Administración de bloqueos por admin

El sistema SHALL permitir al rol `admin` crear, listar (filtrando por profesional, sillón y ventana de fechas), modificar y dar de baja lógica cualquier bloqueo de su clínica bajo `/api/admin/bloqueos`, con aislamiento por tenant (`404` ante id ajeno).

#### Scenario: Listado por ventana

- **WHEN** el admin lista bloqueos con `desde=2026-10-01` y `hasta=2026-10-31`
- **THEN** recibe solo los bloqueos activos de su clínica que se superponen con esa ventana.

#### Scenario: Baja lógica

- **WHEN** el admin hace `DELETE /api/admin/bloqueos/{id}`
- **THEN** el sistema responde `204` y el bloqueo deja de impedir reservas.

### Requirement: Bloqueos propios del odontólogo

El sistema SHALL permitir a un usuario `odontologo` vinculado a un profesional listar, crear y dar de baja bloqueos solo de ese profesional vía `/api/profesionales/{profesional_id}/bloqueos`, SHALL responder `403` ante otro profesional y SHALL asociar siempre el bloqueo creado a ese profesional (nunca a un sillón ni a la clínica).

#### Scenario: Odontólogo bloquea su almuerzo

- **WHEN** el odontólogo vinculado a P crea un bloqueo en `/api/profesionales/P/bloqueos`
- **THEN** el sistema responde `201` con el bloqueo asociado a P.

#### Scenario: Odontólogo bloquea agenda ajena

- **WHEN** el mismo odontólogo intenta crear un bloqueo en `/api/profesionales/Q/bloqueos`
- **THEN** el sistema responde `403`.

#### Scenario: Recepcionista no gestiona bloqueos

- **WHEN** una recepcionista intenta crear un bloqueo por cualquiera de las dos rutas
- **THEN** el sistema responde `403`.

### Requirement: Consulta de bloqueos que impiden una reserva

El sistema SHALL determinar, para un rango y un par (profesional, sillón) de una clínica, los bloqueos activos superpuestos que aplican al profesional, al sillón o a toda la clínica, ignorando bloqueos inactivos, de otros profesionales/sillones y de otras clínicas.

#### Scenario: Bloqueo del profesional impide el hueco

- **WHEN** P tiene un bloqueo `[13:00, 14:00)` y se consulta `[13:30, 14:00)` para (P, S1)
- **THEN** la consulta devuelve ese bloqueo.

#### Scenario: Bloqueo de clínica aplica a todos

- **WHEN** existe un bloqueo de clínica para todo el día y se consulta cualquier (profesional, sillón) de esa clínica
- **THEN** la consulta devuelve el bloqueo de clínica.

#### Scenario: Bloqueo de otro sillón no aplica

- **WHEN** solo el sillón S2 está bloqueado y se consulta (P, S1) en el mismo rango
- **THEN** la consulta no devuelve bloqueos.

#### Scenario: Bloqueo de otra clínica no aplica

- **WHEN** la clínica B tiene un bloqueo de clínica en el mismo rango
- **THEN** la consulta para la clínica A no lo devuelve.
