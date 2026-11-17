# Spec Delta — user-administration

## Purpose

Permite al administrador de la clínica dar de alta usuarios del personal, listarlos y asignarles roles desde la API, aplicando el RBAC de C-03 sin salir nunca del tenant (US-014).

## ADDED Requirements

### Requirement: Alta de usuario por el administrador

El sistema SHALL permitir a un admin crear un usuario de su clínica con email, nombre, contraseña y al menos un rol del personal (`admin`, `odontologo`, `recepcionista`), guardando la contraseña solo como hash bcrypt; el email SHALL ser único por clínica.

#### Scenario: Alta de odontólogo

- **WHEN** un admin hace `POST /api/admin/usuarios` con un email nuevo, nombre, contraseña de 8+ caracteres y `roles = ["odontologo"]`
- **THEN** el sistema responde `201` con id, email en minúsculas, nombre y roles, sin contraseña ni hash, y el usuario puede hacer login.

#### Scenario: Email repetido en la clínica

- **WHEN** el email ya existe en la clínica (sin importar mayúsculas)
- **THEN** el sistema responde `409` y no crea el usuario.

#### Scenario: Rol no asignable (borde)

- **WHEN** `roles` está vacío, trae una clave inexistente o trae `paciente-enlace`
- **THEN** el sistema responde `422` y no crea el usuario.

#### Scenario: Campo no declarado (borde)

- **WHEN** el cuerpo trae `clinica_id`, `password_hash` o `is_active`
- **THEN** el sistema responde `422`; el usuario siempre se crea en la clínica del admin autenticado.

### Requirement: Listado de usuarios de la clínica

El sistema SHALL listar a un admin los usuarios de su clínica con sus roles activos, paginado por cursor, sin exponer hashes de contraseña.

#### Scenario: Listado propio

- **WHEN** un admin hace `GET /api/admin/usuarios`
- **THEN** recibe solo usuarios de su clínica, cada uno con sus roles activos y sin `password_hash`.

#### Scenario: Límite fuera de rango

- **WHEN** pide `limit = 0` o `limit = 500`
- **THEN** el sistema responde `422`.

#### Scenario: Clínica con un solo usuario (borde)

- **WHEN** la clínica tiene solo al admin
- **THEN** la lista tiene un único elemento y no hay cursor siguiente.

### Requirement: Asignación de roles

El sistema SHALL reemplazar el conjunto de roles activos de un usuario de la clínica con `PATCH /api/admin/usuarios/{id}/roles`, con efecto inmediato en las siguientes requests del usuario, y SHALL impedir que la clínica quede sin ningún admin activo.

#### Scenario: Cambio de rol efectivo

- **WHEN** un admin cambia los roles de un usuario de `["recepcionista"]` a `["odontologo"]`
- **THEN** el sistema responde `200` con los roles nuevos y la siguiente request de ese usuario a una ruta de lectura clínica (que antes le daba `403`) responde `200`, sin necesidad de un token nuevo.

#### Scenario: Quitar el último admin

- **WHEN** un admin quita el rol `admin` al único admin activo de la clínica (incluido él mismo)
- **THEN** el sistema responde `409` y los roles no cambian.

#### Scenario: Mismo conjunto de roles (borde)

- **WHEN** se envía el mismo conjunto de roles que ya tiene
- **THEN** el sistema responde `200` sin cambios y no registra un evento de auditoría.

### Requirement: Administración de usuarios solo admin y aislada

El sistema SHALL exigir rol `admin` en todas las rutas `/api/admin/usuarios` y SHALL tratar un usuario de otra clínica como inexistente.

#### Scenario: Odontólogo o recepcionista

- **WHEN** un odontólogo o un recepcionista llama a cualquier ruta de `/api/admin/usuarios`
- **THEN** el sistema responde `403` y no cambia nada.

#### Scenario: Usuario de otra clínica

- **WHEN** un admin de la clínica A cambia roles de un usuario de la clínica B
- **THEN** el sistema responde `404` y los roles del usuario B no cambian.

#### Scenario: Sin token (borde)

- **WHEN** se llama sin JWT
- **THEN** el sistema responde `401`.
