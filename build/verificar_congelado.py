"""Verifica que la app congelada no escriba dentro de su propio bundle.

Guarda de regresion del bug de la 1.1.0: `app.escribir_tokens_css()` hacia
mkdir(parents=True) sobre <bundle>/spamed/recursos/web/comun/ en el primer
arranque. Esa carpeta recien creada le ganaba despues a la carpeta de
recursos real en la busqueda, y las diez pantallas HTML quedaban en
ERR_FILE_NOT_FOUND mientras el resto de la app andaba normal.

Corre en el workflow de release (ver .github/workflows/release.yml) y se
puede correr a mano:

    python build/verificar_congelado.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

# Importar spamed.app trae PySide6, que sin esto querria una pantalla real.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    bundle = Path(tempfile.mkdtemp()) / "bundle"
    (bundle / "recursos").mkdir(parents=True)

    # Simula el bundle de PyInstaller.
    sys.frozen = True            # type: ignore[attr-defined]
    sys._MEIPASS = str(bundle)   # type: ignore[attr-defined]

    from spamed import app
    from spamed.core import config

    fallos: list[str] = []

    if not config.es_congelado():
        fallos.append("es_congelado() deberia dar True con sys.frozen puesto")

    if config.dirs_recursos() != (bundle / "recursos",):
        fallos.append(
            "congelado tiene que buscar SOLO en %s, pero busca en %s"
            % (bundle / "recursos", config.dirs_recursos()))

    app.escribir_tokens_css()

    creados = sorted(
        str(p.relative_to(bundle))
        for p in bundle.rglob("*")
        if p.relative_to(bundle).parts[0] != "recursos"
    )
    if creados:
        fallos.append(
            "congelado escribio dentro del bundle: %s "
            "(esto es exactamente el bug de la 1.1.0)" % creados)

    if app.recurso("web") is not None:
        fallos.append(
            "recurso('web') deberia dar None en un bundle sin recursos/web, "
            "dio %s" % app.recurso("web"))

    if fallos:
        for f in fallos:
            print("FALLA: %s" % f)
            # En Actions esto pinta el paso de rojo con el mensaje.
            print("::error::%s" % f)
        return 1

    print("OK: congelado no escribe nada dentro del bundle y resuelve "
          "los recursos solo desde la carpeta empaquetada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
