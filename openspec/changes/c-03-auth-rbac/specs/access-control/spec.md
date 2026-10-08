# Spec Delta — access-control

## Purpose

Codifica en servidor la matriz RBAC del 03_actores_y_roles.md: qué rol puede hacer qué, qué rutas son públicas y cómo se aíslan las agendas tercerizadas.

## ADDED Requirements

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
