"""Regenera recursos/web/comun/tokens.css desde core/tema.py.

El .exe ya no lo hace al arrancar (escribir ahi creaba una carpeta senuelo
que rompia las pantallas web, bug de la 1.1.0), asi que el archivo tiene
que quedar actualizado ANTES de empaquetar. Lo corren build.bat y el
workflow de release; tambien sirve a mano despues de tocar la paleta:

    python build/generar_tokens_css.py

No necesita Qt: core/tema.py es Python puro.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from spamed.core import tema  # noqa: E402

DESTINO = RAIZ / "src" / "spamed" / "recursos" / "web" / "comun" / "tokens.css"


def main() -> int:
    contenido = tema.tokens_css()
    if not contenido.strip():
        print("::error::tema.tokens_css() devolvio vacio")
        return 1
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    anterior = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else None
    DESTINO.write_text(contenido, encoding="utf-8")
    estado = "sin cambios" if anterior == contenido else "ACTUALIZADO"
    print("tokens.css %s (%d bytes) -> %s"
          % (estado, len(contenido), DESTINO.relative_to(RAIZ)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
