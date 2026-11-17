# platform-config Specification

## Purpose

Garantiza que toda la configuración del sistema se cargue desde variables de entorno documentadas, con defaults seguros y sin secretos en el repo, como base multi-tenant y de integraciones futuras.

## Requirements

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

### Requirement: Configuración del partner de recetas

El sistema SHALL leer de variables de entorno el partner de recetas (`RECETAS_PARTNER`), su credencial (`RECETAS_PARTNER_KEY`, opcional y tratada como secreta) y el entorno de ejecución (`ENTORNO`, por defecto `produccion`); SHALL arrancar aunque falten la credencial o el partner, y SHALL NOT usar el partner simulado cuando `ENTORNO = produccion`.

#### Scenario: Arranque sin credencial

- **WHEN** el backend arranca sin `RECETAS_PARTNER` ni `RECETAS_PARTNER_KEY`
- **THEN** la app arranca, `/api/health` responde `200` y solo la emisión de recetas responde `501`.

#### Scenario: Credencial vacía en el archivo de entorno

- **WHEN** el archivo de entorno trae `RECETAS_PARTNER_KEY=` (vacía)
- **THEN** el arranque no falla y la credencial se considera ausente.

#### Scenario: Credencial nunca expuesta (borde)

- **WHEN** se serializan o loguean los settings
- **THEN** la credencial aparece enmascarada y nunca en texto plano, y no existe ninguna variable `VITE_` relacionada con recetas.

#### Scenario: Valor de partner desconocido (borde)

- **WHEN** `RECETAS_PARTNER` tiene un valor que no corresponde a ningún adapter
- **THEN** la app arranca, registra una advertencia y la emisión responde `501`.

#### Scenario: Ejemplo de entorno de desarrollo

- **WHEN** un desarrollador lee `backend/.env.example`
- **THEN** encuentra `RECETAS_PARTNER=fake`, `ENTORNO=desarrollo` y `RECETAS_PARTNER_KEY` con un placeholder, sin ningún valor real.
