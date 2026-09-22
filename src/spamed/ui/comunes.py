"""Widgets y helpers reutilizables de la interfaz."""
from __future__ import annotations

from datetime import date
from typing import Any, Callable, Sequence

from PySide6.QtCore import QDate, QEvent, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDoubleSpinBox, QFileDialog,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLayout, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from ..core import calculos, exportador, tema

# Tema activo del proceso. La ventana principal lo fija al arrancar y al
# cambiarlo desde el menu; los widgets leen los colores desde aca.
_TEMA = "claro"


def tema_actual() -> str:
    return _TEMA


def set_tema(nombre: str) -> None:
    global _TEMA, COLOR_ESTADO
    _TEMA = "oscuro" if str(nombre).lower() == "oscuro" else "claro"
    COLOR_ESTADO.clear()
    COLOR_ESTADO.update(tema.estados(_TEMA))


def color(clave: str) -> str:
    """Un color de la paleta del tema activo."""
    return tema.paleta(_TEMA)[clave]


# Se mantiene como dict mutable para que el resto del codigo lo importe una
# sola vez y siga viendo los colores del tema vigente.
COLOR_ESTADO: dict[str, str] = dict(tema.estados("claro"))


# ------------------------------------------------------------- mensajes

def aviso(padre: QWidget, texto: str, titulo: str = "Spamed") -> None:
    QMessageBox.information(padre, titulo, texto)


def error(padre: QWidget, texto: str, titulo: str = "Spamed") -> None:
    QMessageBox.critical(padre, titulo, texto)


def confirmar(padre: QWidget, texto: str, titulo: str = "Confirmar") -> bool:
    return QMessageBox.question(
        padre, titulo, texto,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    ) == QMessageBox.StandardButton.Yes


# ------------------------------------------------------------- controles

class FechaEdit(QDateEdit):
    """QDateEdit con calendario, formato dd/MM/yyyy y soporte de valor vacio.

    Cuando el campo esta vacio el valor interno es la fecha minima (1900), asi
    que el calendario se abriria en enero de 1900. Por eso, al desplegarlo, se
    lo reposiciona en el mes actual.
    """

    def __init__(self, opcional: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd/MM/yyyy")
        self.setSpecialValueText("  —  " if opcional else "")
        self.setMinimumDate(QDate(1900, 1, 1))
        self.opcional = opcional
        self.limpiar()
        cal = self.calendarWidget()
        if cal is not None:
            cal.installEventFilter(self)

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.Type.Show and self.esta_vacio():
            hoy = QDate.currentDate()
            obj.setCurrentPage(hoy.year(), hoy.month())
            obj.setSelectedDate(hoy)
        return super().eventFilter(obj, event)

    def esta_vacio(self) -> bool:
        return self.opcional and self.date() == self.minimumDate()

    def limpiar(self) -> None:
        if self.opcional:
            self.setDate(self.minimumDate())
        else:
            self.setDate(QDate.currentDate())

    def valor(self) -> str | None:
        if self.opcional and self.date() == self.minimumDate():
            return None
        return self.date().toString("yyyy-MM-dd")

    def set_valor(self, v: Any) -> None:
        f = calculos.a_fecha(v)
        if f is None:
            self.limpiar()
        else:
            self.setDate(QDate(f.year, f.month, f.day))

    def hoy(self) -> None:
        h = date.today()
        self.setDate(QDate(h.year, h.month, h.day))


class MontoEdit(QDoubleSpinBox):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setRange(0, 999_999_999)
        self.setDecimals(2)
        self.setGroupSeparatorShown(True)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)


