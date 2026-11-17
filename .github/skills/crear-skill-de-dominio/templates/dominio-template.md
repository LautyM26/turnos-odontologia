---
name: dominio-<área>
description: Reglas vigentes de <área> (<prefijos RN>) con trazabilidad a specs y tests. Usar al programar <sustantivos con los que se pide el trabajo> (changes <C-NN>), y antes de /opsx:propose de cualquier change de <área>.
---

# dominio-<área>

> Generada con `crear-skill-de-dominio` el <AAAA-MM-DD> a partir de `knowledge-base/05_reglas_de_negocio.md`, `knowledge-base/09_decisiones_y_supuestos.md` y `AGENTS.md`. Si cambia una RN o DD de esta área, regenerarla.

## 1. Propósito

<Una o dos frases: qué parte del sistema cubre y qué problema de la clínica resuelve.>

## 2. Cuándo usarla

- <Tareas concretas: endpoints, modelos, pantallas.>
- Changes del roadmap: <C-NN `nombre` (estado)>.

## 3. Reglas vigentes

| Código | Regla (texto vigente) | DD que la condiciona |
|---|---|---|
| RN-XX-01 | <texto> | <DD-NN o —> |

### Reglas duras de AGENTS.md que aplican

- **<N>**: <texto corto de la regla>.

### Supuestos abiertos (no son reglas cerradas)

- <SU/PA de 09/10 que el área usa; o "ninguno".>

## 4. Cómo aplicarlas

- <Instrucciones operativas para el agente: dónde vive el código, qué patrones reutilizar, qué códigos HTTP devolver.>

## 5. Matriz de trazabilidad RN → spec → test

| Regla | Spec (archivo · requirement) | Test (archivo · función) | Estado |
|---|---|---|---|
| RN-XX-01 | — | — | pendiente |

Resumen: <n> reglas · <n> cubiertas · <n> parciales · <n> pendientes.

### Conflictos detectados

- <Texto de la KB que contradice una DD vigente y qué hay que corregir; o "ninguno".>

## 6. Criterios de revisión

Antes de dar por terminado un change de esta área:

- [ ] Cada regla de la sección 3 que el change toca tiene escenario en la spec del change.
- [ ] Cada escenario nuevo tiene un test y la fila correspondiente de la matriz se actualizó (regenerar esta skill).
- [ ] Ninguna implementación contradice una DD vigente.
- [ ] Se respetaron las reglas duras listadas arriba.
- [ ] Solo datos sintéticos en tests, seeds y ejemplos (regla dura 14).
