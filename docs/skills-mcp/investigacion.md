# Ficha de investigación — Skill propia + MCP

Proyecto Turnos Odontología · TP Skills + MCP (Metodología I) · 2026-11-16

## 1. Necesidad detectada

Para programar un área, el agente tiene que leer los 11 archivos de `knowledge-base/` y deducir solo qué reglas siguen vigentes. Eso es lento y lleva a errores. Encontramos tres casos reales en el repo:

- `.atl/skill-registry.md` decía "QR prohibido" para WhatsApp, cuando DD-10 decidió QR con número dedicado.
- `AGENTS.md` hablaba de "9 decisiones" (ya existe DD-10) y de "30 reglas" (hay 37).
- RN-TU-02 en `05` todavía decía "WhatsApp oficial (plantilla aprobada)".

El hilo regla → spec → test está cortado: de 37 RN, 7 se citan en specs y ninguna en tests.

La segunda necesidad es documentación vigente de librerías (SQLAlchemy, FastAPI, Mercado Pago). Hoy el agente responde de memoria, y esa memoria puede estar desactualizada.

## 2. Change elegido

**C-05b `transiciones-estado-turno`**: el resto de C-05. Cubre la máquina de estados `reservado → confirmado → asistido | ausente | cancelado` con transiciones auditadas (RN-TU-01).

Se puede preparar sin funcionalidades inexistentes, porque el `Turno` ya existe por el recorte archivado `crear-turno-sin-solapamientos`. Es además el primer change de los que implementa Matheo para el TPI.

Cómo ayudan las dos incorporaciones:

- **Skill `dominio-agenda`** (generada con la skill propia): da las reglas vigentes y muestra que RN-TU-01 está *parcial* (solo existe el estado inicial).
- **MCP Context7**: consulta la doc vigente de SQLAlchemy sobre bloqueo de filas (`with_for_update`) para la transición concurrente.

Cambio respecto a la propuesta inicial: la propuesta usaba C-12 caja como "uso hacia adelante", pero C-12 depende de C-11 (presupuesto), que no existe, y la consigna pide un change sin dependencias faltantes. `dominio-caja` igual se genera y queda lista para quien tome C-12.

## 3. Skill creadora y diseño de la skill propia

| Dato | Valor |
|---|---|
| Skill creadora | `skill-creator`, de Anthropic |
| Fuente | https://github.com/anthropics/skills, carpeta `skills/skill-creator` (licencia Apache 2.0) |
| Qué hace | Crea skills, arma casos de prueba (evals) con y sin la skill, los califica y optimiza la `description` para que se active cuando corresponde |
| Compatibilidad | Claude Code (plugins o carpeta `~/.claude/skills`), Claude.ai (planes pagos) y API. La optimización de la description requiere el CLI `claude` |
| Instalación | `/plugin marketplace add anthropics/skills` + `/plugin install example-skills@anthropic-agent-skills`. **Pendiente:** el README no confirma en qué plugin viene `skill-creator`. En esta PC se usó la copia ya disponible en Claude Code (`anthropic-skills:skill-creator`) |
| Cómo comprobar que está | Pedir en Claude Code "usá skill-creator" o ver la lista de skills disponibles |

**Skill propia: `crear-skill-de-dominio`** (ubicación `.claude/skills/crear-skill-de-dominio/`):

| Sección | Contenido |
|---|---|
| Propósito | Generar `dominio-<área>` con las RN vigentes del área, filtradas por las DD vigentes, más las reglas duras y la matriz RN → spec → test |
| Cuándo se activa | "Creá la skill del dominio X", o antes de `/opsx:propose` de un área sin skill propia |
| Entradas | Prefijo(s) RN (por ejemplo `RN-AG + RN-TU`) y el change del roadmap |
| Procedimiento | 1. Leer las RN. 2. Filtrar con las DD vigentes. 3. Sumar las reglas duras. 4. Buscar specs, código y tests (por significado). 5. Escribir desde la plantilla. 6. Copiar y registrar |
| Resultado | `SKILL.md` + copias para Copilot/OpenCode + registro en `AGENTS.md`, `CLAUDE.md` y `.atl/skill-registry.md` |
| Criterios de revisión | 6 criterios verificables, cada uno con un comando (toda RN en la matriz, nada contra una DD vigente, rutas existentes, description con las palabras del área, índices coherentes, sin datos reales) |

