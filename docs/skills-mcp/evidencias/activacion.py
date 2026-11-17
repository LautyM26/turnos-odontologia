"""Prueba de activación de skills (reemplazo Windows de skill-creator/run_eval.py).

Corre `claude -p` en la raíz del repo (donde están las skills reales en .claude/skills)
y registra qué skill invoca el modelo en sus primeros turnos. Uso:
    python activacion.py <repo> <casos.json> <salida.json>
"""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor


def correr(repo: str, caso: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    exe = os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules", "@anthropic-ai",
                       "claude-code", "bin", "claude.exe") if os.name == "nt" else "claude"
    cmd = [exe, "-p", caso["query"], "--output-format", "stream-json", "--verbose",
           "--max-turns", "2", "--permission-mode", "plan"]
    try:
        out = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, timeout=240,
                             text=True, encoding="utf-8", errors="replace").stdout
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
    skills = []
    for linea in out.splitlines():
        try:
            ev = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if ev.get("type") != "assistant":
            continue
        for bloque in ev.get("message", {}).get("content", []):
            if bloque.get("type") == "tool_use" and bloque.get("name") == "Skill":
                skills.append(bloque.get("input", {}).get("skill", ""))
            if bloque.get("type") == "tool_use" and bloque.get("name") == "Read":
                ruta = bloque.get("input", {}).get("file_path", "").replace("\\", "/")
                if "/skills/" in ruta and ruta.endswith("SKILL.md"):
                    skills.append(ruta.split("/skills/")[1].split("/")[0])
    activada = caso["skill"] in skills
    return {**caso, "skills_invocadas": skills, "activada": activada,
            "ok": activada == caso["debe_activar"]}


def main(repo: str, casos_path: str, salida: str) -> None:
    casos = json.load(open(casos_path, encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(lambda c: correr(repo, c), casos))
    json.dump(res, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    ok = sum(r["ok"] for r in res)
    for r in res:
        print(("OK  " if r["ok"] else "MAL ") + f"[{r['skill']} debe={r['debe_activar']} activó={r['activada']}] {r['query'][:70]} -> {r['skills_invocadas']}")
    print(f"\n{ok}/{len(res)} correctos")


if __name__ == "__main__":
    main(*sys.argv[1:4])
