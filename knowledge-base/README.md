# Turnos Odontología — Base de Conocimiento

Base de conocimiento generada desde `discovery/Discovery Consolidado Turnos Odontologia.pdf` (corte 23/09/2026, 46 sistemas, base Claude R2). Modo kb-creator: **ingest** (Mode A adaptado: fuente en `discovery/` en lugar de `docs/`). Todo archivo traza al PDF; lo inferido se marca **Suposición / (S)**.

## Índice de Archivos

| Archivo | Contenido |
|---------|-----------|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito (cuadrante vacío: clínica + AR + OS + WhatsApp oficial), objetivos por actor, alcance MVP v1.0, fuera de alcance F2, métricas propias |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack (sin definir en discovery — ver PA-01), arquitectura SaaS + integraciones (WhatsApp oficial, MP, ARCA, partner ReNaPDiS, OS etapa 2) |
| [03_actores_y_roles.md](03_actores_y_roles.md) | 4 roles humanos + sistemas externos; matriz RBAC propuesta (S); rutas públicas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | 6 dominios, ERD textual, 12 entidades (las marcadas (S) son inferencia de modelado), seed data |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | 30 reglas RN-AG/TU/WA/CL/PR/CA/AF/OS/CU/GL con trazabilidad a §§06/07/09/10 |
| [06_funcionalidades.md](06_funcionalidades.md) | 17 US en 5 épicas (IMP/DIF) + 6 US-F2; criterios de aceptación y reglas relacionadas |
| [07_flujos_principales.md](07_flujos_principales.md) | 9 flujos extremo a extremo (reserva+seña, WhatsApp bidi, reprogramación, lista de espera, clínica, presupuesto→turnos, caja+ARCA, consentimiento, etapa 2 OS/receta) |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | 8 patrones, estructura agnóstica al stack, seguridad (leyes AR), 12 env vars |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | 7 decisiones (DD-01…DD-07) + 5 supuestos (SU-01…SU-05) |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | 16 inconsistencias (IN-01…IN-16) + 12 preguntas priorizadas (PA-01…PA-12) + question round de 6 |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Antes de codificar → [10](10_preguntas_abiertas.md)

## Resumen Ejecutivo

Sistema de turnos y gestión odontológica para Argentina que ocupa el cuadrante vacío del mercado: profundidad clínica (odontograma FDI + HC auditada) + circuito local (ARCA, Mercado Pago, obras sociales por etapas) + WhatsApp Business API oficial bidireccional con costo transparente. MVP de 17 historias en 5 épicas con reglas de agenda (sillón como recurso, anti-solapamiento duro) como vacío diferencial; stack técnico y 6 gaps operativos quedan en `10_preguntas_abiertas.md` para cerrar sin asumir.
