# Tasks — reserva-online-publica (C-06)

> Governance ALTO: antes de la tarea 1.1, el usuario aprueba `design.md` (D1–D6).
> TDD en cada grupo. Integración solo con testcontainers `postgres:16-alpine` (regla dura 9).

## 1. Modelo y migración

- [x] 1.1 Migración `backend/alembic/versions/013_reserva_online.py` + `Clinica.slug`, `Turno.token_publico_hash`, `TurnoTransicion.actor_tipo`/`actor_usuario_id` nullable (D1, D2, D4); `seed_core` fija `slug = "clinica-piloto"`. Verificar con `backend/tests/integration/test_migracion_013.py`:
  - columnas, UNIQUE y CHECKs del slug: formato inválido → 23514, duplicado → 23505;
  - UNIQUE parcial del token;
  - CHECK de coherencia del actor (`usuario` sin id y `paciente_enlace` con id → 23514);
  - filas previas quedan con `actor_tipo='usuario'`;
  - downgrade a 012 sin cancelaciones por enlace y re-upgrade;
  - único head.
- [x] 1.2 `crear_turno(..., origen, token_publico_hash)` y `transicionar_turno(..., actor_id: int | None, actor_tipo)` con defaults que no cambian el mostrador (D3, D4). Verificar que `test_turnos_api.py`, `test_turno_transiciones_api.py` y `test_turno_transicion_db.py` siguen verdes, y agregar en `test_turno_transicion_db.py` la transición `paciente_enlace` sin usuario.

## 2. Servicio de reserva pública

- [x] 2.1 Schemas públicos (`ReservaIn` con `acepta_privacidad: Literal[True]`, normalización de DNI/email/teléfono, al menos un contacto; salidas sin datos del paciente) (D5). Verificar en `backend/tests/unit/test_reserva_schemas.py`:
  - privacidad false o ausente;
  - DNI inválido;
  - sin contacto;
  - teléfono no E.164;
  - campo extra (`sobreturno`, `clinica_id`);
  - nombre vacío o >100 → error.
- [x] 2.2 `reserva_publica.py`: catálogo público, huecos públicos, `reservar` (paciente nuevo o reutilizado, tope por DNI, elección de sillón, token con hash), `obtener_por_token` y `cancelar_por_token` (D3, D4). Verificar con `backend/tests/integration/test_reserva_publica_servicio.py`:
  - paciente nuevo sin usuario, auditado con `actor_tipo='sistema'`;
  - DNI existente no modifica la ficha;
  - paciente de baja → 422;
  - tercera reserva → 409 y una cancelada libera el cupo;
  - segundo sillón libre;
  - fuera de horario → 409;
  - token guardado solo como hash;
  - cancelar antes y después del inicio;
  - historial `paciente_enlace`.
- [x] 2.3 Concurrencia: dos reservas simultáneas del mismo hueco con un único sillón → un 201 y un 409; dos reservas simultáneas con el mismo DNI nuevo → un solo paciente. Verificar con `backend/tests/integration/test_reserva_publica_concurrencia.py`.

## 3. API pública

- [x] 3.1 Router `backend/app/api/publico.py` + `include_router` + límites de rate en settings y `.env.example` (D5). Verificar con `backend/tests/integration/test_reserva_publica_api.py`, un test por escenario de `public-booking`:
  - catálogo: 200, profesional sin horario ausente, slug inexistente 404;
  - huecos: sin sillones, profesional de otra clínica 422;
  - reserva: 201 con token, privacidad 422, DNI existente;
  - tope 409;
  - token: ver sin datos personales, cancelar 200 + hueco reaparece, después del inicio 422, token inválido 404;
  - **sin JWT**: funciona sin `Authorization`;
  - aislamiento: el slug de A no ve ni reserva profesionales de B.
- [x] 3.2 Rate limit: superar `RATE_LIMIT_PUBLICO_RESERVA` desde una IP → 429 con `Retry-After`. Verificar en `test_reserva_publica_api.py`, reseteando el limiter entre tests como hace el login.

## 4. Frontend público

- [x] 4.1 `frontend/src/features/reserva/api.ts` (fetch público sin credenciales ni headers de sesión) + tipos. Verificar con `frontend/tests/reserva-api.test.ts`: URLs, cuerpo, manejo de 404/409/422/429 y que nunca envía `Authorization`.
- [x] 4.2 `ReservarPage` (`/reservar/:slug`) y `ReservaPage` (`/reserva/:token`) + rutas en `router.tsx` (D6), aplicando el checklist de UX/a11y de las skills de diseño sobre el sistema visual de C-10. Verificar con `frontend/tests/reserva.test.tsx` (mocks de fetch):
  - flujo completo navega al comprobante;
  - 409 recarga huecos y conserva datos;
  - 422 muestra error asociado;
  - slug 404 → "Enlace no encontrado";
  - comprobante → cancelar con confirmación → "Turno cancelado";
  - token 404 → "Reserva no encontrada";
  - no escribe en `localStorage`.
- [x] 4.3 `npm run build` (tsc estricto + vite) y `npm run lint` y `npm test` en verde (regla dura 11).

## 5. Integración, documentación y trazabilidad

- [x] 5.1 Suite backend completa + `ruff check backend` en verde; prueba de mutación (quitar el tope por DNI o el filtro "profesional con horario" del catálogo y verificar que algún test falla). Todo en `verify.md`.
- [x] 5.2 Prueba manual: uvicorn + `npm run dev`, reservar desde `/reservar/clinica-piloto`, ver el turno en `GET /api/turnos/{id}` con `origen=enlace`, cancelar desde `/reserva/{token}`. Registrar en `verify.md`.
- [x] 5.3 KB `04` (`Clinica.slug`, `Turno.token_publico_hash`, `TurnoTransicion.actor_tipo`), README (tests y enlace de reserva) y `docs/CONTINUAR.md` (migración 013, próxima 014; C-12 debe agregar la rama seña sobre `reserva_publica.reservar`).
- [x] 5.4 `dominio-agenda` (RN-AG-05 → cubierta) y `dominio-caja` (RN-CA-01/02 siguen pendientes, con nota "punto de extensión en `reserva_publica.reservar`"), copias sincronizadas. Verificar con `verificar.py` de ambas → OK después del archive.

## Workflow follow-up

- `/opsx:archive reserva-online-publica` tras la revisión humana y con `verify.md` completo.
- Marcar C-06 `[x]` en `CHANGES.md` con la nota "sin seña (→ C-12)".
