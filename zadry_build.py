# SPDX-License-Identifier: MPL-2.0
"""Construye el mod de Zadry para la XDJ-RX3 con una sola orden: elige los módulos y, si quieres, mete tu logo dentro.

Ejemplos (desde la carpeta rx3-mod, con LLVM en el PATH):
    python zadry_build.py --list
    python zadry_build.py --out C:\\ruta\\salida                       (stems + samples + registro)
    python zadry_build.py --out C:\\ruta\\salida --logo mi-logo.png     (además el logo en la pantalla principal)
    python zadry_build.py --out C:\\ruta\\salida --modules stems logging samples theme-white --logo mi-logo.png --canvas full

El logo va DENTRO del autoexec.bin (la mesa lo lee de la imagen del mod), por eso solo se cambia reconstruyendo el mod.
La clave se lee del archivo indicado (por defecto C:\\ruta\\aes256.key) y no se copia a ningún sitio.
"""

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.runtime.build import build_runtime, discover_patches  # noqa: E402
from app.services import logo as logo_service  # noqa: E402

DEFAULT_KEY = pathlib.Path(r"C:\ruta\aes256.key")
DEFAULT_MODULES = ["stems", "logging", "samples"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--firmware", default="1.19")
    parser.add_argument("--modules", nargs="+", default=None, help=f"módulos a incluir (por defecto: {' '.join(DEFAULT_MODULES)}); con --logo se añade 'logo' solo")
    parser.add_argument("--logo", type=pathlib.Path, help="imagen PNG con tu logo (mejor con fondo transparente)")
    parser.add_argument("--canvas", default="classic", choices=["classic", "full"], help="tamaño de la pantalla del logo")
    parser.add_argument("--no-invert-light", action="store_true", help="no invertir los grises del logo en el tema claro")
    parser.add_argument("--key", type=pathlib.Path, default=DEFAULT_KEY)
    parser.add_argument("--out", type=pathlib.Path, help="carpeta de salida (se crea si no existe)")
    parser.add_argument("--list", action="store_true", help="lista los módulos disponibles y sale")
    args = parser.parse_args()

    definitions = discover_patches(ROOT, args.firmware)
    if args.list:
        for patch in definitions:
            if patch.selectable:
                print(f"{patch.patch_id:20} {'por defecto' if patch.default else 'opcional':12} {patch.name}")
        return 0
    if not args.out:
        parser.error("falta --out <carpeta>")

    modules = list(args.modules or DEFAULT_MODULES)
    supplied = None
    if args.logo:
        if not args.logo.is_file():
            parser.error(f"no existe el logo: {args.logo}")
        if "logo" not in modules:
            modules.append("logo")
        supplied = {logo_service.MODULE_ID: logo_service.files(args.logo, args.canvas, invert_light=not args.no_invert_light)}
        print(f"Logo: {args.logo.name} ({args.canvas}), claro y oscuro generados")
    elif "logo" in modules:
        parser.error("el módulo 'logo' necesita --logo <imagen.png>")

    known = {patch.patch_id for patch in definitions}
    unknown = [m for m in modules if m not in known]
    if unknown:
        parser.error(f"módulos desconocidos: {', '.join(unknown)} (usa --list)")

    args.out.mkdir(parents=True, exist_ok=True)
    print("Módulos:", " ".join(modules))
    result = build_runtime(args.firmware, modules, args.key, args.out, root=ROOT, supplied_files=supplied, progress=print)
    print(f"{result.output}: {result.size:,} bytes")
    print(f"SHA-256: {result.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
