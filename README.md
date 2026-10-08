# Turnos Odontología — SaaS multi-tenant (AR)

Sistema de gestión de turnos para clínicas odontológicas argentinas: agenda con
anti-solapamiento duro, reserva online sin cuenta, odontograma + HC append-only,
presupuesto → plan → turnos, caja con Mercado Pago, factura electrónica ARCA,
WhatsApp por QR con número dedicado y cumplimiento Ley 25.326/26.529.

## Stack (DD-08)

Backend Python + FastAPI · PostgreSQL 16 · Frontend React + Vite + TS · Alembic.

## Quick start (C-01)

```bash
docker compose up db            # PostgreSQL 16 en :5432
uvicorn app.main:app --reload --app-dir backend   # API en :8000
cd frontend && npm install && npm run dev          # UI en :5173
curl http://localhost:8000/api/health             # {"status":"ok"}
```

## Estructura

`backend/` · `frontend/` · `jobs/` · `docs-legales/` · `knowledge-base/` ·
`openspec/` · `CHANGES.md` (roadmap de 19 changes) · `AGENTS.md` (17 reglas duras).

## Estado

C-01 `foundation-setup` en progreso; ver `CHANGES.md` y `openspec/changes/`.
