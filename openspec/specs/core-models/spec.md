# core-models Specification

## Purpose

Define las entidades base del SaaS — `Clinica`, `Usuario`, `Rol`, `UsuarioRol` — con identidad fiscal AR válida, unicidad de email por tenant y seed mínimo idempotente que deja el sistema arrancable.

## Requirements

### Requirement: Clínica con CUIT argentino válido

El sistema SHALL validar el CUIT con algoritmo módulo 11, SHALL normalizarlo a 11 dígitos y SHALL rechazar con `422` cualquier CUIT inválido; la moneda por defecto es ARS.

#### Scenario: CUIT inválido rechazado

- **WHEN** se crea una clínica con CUIT `20-12345678-9` (dígito verificador incorrecto)
- **THEN** el sistema responde `422` y no persiste la clínica.

#### Scenario: CUIT con guiones se normaliza

- **WHEN** se crea una clínica con `30-12345678-1` válido con guiones
- **THEN** el sistema persiste `30123456781` normalizado.

### Requirement: Usuario scoped con email único por tenant

El sistema SHALL normalizar el email a minúsculas, SHALL exigir unicidad de email por `clinica_id`, SHALL almacenar solo hash (nunca plaintext) y SHALL exponer `activo` para alta/baja lógica.

#### Scenario: Mismo email en distintas clínicas permitido

- **WHEN** `admin@demo.com` existe en clínica A y se registra en clínica B
- **THEN** ambas filas coexisten sin violar unicidad.

#### Scenario: Email duplicado en misma clínica rechazado

- **WHEN** `admin@demo.com` ya existe activo en clínica A y se reintenta en A
- **THEN** el sistema rechaza con `409` conflicto.

#### Scenario: Hash nunca expone secreto

- **WHEN** se lee un usuario vía API o dump de seed
- **THEN** ningún campo contiene la password en claro.

### Requirement: Cuatro roles base y join UsuarioRol

El sistema SHALL proveer los roles `admin`, `odontologo`, `recepcionista`, `paciente-enlace` y SHALL asignar roles vía tabla `UsuarioRol` (un usuario puede tener varios roles).

#### Scenario: Seed crea los cuatro roles

- **WHEN** se ejecuta el seed sobre base vacía
- **THEN** existen exactamente los 4 roles con claves estables.

#### Scenario: Usuario con múltiples roles

- **WHEN** un usuario tiene `admin` + `odontologo`
- **THEN** ambas asignaciones persisten en `UsuarioRol` y son consultables.

### Requirement: Schemas estrictos extra=forbid

Todo schema Pydantic de C-02 SHALL usar `extra="forbid"` y SHALL responder `422` ante campos no declarados.

#### Scenario: Campo desconocido rechazado

- **WHEN** un payload incluye un campo no declarado (p. ej. `is_superuser: true`)
- **THEN** el sistema responde `422` en lugar de ignorarlo.

### Requirement: Seed mínimo idempotente y sintético

El seed SHALL crear 1 clínica piloto sintética, los 4 roles y 1 usuario ADMIN, SHALL ser re-ejecutable sin duplicados y SHALL usar solo datos sintéticos marcados `seed=true` (ningún dato real de paciente, Ley 25.326).

#### Scenario: Seed re-ejecutado no duplica

- **WHEN** el seed corre dos veces seguidas
- **THEN** sigue habiendo 1 clínica, 4 roles y 1 admin (upsert por clave natural, sin filas duplicadas).