Dónde se guarda: en `.claude/skills/`, donde Claude Code la descubre sola. Copias idénticas en `.github/skills/` (Copilot) y `.opencode/skills/` (OpenCode), con la misma convención que ya usan las skills `openspec-*`. Quedan versionadas en el repo, a diferencia de las 13 skills externas que solo están en una PC.

## 4. Comparación de servidores MCP

| Criterio | **Context7** (Upstash) | **GitHub MCP** (GitHub) |
|---|---|---|
| Propósito | Documentación vigente y ejemplos de código de librerías | Operar GitHub: repos, issues, PRs, Actions, alertas de seguridad |
| Capacidades | `resolve-library-id`, `query-docs` | Toolsets: repos, issues, pull_requests, actions, code_security y otros. Modo `--read-only` |
| Compatibilidad | Claude Code por HTTP remoto o stdio (`@upstash/context7-mcp`) | Claude Code (local con Docker o remoto) |
| Conexión | `https://mcp.context7.com/mcp` | `https://api.githubcopilot.com/mcp/` o Docker `ghcr.io/github/github-mcp-server` |
| Credenciales | Ninguna obligatoria. API key gratis opcional, para más cuota | OAuth o PAT con scopes `repo`, `read:packages`, `read:org` |
| Permisos | Solo lectura de docs públicas | Lectura y escritura sobre el repo según el token |
| Costo | Plan gratuito. El README no publica las cuotas exactas (**pendiente**) | No figura en el README (**pendiente**) |
| Aporte al change | Alto: SQLAlchemy/FastAPI para C-05b, Mercado Pago para C-12 | Bajo: el contenido del change no depende de issues ni PRs |

**Elección: Context7.** Aporta directamente al diseño del change, no necesita secretos ni Docker (Docker no está instalado en la PC de trabajo) y no puede modificar nada. Eso simplifica fijar límites.

## 5. Pasos de instalación y configuración

1. `.mcp.json` en la raíz (scope proyecto, sin secretos): `{"mcpServers":{"context7":{"type":"http","url":"https://mcp.context7.com/mcp"}}}`. El `type` es obligatorio: sin él Claude Code lo interpreta como stdio.
2. Reiniciar Claude Code y aprobar el servidor del proyecto.
3. Comprobar con `/mcp` o `claude mcp list` que aparezca `✔ Connected`.
4. Ejecutar una herramienta: `resolve-library-id` ("sqlalchemy") y después `query-docs` (id + "with_for_update").
5. API key opcional, solo en el scope de usuario (`claude mcp add --scope user … --header "Authorization: Bearer $CONTEXT7_API_KEY"`), nunca en el repo.

Límites: solo documentación pública. No se envían secretos, tokens, datos de pacientes ni código privado. Como máximo unas 3 consultas por pregunta, y la doc oficial se contrasta ante dudas.

## 6. Archivos de la fundación que se actualizan

`AGENTS.md` y `CLAUDE.md` (skills del proyecto, integraciones MCP, conteos corregidos) · `.atl/skill-registry.md` (Project Skills, matriz Change → Skills, MCP como integración, corrección DD-10) · `knowledge-base/05` (RN-TU-02) · `knowledge-base/09` (nota en DD-08) · `knowledge-base/README.md` · `README.md` · `CHANGES.md` (C-05b) · `.mcp.json`.

## 7. Fuentes (consultadas el 2026-11-16)

- Anthropic, skills: https://github.com/anthropics/skills · skill-creator: https://github.com/anthropics/skills/tree/main/skills/skill-creator
- Context7 (Upstash): https://github.com/upstash/context7 · panel: https://context7.com/dashboard
- Claude Code, MCP: https://code.claude.com/docs/en/mcp
- GitHub MCP Server: https://github.com/github/github-mcp-server
- Pendientes de verificar: cuotas del plan gratuito de Context7, plugin exacto que contiene `skill-creator`, guía de instalación remota de GitHub MCP en Claude Code (https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-claude.md, no consultada).
