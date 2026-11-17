# Proposal — horario-atencion (C-05d)

## Why

Hoy un profesional "atiende" las 24 horas, los 7 días: `GET /api/agenda/huecos` devuelve cualquier inicio dentro de la ventana que se pida, y `POST /api/turnos` acepta un turno de madrugada. Para el mostrador alcanza con que la recepción pida bien la ventana. Pero la reserva pública (C-06) expone los huecos al paciente, y sin un horario de atención le ofrecería las 3 de la mañana. La KB no define horario (C-05c, D1). Por eso C-05d bloquea a C-06.

## What Changes

- **Horario por profesional**: franjas semanales (día de la semana + hora de inicio y fin en hora local), por ejemplo "lunes 09:00–13:00 y 15:00–19:00".
  - El admin reemplaza el horario completo de un profesional con `PUT /api/admin/profesionales/{id}/horario`, que es todo o nada.
  - El staff lo consulta con `GET /api/catalogo/profesionales/{id}/horario`.
- **Zona horaria de la clínica**: columna `clinica.zona_horaria`, por defecto `America/Argentina/Buenos_Aires`. Las franjas se interpretan en esa zona, y el horario de verano lo resuelve PostgreSQL con la regla de la zona.
- **Huecos**: `GET /api/agenda/huecos` solo ofrece inicios cuyo turno completo cae dentro del horario del profesional. Dos franjas contiguas cuentan como una.
- **Alta de turno**: un turno **normal** fuera del horario responde `409` "Horario no disponible". El **sobreturno** queda exceptuado (RN-AG-04: "lo agrego al final del día"), pero sigue respetando bloqueos.
- **Sin horario cargado = no atiende** (falla cerrado). Si el profesional no tiene franjas, no aparece en huecos y no acepta turnos normales. **BREAKING** para datos existentes: los profesionales sin franjas dejan de aceptar turnos normales hasta que el admin les cargue el horario. El seed sintético carga un horario de ejemplo.
- **Feriados**: siguen siendo bloqueos de toda la clínica (C-04). No se agrega una entidad nueva.
- Migración `012_horario_atencion` (`down_revision = "011_sobreturno_huecos"`): tabla `franja_horaria` y columna `clinica.zona_horaria`.

### Decisiones de dominio tomadas con el usuario (2026-11-17)

1. Horario **por profesional**, no por sillón ni por clínica (agenda tercerizada, DD-04).
2. Zona horaria **en la clínica** (columna), no global.
3. Fuera del horario: turno normal `409`; sobreturno exceptuado; huecos solo dentro del horario.
4. Profesional sin franjas: **sin huecos ni turnos normales**.

## Non-goals

- Horario por sillón o de la clínica, y excepciones por fecha ("este jueves atiendo hasta las 12"). Una excepción que reduce el horario es un bloqueo; una que lo amplía no se modela.
- Editar `zona_horaria` por API: queda con el valor por defecto, que cambia la migración o el seed. La configuración de clínica es de C-14.
- Franjas que cruzan la medianoche.
- Reserva pública (C-06) y UI de horario (C-07/C-14).

## Capabilities

### New Capabilities

- `business-hours`: franjas semanales de atención por profesional, su administración, su consulta y la zona horaria de la clínica en que se interpretan.

### Modified Capabilities

- `schedule-availability`: los huecos se limitan al horario de atención del profesional.
- `appointments`: el alta de un turno normal exige caer dentro del horario de atención; el sobreturno queda exceptuado.

## Impact

- Código nuevo:
  - modelo `FranjaHoraria` en `backend/app/domain/agenda/models.py`;
  - servicio de horario (reemplazo, consulta y multirango del horario) en `backend/app/domain/agenda/horario.py`;
  - schemas `FranjaIn`/`FranjaOut`/`HorarioIn`;
  - rutas en `admin_catalogo.py` y `catalogo.py`;
  - `backend/alembic/versions/012_horario_atencion.py`.
- Código modificado:
  - `huecos.py`: intersección con el horario;
  - `turnos.py`: chequeo de horario en `crear_turno` normal;
  - `core/models.py`: `Clinica.zona_horaria`;
  - `seed_catalogo.py`: horario de ejemplo;
  - fixture `turnos_data` de los tests: horario de día completo para los profesionales de prueba, para que los tests previos no cambien de significado.
- DB: 1 tabla nueva tenant-scoped (índice `(clinica_id, profesional_id, dia_semana)`) y 1 columna.
- Dependencias: ninguna nueva.
- Governance: CRÍTICO (toca el motor de turnos de C-05); el apply requiere aprobar el diseño.
