"""Verifica los criterios objetivos de una skill dominio-<área>.

Uso (desde la raíz del repo):
    python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-caja RN-CA
    python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-agenda RN-AG RN-TU

Sale con código 1 si algún criterio falla. El criterio 4 (palabras de la description)
y el 6 (sin datos reales) requieren lectura humana: el script solo muestra la description.
"""

import re
import sys
from pathlib import Path


def main(nombre: str, prefijos: list[str]) -> int:
    skill = Path(".claude/skills") / nombre / "SKILL.md"
    texto = skill.read_text(encoding="utf-8")
    kb = Path("knowledge-base/05_reglas_de_negocio.md").read_text(encoding="utf-8")
    fallas: list[str] = []

    # 1. Cada RN del dominio tiene fila en la matriz (sección 5).
    matriz = texto.split("## 5.", 1)[1].split("## 6.", 1)[0]
    for p in prefijos:
        rn_kb = sorted(set(re.findall(rf"^- \*\*({p}-\d+)", kb, re.M)))
        rn_matriz = sorted(set(re.findall(rf"^\| ({p}-\d+)", matriz, re.M)))
        faltan = sorted(set(rn_kb) - set(rn_matriz))
        print(f"[1] {p}: {len(rn_kb)} en KB, {len(rn_matriz)} en matriz")
        if faltan:
            fallas.append(f"1: faltan en la matriz {faltan}")

    # 2. Nada contradice DD-10 fuera de "Conflictos detectados".
    sin_conflictos = re.sub(r"### Conflictos detectados.*?(?=\n## )", "", texto, flags=re.S)
    prohibidas = re.findall(r"QR prohibido|API oficial|plantilla aprobada", sin_conflictos, re.I)
    print(f"[2] frases contrarias a DD vigentes fuera de Conflictos: {len(prohibidas)}")
    if prohibidas:
        fallas.append(f"2: {prohibidas}")

    # 3. Toda ruta citada existe.
    rutas = sorted(set(re.findall(r"`((?:backend|frontend|openspec|knowledge-base|docs|\.atl|\.claude)/[^`\s]+)`", texto)))
    faltantes = [r for r in rutas if not Path(r).exists()]
    print(f"[3] rutas citadas: {len(rutas)}, inexistentes: {faltantes or 0}")
    if faltantes:
        fallas.append(f"3: {faltantes}")

    # 4. Description (revisión humana).
    desc = re.search(r"^description: (.+)$", texto, re.M)
    print(f"[4] description: {desc.group(1) if desc else 'FALTA'}")
    if not desc:
        fallas.append("4: sin description")

    # 5. Registro en índices + AGENTS.md == CLAUDE.md + copias idénticas.
    for indice in ("AGENTS.md", "CLAUDE.md", ".atl/skill-registry.md"):
        if nombre not in Path(indice).read_text(encoding="utf-8"):
            fallas.append(f"5: {nombre} no figura en {indice}")
    if Path("AGENTS.md").read_bytes() != Path("CLAUDE.md").read_bytes():
        fallas.append("5: AGENTS.md y CLAUDE.md difieren")
    for copia in (".github/skills", ".opencode/skills"):
        otra = Path(copia) / nombre / "SKILL.md"
        if not otra.exists() or otra.read_bytes() != skill.read_bytes():
            fallas.append(f"5: copia distinta o ausente en {otra}")
    print("[5] índices y copias revisados")

    # 6. Datos reales (revisión humana): se listan DNI/teléfonos con forma real.
    sospechosos = re.findall(r"\b\d{7,8}\b|\+?54\s?9?\s?\d{2,4}[\s-]?\d{6,8}", texto)
    print(f"[6] números con forma de DNI/teléfono: {sospechosos or 'ninguno'} (revisar a mano)")

    print("\nRESULTADO:", "OK" if not fallas else "FALLA")
    for f in fallas:
        print("  -", f)
    return 1 if fallas else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2:]))
