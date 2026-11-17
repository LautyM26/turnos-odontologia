---
name: dominio-caja
description: Reglas vigentes de caja y seña (RN-CA) con trazabilidad a specs y tests. Usar al programar cobros, señas, saldos, anulaciones de caja, resumen o arqueo diario, preferencias o webhooks de Mercado Pago, o el score de riesgo que decide si se exige seña (change C-12 caja-mercadopago, y la parte de seña de C-06), y antes de /opsx:propose de cualquier change de caja.
---

# dominio-caja

> Generada con `crear-skill-de-dominio` el 2026-11-16 a partir de `knowledge-base/05_reglas_de_negocio.md`, `knowledge-base/09_decisiones_y_supuestos.md` y `AGENTS.md`. Si cambia una RN o DD de esta área, regenerarla.

## 1. Propósito

Cubre el dinero que entra a la clínica por turno o presupuesto: seña online por Mercado Pago, saldo, anulaciones y caja diaria. La seña reduce ausencias porque bloquea el horario solo cuando se paga, y se exige únicamente a pacientes con riesgo de faltar.

## 2. Cuándo usarla

- Modelos `Cobro`, `CajaMovimiento`, `RiesgoAusencia`; preferencia y webhook de Mercado Pago; anulación de cobros; resumen de caja.
- Changes del roadmap: C-12 `caja-mercadopago` (pendiente; depende de C-05 y C-11), rama "seña exigida" de C-06 `reserva-online-publica`, pantalla `/caja` de C-14. La factura (C-13) es otra área: solo se emite desde un cobro aprobado (RN-AF-01).

## 3. Reglas vigentes

| Código | Regla (texto vigente) | DD que la condiciona |
|---|---|---|
| RN-CA-01 | El turno online se confirma al pagar la seña por Mercado Pago, que va directo a la cuenta del profesional; la seña bloquea el horario. | — (cuenta MP abierta: PA-06) |
| RN-CA-02 | La seña es obligatoria solo para pacientes con historial o riesgo de faltas (score de riesgo). | — |
| RN-CA-03 | Caja con seña y saldo por turno/presupuesto; anulaciones solo con rol y traza. | — |

Reglas relacionadas de otras áreas: RN-PR-03 (montos siempre en ARS, precio público sin packs, DD-05), RN-TU-04 (el ausente alimenta el score de riesgo), RN-AF-01/02 (factura solo desde el cobro y con CUIT configurado).

### Reglas duras de AGENTS.md que aplican

- **4**: schemas Pydantic con `extra='forbid'` (422 ante campos no declarados).
- **7**: montos siempre `NUMERIC` en ARS, nunca float/money; tiempo siempre `TIMESTAMPTZ`.
- **10**: tablas con `clinica_id` + índice `(clinica_id, …)` + test de aislamiento.
- **12**: credenciales de Mercado Pago (`MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`) solo en env/vault del backend; nunca en el browser ni en el repo.
- **17**: la factura ARCA se emite solo desde el cobro y con CUIT configurado.

### Supuestos abiertos (no son reglas cerradas)

- **PA-06 / SU-07**: titularidad de la cuenta Mercado Pago (¿profesional directo?), credenciales y política de reembolso ante cancelación. Sin definir: el diseño de C-12 debe documentar el supuesto elegido.
- **SU-04**: tiempo de pre-bloqueo del horario mientras se paga la seña (`RESERVA_PREBLOQUEO_MIN`, ~15 min).
- Umbral del score de riesgo que vuelve obligatoria la seña: no está definido en la KB. Preguntar antes de fijarlo.

## 4. Cómo aplicarlas

- Webhook de Mercado Pago: ruta pública declarada; validar la firma con `MP_WEBHOOK_SECRET` (firma inválida → `401`) e idempotencia por `id_externo_MP` único (webhook duplicado no duplica el cobro).
- Anulación: reutilizar `require_anulacion_caja()` de `backend/app/api/permissions.py` (hoy solo admin → resto `403`) y registrar quién, cuándo y por qué.
- La seña confirma el turno vía transición de estado: depende de C-05b `transiciones-estado-turno`.
- Para la API de Mercado Pago (preferencias, notificaciones, firma) usar el MCP Context7 con docs vigentes en lugar de memoria. Nunca enviar credenciales ni datos de pacientes en la consulta.

## 5. Matriz de trazabilidad RN → spec → test

| Regla | Spec (archivo · requirement) | Test (archivo · función) | Estado |
|---|---|---|---|
| RN-CA-01 | — | — | pendiente |
| RN-CA-02 | — | — | pendiente |
| RN-CA-03 | `openspec/specs/access-control/spec.md` · "Sobreturnos y anulaciones chequeados por rol" (solo el permiso) | `backend/tests/integration/test_rbac.py` · `test_anulacion_caja_solo_admin` | parcial: existe el guard de rol, faltan caja, cobros y traza |

Resumen: 3 reglas · 0 cubiertas · 1 parcial · 2 pendientes.

### Conflictos detectados

- Ninguna RN-CA contradice una DD vigente.
- Matiz a confirmar: `knowledge-base/03_actores_y_roles.md` dice que la recepción "no anula sin rol", y el guard actual permite anular solo a admin. Es coherente, pero si el piloto quiere un rol de recepción con permiso de anulación hay que cambiar el guard y la spec.

## 6. Criterios de revisión

Antes de dar por terminado un change de esta área:

- [ ] Cada regla de la sección 3 que el change toca tiene escenario en la spec del change.
- [ ] Cada escenario nuevo tiene un test y la fila correspondiente de la matriz se actualizó (regenerar esta skill).
- [ ] Montos en `NUMERIC`, nunca float; ningún secreto de Mercado Pago fuera del backend.
- [ ] Webhook duplicado no duplica cobros; firma inválida → 401.
- [ ] Solo datos sintéticos en tests, seeds y ejemplos (regla dura 14).
