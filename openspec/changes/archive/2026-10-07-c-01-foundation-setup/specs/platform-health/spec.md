# Spec Delta

## Purpose

Expone el estado operativo mínimo del backend para que CI, Docker y futuros despliegues verifiquen que la API está viva sin autenticación ni dependencias externas.

## ADDED Requirements

### Requirement: Health endpoint público

El sistema SHALL exponer `GET /api/health` sin autenticación y responder `200` con un cuerpo JSON que incluya al menos `status: "ok"`.

#### Scenario: Health check exitoso

- **WHEN** un cliente hace `GET /api/health`
- **THEN** el sistema responde `200` con `{"status": "ok", ...}` en menos de 1s sin requerir headers de auth ni tenant.

#### Scenario: Health no depende de la base de datos

- **WHEN** PostgreSQL está caído o `DATABASE_URL` no es alcanzable
- **THEN** `GET /api/health` sigue respondiendo `200` (el chequeo de DB, si existe, va en un campo separado y nunca convierte el health en 5xx en este change).

### Requirement: Formato de error consistente

El sistema SHALL responder errores de API con un cuerpo JSON consistente que incluya `detail`, y SHALL registrar la excepción con logger estructurado sin exponer trazas internas al cliente.

#### Scenario: Ruta inexistente

- **WHEN** un cliente hace `GET /api/ruta-que-no-existe`
- **THEN** el sistema responde `404` con cuerpo JSON con `detail` y no expone stack traces.

#### Scenario: Error interno no filtra detalles

- **WHEN** un handler lanza una excepción no controlada
- **THEN** el sistema responde `500` con `detail` genérico, loguea la traza en servidor y no incluye la traza en la respuesta.
