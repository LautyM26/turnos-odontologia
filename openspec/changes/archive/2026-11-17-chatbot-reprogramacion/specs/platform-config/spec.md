# Spec Delta — platform-config

## ADDED Requirements

### Requirement: Configuración de la reprogramación

El sistema SHALL leer de variables de entorno el plazo de la conversación de reprogramación (`CHATBOT_TIMEOUT_MIN`, 30 por defecto, entre 5 y 240) y la anticipación mínima de un horario ofrecible al reprogramar (`REPROGRAMACION_ANTICIPACION_MIN`, 120 por defecto, entre 0 y 1440), y SHALL rechazar valores fuera de rango al arrancar.

#### Scenario: Defaults

- **WHEN** el backend arranca sin esas variables
- **THEN** la conversación vence a los 30 minutos y solo se ofrecen horarios con 120 minutos o más de anticipación.

#### Scenario: Valor fuera de rango (borde)

- **WHEN** `CHATBOT_TIMEOUT_MIN=0`
- **THEN** la validación de settings falla en el arranque.
