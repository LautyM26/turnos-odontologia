# WhatsApp por sesión QR — runbook de operación (C-15)

Cómo poner en marcha, mantener y recuperar el canal de WhatsApp del consultorio. Decisión de base: **DD-10** (`knowledge-base/09_decisiones_y_supuestos.md`). Usamos una sesión de WhatsApp Web (QR) con un número dedicado, a través del gateway autoalojado **WAHA**. No usamos la plataforma oficial de Meta.

---

## 1. Riesgo asumido (leer antes de activar)

- Usar WhatsApp por QR **no es un uso oficial**. Meta puede **bloquear el número** por sus Términos de Servicio, sin aviso.
- La sesión puede caerse o desvincularse: el teléfono se queda sin batería o sin datos, se cierra la sesión desde el celular, o cambia la versión de WhatsApp Web.
- No hay garantía de entrega ni SLA.

Mitigaciones que ya trae el sistema:

| Riesgo | Qué hace el sistema |
|---|---|
| Bloqueo del número | Se usa solo un **número dedicado**, nunca el personal ni el del consultorio. Hay un límite de envíos (`WHATSAPP_ENVIOS_POR_MINUTO`, 20 por defecto). Solo se escribe a pacientes con turno y nunca se contesta automáticamente un mensaje que no se entendió. |
| Sesión caída | El estado se ve en `GET /api/whatsapp/sesion` y queda un log `WARNING` con `evento=whatsapp_sesion_caida`. Los recordatorios que no salen van a la **bandeja de fallos**. |
| Nada sale | **Fallback manual**: recepción mira `GET /api/whatsapp/fallos`, avisa por teléfono y marca el fallo como resuelto. El turno nunca cambia por un fallo de envío. |
| Cambio de proveedor | La mensajería está detrás de un puerto (`backend/app/infrastructure/whatsapp/puerto.py`). Ver §7. |

## 2. Configuración

En `backend/.env`. Los valores reales van **solo** en el entorno del servidor, nunca en el repo.

| Variable | Valor |
|---|---|
| `WHATSAPP_GATEWAY` | `waha` en producción; `fake` en desarrollo/demo (no envía nada; está bloqueado si `ENTORNO=produccion`); vacío = canal apagado |
| `WHATSAPP_GATEWAY_URL` | URL del gateway vista desde la API: `http://waha:3000` si la API corre en compose, `http://localhost:3000` si corre en el host |
| `WHATSAPP_GATEWAY_API_KEY` | Clave larga al azar. Es la misma que recibe WAHA como `WAHA_API_KEY` |
| `WHATSAPP_WEBHOOK_HMAC_KEY` | Otra clave larga al azar. Con ella WAHA firma los eventos y la API los verifica (firma inválida → `401`) |
| `APP_BASE_URL` | URL de la API **alcanzable desde WAHA**. Con esta URL se arma el webhook `…/api/webhooks/whatsapp`. Si la API está en compose: `http://api:8000`; si está en el host: `http://host.docker.internal:8000` |
| `WHATSAPP_RECORDATORIO_HORAS` | Ventana del recordatorio (24). Hay que validarla con el piloto (SU-04) |
| `WHATSAPP_MAX_INTENTOS` | Reintentos por recordatorio (3) |
| `WHATSAPP_ENVIOS_POR_MINUTO` | Límite de envíos por minuto (20) |
| `ARS_PRECIO_MENSAJE` | Costo interno por mensaje saliente en pesos (RN-WA-02) |

Para generar una clave: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## 3. Poner en marcha y escanear el QR

1. Levantar el gateway. Solo arranca con el perfil `whatsapp`; un `docker compose up` normal no lo levanta.

   ```bash
   docker compose --profile whatsapp up -d waha
   ```

2. Con un usuario **admin**, pedir la reconexión. La API crea la sesión `clinica-<id>` con el webhook firmado:

   ```bash
   curl -X POST "$API/api/whatsapp/sesion/reconectar" -H "Authorization: Bearer $TOKEN"
   ```

   La respuesta trae `estado = "escanear_qr"` y el campo `qr` (PNG en base64).
3. Abrir el QR (en Swagger, en `/docs`, o pegando `data:image/png;base64,<qr>` en el navegador). En el **teléfono dedicado**, ir a WhatsApp → Dispositivos vinculados → Vincular un dispositivo y escanear. El QR vence rápido: si vence, pedir `GET /api/whatsapp/sesion` de nuevo para obtener uno fresco.
4. Confirmar que `GET /api/whatsapp/sesion` devuelve `estado = "activa"` y el `numero` vinculado.

