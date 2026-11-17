# Spec Delta — odontogram-web

## Purpose

Gobierna el odontograma FDI interactivo en el navegador: dibujar las piezas de la dentición elegida, marcar estados por pieza y por cara con el catálogo del MVP, y guardar cada cambio como una versión nueva sin pisar el trabajo de otro profesional.

## ADDED Requirements

### Requirement: Piezas según la dentición

El frontend SHALL dibujar el odontograma en notación FDI en el orden clínico (maxilar superior arriba, cuadrantes 1|2 y 4|3 vistos de frente al paciente): `permanente` = 32 piezas (11–18, 21–28, 31–38, 41–48), `temporal` = 20 piezas (51–55, 61–65, 71–75, 81–85) y `mixta` = las 52, cada pieza con su número visible.

#### Scenario: Dentición permanente (happy path)

- **WHEN** el odontograma vigente tiene `denticion = "permanente"`
- **THEN** se muestran exactamente 32 piezas, de la 18 a la 28 arriba y de la 48 a la 38 abajo.

#### Scenario: Dentición temporal

- **WHEN** la dentición es `temporal`
- **THEN** se muestran exactamente 20 piezas, de la 55 a la 65 arriba y de la 85 a la 75 abajo.

#### Scenario: Dentición mixta (borde)

- **WHEN** la dentición es `mixta`
- **THEN** se muestran las 52 piezas, con las temporales en una fila interna de cada arcada.

#### Scenario: Paciente sin odontograma (borde)

- **WHEN** el odontograma actual tiene `version = 0`
- **THEN** se muestra la dentición permanente sin marcas y el texto "Sin odontograma registrado todavía".

### Requirement: Selector de dentición

El odontólogo SHALL poder elegir la dentición (permanente, temporal o mixta) del borrador. Si el cambio deja fuera piezas que tienen marcas, el frontend SHALL pedir confirmación indicando cuáles se van a quitar antes de aplicar el cambio.

#### Scenario: Cambio sin marcas afectadas (happy path)

- **GIVEN** un borrador permanente sin marcas
- **WHEN** el odontólogo elige `temporal`
- **THEN** se dibujan 20 piezas sin pedir confirmación.

#### Scenario: Cambio que descarta marcas (borde)

- **GIVEN** un borrador mixto con marcas en las piezas 16 y 55
- **WHEN** el odontólogo elige `permanente`
- **THEN** el frontend avisa que se quitará la marca de la pieza 55, y solo si confirma cambia la dentición conservando la marca de la 16.

### Requirement: Marcado por pieza y por cara

Al elegir una pieza, el frontend SHALL abrir un panel con su número donde el odontólogo marque el estado de la pieza (ausente, extraída, extracción indicada, corona, endodoncia, implante) y el estado de cada cara V, L, M, D, O (caries, obturación, sellador, fractura), cada marca como `existente` o `a_realizar`, o la quite. Hacer clic en una cara SHALL abrir el panel con esa cara seleccionada.

#### Scenario: Caries a realizar en oclusal (happy path)

- **WHEN** el odontólogo hace clic en la cara oclusal de la pieza 16 y marca "caries" como "a realizar"
- **THEN** la cara O de la 16 queda pintada con el color de "a realizar" y el borrador queda marcado con cambios sin guardar.

#### Scenario: Pieza ausente con caras marcadas (error de negocio)

- **GIVEN** la pieza 26 con una obturación en la cara O
- **WHEN** el odontólogo marca la pieza como "ausente"
- **THEN** el frontend avisa que se quitarán las marcas de las caras, y al confirmar la pieza queda ausente sin caras marcadas.

#### Scenario: Quitar una marca (borde)

- **WHEN** el odontólogo elige "Sin marca" en una cara marcada
- **THEN** la cara vuelve a verse sana y, si la pieza queda sin estado ni caras, deja de enviarse en `piezas`.

### Requirement: Odontograma accesible y legible sin color

