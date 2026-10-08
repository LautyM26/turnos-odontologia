# patients Specification

## Purpose

Gobierna la entidad Paciente de cada clínica: alta, edición, búsqueda y deduplicación con identificadores normalizados, datos mínimos de obra social y el flag de consentimiento de datos, independiente de la existencia de una cuenta de usuario.

## Requirements

### Requirement: Alta de paciente scoped por clínica

El sistema SHALL permitir crear un paciente con nombre, apellido, DNI y al menos un contacto (email o teléfono) dentro del tenant del JWT, y SHALL responder `201` con el paciente creado. Payloads con campos no declarados (incluido `riesgo_ausencia` o `clinica_id`) SHALL rechazarse con `422`.

#### Scenario: Alta válida

- **WHEN** un usuario autenticado con rol admin, recepcionista u odontólogo POSTea `/api/pacientes` con nombre, apellido, DNI y teléfono
- **THEN** el sistema responde `201` con el paciente creado en la clínica del JWT, `riesgo_ausencia = 0` y `consentimiento_datos = false`.

#### Scenario: Alta sin contacto

- **WHEN** se POSTea un paciente sin email ni teléfono
- **THEN** el sistema responde `422` y no crea el paciente.

#### Scenario: Campo no declarado

- **WHEN** el payload incluye `riesgo_ausencia`, `clinica_id` o cualquier campo no declarado
- **THEN** el sistema responde `422`.

### Requirement: Paciente no requiere cuenta de usuario

El sistema SHALL crear pacientes sin crear ni exigir un `Usuario` asociado, de modo que un paciente pueda reservar y ser atendido sin cuenta (RN-AG-05).

#### Scenario: Alta no crea usuario

- **WHEN** se crea un paciente por cualquier vía (mostrador o servicio que usará la reserva pública)
- **THEN** la cantidad de usuarios de la clínica no cambia y el paciente existe sin vínculo a usuario.

### Requirement: Normalización de identificadores de contacto

El sistema SHALL normalizar en servidor el DNI a solo dígitos (7 u 8), el email a minúsculas sin espacios y el teléfono a formato E.164 argentino antes de persistir o buscar; valores no normalizables SHALL rechazarse con `422`.

#### Scenario: DNI con puntos

- **WHEN** se envía DNI `30.123.456`
- **THEN** el sistema persiste `30123456`.

#### Scenario: Teléfono móvil en formato local

- **WHEN** se envía teléfono `011 15 5555-0001`
- **THEN** el sistema persiste `+5491155550001`.

#### Scenario: DNI inválido

- **WHEN** se envía DNI `12AB` o con menos de 7 dígitos
- **THEN** el sistema responde `422`.

### Requirement: DNI único por clínica

El sistema SHALL impedir dos pacientes con el mismo DNI normalizado dentro de una clínica y SHALL permitir el mismo DNI en clínicas distintas. Ante duplicado SHALL responder `409` indicando el id del paciente existente, sin exponer pacientes de otras clínicas.

#### Scenario: DNI duplicado en la misma clínica

- **WHEN** se POSTea un paciente con un DNI ya registrado en la clínica (aunque con otro formato, p. ej. con puntos)
- **THEN** el sistema responde `409` con el id del paciente existente y no crea un duplicado.

#### Scenario: Mismo DNI en otra clínica

- **WHEN** la clínica B da de alta un DNI ya existente en la clínica A
- **THEN** el sistema responde `201` y la clínica A no ve el paciente de B.

### Requirement: Búsqueda de pacientes

El sistema SHALL permitir buscar pacientes de la clínica por DNI exacto, por teléfono exacto (ambos normalizados con las mismas reglas del alta) y por nombre/apellido parcial sin distinguir mayúsculas ni acentos (mínimo 3 caracteres), con paginación por cursor y un límite máximo de página.

#### Scenario: Búsqueda por DNI con formato distinto

- **WHEN** se busca `dni=30.123.456` y existe el paciente con DNI `30123456`
- **THEN** el sistema lo retorna.

#### Scenario: Búsqueda por nombre sin acento

- **WHEN** se busca `q=perez` y existe el paciente de apellido `Pérez`
- **THEN** el sistema lo retorna.

#### Scenario: Paginación por cursor

- **WHEN** hay más resultados que el límite de página
- **THEN** la respuesta incluye `next_cursor` y la página pedida con ese cursor no repite ni omite pacientes; un `limit` fuera de 1..200 responde `422`.

#### Scenario: Búsqueda no cruza tenants

- **WHEN** la clínica A busca un DNI que solo existe en la clínica B
- **THEN** el sistema retorna una lista vacía.

### Requirement: Consulta y edición de datos administrativos

El sistema SHALL permitir leer (`GET /api/pacientes/{id}`) y editar parcialmente (`PATCH`) los datos administrativos, de contacto y de obra social de un paciente de la clínica, aplicando las mismas normalizaciones y la unicidad de DNI; un paciente de otra clínica SHALL responder `404`. No existe borrado de pacientes por API.

#### Scenario: Edición de contacto

- **WHEN** un recepcionista PATCHea el teléfono de un paciente de su clínica
- **THEN** el sistema persiste el teléfono normalizado y responde `200`.

#### Scenario: Paciente de otra clínica

- **WHEN** se pide GET o PATCH de un paciente de otra clínica
- **THEN** el sistema responde `404` y no modifica nada.

#### Scenario: Sin endpoint de borrado

- **WHEN** se envía `DELETE /api/pacientes/{id}`
- **THEN** el sistema responde `405` y el paciente persiste.

### Requirement: Datos mínimos de obra social

El sistema SHALL registrar obra social (nombre), plan y número de afiliado como texto libre opcional del paciente, sin validación en línea contra el financiador (RN-OS-01).

#### Scenario: Registro de obra social

- **WHEN** un recepcionista carga obra social, plan y nro de afiliado
- **THEN** el sistema los persiste tal cual (recortando espacios) sin consultar servicios externos.

### Requirement: Registro del consentimiento de datos

El sistema SHALL registrar `consentimiento_datos` del paciente junto con la fecha/hora (TIMESTAMPTZ) y el usuario que lo registró; otorgarlo o revocarlo SHALL quedar auditado. Revocarlo SHALL impedir nuevas cargas de datos de salud sin borrar los existentes.

#### Scenario: Otorgar consentimiento

- **WHEN** un usuario PATCHea `consentimiento_datos=true`
- **THEN** el sistema guarda la fecha/hora y el usuario que lo registró y deja un evento de auditoría.

#### Scenario: Revocar consentimiento

- **WHEN** un usuario PATCHea `consentimiento_datos=false` en un paciente con ficha
- **THEN** la ficha y los adjuntos existentes se conservan, el evento se audita y las nuevas cargas de datos de salud quedan bloqueadas.

### Requirement: Riesgo de ausencia de solo lectura

El sistema SHALL exponer `riesgo_ausencia` (entero 0–100, default 0) en la lectura del paciente y SHALL impedir modificarlo por la API de pacientes.

#### Scenario: Intento de escribir el score

- **WHEN** un PATCH incluye `riesgo_ausencia`
- **THEN** el sistema responde `422` y el score no cambia.
