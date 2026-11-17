# Spec Delta — platform-config

## MODIFIED Requirements

### Requirement: Tenant header en cliente HTTP

El cliente HTTP del frontend SHALL enviar el header de tenant (`X-Clinica-Id`) en cada request a la API cuando conozca la clínica: primero desde configuración `VITE_`-prefixed (`VITE_CLINICA_ID`, nunca tokens) y, si no está configurada, desde el `tenant_id` de la sesión autenticada. Sin ninguno de los dos SHALL omitir el header; nunca SHALL enviarlo vacío.

#### Scenario: Request incluye tenant header

- **WHEN** el frontend hace cualquier request a `/api/*` con tenant configurado
- **THEN** el request incluye `X-Clinica-Id` con el valor configurado.

#### Scenario: Sin token en browser

- **WHEN** se inspecciona el bundle frontend y sus env vars
- **THEN** solo existen vars `VITE_`-prefixed (base URL + tenant); ningún secret de backend está presente.

#### Scenario: Tenant desde la sesión

- **GIVEN** `VITE_CLINICA_ID` sin configurar y una sesión cuyo `tenant_id` es 1
- **WHEN** el frontend pide `/api/pacientes`
- **THEN** el request incluye `X-Clinica-Id: 1`.

#### Scenario: Sin tenant conocido (borde)

- **GIVEN** `VITE_CLINICA_ID` sin configurar y ninguna sesión iniciada
- **WHEN** el frontend llama a `POST /api/auth/login`
- **THEN** el request no incluye el header `X-Clinica-Id`.
