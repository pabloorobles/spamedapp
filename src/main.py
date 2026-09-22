"""Punto de entrada para el ejecutable empaquetado.

PyInstaller corre el script de arranque como '__main__' sin paquete padre, asi
que el archivo de entrada no puede usar imports relativos. Este modulo usa
import absoluto y es el que apunta el .spec.
"""
from __future__ import annotations

import sys

from spamed.app import main

if __name__ == "__main__":
    sys.exit(main())
