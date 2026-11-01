"""Configuracion global y rutas de la aplicacion."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Spamed Travel"
APP_ID = "SpamedTravel"
APP_VERSION = "1.1.1"
ORG_NAME = "Spamed Travel"

# Porcentaje minimo de cobro para considerar una reserva "senada".
PCT_SENA_DEFAULT = 20.0

MONEDAS = ("PESOS", "DOLAR")

ESTADOS = (
    "Cotizado",
    "Reservado",
    "Confirmado",
    "Emitido",
    "En Viaje",
    "Finalizado",
    "Vencido",
    "Cancelado",
)

TIPOS_MOVIMIENTO = ("INGRESO", "EGRESO")


def es_congelado() -> bool:
    """True si corre empaquetado con PyInstaller."""
    return getattr(sys, "frozen", False)


def dir_datos() -> Path:
    """Carpeta de datos del usuario (%LOCALAPPDATA% en Windows)."""
    base = os.environ.get("SPAMED_DATA_DIR")
    if base:
        p = Path(base)
    elif os.name == "nt":
        p = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_ID
    else:
        p = Path.home() / f".{APP_ID.lower()}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ruta_db() -> Path:
    return dir_datos() / "spamed.db"


def dir_backups() -> Path:
    p = dir_datos() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def dir_descargas() -> Path:
    """Carpeta Descargas del usuario, con subcarpeta propia de la app.

    Se pregunta al registro de Windows en vez de armar la ruta a mano, porque
    la carpeta se puede haber movido a otro disco. Si algo de eso falla se
    cae a %USERPROFILE%\\Downloads y, en ultima instancia, a la carpeta de
    datos de la app (que siempre existe).
    """
    if os.name == "nt":
        try:
            import winreg

            clave = (r"Software\Microsoft\Windows\CurrentVersion"
                     r"\Explorer\Shell Folders")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
                # GUID de la carpeta Descargas (KNOWNFOLDERID FOLDERID_Downloads)
                ruta, _ = winreg.QueryValueEx(
                    k, "{374DE290-123F-4565-9164-39C4925E467B}")
            base = Path(os.path.expandvars(ruta))
            if base.is_dir():
                return base / APP_NAME
        except Exception:  # noqa: BLE001  - registro ausente o valor raro
            pass
    candidata = Path.home() / "Downloads"
    if candidata.is_dir():
        return candidata / APP_NAME
    return dir_datos() / "exportaciones"


def dir_exports() -> Path:
    """Donde caen los PDFs y las exportaciones a Excel/CSV.

    Por defecto la carpeta Descargas; el usuario la puede cambiar desde
    Configuracion general (parametro 'carpeta_exportaciones'). El parametro se
    lee con import diferido: 'db' importa a 'config', asi que importarlo
    arriba seria circular. Sin base disponible (tests, arranque temprano) se
    usa el default sin fallar.
    """
    destino: Path | None = None
    try:
        from . import db

        valor = db.parametro("carpeta_exportaciones", "").strip()
        if valor:
            destino = Path(valor)
    except Exception:  # noqa: BLE001  - sin base todavia, o parametro invalido
        destino = None

    if destino is None:
        destino = dir_descargas()
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError:
        # La carpeta configurada ya no existe (pendrive, red caida): se cae a
        # la de datos antes que romperle la exportacion al usuario.
        destino = dir_datos() / "exportaciones"
        destino.mkdir(parents=True, exist_ok=True)
    return destino


def dirs_recursos() -> tuple[Path, ...]:
    """Carpetas donde buscar un recurso estatico, en orden de prioridad.

    Congelado devuelve SOLO la del bundle (sys._MEIPASS/recursos), y eso
    es deliberado. Antes se buscaba tambien al lado del paquete
    (<bundle>/spamed/recursos), como respaldo, y esa "red de seguridad"
    fue justamente el bug de la 1.1.0: `escribir_tokens_css()` creaba
    <bundle>/spamed/recursos/web/comun/ en el primer arranque, con
    tokens.css adentro y nada mas. A partir de ahi `buscar_recurso("web")`
    encontraba esa carpeta senuelo antes que la real y las diez pantallas
    HTML quedaban en ERR_FILE_NOT_FOUND, mientras los iconos seguian
    andando (esos no existian en el senuelo, asi que caian a la carpeta
    buena). Si el bundle no trae recursos/, la app esta rota: mejor que
    falle claro y no a medias.
    """
    if es_congelado():
        return (Path(sys._MEIPASS) / "recursos",)  # type: ignore[attr-defined]
    return (Path(__file__).resolve().parent.parent / "recursos",)


def dir_recursos() -> Path:
    """Carpeta de recursos estaticos (iconos, fuentes, web), congelado o no."""
    return dirs_recursos()[0]


def buscar_recurso(nombre: str) -> Path | None:
    """Ubica un archivo o carpeta dentro de los recursos. None si no esta.

    Vive aca y no en app.py para que se pueda probar sin importar Qt
    (tests/test_negocio.py lo cubre); `app.recurso()` es una envoltura.
    """
    for base in dirs_recursos():
        p = base / nombre
        if p.exists():
            return p
    return None