class ComboBusqueda(QComboBox):
    """Lista desplegable de entidades; guarda (id, texto).

    No admite escritura libre: solo se elige de lo que ya existe. Para dar de
    alta algo nuevo esta ComboConAlta, que agrega el boton "+".
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setEditable(False)
        self.setMaxVisibleItems(18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def cargar(self, items: Sequence[tuple[int, str]], vacio: str = "") -> None:
        actual = self.id_actual()
        self.clear()
        if vacio is not None:
            self.addItem(vacio, None)
        for id_, texto in items:
            self.addItem(texto, id_)
        if actual is not None:
            self.set_id(actual)

    def id_actual(self) -> int | None:
        return self.currentData()

    def set_id(self, id_: int | None) -> None:
        if id_ is None:
            self.setCurrentIndex(0)
            return
        idx = self.findData(id_)
        self.setCurrentIndex(idx if idx >= 0 else 0)


class ComboTexto(QComboBox):
    """Combo de valores de texto (listas Helper)."""

    def __init__(self, valores: Sequence[str] = (), editable: bool = False,
                 vacio: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.setEditable(editable)
        self.setMaxVisibleItems(18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vacio = vacio
        self.cargar(valores)

    def cargar(self, valores: Sequence[str]) -> None:
        self.clear()
        if self._vacio:
            self.addItem("")
        self.addItems(list(valores))

    def valor(self) -> str:
        return self.currentText().strip()

    def set_valor(self, v: Any) -> None:
        texto = str(v or "")
        idx = self.findText(texto)
        if idx >= 0:
            self.setCurrentIndex(idx)
        elif self.isEditable():
            self.setEditText(texto)
        else:
            self.setCurrentIndex(0)


class BarraBusqueda(QWidget):
    """Caja de texto + boton limpiar, emite 'cambio' al tipear."""

    cambio = Signal(str)

    def __init__(self, placeholder: str = "Buscar...", parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.txt = QLineEdit()
        self.txt.setObjectName("busqueda")
        self.txt.setPlaceholderText(placeholder)
        self.txt.setClearButtonEnabled(True)
        self.txt.textChanged.connect(self.cambio.emit)
        lay.addWidget(self.txt)

    def texto(self) -> str:
        return self.txt.text().strip()


class Tarjeta(QFrame):
    """Tarjeta de indicador para el tablero."""

    def __init__(self, titulo: str, valor: str = "-", detalle: str = "",
                 color: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("tarjeta")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(2)

        self.lbl_titulo = QLabel(titulo)
        self.lbl_titulo.setObjectName("tarjetaTitulo")
        self.lbl_valor = QLabel(valor)
        self.lbl_valor.setObjectName("tarjetaValor")
        f = QFont()
        f.setPointSize(17)
        f.setBold(True)
        self.lbl_valor.setFont(f)
        self._color = color or tema.paleta(_TEMA)["primario"]
        self.lbl_valor.setStyleSheet(f"color: {self._color};")
        self.lbl_detalle = QLabel(detalle)
        self.lbl_detalle.setObjectName("tarjetaDetalle")
        self.lbl_detalle.setWordWrap(True)

        lay.addWidget(self.lbl_titulo)
        lay.addWidget(self.lbl_valor)
        lay.addWidget(self.lbl_detalle)

    def actualizar(self, valor: str, detalle: str = "") -> None:
        self.lbl_valor.setText(valor)
        self.lbl_detalle.setText(detalle)

    def set_color(self, color: str) -> None:
        """Recolorea el valor. Se usa al cambiar de tema."""
        self._color = color
        self.lbl_valor.setStyleSheet(f"color: {color};")


class Tabla(QTableWidget):
    """QTableWidget con columnas declarativas, formato y exportacion."""

    def __init__(self, columnas: Sequence[tuple[str, str]],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.columnas = list(columnas)
        self._filas: list[dict[str, Any]] = []
        self.setColumnCount(len(self.columnas))
        self.setHorizontalHeaderLabels([t for _, t in self.columnas])
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.horizontalHeader().setStretchLastSection(True)

    def cargar(self, filas: Sequence[dict[str, Any]],
               formato: Callable[[dict[str, Any], str], Any] | None = None,
               color_fila: Callable[[dict[str, Any]], str | None] | None = None,
               ) -> None:
        self.setSortingEnabled(False)
        self._filas = [dict(f) for f in filas]
        self.setRowCount(len(self._filas))
        for i, f in enumerate(self._filas):
            for j, (clave, _) in enumerate(self.columnas):
                bruto = f.get(clave)
                texto = formato(f, clave) if formato else bruto
                item = QTableWidgetItem()
                if isinstance(bruto, (int, float)) and not isinstance(bruto, bool):
                    item.setData(Qt.ItemDataRole.EditRole, float(bruto))
                    item.setText(str(texto) if texto is not None else "")
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    item.setText("" if texto is None else str(texto))
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, f.get("id"))
                col = color_fila(f) if color_fila else None
                if col:
                    item.setForeground(QColor(col))
                self.setItem(i, j, item)
        self.setSortingEnabled(True)
        self.resizeColumnsToContents()

    def fila_actual(self) -> dict[str, Any] | None:
        r = self.currentRow()
        if r < 0:
            return None
        item = self.item(r, 0)
        if item is None:
            return None
        id_ = item.data(Qt.ItemDataRole.UserRole)
        for f in self._filas:
            if f.get("id") == id_:
                return f
        return None

    def datos(self) -> list[dict[str, Any]]:
        return list(self._filas)

    def exportar(self, padre: QWidget, nombre: str = "export") -> None:
        if not self._filas:
            aviso(padre, "No hay datos para exportar.")
            return
        from datetime import datetime

        from ..core import config
        # Se propone la carpeta configurada (por defecto Descargas) y un
        # nombre con fecha, para que no se pierda entre lo demas que hay ahi.
        sugerido = config.dir_exports() / (
            f"{nombre.replace(' ', '-')}_{datetime.now():%Y%m%d}.xlsx")
        ruta, _ = QFileDialog.getSaveFileName(
            padre, "Exportar", str(sugerido),
            "Excel (*.xlsx);;CSV (*.csv)",
        )
        if not ruta:
            return
        try:
            from pathlib import Path
            p = Path(ruta)
            if p.suffix.lower() == ".csv":
                exportador.a_csv(self._filas, self.columnas, p)
            else:
                exportador.a_excel(self._filas, self.columnas, p, titulo_hoja=nombre)
            aviso(padre, f"Exportado a:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(padre, f"No se pudo exportar:\n{e}")


def boton(texto: str, slot: Callable[[], Any] | None = None,
          primario: bool = False, ancho: int = 0,
          suave: bool = False, acento: bool = False) -> QPushButton:
    """Boton con las tres variantes de la interfaz: primario, acento y suave."""
    b = QPushButton(texto)
    if primario:
        b.setObjectName("primario")
    elif acento:
        b.setObjectName("acento")
    elif suave:
        b.setObjectName("suave")
    if ancho:
        b.setMinimumWidth(ancho)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    return b


def separador() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setObjectName("separador")
    return f


class FlowLayout(QLayout):
    """Layout que acomoda los widgets en fila y pasa a la siguiente cuando
    no entran mas. Para filas con muchos botones (ver _PanelFiles.acciones
    en ui/reservas.py): con QHBoxLayout, en una ventana angosta los botones
    se aprietan hasta recortar el texto en vez de acomodarse en dos lineas.
    """

    def __init__(self, parent: QWidget | None = None, margen: int = 0,
                 espacio: int = 8):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margen, margen, margen, margen)
        self._espacio = espacio
        self._items: list = []

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, ancho: int) -> int:
        return self._acomodar(QRect(0, 0, ancho, 0), simular=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._acomodar(rect, simular=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        tam = QSize()
        for item in self._items:
            tam = tam.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        tam += QSize(m.left() + m.right(), m.top() + m.bottom())
        return tam

    def _acomodar(self, rect: QRect, simular: bool) -> int:
        x, y = rect.x(), rect.y()
        alto_fila = 0
        for item in self._items:
            prox_x = x + item.sizeHint().width() + self._espacio
            if prox_x - self._espacio > rect.right() and alto_fila > 0:
                x = rect.x()
                y += alto_fila + self._espacio
                prox_x = x + item.sizeHint().width() + self._espacio
                alto_fila = 0
            if not simular:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = prox_x
            alto_fila = max(alto_fila, item.sizeHint().height())
        return y + alto_fila - rect.y()


class ComboConAlta(QWidget):
    """Lista desplegable con un boton "+" para dar de alta sin salir del form.

    El dialogo de alta se abre encima; al aceptar, la lista se recarga y queda
    seleccionado lo recien creado.
    """

    cambio = Signal()

    def __init__(self, cargador: Callable[[], Sequence[tuple[int, str]]],
                 alta: Callable[[QWidget], Any] | None = None,
                 vacio: str = "", tooltip: str = "Agregar nuevo",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._cargador = cargador
        self._alta = alta
        self._vacio = vacio

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.combo = ComboBusqueda()
        self.combo.currentIndexChanged.connect(lambda _: self.cambio.emit())
        lay.addWidget(self.combo, 1)

        if alta is not None:
            self.btn = QPushButton("+")
            self.btn.setObjectName("mas")
            self.btn.setFixedWidth(38)
            self.btn.setToolTip(tooltip)
            self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn.clicked.connect(self._nuevo)
            lay.addWidget(self.btn)

        self.recargar()

    def recargar(self, seleccionar: int | None = None) -> None:
        actual = seleccionar if seleccionar is not None else self.id_actual()
        self.combo.cargar(list(self._cargador()), vacio=self._vacio)
        if actual is not None:
            self.combo.set_id(actual)

    def _nuevo(self) -> None:
        if self._alta is None:
            return
        nuevo_id = self._alta(self)
        self.recargar(nuevo_id if nuevo_id else None)

    def id_actual(self) -> int | None:
        return self.combo.id_actual()

    def set_id(self, id_: int | None) -> None:
        self.combo.set_id(id_)

    def texto_actual(self) -> str:
        return self.combo.currentText()


class ComboLista(QWidget):
    """Combo de una lista editable (moneda, medio de pago, concepto...).

    Los valores salen de la tabla `listas`. El boton "+" permite sumar uno
    nuevo, que queda guardado para las proximas veces.
    """

    def __init__(self, tipo: str, vacio: bool = True,
                 permitir_alta: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        from ..core import db as _db
        self._db = _db
        self.tipo = tipo
        self._vacio = vacio

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.combo = ComboTexto(vacio=vacio, editable=False)
        lay.addWidget(self.combo, 1)

        if permitir_alta:
            self.btn = QPushButton("+")
            self.btn.setObjectName("mas")
            self.btn.setFixedWidth(38)
            self.btn.setToolTip(f"Agregar un valor nuevo a «{tipo}»")
            self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn.clicked.connect(self._nuevo)
            lay.addWidget(self.btn)

        self.recargar()

    def recargar(self, seleccionar: str = "") -> None:
        actual = seleccionar or self.valor()
        self.combo.cargar(self._db.listas(self.tipo))
        if actual:
            self.combo.set_valor(actual)

    def _nuevo(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        texto, ok = QInputDialog.getText(
            self, "Agregar valor", f"Nuevo valor para «{self.tipo}»:")
        texto = (texto or "").strip()
        if not ok or not texto:
            return
        try:
            self._db.execute(
                "INSERT OR IGNORE INTO listas (tipo, valor, orden) "
                "VALUES (?, ?, (SELECT COALESCE(MAX(orden),0)+1 FROM listas "
                "WHERE tipo = ?))",
                (self.tipo, texto, self.tipo))
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo agregar el valor:\n{e}")
            return
        self.recargar(texto)

    def valor(self) -> str:
        return self.combo.valor()

    def set_valor(self, v: Any) -> None:
        self.combo.set_valor(v)

    @property
    def currentTextChanged(self):  # noqa: N802
        return self.combo.currentTextChanged
