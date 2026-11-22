"""CI: ningún commit mezcla tests/ con app/ en el mismo proyecto, y en el taller
todo commit que toca tests/ lleva la línea "Rol: escritor-tests" (la que lee el hook Stop).

Los tests los escribe el rol escritor-tests en su propio commit; el código, el constructor
en otro. Si un commit toca los dos, alguien cambió el contrato y el código a la vez.

Uso: python3 .github/scripts/commits_separados.py <base>..<head>
"""

import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]  # consola de Windows


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def zonas(archivos: list[str]) -> dict[str, set[str]]:
    """{proyecto: {"tests", "app"}} para cada archivo dentro de tests/ o app/."""
    por_proyecto: dict[str, set[str]] = {}
    for ruta in archivos:
        partes = ruta.split("/")
        for i, parte in enumerate(partes[:-1]):
            if parte in ("tests", "app"):
                por_proyecto.setdefault("/".join(partes[:i]) or ".", set()).add(parte)
                break
    return por_proyecto


def main() -> int:
    rango = sys.argv[1]
    malos = []
    for sha in git("rev-list", "--no-merges", rango).split():
        archivos = git("diff-tree", "--no-commit-id", "--name-only", "-r", sha).split()
        mensaje = git("log", "-1", "--format=%B", sha)
        if any(a.startswith("taller/tests/") for a in archivos) and "Rol: escritor-tests" not in mensaje:
            titulo = mensaje.splitlines()[0] if mensaje.strip() else sha[:7]
            malos.append(f"  {sha[:7]} {titulo}  (toca taller/tests/ sin la línea 'Rol: escritor-tests')")
        for proyecto, tipos in zonas(archivos).items():
            if tipos == {"tests", "app"}:
                titulo = git("log", "-1", "--format=%s", sha).strip()
                malos.append(f"  {sha[:7]} {titulo}  ({proyecto}: tests/ y app/ en el mismo commit)")
    if malos:
        print("✗ Estos commits rompen la regla de los tests:")
        print("\n".join(malos))
        print("Separa los tests (rol escritor-tests) del código en commits distintos, y marca esos commits con 'Rol: escritor-tests'.")
        return 1
    print(f"✓ Ningún commit de {rango} mezcla tests/ con app/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
