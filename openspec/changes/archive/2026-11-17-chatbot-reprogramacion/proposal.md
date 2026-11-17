# Proposal — chatbot-reprogramacion (C-17)

## Why

US-006 y el Flujo 3 (RN-TU-03): hoy, cuando el paciente responde "3/reprogramar" al recordatorio (C-15), el pedido cae en la bandeja y recepción tiene que llamarlo. Reprogramar es lo que más tiempo de mostrador consume. El motor de huecos (C-05c), el alta con 409 (C-05), el canal de WhatsApp (C-15) y el token de la reserva online (C-06) ya existen: falta la conversación guiada que los une.

## What Changes

- **Chatbot por WhatsApp** con estado en el servidor (`conversacion_wa`), en tres pasos: `eligiendo → confirmando → cerrada`.
  1. El paciente responde "3"/"reprogramar" a un recordatorio vigente. El sistema le ofrece hasta **3 huecos reales del mismo profesional y prestación**, de los próximos 14 días y a partir de 2 h desde ahora (`buscar_huecos`). Le escribe "1) jue 12/03 10:00 …" y le pide un número, o "0" para dejar el turno como está.
  2. El paciente elige un número. El sistema le pide confirmar ("¿Confirmás el cambio a …? SI/NO").
  3. El paciente responde "SI". El sistema **crea el turno nuevo** con `crear_turno` (mismas reglas, 409 incluido) y **cancela el viejo** con actor `paciente_whatsapp` y motivo "reprogramado". Su hueco entra solo a la lista de espera (C-16). Responde con `reprogramacion_hecha`.
  - **Horario ocupado entre la consulta y la confirmación:** el sistema recalcula y ofrece alternativas, con el mismo 409 de C-05.
  - **Sin huecos disponibles:** el pedido va a la bandeja con el texto `reprogramacion`, como hoy.
  - **"0" o "no":** el turno sigue igual (`reprogramacion_sin_cambios`).
  - **Conversación vencida** (`CHATBOT_TIMEOUT_MIN`, 30 por defecto): la respuesta no toca la agenda y recibe `reprogramacion_vencida`. Un "2" tardío nunca cancela el turno por accidente.
  - **Reintentos:** un evento duplicado no tiene efecto (C-15). Dos "SI" distintos dan una sola reprogramación, gracias al claim de estado.
- **Reprogramación por enlace** (API pública, con el token de C-06):
  - `GET /api/public/reservas/{token}/opciones`: hasta 3 huecos, con las mismas reglas.
  - `POST /api/public/reservas/{token}/reprogramar {inicio}`: crea el turno nuevo y cancela el viejo con actor `paciente_enlace`. El **mismo token** sigue valiendo para el turno nuevo. Un horario ocupado da `409` con alternativas. La pantalla web es de C-07.
- **Textos base**: se suman `reprogramacion_opciones`, `reprogramacion_confirmar`, `reprogramacion_hecha`, `reprogramacion_sin_cambios` y `reprogramacion_vencida` (12 en total).
- **Configuración**: `CHATBOT_TIMEOUT_MIN=30` y `REPROGRAMACION_ANTICIPACION_MIN=120`.
- **Exportación**: suma `conversaciones_whatsapp.csv`.
- Migración `016_reprogramacion` (`down_revision = "015_lista_espera"`).

### Decisiones tomadas con el usuario (2026-11-17)

1. Reprogramar es crear un turno nuevo y cancelar el viejo, no mover el mismo turno. No se toca `turnos.py` y el hueco viejo pasa por la lista de espera.
2. Alcance: chatbot de WhatsApp más la API pública del enlace. La pantalla la hace C-07.
3. Opciones: hasta 3 huecos del mismo profesional y prestación, en 14 días.

### Supuestos (registrados, de bajo impacto)

- **Seña:** todavía no existe (C-12). "Conserva la seña imputada" se resolverá en C-12 enlazando el turno nuevo con el cobro del viejo.
- **Prestación:** es la misma, así que no cambia la duración. "Cambio de duración recalcula fin" (RN-AG-02) queda garantizado por `crear_turno`.
- **Turnos reprogramables:** solo los `reservado` o `confirmado` que todavía no empezaron. El turno nuevo nace `reservado`, porque la confirmación la dispara el próximo recordatorio.
- **Respuesta no reconocida dentro de la conversación** (texto libre, número fuera de rango): va a la bandeja y la conversación sigue abierta hasta vencer.

## Non-goals

- Pantalla web de reprogramación (C-07).
- Seña (C-12).
- Cambiar de profesional o de prestación.
- Reprogramar sin un recordatorio vigente: el paciente que escribe de la nada va a la bandeja.

## Capabilities

### New Capabilities

- `appointment-rescheduling`:
  - conversación de reprogramación por WhatsApp (opciones, elección, confirmación, vencimiento y concurrencia);
  - cálculo de opciones;
  - reprogramación por enlace con el token de C-06.

### Modified Capabilities

- `whatsapp-messaging`: "reprogramar" abre el chatbot en lugar de ir directo a la bandeja; la conversación abierta tiene prioridad al asociar la respuesta; los textos base pasan a ser 12.
- `public-booking`: el token permite consultar opciones y reprogramar.
- `platform-config`: configuración del chatbot.
- `data-export`: la exportación incluye las conversaciones.

## Impact

- **Código nuevo**:
  - `backend/app/domain/reprogramacion/` (modelo, servicios, schemas);
  - `backend/alembic/versions/016_reprogramacion.py`.
- **Código modificado**:
  - `domain/whatsapp/servicios.py`: rama de la conversación y "reprogramar" abre el chatbot;
  - `api/publico.py`: dos endpoints con límite por IP;
  - `settings.py`, `.env.example`, `exportador.py`.
- **DB**:
  - tabla `conversacion_wa`, con UNIQUE parcial de una conversación abierta por teléfono y clínica;
  - CHECK de `plantilla_wa` ampliado.
- **Dependencias nuevas**: ninguna.
- **Governance**: MEDIO (endpoint público nuevo con token existente).
