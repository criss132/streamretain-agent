"""Renderiza los diagramas Mermaid de docs/diagramas/*.mmd a PNG con Chrome o Edge headless.

Requiere conexión a internet (carga mermaid desde cdn.jsdelivr.net) y Chrome o Edge instalado.
Uso: python scripts/render_diagramas.py
"""

from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

RAIZ = Path(__file__).resolve().parents[1]
DIR = RAIZ / "docs" / "diagramas"
NAVEGADORES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "msedge",
]
PLANTILLA = """<!doctype html><html><head><meta charset="utf-8">
<style>body{{margin:0;padding:24px;background:#fff;font-family:Arial, sans-serif}}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script></head>
<body><pre class="mermaid">{codigo}</pre>
<script>mermaid.initialize({{startOnLoad:true, theme:"default", securityLevel:"loose",
sequence:{{mirrorActors:false, useMaxWidth:false}}, flowchart:{{useMaxWidth:false}}}});</script>
</body></html>"""


def navegador() -> str:
    for n in NAVEGADORES:
        if Path(n).exists() or shutil.which(n):
            return n
    raise SystemExit("No se encontró Chrome ni Edge.")


def recortar(ruta: Path, margen: int = 20) -> None:
    im = Image.open(ruta).convert("RGB")
    fondo = Image.new("RGB", im.size, (255, 255, 255))
    caja = ImageChops.difference(im, fondo).getbbox()
    if caja:
        x0, y0, x1, y1 = caja
        im.crop((max(x0 - margen, 0), max(y0 - margen, 0),
                 min(x1 + margen, im.width), min(y1 + margen, im.height))).save(ruta)


def main() -> None:
    exe = navegador()
    for mmd in sorted(DIR.glob("*.mmd")):
        png = mmd.with_suffix(".png")
        with tempfile.TemporaryDirectory() as tmp:
            pagina = Path(tmp) / "d.html"
            pagina.write_text(PLANTILLA.format(codigo=html.escape(mmd.read_text(encoding="utf-8"))),
                              encoding="utf-8")
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--force-device-scale-factor=2", "--window-size=3000,2600",
                            "--virtual-time-budget=15000", f"--screenshot={png}", pagina.as_uri()],
                           check=True, capture_output=True, timeout=120)
        recortar(png)
        print(f"{mmd.name} -> {png.name} {Image.open(png).size}")


if __name__ == "__main__":
    main()
