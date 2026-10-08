# Arquitectura Propuesta

> Fuente: `discovery/Discovery Consolidado Turnos Odontologia.pdf`. Stack DECIDIDO en ronda de respuestas usuario 1 (2026-10-07, PA-01 → DD-08): Python + FastAPI (backend) + PostgreSQL (DB) + React/Vite (frontend). El discovery no imponía tecnología. Lo marcado **(S)** es propuesta de modelado a validar, no texto del PDF.

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|--------|--------------|---------|
| SaaS multi-tenant (S) | Toda la app: clínica como tenant | Todo el mapa de competidores cobra por profesional/sillón/usuario; agenda en la nube y reserva online lo presuponen. Ver SU-01 |
| Recurso de agenda + anti-solapamiento duro | Motor de turnos (sillón + profesional + equipo) | Es el vacío documentado del mercado; ningún competidor lo documenta públicamente (§01, §06). Debe ser regla de dominio, no solo validación de UI |
| RBAC por recurso | Panel admin / recepción / clínica | Exigido en MVP ("roles, permisos"); referencia Dentally con permisos granulares |
| Append-only + auditoría inmutable | Evoluciones, HC, consentimientos | Exigido por Ley 26.529; argumento comercial de cumplimiento (§07) |
| Presupuesto → plan → turnos (saga simple) | Conversión clínica en agenda | Diferenciador §07: cada presupuesto aceptado genera secuencia de turnos; lo no agendado va a seguimiento |
| Webhooks + idempotencia | WhatsApp/Meta, Mercado Pago, ARCA | Respuestas por WhatsApp actualizan la agenda; pagos y CAE llegan asíncronos; los reintentos no pueden duplicar turnos ni cobros (S) |
| Cola + reintentos visibles | Factura ARCA, mensajes WhatsApp, ofertas de lista de espera | Los servicios externos caen; el estado pendiente/reintentando debe ser visible, no mudo (S) |
| Score de riesgo + seña condicional | Confirmación de reserva online | Combina puntaje de riesgo tipo DrApp con relleno tipo DentalCore (§07): la seña solo se exige ante riesgo |

## Estructura de directorios

> Stack decidido (DD-08): `frontend/` = React/Vite, `backend/` = Python/FastAPI, DB = PostgreSQL.

```
proyecto/
├── frontend/                 # React + Vite (decidido ronda usuario 1)
│   └── src/
│       ├── features/
│       │   ├── agenda/       # vista día/semana, reglas, bloqueos, sobreturnos
│       │   ├── reserva/      # enlace público sin registro
│       │   ├── clinica/      # ficha, odontograma FDI, evolución
│       │   ├── presupuesto/  # presupuesto → plan → turnos, seguimiento
│       │   ├── caja/         # seña/saldo MP, factura ARCA, arqueo
│       │   ├── whatsapp/     # bandeja, plantillas, costos, fallos
│       │   └── admin/        # usuarios/RBAC, sillones, precios ARS, reportes
│       ├── shared/
│       └── pages/            # rutas públicas: reserva, cumplimiento, comprobantes
├── backend/                  # Python + FastAPI (decidido ronda usuario 1)
│   └── app/
│       ├── domain/
│       │   ├── agenda/       # motor anti-solapamiento, sobreturnos, lista de espera
│       │   ├── clinica/      # HC append-only, odontograma, auditoría
│       │   ├── comercial/    # presupuesto/plan, riesgo de ausencia, recall
│       │   └── cumplimiento/ # consentimientos, firma, exportación
│       ├── infrastructure/
│       │   ├── whatsapp/     # API oficial Meta + webhooks + costos
│       │   ├── pagos/        # Mercado Pago (seña/saldo)
│       │   ├── fiscal/       # ARCA FE B/C con CAE + QR + cola de reintentos
│       │   ├── recetas/      # partner ReNaPDiS (propia es F2)
│       │   └── os/           # etapa 2: cobertura/copago/lotes/RNO, Frontini
│       └── application/
├── jobs/                     # recordatorios, ofertas de hueco, recall, RNO/lotes (etapa 2)
└── docs-legales/             # política de privacidad, página de cumplimiento (con asesoría legal)
```

## Seguridad

- Autenticación: a definir sobre el stack decidido (FastAPI + React/Vite). Mínimo exigible (S): sesiones con expiración, todo lo no-público tras login (ver rutas públicas en `03_actores_y_roles.md`).
- Autorización: RBAC por recurso (matriz en `03_actores_y_roles.md`); sobreturnos y anulaciones de caja solo con rol; evolución exige autor profesional.
- Validación de input: duraciones/end-times calculados en servidor (nunca confiar en el cliente para solapamientos); DNI/email/teléfono normalizados para reserva sin cuenta (S).
- HC y datos sensibles: cifrado en tránsito y en reposo, auditoría inmutable, consentimiento de datos (Ley 25.326 — datos de salud = sensibles); ubicación de datos declarada públicamente (hoy nadie la publica, §06).
- Firma: consentimientos con fecha, IP, dispositivo y hash, documento bloqueado (modelo Odonthia, Ley 25.506).
- Secrets management: sobre el stack decidido (env gestionado / vault compatible con despliegue FastAPI + PostgreSQL). Mínimo (S): ningún secreto en repo; credenciales MP/ARCA/Meta solo en vault o env gestionado.

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Conexión a PostgreSQL (decidido, DD-08) | `postgres://…` | Y |
| `MP_ACCESS_TOKEN` | Mercado Pago, cobro de seña/saldo a cuenta del profesional | `APP_USR-…` | Y |
| `MP_WEBHOOK_SECRET` | Firma de webhooks de pago | `whsec_…` | Y |
| `WHATSAPP_API_TOKEN` | Meta WhatsApp Business API oficial | `EAAB…` | Y |
| `WHATSAPP_PHONE_ID` | Número remitente oficial | `54911…` | N |
| `WHATSAPP_WEBHOOK_VERIFY` | Token de verificación del webhook | `…` | Y |
| `ARCA_CUIT` | CUIT del consultorio para FE | `30-…-…` | N |
| `ARCA_CERT` / `ARCA_KEY` | Certificado fiscal | ruta/vault | Y |
| `RECETAS_PARTNER_KEY` | Partner ReNaPDiS (Farmalink/Innovamed/u otro) | `…` | Y |
| `ARS_PRECIO_MENSAJE` | Costo de mensajería expuesto en pesos (transparencia §07) | `12.50` | N |
| `RESERVA_PREBLOQUEO_MIN` | Expiración del pre-bloqueo de horario sin pago (S, a validar) | `15` | N |
| `APP_BASE_URL` | URL pública (enlaces de reserva, comprobantes, cumplimiento) | `https://…` | N |
