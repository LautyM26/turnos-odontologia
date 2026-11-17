# Spec Delta — public-booking

## Purpose

Reserva de turnos por enlace público sin cuenta (US-003, Flujo 1, RN-AG-05): el paciente elige prestación, profesional y hueco real, se identifica con DNI y contacto, y recibe un enlace privado para ver o cancelar su turno. Sin seña en esta versión (RN-CA-01/02 quedan para C-12).

## ADDED Requirements

### Requirement: Catálogo público por clínica

El sistema SHALL responder sin autenticación en `GET /api/public/clinicas/{slug}` con el nombre de la clínica, sus prestaciones activas (id, nombre, duración) y los profesionales que atienden online (activos, con agenda activa y con al menos una franja de horario), sin exponer matrículas, usuarios, sillones ni datos de pacientes. Un `slug` inexistente o de una clínica inactiva SHALL responder `404`.

#### Scenario: Paciente abre el enlace de la clínica (happy path)

- **WHEN** un visitante sin sesión pide `GET /api/public/clinicas/clinica-piloto`
- **THEN** el sistema responde `200` con la clínica, las prestaciones activas y los profesionales con horario cargado.

#### Scenario: Profesional sin horario no se ofrece

- **GIVEN** el profesional Q tiene agenda activa pero ninguna franja cargada
- **WHEN** se pide el catálogo público
- **THEN** Q no figura entre los profesionales.

#### Scenario: Slug inexistente

- **WHEN** se pide `GET /api/public/clinicas/no-existe`
- **THEN** el sistema responde `404`.

### Requirement: Huecos públicos

El sistema SHALL responder sin autenticación en `GET /api/public/clinicas/{slug}/huecos` con los mismos inicios que `GET /api/agenda/huecos` (horario, turnos, bloqueos, ventana de hasta 7 días, nunca en el pasado), devolviendo por hueco solo `inicio` y `fin`. Un profesional que no atiende online, una prestación inactiva o de otra clínica, o una ventana inválida SHALL responder `422`.

#### Scenario: Huecos de una semana

- **GIVEN** P atiende de lunes a viernes de 09:00 a 13:00 y tiene un turno el lunes de 09:00 a 09:30
- **WHEN** el visitante consulta los huecos de P para una prestación de 30 min de esa semana
- **THEN** el sistema responde `200` sin el inicio de las 09:00 del lunes y sin campos de sillón.

#### Scenario: Profesional de otra clínica

- **WHEN** se piden huecos con el slug de A y un profesional de B
- **THEN** el sistema responde `422`.

### Requirement: Reserva sin cuenta

El sistema SHALL crear con `POST /api/public/clinicas/{slug}/reservas` un turno `reservado` con `origen = "enlace"` a partir de `profesional_id`, `prestacion_id`, `inicio`, `dni`, `nombre`, `apellido`, `email` y/o `telefono` y `acepta_privacidad = true`. La respuesta `201` SHALL incluir un token opaco para ver y cancelar la reserva. El sistema SHALL NOT crear usuario ni contraseña, y SHALL NOT aceptar `sobreturno`.

#### Scenario: Paciente nuevo reserva un hueco (happy path)

- **GIVEN** el DNI 30111222 no existe en la clínica y P tiene libre el lunes a las 10:00
- **WHEN** el visitante reserva ese hueco con sus datos y `acepta_privacidad = true`
- **THEN** el sistema responde `201` con el token, el inicio, el fin, la prestación y el profesional; existe un paciente nuevo sin usuario y un turno `reservado` con `origen = "enlace"`.

#### Scenario: Sin aceptar la política de privacidad

- **WHEN** el cuerpo trae `acepta_privacidad = false` o no lo trae
- **THEN** el sistema responde `422` y no crea paciente ni turno.

### Requirement: Reglas del alta y elección de sillón en la reserva pública

El servidor SHALL elegir un sillón habilitado libre del profesional y aplicar todas las reglas del alta normal: horario de atención, bloqueos, anti-solapamiento y no en el pasado. Si ningún sillón queda libre, SHALL responder `409` "Horario no disponible".

