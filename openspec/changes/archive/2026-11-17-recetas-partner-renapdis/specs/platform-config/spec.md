# Spec Delta — platform-config

## ADDED Requirements

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
