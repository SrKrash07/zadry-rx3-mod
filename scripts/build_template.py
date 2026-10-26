# SPDX-License-Identifier: MPL-2.0
"""Genera la PLANTILLA del mod de Zadry: la imagen ISO del runtime SIN CIFRAR, con huecos de tamaño fijo para el logo.

El navegador de cada cliente coloca su logo en esos huecos y cifra la imagen con su propia clave (la que saca del paquete que Pioneer publica),
así que la clave nunca pasa por nuestro servidor. Esta plantilla no contiene ninguna clave ni nada de Pioneer: son nuestros scripts y el núcleo
compilado a partir de nuestro código.

    python scripts/build_template.py --out C:\\ruta\\salida [--modules stems logging samples]

Escribe, por cada lienzo (classic y full): template-<lienzo>.iso y, en template.json, dónde está cada archivo del logo dentro de la imagen.
No hace falta la clave (se usa una falsa de 32 bytes solo para cumplir la firma de build_runtime; la imagen guardada es la que va SIN cifrar).
"""

import argparse
import hashlib
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.runtime import build as B  # noqa: E402
from app.services import logo as logo_service  # noqa: E402
from app.logo import container  # noqa: E402

DEFAULT_MODULES = ["stems", "logging", "samples"]
SECTOR = 512


def placeholder(tag: bytes, size: int) -> bytes:
    """Contenido de relleno: cabecera 'RX3LOGO1' + bytes pseudoaleatorios deterministas (ninguna ventana de 64 bytes se repite, así el hueco se localiza sin dudas)."""
    out = bytearray(b"RX3LOGO1" + bytes(8))
    counter = 0
    while len(out) < size:
        out += hashlib.sha256(tag + counter.to_bytes(8, "little")).digest()
        counter += 1
    return bytes(out[:size])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--firmware", default="1.19")
    parser.add_argument("--modules", nargs="+", default=DEFAULT_MODULES)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    base_modules = list(dict.fromkeys(args.modules))
    original_loader = B._load_firmware_module
    captured: dict[str, bytes] = {}

    class Wrapper:
        """Igual que el módulo de firmware, pero guarda la imagen SIN cifrar en lugar de depender de la clave."""

        def __init__(self, module):
            self._m = module

        def __getattr__(self, name):
            return getattr(self._m, name)

        def load_key(self, path):                      # no hace falta una clave real
            return bytes(32)

        def write_autoexec(self, source, output, key_path):
            plain = self._m.build_autoexec_iso(source)
            if len(plain) % SECTOR:
                plain += b"\0" * (SECTOR - len(plain) % SECTOR)
            captured["plain"] = plain
            pathlib.Path(output).write_bytes(self._m.crypt(plain, bytes(32), False))
            return len(plain)

        def read_autoexec(self, output, key_path):
            return captured["plain"]

    B._load_firmware_module = lambda root: Wrapper(original_loader(root))
    fake_key = args.out / ".fake.key"
    fake_key.write_bytes(bytes(32))

    manifest = {"version": args.version, "firmware": args.firmware, "modules": base_modules, "sector": SECTOR, "canvases": {}}
    try:
        # Las variantes con tema claro (classic-white, full-white, white) se retiraron del producto el 2026-10-26 (el resultado en la mesa no era bueno). El módulo theme-white sigue en el árbol.
        for canvas, geometry, white in (("base", None, False), ("classic", container.CLASSIC, False), ("full", container.FULL, False)):
            modules = [*base_modules, *(["logo"] if geometry else []), *(["theme-white"] if white else [])]
            supplied = None
            if geometry:
                size = 16 + geometry.canvas_width * geometry.canvas_height * 2
                dark = placeholder(b"<<ZADRY-LOGO-DARK-SLOT>>", size)
                light = placeholder(b"<<ZADRY-LOGO-LIGHT-SLOT>>", size)
                supplied = {logo_service.MODULE_ID: {logo_service.DARK_NAME: dark, logo_service.LIGHT_NAME: light}}
            with tempfile.TemporaryDirectory(prefix="zadry-template-") as tmp:
                B.build_runtime(args.firmware, modules, fake_key, pathlib.Path(tmp), supplied_files=supplied)
            plain = captured["plain"]
            name = f"template-{canvas}.iso"
            (args.out / name).write_bytes(plain)
            entry = {"file": name, "bytes": len(plain), "modules": modules, "sha256": hashlib.sha256(plain).hexdigest()}
            if geometry:
                offsets = {}
                for key, content in (("dark", dark), ("light", light)):
                    probe = content[16:16 + 64]
                    first = plain.find(probe)
                    if first < 0 or plain.find(probe, first + 1) >= 0:
                        raise SystemExit(f"no encuentro el hueco del logo {key} ({canvas}) una sola vez en la imagen")
                    start = first - 16
                    if plain[start:start + size] != content:
                        raise SystemExit(f"el archivo del logo {key} ({canvas}) no está contiguo en la imagen")
                    offsets[key] = start
                entry.update({"logoBytes": size, "canvas": [geometry.canvas_width, geometry.canvas_height], "darkOffset": offsets["dark"], "lightOffset": offsets["light"]})
            manifest["canvases"][canvas] = entry
            print(f"{canvas}: {len(plain):,} bytes", entry.get("darkOffset", ""), entry.get("lightOffset", ""))
    finally:
        B._load_firmware_module = original_loader
        fake_key.unlink(missing_ok=True)
    (args.out / "template.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("template.json escrito")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