#### Scenario: Horario tomado entre la consulta y la reserva (borde)

- **GIVEN** dos visitantes eligieron el mismo hueco y el único sillón habilitado
- **WHEN** reservan a la vez
- **THEN** uno recibe `201` y el otro `409` "Horario no disponible", sin datos del turno ajeno.

#### Scenario: Segundo sillón libre

- **GIVEN** P está habilitado en S1 y S2 y Q ocupa S1 a las 10:00
- **WHEN** el visitante reserva a P a las 10:00
- **THEN** el sistema responde `201` y el turno queda en S2.

### Requirement: Paciente existente reutilizado sin revelar ni modificar datos

Si el DNI ya pertenece a un paciente activo de la clínica, el sistema SHALL asociar el turno a ese paciente sin modificar su nombre, apellido ni contacto, y la respuesta SHALL ser indistinguible de la de un paciente nuevo. Un DNI que pertenece a un paciente dado de baja SHALL responder `422` genérico.

#### Scenario: DNI existente con otro teléfono

- **GIVEN** el paciente con DNI 30111222 tiene teléfono `+5491100000001`
- **WHEN** alguien reserva con ese DNI y teléfono `+5491199999999`
- **THEN** el sistema responde `201`, el turno queda asociado a ese paciente y su teléfono sigue siendo `+5491100000001`.

### Requirement: Tope de reservas online por DNI

El sistema SHALL rechazar con `409` una reserva por enlace si el DNI ya tiene 2 turnos futuros activos (`reservado` o `confirmado`, no dados de baja) creados por enlace en la clínica.

#### Scenario: Tercera reserva del mismo DNI (error de negocio)

- **GIVEN** el DNI 30111222 tiene 2 turnos futuros reservados por enlace
- **WHEN** reserva un tercero
- **THEN** el sistema responde `409` y no crea el turno.

#### Scenario: Una cancelada libera el cupo

- **GIVEN** uno de esos 2 turnos fue cancelado
- **WHEN** el mismo DNI reserva otro
- **THEN** el sistema responde `201`.

### Requirement: Consulta de la reserva con el token

El sistema SHALL devolver en `GET /api/public/reservas/{token}` la clínica, el profesional, la prestación, el inicio, el fin y el estado del turno, sin datos personales del paciente. El token SHALL guardarse solo como hash; un token desconocido SHALL responder `404`.

#### Scenario: Ver la reserva

- **WHEN** el paciente abre `GET /api/public/reservas/{token}`
- **THEN** el sistema responde `200` sin DNI, nombre ni contacto del paciente.

### Requirement: Cancelación con el token

`POST /api/public/reservas/{token}/cancelar` SHALL pasar el turno a `cancelado` según la tabla de transiciones del turno, solo antes de su inicio, registrando un actor de tipo enlace. Un turno ya iniciado o en un estado que no admite cancelación SHALL responder `422`; un token desconocido, `404`.

#### Scenario: Paciente cancela su reserva

- **GIVEN** un turno reservado por enlace para mañana
- **WHEN** el paciente hace `POST /api/public/reservas/{token}/cancelar`
- **THEN** el sistema responde `200` con `estado = "cancelado"`, el hueco vuelve a aparecer y el historial registra la transición con `actor_tipo = "paciente_enlace"`.

#### Scenario: Cancelar después del inicio (error de negocio)

- **GIVEN** el turno ya empezó
- **WHEN** el paciente intenta cancelarlo
- **THEN** el sistema responde `422` y el turno no cambia.

#### Scenario: Token inválido

- **WHEN** se consulta o cancela con un token inexistente
- **THEN** el sistema responde `404`.

### Requirement: Límite de pedidos por IP

El sistema SHALL limitar por dirección IP los pedidos a los endpoints públicos de huecos, reservas y cancelación, y SHALL responder `429` con `Retry-After` al exceder el límite.

#### Scenario: Ráfaga de reservas desde una IP

- **WHEN** una misma IP envía más reservas que el límite configurado dentro de la ventana
- **THEN** los pedidos excedentes reciben `429`.
