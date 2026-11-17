# Verify — chatbot-reprogramacion (C-17)

Fecha: 2026-11-17. Resultado: **VERDE** (suite completa, ruff, mutaciones y E2E por HTTP).

## Entorno

- Windows 11, Docker Desktop 29.9.2 sobre WSL2; PostgreSQL `postgres:16-alpine` vía testcontainers.
- Python 3.13.5 (`.venv`), pytest 9.2.0, ruff 0.17.5.
- Diseño D1–D6 aprobado por el usuario el 2026-11-17 (governance MEDIO).
- Base: rama `feat/chatbot-c17` sobre `326927a` (C-16).

## Comandos (desde la raíz del repo)

```
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/python -m ruff check backend
openspec validate chatbot-reprogramacion --strict
```

## Resultados

- Backend, suite completa: **1567 en verde**: 1566 passed, 0 failed en la corrida completa (21 min 04 s); `test_confirmacion_con_conversacion_vieja_no_repite` se agregó después de lanzarla y pasó aparte (antes del change: 1529).
- `ruff check backend`: limpio.
- `openspec validate --strict`: válido.
- Tests nuevos: **38**. Son 37 en archivos nuevos y 1 en `test_exportacion_api.py`.
- Además se reemplazó el test de C-15 `test_reprogramar_va_a_la_bandeja_con_respuesta` por `test_reprogramar_abre_el_chatbot`. La spec cambió: con horarios disponibles, "reprogramar" abre el chatbot.
- La suite de C-15 y C-16 (entrantes, idempotencia, webhook, respuestas de la lista) y la de C-06 (reserva pública) siguen en verde.

| Archivo | Tests | Cubre |
|---|---|---|
| unit/test_settings_reprogramacion.py | 5 | defaults 30/120; valores fuera de rango |
| integration/test_migracion_016.py | 10 | tabla, índice y 12 textos; CHECKs → 23514; una conversación abierta por número (23505), una cerrada convive con una abierta; turno ajeno → 23503; downgrade y re-upgrade; único head |
| integration/test_reprogramacion_servicio.py | 8 | 3 primeros huecos del mismo profesional; un horario ocupado no se ofrece; turnos no reprogramables sin opciones; reprogramar = turno nuevo + viejo cancelado con actor y motivo; 422 (anticipación en el enlace, pasado, no es opción); 409 con alternativas; el token pasa al turno nuevo; una opción ofrecida se confirma aunque pasen minutos |
| integration/test_chatbot_reprogramacion.py | 8 | "3" abre el chatbot; sin huecos → bandeja; "2" + "si" reprograma (y el "2" no cancela); arrepentirse; número fuera de rango; hueco tomado → alternativas; conversación vencida no cancela; evento duplicado |
| integration/test_chatbot_concurrencia.py | 2 | "si" y "SI" en paralelo → 1 turno y 1 cancelación (estable en 3 corridas); confirmación con la conversación leída antes → `sin_efecto` (claim) |
| integration/test_reprogramacion_publica_api.py | 4 | opciones sin sillones y sin JWT, token inválido → 404; reprogramar → 200, original cancelado `paciente_enlace`, el mismo token muestra y cancela el nuevo; `inicio` no opción o campo extra → 422; ocupado → 409 con alternativas |
| integration/test_exportacion_api.py | +1 | `conversaciones_whatsapp.csv` aislado por clínica |

### Hallazgos durante el apply

- **Bug real encontrado por el test de concurrencia.** `reprogramar` volvía a exigir la anticipación mínima (2 h) al **confirmar**. Una opción ofrecida justo a +2 h se rechazaba si el paciente confirmaba un minuto después. Ahora la anticipación se exige al **ofrecer**, o sea en el enlace, que valida contra las opciones vigentes. Una opción ya ofrecida solo tiene que seguir en el futuro y libre. Se agregó un test de regresión.
- **`buscar_huecos` solo genera inicios cuyo turno completo entra en la ventana.** Para verificar un horario puntual se usa la ventana exacta `[inicio, fin)` con la **duración vigente** de la prestación (RN-AG-02), no la guardada en el turno viejo.
- **El test concurrente no detectaba la mutación del claim**, porque otras guardas (el estado `ejecutando` y "turno ya no reprogramable") también frenan la carrera. Se agregó un test determinista con la conversación leída antes de que otro proceso la cierre, y la mutación quedó detectada.
- **Tests de migraciones anteriores** (`test_migracion_014/015.py`) pasaron a validar "al menos" sus textos base, porque cada migración posterior suma textos.

## Pruebas de mutación

Corridas sobre una copia del backend, en paralelo a la suite.

| Mutación | Tests que fallan | Resultado |
|---|---|---|
| Claim `confirmando → ejecutando` sin la condición de estado | `test_confirmacion_con_conversacion_vieja_no_repite` | detectada, tras agregar ese test; antes no se detectaba |
| La conversación abierta pierde prioridad sobre el recordatorio | `test_elegir_y_confirmar_reprograma`, `test_arrepentirse`, `test_hueco_tomado_en_el_medio_ofrece_alternativas`, `test_conversacion_vencida_no_cancela`, `test_evento_duplicado_sin_efecto` | detectada |

## Prueba manual end-to-end (API real por HTTP)

Montaje:

- PostgreSQL 16 en Docker, migrado a la 016, con el seed demo;
- `uvicorn` en `:8012` con `WHATSAPP_GATEWAY=fake`;
- script `evidencias/e2e_c17.py`, con la salida completa en `evidencias/e2e-api-http.txt`.

**Chatbot por WhatsApp**

1. Recepción crea un turno para dentro de unas 20 h. El job envía 1 recordatorio.
2. El paciente responde "3" con un evento firmado. Recibe: "Estos son los horarios disponibles con Profesional Ejemplo (seed): 1) 18/11 a las 09:00, 2) 09:15, 3) 09:30…".
3. Responde "2". Recibe: "¿Confirmás el cambio de tu turno al 18/11 a las 09:15…?".
4. Responde "si". Recibe: "¡Listo Demo Uno! Tu turno quedó para el 18/11 a las 09:15…".
5. Resultado en la base:
   - el turno 1 quedó `cancelado` y el turno 2 (`whatsapp`) `reservado`;
   - la conversación quedó `cerrada/reprogramado` (1 → 2);
   - el historial registra `reservado → cancelado`, actor `paciente_whatsapp`, motivo "reprogramado al turno 2".

**Enlace (token de C-06)**

1. Reserva online → `201` con token.
2. `GET …/opciones` → 3 horarios, sin sillones.
3. `POST …/reprogramar` a la primera opción → `200`, turno nuevo `reservado`.
4. `GET /api/public/reservas/{token}` muestra el horario nuevo.
