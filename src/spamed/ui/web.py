"""Plomeria para las pantallas migradas a HTML/CSS/JS (ver MIGRACION_WEB.md).

Este modulo es el unico lugar del proyecto que depende de QtWebEngine
(PySide6-Addons). Se compone de tres piezas:

  1. ``registrar_esquema()`` -- registra el esquema de URL propio
     ``spamed://``. Tiene que llamarse ANTES de crear la QApplication (es
     un requisito documentado de QtWebEngine, no una eleccion de diseno);
     por eso ``app.py::main()`` la llama como primer paso, antes de
     ``QApplication(sys.argv)``.
  2. ``instalar_manejador()`` -- registra el manejador que sirve los
     archivos de ``recursos/web/`` para ese esquema. Se llama DESPUES de
     crear la QApplication (``QWebEngineProfile`` necesita que ya exista).
  3. ``VistaWeb`` -- el widget reutilizable que cada pantalla migrada usa:
     un ``QWebEngineView`` mas un ``QWebChannel`` para hablar con un
     "puente" de Python (un ``QObject`` con metodos ``@Slot``).

ADVERTENCIA para quien retome esto: este entorno de desarrollo no tiene
``PySide6-Addons`` instalado ni acceso a internet para instalarlo, asi que
nada de este archivo se pudo ejecutar ni probar aca. Es el unico codigo de
todo el proyecto en esa situacion -- verificarlo en una maquina con
Qt WebEngine real antes de dar por buena cualquier pantalla que dependa
de esto.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEngineProfile, QWebEngineUrlRequestJob, QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

ESQUEMA = b"spamed"

_MIME = {
    ".html": b"text/html; charset=utf-8",
    ".css":  b"text/css; charset=utf-8",
    ".js":   b"text/javascript; charset=utf-8",
    ".json": b"application/json; charset=utf-8",
    ".svg":  b"image/svg+xml",
    ".png":  b"image/png",
}


def registrar_esquema() -> None:
    """Registra el esquema spamed://. Llamar ANTES de crear la QApplication."""
    esquema = QWebEngineUrlScheme(ESQUEMA)
    esquema.setSyntax(QWebEngineUrlScheme.Syntax.Path)
    esquema.setFlags(
        QWebEngineUrlScheme.Flag.LocalScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
    )
    QWebEngineUrlScheme.registerScheme(esquema)


class _ManejadorEsquema(QWebEngineUrlSchemeHandler):
    """Sirve los archivos de recursos/web/ (o el .js de QWebChannel) para
    spamed://<lo-que-sea>."""

    def __init__(self, raiz: Path, parent: QObject | None = None):
        super().__init__(parent)
        self._raiz = raiz.resolve()

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:  # noqa: N802
        ruta = job.requestUrl().path().lstrip("/")

        # qwebchannel.js no se copia a mano: viene empaquetado como
        # recurso interno de Qt y se sirve tal cual desde ahi, para no
        # depender de encontrar el archivo fisico en el disco del usuario.
        if ruta == "comun/qwebchannel.js":
            self._responder_recurso_qt(job, ":/qtwebchannel/qwebchannel.js")
            return

        archivo = (self._raiz / ruta).resolve()
        # Nunca servir nada fuera de recursos/web/ (evita que una ruta con
        # ".." se escape de la carpeta).
        if self._raiz not in archivo.parents and archivo != self._raiz:
            job.fail(QWebEngineUrlRequestJob.Error.UrlInvalid)
            return
        if not archivo.is_file():
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return

        tipo = _MIME.get(archivo.suffix, b"application/octet-stream")
        buffer = QBuffer(job)
        buffer.setData(archivo.read_bytes())
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(tipo, buffer)

    def _responder_recurso_qt(self, job: QWebEngineUrlRequestJob,
                              ruta_qt: str) -> None:
        from PySide6.QtCore import QFile
        recurso = QFile(ruta_qt)
        if not recurso.open(QIODevice.OpenModeFlag.ReadOnly):
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return
        datos = bytes(recurso.readAll())
        recurso.close()
        buffer = QBuffer(job)
        buffer.setData(QByteArray(datos))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(b"text/javascript; charset=utf-8", buffer)


_manejador: _ManejadorEsquema | None = None


def instalar_manejador() -> None:
    """Registra el manejador de spamed:// en el perfil por defecto.

    Llamar DESPUES de crear la QApplication, una sola vez, antes de que
    cualquier VistaWeb intente cargar una URL spamed://.
    """
    global _manejador
    from ..app import recurso
    raiz = recurso("web")
    if raiz is None:
        raise FileNotFoundError(
            "No se encontro la carpeta recursos/web/. "
            "?Se creo recursos/web/comun/tokens.css?"
        )
    _manejador = _ManejadorEsquema(raiz)
    QWebEngineProfile.defaultProfile().installUrlSchemeHandler(
        ESQUEMA, _manejador)


class VistaWeb(QWidget):
    """Envoltorio reutilizable: un QWebEngineView + QWebChannel, listo para
    que cada pantalla migrada le pase su propio "puente" (un QObject con
    metodos @Slot que expone lo que hace falta de core/repo.py)."""

    def __init__(self, ruta: str, puente: QObject | None = None,
                 parent: QWidget | None = None, tema: str = "claro"):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        lay.addWidget(self.view)

        self.canal = QWebChannel(self.view.page())
        self.puente = puente
        if puente is not None:
            self.canal.registerObject("puente", puente)
        self.view.page().setWebChannel(self.canal)

        # El tema de la pagina lo maneja la app (parametro "tema", el
        # mismo que ya usa el QSS de Qt), no el prefers-color-scheme del
        # sistema operativo -- por eso se empuja explicitamente ni bien
        # carga, y de nuevo cada vez que Herramientas -> Cambiar tema lo
        # cambia en caliente (ver VentanaPrincipal.cambiar_tema).
        self._tema = tema
        self.view.loadFinished.connect(
            lambda ok: self.aplicar_tema(self._tema) if ok else None)

        self.view.load(QUrl(f"spamed://app/{ruta.lstrip('/')}"))

    def aplicar_tema(self, nombre: str) -> None:
        self._tema = nombre
        valor = "dark" if str(nombre).lower() == "oscuro" else "light"
        self.js(f'document.documentElement.setAttribute("data-theme", "{valor}");')

    def recargar(self) -> None:
        self.view.reload()

    def refrescar(self) -> None:
        """Vuelve a pedir los datos sin recargar la pagina entera (no
        perder los filtros que haya elegido el usuario). Cada pantalla
        web expone su propia funcion como window.refrescar -- mismo
        criterio que .refrescar() en las pantallas de Qt, para que
        VentanaPrincipal.ir_a()/refrescar_todo() las traten igual."""
        self.js("if (window.refrescar) { window.refrescar(); }")

    def js(self, codigo: str, callback: Any = None) -> None:
        """Ejecuta JS en la pagina cargada. Atajo para pruebas de humo y
        para forzar un refresco puntual desde Python si hiciera falta."""
        if callback is not None:
            self.view.page().runJavaScript(codigo, callback)
        else:
            self.view.page().runJavaScript(codigo)


class PuenteHumo(QObject):
    """Puente minimo de prueba para la Etapa 0 (ver MIGRACION_WEB.md):
    solo confirma que QWebChannel funciona de punta a punta. Se borra en
    cuanto la Etapa 1 tenga su propio puente real (PuenteInicio)."""

    @Slot(str, result=str)
    def saludar(self, nombre: str) -> str:
        return f"Hola {nombre or 'Pablo'}, el canal Python <-> JS funciona."
