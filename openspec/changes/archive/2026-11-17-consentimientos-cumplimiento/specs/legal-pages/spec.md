# Spec Delta — legal-pages

## Purpose

Publica sin login la política de privacidad y la página de cumplimiento del producto, con textos base versionados que declaran el tratamiento de datos de salud y su ubicación, marcados como pendientes de validación legal (RN-CU-01, RN-CU-05, US-015).

## ADDED Requirements

### Requirement: Página pública de cumplimiento

El frontend SHALL servir `/cumplimiento` sin autenticación, con la versión y fecha del texto, las leyes que el producto declara cumplir (26.529, 25.326, 25.506, 27.706), cómo se cumple cada una (historia clínica append-only y auditada, consentimientos firmados con constancia, receta solo vía partner ReNaPDiS, exportación sin retención) y un enlace a `/privacidad`.

#### Scenario: Visitante sin sesión

- **WHEN** alguien abre `/cumplimiento` sin haber iniciado sesión
- **THEN** ve el título, la versión del texto, las cuatro leyes con su explicación y el enlace a `/privacidad`.

#### Scenario: Aviso de validación legal

- **WHEN** se renderiza `/cumplimiento`
- **THEN** se muestra de forma visible el aviso "Texto base a validar con asesoría legal".

#### Scenario: Sin llamadas a la API (borde)

- **WHEN** la API no está disponible
- **THEN** la página se muestra completa igual, porque sus textos no dependen del backend.

### Requirement: Política de privacidad pública

El frontend SHALL servir `/privacidad` sin autenticación con la política de privacidad base: responsable, datos tratados (incluidos datos de salud como sensibles), finalidad, consentimiento, ubicación declarada del alojamiento, plazo de conservación, derechos de acceso, rectificación y supresión ante la AAIP, y exportación sin retención.

#### Scenario: Ubicación de datos declarada

- **WHEN** alguien abre `/privacidad`
- **THEN** ve una sección "Dónde se guardan tus datos" con la ubicación declarada del alojamiento y su versión de texto.

#### Scenario: Aviso de validación legal en privacidad

- **WHEN** se renderiza `/privacidad`
- **THEN** se muestra el aviso "Texto base a validar con asesoría legal" y los datos a completar se ven marcados como pendientes, no como hechos.

#### Scenario: Ruta inexistente cercana (borde)

- **WHEN** alguien abre `/privacidad/` con barra final
- **THEN** ve la misma política de privacidad.

### Requirement: Textos legales sin datos reales

Los textos legales base SHALL contener solo datos genéricos o marcadores de completado (sin nombres, CUIT, domicilios ni contactos reales) hasta que la asesoría legal los valide.

#### Scenario: Marcadores en lugar de datos

- **WHEN** se revisan los textos de `/cumplimiento` y `/privacidad`
- **THEN** el responsable, el CUIT y el contacto aparecen como marcadores `[A completar …]`.

#### Scenario: Versión visible

- **WHEN** se cambia un texto legal
- **THEN** su número de versión y fecha cambian y se ven en la página.

#### Scenario: Sin números con forma de DNI o teléfono (borde)

- **WHEN** se buscan números de 7 u 8 dígitos o teléfonos en los textos legales
- **THEN** no aparece ninguno.
