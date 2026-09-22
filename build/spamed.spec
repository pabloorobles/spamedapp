# -*- mode: python ; coding: utf-8 -*-
"""Receta de PyInstaller para Spamed Travel.

Se invoca desde `build\\build.bat` o desde el workflow de GitHub Actions:

    pyinstaller --noconfirm --clean build/spamed.spec

Genera `dist\\SpamedTravel\\SpamedTravel.exe` (modo carpeta, no onefile: el
arranque es mucho mas rapido y Chromium de QtWebEngine no tiene que
descomprimirse en cada ejecucion).

Tres cosas de este archivo NO son de estilo, son correcciones a errores que
ya mordieron una vez (ver CLAUDE.md, seccion "Bugs ya resueltos"):

  1. `schema.sql` va SOLO a `recursos/`. Copiarlo tambien a `spamed/core/`
     materializa una carpeta `spamed` real dentro del bundle que le compite
     al paquete empaquetado y rompe los imports en el .exe.
  2. Los hiddenimports salen de `collect_submodules("spamed")`, no de una
     lista a mano: enumerarlos era fragil y se desactualizaba.
  3. QtWebEngine NO va en `excludes`. Desde la migracion a HTML/CSS/JS
     (MIGRACION_WEB.md) diez de las once pantallas lo necesitan.
"""
import sys
from pathlib import Path

RAIZ = Path(SPECPATH).resolve().parent
SRC = RAIZ / "src"
PAQUETE = SRC / "spamed"
RECURSOS = PAQUETE / "recursos"

# `collect_submodules` importa el paquete para recorrerlo: sin esto no lo
# encuentra, porque el .spec se ejecuta desde la raiz del proyecto.
sys.path.insert(0, str(SRC))

from PyInstaller.utils.hooks import collect_submodules  # noqa: E402

# schema.sql vive dentro del paquete pero se lee como recurso (db._sql_esquema
# lo busca en config.dir_recursos()). Ver la nota 1 de arriba.
datas = [(str(PAQUETE / "core" / "schema.sql"), "recursos")]

a = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("spamed"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Solo paquetes que el proyecto no usa en ningun lado. Deliberadamente
    # NO se excluye ningun modulo de Qt: QtWebEngine arrastra QtQml, QtQuick,
    # QtNetwork, QtPositioning y QtOpenGL, y recortar de a uno a ciegas es la
    # forma conocida de romper el render de las pantallas web.
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "pytest", "pydoc"],
    noarchive=False,
    optimize=0,
)

# Todo el arbol de recursos (logos, .ico, iconos SVG, fuentes .ttf y las
# pantallas HTML/CSS/JS de recursos/web/) con la misma estructura interna que
# en desarrollo, para que `config.dir_recursos()` resuelva igual congelado.
a.datas += Tree(str(RECURSOS), prefix="recursos",
                excludes=["*.pyc", "__pycache__"])

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SpamedTravel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(RECURSOS / "spamed.ico"),
    version=str(RAIZ / "build" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SpamedTravel",
)
