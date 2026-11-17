# Spec Delta — platform-config

## ADDED Requirements

### Requirement: Configuración de la lista de espera

El sistema SHALL leer de variables de entorno el vencimiento de la oferta de lista de espera (`LISTA_ESPERA_OFERTA_MIN`, 30 por defecto, entre 5 y 240) y la anticipación mínima de un hueco ofrecible (`LISTA_ESPERA_ANTICIPACION_MIN`, 120 por defecto, entre 0 y 1440), y SHALL rechazar valores fuera de rango al arrancar.

#### Scenario: Defaults

- **WHEN** el backend arranca sin esas variables
- **THEN** la oferta vence a los 30 minutos y la anticipación mínima es de 120 minutos.

#### Scenario: Valor fuera de rango (borde)

- **WHEN** `LISTA_ESPERA_OFERTA_MIN=1`
- **THEN** la validación de settings falla en el arranque.
