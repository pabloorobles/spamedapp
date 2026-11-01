"""Arranque de la aplicacion."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from .core import config, db, tema


def recurso(nombre: str) -> Path | None:
    """Ubica un archivo de recursos, funcione o no empaquetado.

    La logica real vive en `config.buscar_recurso()` para poder probarla
    sin Qt. Esta envoltura queda porque la usa media UI.
    """
    return config.buscar_recurso(nombre)


def cargar_fuentes() -> None:
    """Registra Outfit e Instrument Sans si estan bundleadas.

    Los .ttf van en recursos/fuentes/. Si todavia no se bajaron, esta
    funcion no hace nada: el QSS de tema.py ya tiene Verdana/Arial como
    alternativa de sistema (la misma que habilita el propio Manual de
    Marca), asi que la app queda igual de usable sin ellos.
    """
    for nombre in ("fuentes/Outfit.ttf", "fuentes/InstrumentSans.ttf"):
        ruta = recurso(nombre)
        if ruta:
            QFontDatabase.addApplicationFont(str(ruta))


def _paleta_qt(paleta: dict[str, str]) -> QPalette:
    """Paleta Qt de respaldo por debajo del QSS.

    El QSS pinta el look de los widgets propios, pero hay piezas que Qt
    sigue resolviendo con QPalette sin pasar por ningun selector nuestro
    -- el contenedor nativo del popup de un QComboBox es el caso que
    motivo esto: sin paleta oscura de respaldo, ese contenedor sale
    blanco con la app entera en modo oscuro ("cajas blancas atras de los
    desplegables"), porque nunca hubo un QPalette oscuro debajo, solo QSS.
    """
    p = QPalette()
    texto_suave = QColor(paleta["texto_suave"])
    for rol, valor in (
        (QPalette.ColorRole.Window, paleta["fondo"]),
        (QPalette.ColorRole.WindowText, paleta["texto"]),
        (QPalette.ColorRole.Base, paleta["superficie"]),
        (QPalette.ColorRole.AlternateBase, paleta["alterna"]),
        (QPalette.ColorRole.Text, paleta["texto"]),
        # Igual a Base/superficie a proposito: es el color que Fusion usa
        # para el marco del popup de un QComboBox (el "cuadrado" detras
        # del desplegable). Si no coincide con el fondo de
        # QAbstractItemView de abajo, se ve como dos cajas superpuestas
        # de tonos distintos en vez de una sola.
        (QPalette.ColorRole.Button, paleta["superficie"]),
        (QPalette.ColorRole.ButtonText, paleta["texto"]),
        (QPalette.ColorRole.ToolTipBase, paleta["superficie_2"]),
        (QPalette.ColorRole.ToolTipText, paleta["texto"]),
        (QPalette.ColorRole.PlaceholderText, paleta["texto_suave"]),
        (QPalette.ColorRole.Highlight, paleta["seleccion"]),
        (QPalette.ColorRole.HighlightedText, paleta["texto"]),
    ):
        p.setColor(rol, QColor(valor))
    for rol in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, rol, texto_suave)
    return p


def aplicar_tema(app: QApplication, nombre: str) -> None:
    """Pinta la aplicacion entera con el tema pedido."""
    from .ui import comunes
    comunes.set_tema(nombre)
    app.setStyleSheet(tema.qss(nombre))
    app.setPalette(_paleta_qt(tema.paleta(nombre)))


def escribir_tokens_css() -> None:
    """Regenera recursos/web/comun/tokens.css desde core/tema.py.

    SOLO en desarrollo. Congelado se sale en la primera linea, y no es
    una optimizacion: es el arreglo del bug de la 1.1.0. La version
    anterior asumia que el .exe empaquetado era de solo lectura y que
    escribir ahi "no pasaba nada". Falso por partida doble: la carpeta de
    instalacion esta bajo %LOCALAPPDATA% y es perfectamente escribible, y
    la linea no escribia nomas sino que hacia mkdir(parents=True), o sea
    CREABA <bundle>/spamed/recursos/web/comun/. Esa carpeta nueva, con un
    solo archivo adentro, le ganaba despues a la carpeta de recursos real
    en la busqueda, y las diez pantallas HTML quedaban en
    ERR_FILE_NOT_FOUND. Ver `config.dirs_recursos()`.

    En el .exe el tokens.css viene ya generado: lo regeneran build.bat y
    el workflow de release antes de empaquetar.
    """
    if config.es_congelado():
        return
    try:
        destino = config.dir_recursos() / "web" / "comun"
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "tokens.css").write_text(tema.tokens_css(), encoding="utf-8")
    except OSError:
        pass


def _preparar_web() -> bool:
    """Registra el esquema spamed:// si PySide6-Addons esta instalado.

    Tiene que llamarse ANTES de crear la QApplication (requisito de
    QtWebEngine). Si el paquete todavia no esta instalado -no es
    obligatorio hasta que la Etapa 1 de MIGRACION_WEB.md reemplace la
    primera pantalla-, la app arranca igual, sin las pantallas web.
    Devuelve True si quedo registrado (y hay que instalar el manejador
    despues de crear la QApplication).
    """
    try:
        from .ui import web as web_ui
    except ImportError:
        return False
    web_ui.registrar_esquema()
    return True


def registrar_error(texto: str) -> None:
    """Deja el error en errores.log, al lado de la base de datos.

    Sin esto el traceback solo vive en el cartel que ve el usuario y se
    pierde al cerrarlo, que es justo cuando hace falta para diagnosticar.
    El archivo se trunca al pasar de 1 MB para que no crezca sin control.
    """
    try:
        destino = config.dir_datos() / "errores.log"
        if destino.exists() and destino.stat().st_size > 1_000_000:
            viejo = destino.read_text(encoding="utf-8", errors="replace")
            destino.write_text(viejo[-200_000:], encoding="utf-8")
        marca = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with open(destino, "a", encoding="utf-8") as fh:
            fh.write(f"\n{'=' * 70}\n{marca}  v{config.APP_VERSION}\n{texto}")
    except Exception:  # noqa: BLE001  - registrar no puede romper la app
        pass


def _excepthook(tipo, valor, tb) -> None:
    texto = "".join(traceback.format_exception(tipo, valor, tb))
    sys.stderr.write(texto)
    registrar_error(texto)
    try:
        QMessageBox.critical(
            None, "Error inesperado",
            f"Ocurrió un error inesperado:\n\n{valor}\n\n"
            "Los datos ya guardados no se pierden.\n"
            "El detalle quedó guardado: podés verlo con Ctrl+Shift+D.",
        )
    except Exception:
        pass


def main() -> int:
    # Tiene que ir antes de crear la QApplication: es un requisito de
    # QtWebEngine para registrar un esquema de URL propio (spamed://).
    hay_web = _preparar_web()

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.ORG_NAME)
    app.setStyle("Fusion")
    cargar_fuentes()
    app.setFont(QFont("Instrument Sans", 9))
    escribir_tokens_css()
    if hay_web:
        from .ui import web as web_ui
        web_ui.instalar_manejador()

    ico = recurso("spamed.ico")
    if ico:
        app.setWindowIcon(QIcon(str(ico)))

    sys.excepthook = _excepthook

    db.conectar()
    aplicar_tema(app, db.parametro("tema", "claro"))

    from .ui.principal import VentanaPrincipal
    v = VentanaPrincipal()
    v.show()
    return app.exec()
