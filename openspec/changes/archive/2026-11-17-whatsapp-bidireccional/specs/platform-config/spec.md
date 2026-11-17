# Spec Delta — platform-config

## ADDED Requirements

### Requirement: Configuración del gateway de WhatsApp

El sistema SHALL leer de variables de entorno el gateway de WhatsApp (`WHATSAPP_GATEWAY`: vacío, `fake` o `waha`), su URL, su clave de API y el secreto HMAC del webhook (ambos opcionales y tratados como secretos), la ventana del recordatorio, el máximo de intentos y el límite de envíos por minuto. SHALL arrancar aunque falte cualquiera de ellos y SHALL NOT usar el gateway simulado cuando `ENTORNO = produccion`.

#### Scenario: Arranque sin gateway

- **WHEN** el backend arranca sin ninguna variable `WHATSAPP_*`
- **THEN** la app arranca, `/api/health` responde `200` y los endpoints de sesión de WhatsApp responden `501`.

#### Scenario: Simulado bloqueado en producción (borde)

- **WHEN** `WHATSAPP_GATEWAY=fake` y `ENTORNO=produccion`
- **THEN** la app arranca, registra una advertencia y el canal se trata como no configurado.

#### Scenario: Secretos nunca expuestos

- **WHEN** se serializan o loguean los settings
- **THEN** la clave de API del gateway y el secreto HMAC aparecen enmascarados y no existe ninguna variable `VITE_` relacionada con WhatsApp.

#### Scenario: Ejemplo de entorno de desarrollo

- **WHEN** un desarrollador lee `backend/.env.example`
- **THEN** encuentra `WHATSAPP_GATEWAY=fake`, la URL del gateway local, placeholders para la clave y el secreto HMAC, `WHATSAPP_RECORDATORIO_HORAS=24`, `WHATSAPP_MAX_INTENTOS`, `WHATSAPP_ENVIOS_POR_MINUTO` y `ARS_PRECIO_MENSAJE`, sin ningún valor real.