Cada clínica tiene **su propia** sesión y número. El admin de cada clínica la vincula desde su usuario.

## 4. Recordatorios (cron)

El job envía un recordatorio por turno `reservado` que empiece dentro de la ventana, y reintenta los fallidos. Se recomienda correrlo **cada 15 minutos**: ese período es también el backoff entre reintentos.

```bash
# Linux (crontab del usuario del servicio)
*/15 * * * * cd /srv/turnos/backend && python -m app.jobs.recordatorios
# Con la API en compose
*/15 * * * * cd /srv/turnos && docker compose exec -T api python -m app.jobs.recordatorios
```

Si dos corridas se pisan no hay problema: la base garantiza **un solo recordatorio por turno**.

**Lista de espera (C-16).** Otro cron, cada **5 minutos**, ofrece los huecos de turnos cancelados a la lista de espera y vence las ofertas no respondidas (`LISTA_ESPERA_OFERTA_MIN`, 30 por defecto; solo huecos con `LISTA_ESPERA_ANTICIPACION_MIN`, 120 por defecto, o más de anticipación). Si el canal está caído, la oferta se anula y la corrida se corta: la cola no se consume.

```bash
*/5 * * * * cd /srv/turnos/backend && python -m app.jobs.lista_espera
```

## 5. Sesión caída: reconexión

Señales:
- `GET /api/whatsapp/sesion` devuelve `caida`, `detenida` o `escanear_qr`;
- aparecen fallos `sesion_no_activa` en la bandeja;
- el log muestra `whatsapp_sesion_caida`.

Pasos:
1. Revisar el teléfono dedicado: que tenga batería, datos y WhatsApp abierto alguna vez en el día.
2. Admin: `POST /api/whatsapp/sesion/reconectar`. Si devuelve `escanear_qr`, volver a escanear (§3).
3. Los recordatorios en error se reintentan solos en las corridas siguientes, hasta `WHATSAPP_MAX_INTENTOS`.
4. Lo que no alcance a salir, recepción lo avisa a mano desde la bandeja y lo marca resuelto: `POST /api/whatsapp/fallos/{id}/resolver`.

Si el número fue **bloqueado** por Meta: apagar el canal (§6), conseguir otro número dedicado, borrar la sesión vieja del gateway y repetir §3.

## 6. Backup y restauración cifrada de la sesión

La sesión vive en el volumen `waha_sessions` del gateway, no en la base de datos. Ese volumen tiene **credenciales de WhatsApp**: siempre se respalda **cifrado** (por ejemplo con [`age`](https://age-encryption.org/)), y la clave privada se guarda fuera del servidor y fuera del repo.

El nombre real del volumen lleva el prefijo del proyecto de compose (por defecto `turnos-odontologia_waha_sessions`). Se puede confirmar con `docker volume ls`.

```bash
# Backup (detener el gateway para copiar un estado consistente)
docker compose --profile whatsapp stop waha
docker run --rm -v turnos-odontologia_waha_sessions:/data alpine tar czf - -C /data . \
  | age -r "<clave-publica-age>" -o "waha-sesion-$(date +%F).tar.gz.age"
docker compose --profile whatsapp start waha

# Restauración (en un servidor nuevo o tras perder el volumen)
docker compose --profile whatsapp stop waha
age -d -i clave-privada.txt "waha-sesion-AAAA-MM-DD.tar.gz.age" \
  | docker run --rm -i -v turnos-odontologia_waha_sessions:/data alpine tar xzf - -C /data
docker compose --profile whatsapp start waha
```

Frecuencia sugerida: diaria, conservando 7 copias. Una sesión restaurada puede pedir un nuevo escaneo si WhatsApp la invalidó: en ese caso, seguir §3.

## 7. Apagar el canal (rollback) y migración futura

- **Apagar sin tocar la base:** dejar `WHATSAPP_GATEWAY=` vacío y reiniciar la API. Todo sigue funcionando y los endpoints de sesión responden `501`. Los recordatorios quedan como fallos `no_configurado`, visibles en la bandeja, y salen solos cuando se vuelve a configurar.
- **Bajar la migración** (`alembic downgrade 013_reserva_online`) solo es posible si ningún turno se confirmó o canceló por WhatsApp. El historial de transiciones es inmutable. En producción: roll-forward.
- **Migración a la plataforma oficial de Meta (F2):** escribir un adapter nuevo que cumpla `Mensajeria` en `backend/app/infrastructure/whatsapp/`, con su parser de eventos, y sumarlo a `factory.py` con un valor nuevo de `WHATSAPP_GATEWAY`. El dominio (recordatorios, respuestas, bandeja, costos) no cambia.
