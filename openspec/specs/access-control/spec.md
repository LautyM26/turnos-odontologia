# access-control Specification

## Purpose

Codifica en servidor la matriz RBAC del 03_actores_y_roles.md: qué rol puede hacer qué, qué rutas son públicas y cómo se aíslan las agendas tercerizadas.

## Requirements

### Requirement: Matriz RBAC por recurso en servidor

El sistema SHALL autorizar cada ruta no-pública contra la matriz del `03` (admin, odontólogo, recepcionista, paciente-enlace) y SHALL responder `403` ante rol insuficiente; el cliente solo refleja permisos con fines de display.

#### Scenario: Recepcionista sin acceso clínico

- **WHEN** un usuario con rol `recepcionista` pide HC/odontograma/evolución
- **THEN** el sistema responde `403` (solo datos contacto/OS vía endpoints no-clínicos).

#### Scenario: Odontólogo sin acceso a configuración

- **WHEN** un usuario con rol `odontologo` pide `/api/admin/*`
- **THEN** el sistema responde `403`.

### Requirement: PermissionContext con require_role y require_admin

El sistema SHALL proveer dependencias `require_role(*roles)` y `require_admin()` que resuelven roles desde el JWT y SHALL fallar cerrado (`401` sin token, `403` sin rol).

#### Scenario: Ruta admin con rol admin

- **WHEN** un JWT con rol `admin` accede a una ruta `require_admin()`
- **THEN** el sistema la ejecuta.

#### Scenario: Ruta admin sin rol admin

- **WHEN** un JWT sin rol `admin` accede a una ruta `require_admin()`
- **THEN** el sistema responde `403`.

### Requirement: Tercerizado solo ve su agenda

El sistema SHALL restringir al odontólogo marcado tercerizado a su propia agenda mediante `require_own_agenda()` (profesional_id del JWT) y SHALL responder `403` ante agenda ajena.

#### Scenario: Tercerizado ve agenda ajena

- **WHEN** un odontólogo tercerizado pide turnos de otro profesional
- **THEN** el sistema responde `403`.

#### Scenario: Tercerizado ve su agenda

- **WHEN** el mismo usuario pide sus propios turnos
- **THEN** el sistema los retorna (scoped además por tenant).

### Requirement: Sobreturnos y anulaciones chequeados por rol

El sistema SHALL exigir rol autorizado (admin/recepcionista según matriz; odontólogo solo bloqueos propios) para crear sobreturnos y para anular movimientos de caja, con motivo y traza registrados.

#### Scenario: Sobreturno sin rol autorizado

- **WHEN** un rol no autorizado intenta crear un sobreturno
- **THEN** el sistema responde `403` y no crea el turno.

#### Scenario: Anulación de caja sin rol

- **WHEN** un usuario sin rol de caja intenta anular un cobro
- **THEN** el sistema responde `403` y el cobro queda intacto.

### Requirement: Rutas públicas declaradas

El sistema SHALL eximir de login solo a: enlace de reserva (`/api/public/*`), webhooks de Mercado Pago y de WhatsApp-QR (sesión local, número dedicado), comprobantes por token y páginas `/cumplimiento` + `/privacidad`; todo lo demás SHALL exigir JWT.

#### Scenario: Reserva pública sin token

- **WHEN** un paciente abre el enlace de reserva sin cuenta
- **THEN** el sistema sirve disponibilidad y crea la reserva sin pedir login.

#### Scenario: Ruta privada sin token

- **WHEN** se llama a cualquier endpoint scoped sin JWT
- **THEN** el sistema responde `401`.

### Requirement: Acceso a datos administrativos del paciente por rol

El sistema SHALL permitir crear, leer, buscar y editar datos administrativos, de contacto, obra social y consentimiento de pacientes a los roles admin, recepcionista y odontólogo de la clínica, y SHALL responder `403` a cualquier otro rol (incluido paciente-enlace).

#### Scenario: Recepcionista gestiona contacto

- **WHEN** un recepcionista crea o edita el teléfono de un paciente
- **THEN** el sistema lo permite.

#### Scenario: Rol paciente-enlace en API privada

- **WHEN** un JWT con solo rol `paciente-enlace` llama a `/api/pacientes`
- **THEN** el sistema responde `403`.

### Requirement: Lectura clínica solo admin y odontólogo

El sistema SHALL permitir leer ficha, historial de ficha, listado y contenido de adjuntos solo a admin y odontólogo; el recepcionista SHALL recibir `403` en todo endpoint clínico del paciente.

#### Scenario: Recepcionista lee ficha

- **WHEN** un recepcionista pide `GET /api/pacientes/{id}/ficha` o un adjunto
- **THEN** el sistema responde `403` y no audita una lectura clínica.

#### Scenario: Admin lee ficha

- **WHEN** un admin pide la ficha de un paciente de su clínica
- **THEN** el sistema la retorna y audita la lectura.

### Requirement: Escritura clínica solo odontólogo

El sistema SHALL permitir crear versiones de ficha y subir adjuntos solo a usuarios con rol odontólogo; admin sin rol odontólogo y recepcionista SHALL recibir `403`.

#### Scenario: Admin sin rol odontólogo edita ficha

- **WHEN** un usuario solo admin hace PUT de ficha
- **THEN** el sistema responde `403` y no crea versión.

#### Scenario: Dueño con roles admin y odontólogo

- **WHEN** un usuario con roles admin y odontólogo hace PUT de ficha de un paciente con consentimiento
- **THEN** el sistema crea la versión.

### Requirement: Vínculo odontólogo–paciente

El sistema SHALL decidir el acceso clínico de un odontólogo a un paciente mediante una regla de vínculo reemplazable que falla cerrado (`403`) ante error. Hasta que existan turnos, la regla interina SHALL otorgar vínculo con todo paciente de su propia clínica, con cada lectura clínica auditada.

#### Scenario: Regla interina dentro de la clínica

- **WHEN** un odontólogo pide la ficha de un paciente de su clínica antes de existir turnos
- **THEN** el sistema la retorna y registra el evento de lectura.

#### Scenario: Regla de vínculo niega acceso

- **WHEN** la regla de vínculo configurada indica que el odontólogo no está vinculado al paciente
- **THEN** el sistema responde `403` en ficha y adjuntos de ese paciente.

#### Scenario: Paciente de otra clínica

- **WHEN** un odontólogo pide la ficha de un paciente de otra clínica
- **THEN** el sistema responde `404` sin evaluar el vínculo.