Cada pieza SHALL ser un control enfocable con teclado (Enter o Espacio abre el panel) con un nombre accesible que diga número y marcas. El significado SHALL no depender solo del color: una leyenda y una tabla textual de hallazgos (pieza, cara, estado, existente/a realizar) SHALL acompañar al dibujo.

#### Scenario: Operación por teclado (happy path)

- **WHEN** el usuario recorre las piezas con Tab y pulsa Enter sobre la 36
- **THEN** se abre el panel de la pieza 36 con el foco en su primer control, y Escape lo cierra devolviendo el foco a la pieza.

#### Scenario: Tabla de hallazgos (borde)

- **GIVEN** la pieza 36 con caries a realizar en M y obturación existente en O
- **WHEN** se muestra el odontograma
- **THEN** la tabla de hallazgos lista "36 · M · Caries · A realizar" y "36 · O · Obturación · Existente".

### Requirement: Guardado como versión nueva

"Guardar odontograma" SHALL enviar `POST /api/pacientes/{id}/odontograma` con la dentición y todas las piezas marcadas del borrador, y con `version_esperada` igual a la versión cargada. Con `201`, la UI SHALL mostrar la nueva versión con su autor y fecha y quedar sin cambios pendientes.

#### Scenario: Guardado (happy path)

- **GIVEN** el odontograma en versión 1 con la pieza 16 marcada en el borrador
- **WHEN** el odontólogo guarda
- **THEN** el frontend envía `version_esperada = 1`, muestra "Versión 2 · guardada por <profesional> el <fecha>" y deshabilita "Guardar" hasta un nuevo cambio.

#### Scenario: Sin cambios (borde)

- **WHEN** el borrador es igual a la versión cargada
- **THEN** "Guardar odontograma" está deshabilitado.

#### Scenario: Rechazo de validación (error de negocio)

- **WHEN** el servidor responde `422`
- **THEN** el frontend muestra el motivo devuelto y conserva el borrador.

### Requirement: Conflicto de versión del odontograma

Si el guardado responde `409`, el frontend SHALL avisar que otro profesional guardó una versión más nueva, SHALL conservar el borrador visible y SHALL ofrecer "Recargar versión vigente", que descarta el borrador tras confirmación y carga `GET /odontograma/actual`. La UI SHALL no reintentar el guardado sola.

#### Scenario: Guardado sobre versión vieja (error de negocio)

- **GIVEN** el usuario cargó la versión 1 y otro profesional ya guardó la 2
- **WHEN** guarda su borrador
- **THEN** ve "Hay una versión más nueva del odontograma. Recargá para ver los cambios antes de volver a marcar", su borrador sigue en pantalla y no se crea versión.

#### Scenario: Recargar tras el conflicto (borde)

- **WHEN** el usuario elige "Recargar versión vigente" y confirma
- **THEN** el frontend muestra la versión 2 sin el borrador y "Guardar" queda deshabilitado.

### Requirement: Aviso de cambios sin guardar

Con cambios sin guardar en el odontograma, el frontend SHALL pedir confirmación antes de salir a otra pestaña o ruta de la aplicación y antes de cerrar o recargar la página.

#### Scenario: Cambiar de pestaña con borrador (borde)

- **GIVEN** un borrador con cambios
- **WHEN** el usuario elige la pestaña Evoluciones
- **THEN** el frontend pregunta si quiere descartar los cambios y, si cancela, se queda en el odontograma con el borrador intacto.

### Requirement: Historial de versiones del odontograma

El frontend SHALL ofrecer el historial (`GET /odontograma`) con número, autor y fecha de cada versión, de la más reciente a la más antigua, y SHALL permitir ver una versión anterior en solo lectura, claramente rotulada, sin poder guardarla ni editarla.

#### Scenario: Ver una versión anterior (happy path)

- **GIVEN** un odontograma con versiones 1 y 2
- **WHEN** el usuario elige ver la versión 1
- **THEN** el dibujo muestra las marcas de la versión 1 con el rótulo "Versión 1 (anterior) · solo lectura" y sin controles de guardado.
