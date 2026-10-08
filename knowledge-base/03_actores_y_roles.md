# Actores y Roles

> Fuente: discovery §§01, 03, 06, 08, 09. El discovery no trae una tabla de actores propia; la de abajo se infiere de las funcionalidades MVP y de los competidores. Lo inferido se marca.

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|-------|-------------|-----------------|
| Paciente | Persona que reserva y recibe atención odontológica | Reserva online por enlace sin registro (abierta a nuevos); confirma/cancela/reprograma por WhatsApp; paga seña por Mercado Pago |
| Recepcionista / administrativo | Gestiona agenda, pacientes y caja diaria | Panel web: agenda día/semana, fichas, presupuestos, cobros, lista de espera, mensajes |
| Odontólogo / profesional | Prestador clínico, dueño o tercerizado | Panel web: su agenda, ficha + odontograma + evolución, presupuesto/plan, consentimientos; **Suposición:** firma sus evoluciones con autor/fecha |
| Administrador / dueño de clínica | Configura el consultorio y supervisa | Panel admin: usuarios y roles, sillones/recursos y reglas, precios en ARS, reportes, respaldo/exportación |
| Sistema externo (no humano) | ARCA, Mercado Pago, WhatsApp/Meta, partner recetas, OS/círculos | APIs/webhooks (ver `02_descripcion_general.md`) |

**Confirmado SU-02 (ronda usuario 1, PA-03):** los 4 roles humanos alcanzan para iniciar el MVP, con permisos granulares: el odontólogo tercerizado ve solo su agenda; los sobreturnos los maneja admin/recepcionista según rol. Origen: matriz RBAC/permisos granulares citada como referencia (Dentally) + requisito MVP "roles, permisos, respaldo y exportación" + respuesta usuario ronda 1.

## RBAC — Matriz de permisos

> **Suposición** (propuesta mínima a validar; el discovery exige "roles y permisos" pero no detalla la matriz).

| Rol → Recurso | Agenda/turnos | Pacientes/fichas | HC/odontograma/evolución | Presupuesto/plan | Caja/seña/factura | Configuración/usuarios | Reportes/exportación |
|---------------|---------------|------------------|--------------------------|------------------|--------------------|------------------------|----------------------|
| Administrador | CRUD + reglas y bloqueos | CRUD | Lectura (auditoría) | CRUD | CRUD + arqueo | CRUD | Totales |
| Odontólogo | Lectura + bloqueos propios; sobreturnos según rol | Lectura/escritura de sus pacientes | CRUD propias (autor/fecha) | CRUD propios | Cobrar sus prácticas | Sin acceso | Propios |
| Recepcionista | CRUD turnos; sobreturnos si el rol lo autoriza (confirmado ronda 1: admin/recepcionista manejan sobreturnos) | CRUD | Sin acceso clínico (solo datos contacto/OS) | Crear/seguimiento, no modificar clínica | Cobrar/seña, no anular sin rol | Sin acceso | Operativos |
| Paciente (enlace) | Crear/cancelar/reprogramar los suyos vía enlace + WhatsApp | Solo sus datos | Sin acceso | Ver/aceptar los suyos | Pagar seña/saldo | Sin acceso | Solo sus comprobantes |

Reglas transversales: sobreturnos autorizados por rol; prevención dura de solapamientos (sillón + profesional + equipo); evolución siempre con autor y fecha; anulaciones de caja con traza.

## Rutas públicas

- Enlace de reserva online (sin autenticación; abierta a pacientes nuevos — Bilog solo permite registrados y se cita como contra-ejemplo).
- Confirmación/cancelación/reprogramación vía WhatsApp (deep-link/plantilla, sin app).
- Presupuesto en PDF compartible y comprobantes de pago/factura.
- Política de privacidad y página de cumplimiento (leyes 26.529, 25.326 y 25.506).
- Todo lo demás requiere autenticación y rol.
