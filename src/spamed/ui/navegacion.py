"""Navegacion lateral y cabecera de pagina.

Reemplaza a la barra de menu horizontal: todo se opera con botones visibles.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import (
    Property, QEasingCurve, QPropertyAnimation, QSize, Qt, Signal,
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)
# QIcon(archivo.svg) carga el plugin de QtSvg en tiempo de ejecucion sin
# importarlo explicitamente. PyInstaller solo empaqueta lo que ve importado
# de forma estatica: sin esta linea, los iconos de la barra lateral
# quedarian vacios en el .exe aunque funcionen perfecto en modo desarrollo.
from PySide6 import QtSvg  # noqa: F401

_TAMANO_ICONO = QSize(18, 18)


def _icono(nombre: str) -> QIcon:
    """Icono lineal de recursos/iconos/<nombre>.svg, o vacio si no existe."""
    if not nombre:
        return QIcon()
    from ..app import recurso
    ruta = recurso(f"iconos/{nombre}.svg")
    return QIcon(str(ruta)) if ruta else QIcon()


class BarraLateral(QFrame):
    """Navegacion vertical con secciones y botones excluyentes."""

    navegar = Signal(int)

    _ANCHO_EXPANDIDO = 216
    _ANCHO_COLAPSADO = 64

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("nav")
        self.setFixedWidth(self._ANCHO_EXPANDIDO)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(12, 14, 12, 16)
        self._lay.setSpacing(3)

        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self._indice = 0
        self._colapsado = False
        # (boton, texto sin colapsar) y las etiquetas de seccion, para
        # poder vaciar/restaurar el texto al plegar la barra.
        self._items: list[tuple[QPushButton, str]] = []
        self._secciones: list[QLabel] = []
        self._animacion: QPropertyAnimation | None = None

        # boton de plegar/desplegar -- siempre visible, incluso con la
        # barra colapsada al ancho minimo, para poder volver a abrirla.
        fila_alt = QHBoxLayout()
        fila_alt.setContentsMargins(2, 0, 2, 0)
        self.btn_colapsar = QPushButton("‹")
        self.btn_colapsar.setObjectName("navToggle")
        self.btn_colapsar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_colapsar.setToolTip("Ocultar/mostrar el menú")
        self.btn_colapsar.clicked.connect(self.alternar_colapso)
        fila_alt.addStretch(1)
        fila_alt.addWidget(self.btn_colapsar)
        self._lay.addLayout(fila_alt)

        # marca
        cab = QHBoxLayout()
        cab.setContentsMargins(6, 4, 6, 0)
        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cab.addWidget(self.lbl_logo)
        self._lay.addLayout(cab)
        self._lay.addSpacing(14)

    def set_logo(self, ruta: str | None) -> None:
        if ruta:
            self.lbl_logo.setPixmap(
                QPixmap(ruta).scaledToWidth(
                    168, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self.lbl_logo.setText("SpaMed Travel")
            self.lbl_logo.setObjectName("navMarca")

    def seccion(self, titulo: str) -> None:
        self._lay.addSpacing(12)
        et = QLabel(titulo.upper())
        et.setObjectName("navSeccion")
        self._secciones.append(et)
        self._lay.addWidget(et)

    def item(self, texto: str, icono: str = "") -> QPushButton:
        etiqueta = f"  {texto}"
        b = QPushButton(etiqueta)
        b.setObjectName("navItem")
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if icono:
            b.setIcon(_icono(icono))
            b.setIconSize(_TAMANO_ICONO)
        idx = self._indice
        self._indice += 1
        self.grupo.addButton(b, idx)
        b.clicked.connect(lambda _=False, i=idx: self.navegar.emit(i))
        self._lay.addWidget(b)
        self._items.append((b, etiqueta))
        return b

    def accion(self, texto: str, icono: str, slot: Callable[[], None]) -> QPushButton:
        """Boton que ejecuta algo en vez de navegar (no queda marcado)."""
        etiqueta = f"  {texto}"
        b = QPushButton(etiqueta)
        b.setObjectName("navItem")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if icono:
            b.setIcon(_icono(icono))
            b.setIconSize(_TAMANO_ICONO)
        b.clicked.connect(slot)
        self._lay.addWidget(b)
        self._items.append((b, etiqueta))
        return b

    def espacio(self) -> None:
        self._lay.addStretch(1)

    def seleccionar(self, indice: int) -> None:
        b = self.grupo.button(indice)
        if b:
            b.setChecked(True)

    # ------------------------------------------------------- colapsar
    # El texto de los botones se vacia (queda solo el icono) y el ancho
    # se anima con QPropertyAnimation sobre "ancho" -- ver la Property
    # mas abajo. El boton de plegar nunca se oculta, asi que siempre hay
    # forma de volver a abrir el menu aunque quede en su ancho minimo.
    def alternar_colapso(self) -> None:
        self._colapsado = not self._colapsado
        destino = (self._ANCHO_COLAPSADO if self._colapsado
                   else self._ANCHO_EXPANDIDO)

        self.lbl_logo.setVisible(not self._colapsado)
        for et in self._secciones:
            et.setVisible(not self._colapsado)
        for boton, etiqueta in self._items:
            boton.setText("" if self._colapsado else etiqueta)
            boton.setToolTip(etiqueta.strip() if self._colapsado else "")
        self.btn_colapsar.setText("›" if self._colapsado else "‹")

        self._animacion = QPropertyAnimation(self, b"ancho", self)
        self._animacion.setDuration(200)
        self._animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animacion.setStartValue(self.width())
        self._animacion.setEndValue(destino)
        self._animacion.start()

    def _obtener_ancho(self) -> int:
        return self.width()

    def _definir_ancho(self, valor: int) -> None:
        self.setFixedWidth(valor)

    # Property de Qt (no solo un atributo Python): es lo que le permite a
    # QPropertyAnimation animar el ancho fijo de la barra cuadro a cuadro.
    ancho = Property(int, _obtener_ancho, _definir_ancho)


class Cabecera(QWidget):
    """Titulo de la pagina, bajada y botones de accion a la derecha."""

    def __init__(self, titulo: str = "", bajada: str = "",
                 parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 12)

        izq = QVBoxLayout()
        izq.setSpacing(2)
        self.lbl_titulo = QLabel(titulo)
        self.lbl_titulo.setObjectName("tituloPagina")
        self.lbl_bajada = QLabel(bajada)
        self.lbl_bajada.setObjectName("bajadaPagina")
        self.lbl_bajada.setVisible(bool(bajada))
        izq.addWidget(self.lbl_titulo)
        izq.addWidget(self.lbl_bajada)
        lay.addLayout(izq)
        lay.addStretch(1)

        self.acciones = QHBoxLayout()
        self.acciones.setSpacing(8)
        lay.addLayout(self.acciones)

    def set_bajada(self, texto: str) -> None:
        self.lbl_bajada.setText(texto)
        self.lbl_bajada.setVisible(bool(texto))

    def agregar(self, boton: QPushButton) -> QPushButton:
        self.acciones.addWidget(boton)
        return boton


class Vacio(QWidget):
    """Mensaje para cuando una grilla no tiene datos todavia."""

    def __init__(self, texto: str, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        et = QLabel(texto)
        et.setObjectName("vacio")
        et.setAlignment(Qt.AlignmentFlag.AlignCenter)
        et.setWordWrap(True)
        lay.addWidget(et)
