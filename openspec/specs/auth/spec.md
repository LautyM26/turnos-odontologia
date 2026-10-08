# auth Specification

## Purpose

Gobierna el ciclo de vida de la sesión JWT del SaaS: login, refresh con rotación, logout y verificación de identidad con tenant autoritativo.

## Requirements

### Requirement: Login emite par access + refresh

El sistema SHALL validar `email` (normalizado a minúsculas) + password contra el hash bcrypt del `Usuario` activo del tenant y SHALL emitir un access JWT (15 min) + un refresh JWT (7 días) solo ante credenciales válidas.

#### Scenario: Login OK

- **WHEN** se POSTea `/api/auth/login` con email + password correctos de un usuario activo
- **THEN** el sistema responde `200` con access en cuerpo y refresh en cookie HttpOnly, y registra el evento de login.

#### Scenario: Login con credencial inválida

- **WHEN** se POSTea `/api/auth/login` con email inexistente, usuario inactivo o password incorrecto
- **THEN** el sistema responde `401` con mensaje genérico (sin revelar qué falló) y registra el fallo.

#### Scenario: Login rechaza campos extra

- **WHEN** el body de login trae campos no declarados
- **THEN** el sistema responde `422` (`extra='forbid'`).

### Requirement: Rate limit en login

El sistema SHALL limitar `POST /api/auth/login` a 5 intentos/60s por par IP+email y SHALL responder `429` al excederlo, sin revelar si el email existe.

#### Scenario: Sexto intento bloqueado

- **WHEN** se hacen 6 logins en 60s con misma IP+email
- **THEN** el sexto responde `429` aunque las credenciales sean correctas.

### Requirement: Claims y transporte de tokens

Todo JWT SHALL portar `sub`, `tenant_id`, `roles`, `email`, `jti`, `type`, `iat`, `exp`; el access SHALL viajar en `Authorization: Bearer` y el refresh SHALL viajar solo en cookie HttpOnly (`Secure`, `SameSite=Lax`, `Path=/api/auth`).

#### Scenario: Access sin claim tenant es inválido

- **WHEN** un access no trae `tenant_id` o trae `type != access`
- **THEN** el sistema lo rechaza con `401` en cualquier endpoint protegido.

#### Scenario: Refresh nunca en localStorage ni cuerpo

- **WHEN** el frontend persiste la sesión
- **THEN** el refresh solo vive en la cookie HttpOnly (nunca en `localStorage` ni en cuerpos JSON de respuesta).

### Requirement: Refresh con rotación y blacklist

El sistema SHALL aceptar solo refresh vigentes no revocados, SHALL rotarlos (nuevo par + blacklist del `jti` anterior) y SHALL rechazar con `401` todo refresh reutilizado, expirado o blacklisteado.

#### Scenario: Refresh válido rota

- **WHEN** se POSTea `/api/auth/refresh` con cookie de refresh vigente
- **THEN** el sistema responde `200` con nuevo par y el `jti` anterior queda revocado.

#### Scenario: Replay de refresh rotado

- **WHEN** se reutiliza un refresh ya rotado
- **THEN** el sistema responde `401` y no emite tokens nuevos.

### Requirement: Logout revoca la sesión

El sistema SHALL blacklistar por `jti` el access y el refresh vigentes al POSTear `/api/auth/logout` y SHALL limpiar la cookie de refresh.

#### Scenario: Logout invalida tokens

- **WHEN** se hace logout con sesión vigente
- **THEN** el access anterior responde `401` en el siguiente uso y la cookie queda limpia.

### Requirement: Token expirado es rechazado

El sistema SHALL rechazar con `401` todo access expirado (`exp` superado, reloj con tolerancia ≤60s) sin fallback a header ni a sesión implícita.

#### Scenario: Access de 16 minutos

- **WHEN** se usa un access emitido hace más de 15 min (+tolerancia)
- **THEN** el sistema responde `401` (token expirado).

### Requirement: Identidad actual

El sistema SHALL exponer `GET /api/auth/me` que retorna `sub`, `email`, `tenant_id` y `roles` del access vigente y SHALL responder `401` sin token válido.

#### Scenario: Me con token válido

- **WHEN** se llama `/api/auth/me` con access vigente
- **THEN** el sistema responde `200` con la identidad del token.
