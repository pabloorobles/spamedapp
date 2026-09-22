"""Pagina de Herramientas: todo lo que antes estaba en la barra de menu,
ahora como botones visibles con su explicacion al lado.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from ..core import config
from .comunes import boton, tema_actual
from .navegacion import Cabecera


class FilaAccion(QFrame):
    """Un titulo, una explicacion y el boton que lo ejecuta."""

    def __init__(self, titulo: str, detalle: str, texto_boton: str,
                 slot: Callable[[], None], primario: bool = False,
                 acento: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("panel")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)

        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(titulo)
        t.setStyleSheet("font-weight: 700; font-size: 10.5pt;")
        d = QLabel(detalle)
        d.setObjectName("tarjetaDetalle")
        d.setWordWrap(True)
        col.addWidget(t)
        col.addWidget(d)
        lay.addLayout(col, 1)

        self.boton = boton(texto_boton, slot, primario=primario,
                           acento=acento, ancho=170)
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.boton, 0, Qt.AlignmentFlag.AlignVCenter)


class VistaHerramientas(QWidget):
    """Datos, copias de seguridad y preferencias."""

    def __init__(self, ventana, parent: QWidget | None = None):
        super().__init__(parent)
        self.ventana = ventana

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)

        self.cabecera = Cabecera(
            "Herramientas",
            "Importar datos, copias de seguridad y preferencias",
        )
        raiz.addWidget(self.cabecera)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setObjectName("lienzo")
        cont = QWidget()
        cont.setObjectName("lienzo")
        scroll.setWidget(cont)
        raiz.addWidget(scroll)

        lay = QVBoxLayout(cont)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)

        def titulo(txt: str) -> None:
            e = QLabel(txt.upper())
            e.setObjectName("tarjetaTitulo")
            lay.addSpacing(8)
            lay.addWidget(e)

        titulo("Datos")
        lay.addWidget(FilaAccion(
            "Descargar la plantilla de Excel",
            "El archivo modelo para la carga inicial: una hoja por tipo de "
            "dato, con los títulos de columna que espera la aplicación, un "
            "ejemplo en cada una y una hoja de instrucciones. Completalo y "
            "después importalo con el botón de abajo.",
            "Descargar plantilla", ventana.descargar_plantilla, acento=True))
        lay.addWidget(FilaAccion(
            "Importar desde Excel",
            "Trae clientes, vendedores, operadores, reservas y caja desde el "
            "libro BaseDatosSpamed. Se puede reemplazar todo o sumar sobre lo "
            "que ya está cargado.",
            "Importar Excel…", ventana.importar_excel, primario=True))

        titulo("Copias de seguridad")
        lay.addWidget(FilaAccion(
            "Hacer una copia ahora",
            "Guarda el estado actual de la base. Además se hace una copia "
            "automática cada vez que cerrás el programa.",
            "Crear copia", ventana.backup))
        lay.addWidget(FilaAccion(
            "Restaurar una copia",
            "Vuelve a un estado anterior. Antes de reemplazar nada, guarda "
            "una copia de lo que hay ahora.",
            "Restaurar…", ventana.restaurar))
        lay.addWidget(FilaAccion(
            "Abrir la carpeta de datos",
            f"Ahí viven la base y las copias: {config.dir_datos()}",
            "Abrir carpeta", ventana.abrir_carpeta))

        titulo("Preferencias")
        self.fila_tema = FilaAccion(
            "Aspecto de la aplicación",
            "Alterna entre el tema claro y el oscuro.",
            "Cambiar tema", ventana.alternar_tema)
        lay.addWidget(self.fila_tema)
        lay.addWidget(FilaAccion(
            "Configuración general",
            "Nombre de la agencia, datos para los documentos, porcentaje "
            "mínimo de seña y prefijo de los files.",
            "Configurar…", ventana.configurar))

        titulo("Diagnóstico")
        lay.addWidget(FilaAccion(
            "Ver información técnica",
            "Versión, ubicación de la base, cantidad de registros y los "
            "últimos errores registrados. Sirve para pasarle el detalle a "
            "quien te da soporte. También se abre con Ctrl+Shift+D.",
            "Ver diagnóstico", ventana.diagnostico))

        titulo("Acerca de")
        lay.addWidget(FilaAccion(
            f"{config.APP_NAME} {config.APP_VERSION}",
            "Gestión de reservas, caja, comisiones y documentos.",
            "Ver información", ventana.acerca_de))

        lay.addStretch(1)

    def refrescar(self) -> None:
        otro = "claro" if tema_actual() == "oscuro" else "oscuro"
        self.fila_tema.boton.setText(f"Cambiar a {otro}")
