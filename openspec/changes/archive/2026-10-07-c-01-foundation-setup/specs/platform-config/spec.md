# Spec Delta

## Purpose

Garantiza que toda la configuración del sistema se cargue desde variables de entorno documentadas, con defaults seguros y sin secretos en el repo, como base multi-tenant y de integraciones futuras.

## ADDED Requirements

### Requirement: Settings por variables de entorno

El sistema SHALL cargar su configuración desde variables de entorno, SHALL rechazar campos no declarados (Pydantic `extra="forbid"`) y SHALL proveer defaults seguros para `APP_BASE_URL` y `RESERVA_PREBLOQUEO_MIN` en desarrollo/test.

#### Scenario: Arranque con env mínimo de desarrollo

- **WHEN** el backend arranca con `DATABASE_URL`, `APP_BASE_URL` y `RESERVA_PREBLOQUEO_MIN` definidos
- **THEN** la app arranca sin errores y expone los valores vía settings (nunca vía constantes hardcodeadas).

#### Scenario: Campo no declarado es rechazado

- **WHEN** se provee una variable/campo no declarado en el schema de settings
- **THEN** la validación falla con error (comportamiento `extra="forbid"`) en lugar de ignorarlo silenciosamente.

### Requirement: Ningún secreto en repo

El repo SHALL NOT contener secretos (tokens, keys, certificados, URLs con credenciales); los `.env.example` SHALL contener solo placeholders y las 12 variables de arquitectura documentadas.

#### Scenario: Auditoría de secretos

- **WHEN** se escanea el repo (grep de `APP_USR-`, `EAAB`, `whsec_`, `-----BEGIN`, passwords reales)
- **THEN** no hay coincidencias fuera de placeholders en `.env.example` y tests usan valores sintéticos.

#### Scenario: Las 12 variables están documentadas

- **WHEN** un desarrollador lee `backend/.env.example` y `frontend/.env.example`
- **THEN** encuentra las 12 variables de `08_arquitectura_propuesta.md` (DATABASE_URL, MP_*, WHATSAPP_*, ARCA_*, RECETAS_PARTNER_KEY, ARS_PRECIO_MENSAJE, RESERVA_PREBLOQUEO_MIN, APP_BASE_URL) con placeholders, donde las de WhatsApp reflejan sesión QR (sesión/reconexión/backup) según decisión 2026-10-08 y no credenciales de API oficial.

### Requirement: Tenant header en cliente HTTP

El cliente HTTP del frontend SHALL enviar el header de tenant (`X-Clinica-Id`) en cada request a la API, tomado de configuración `VITE_`-prefixed (nunca tokens), como base del aislamiento multi-tenant de C-02.

#### Scenario: Request incluye tenant header

- **WHEN** el frontend hace cualquier request a `/api/*` con tenant configurado
- **THEN** el request incluye `X-Clinica-Id` con el valor configurado.

#### Scenario: Sin token en browser

- **WHEN** se inspecciona el bundle frontend y sus env vars
- **THEN** solo existen vars `VITE_`-prefixed (base URL + tenant); ningún secret de backend está presente.
