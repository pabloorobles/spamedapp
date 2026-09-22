"""Ajustes (listas desplegables) y Caja y gastos (fijos, extraordinarios,
arqueos)."""
from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)

from ..core import calculos, db, repo
from .comunes import (
    ComboLista, FechaEdit, MontoEdit, Tabla, aviso, boton, color, confirmar,
    error,
)
from .navegacion import Cabecera

# Nombre legible de cada lista, para no mostrar la clave tecnica.
ETIQUETAS = {
    "moneda": "Monedas",
    "concepto_ingreso": "Conceptos de ingreso",
    "concepto_egreso": "Conceptos de egreso",
    "medio_pago": "Medios de pago",
    "canal": "Cómo nos conoció el cliente",
    "canal_contacto": "Canales de contacto",
    "tipo_proveedor": "Tipos de operador",
    "transporte": "Tipos de transporte",
    "regimen": "Regímenes de alojamiento",
    "servicio": "Tipos de servicio",
    "motivo_cancelacion": "Motivos de cancelación",
}


class PanelListas(QWidget):
    """Alta, baja y orden de los valores de cada lista desplegable."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        ayuda = QLabel(
            "Estos son los valores que aparecen en los menús desplegables de "
            "toda la aplicación. Agregá los que uses y sacá los que no, así "
            "las cargas son más rápidas y sin errores de tipeo.")
        ayuda.setObjectName("tarjetaDetalle")
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)

        barra = QHBoxLayout()
        self.cmb = QComboBox()
        for clave, etiqueta in ETIQUETAS.items():
            self.cmb.addItem(etiqueta, clave)
        self.cmb.currentIndexChanged.connect(lambda _: self.refrescar())
        barra.addWidget(QLabel("Lista:"))
        barra.addWidget(self.cmb, 1)
        barra.addWidget(boton("Agregar valor", self.agregar, primario=True))
        barra.addWidget(boton("Renombrar", self.renombrar))
        barra.addWidget(boton("Quitar", self.quitar, suave=True))
        lay.addLayout(barra)

        self.lista = QListWidget()
        self.lista.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.lista.model().rowsMoved.connect(lambda *_: self.guardar_orden())
        lay.addWidget(self.lista)

        pie = QLabel("Arrastrá los valores para cambiar el orden en que "
                     "aparecen en los desplegables.")
        pie.setObjectName("tarjetaDetalle")
        lay.addWidget(pie)

    def _tipo(self) -> str:
        return self.cmb.currentData() or "moneda"

    def refrescar(self) -> None:
        self.lista.clear()
        for v in db.listas(self._tipo()):
            self.lista.addItem(QListWidgetItem(v))

    def agregar(self) -> None:
        texto, ok = QInputDialog.getText(
            self, "Agregar valor",
            f"Nuevo valor para «{self.cmb.currentText()}»:")
        texto = (texto or "").strip()
        if not ok or not texto:
            return
        db.execute(
            "INSERT OR IGNORE INTO listas (tipo, valor, orden) VALUES "
            "(?, ?, (SELECT COALESCE(MAX(orden),0)+1 FROM listas WHERE tipo=?))",
            (self._tipo(), texto, self._tipo()))
        self.refrescar()

    def renombrar(self) -> None:
        it = self.lista.currentItem()
        if not it:
            aviso(self, "Seleccioná un valor.")
            return
        viejo = it.text()
        texto, ok = QInputDialog.getText(
            self, "Renombrar", "Nuevo nombre:", text=viejo)
        texto = (texto or "").strip()
        if not ok or not texto or texto == viejo:
            return
        db.execute("UPDATE listas SET valor = ? WHERE tipo = ? AND valor = ?",
                   (texto, self._tipo(), viejo))
        self.refrescar()
        aviso(self, "Valor renombrado.\n\nOjo: los registros que ya tenían el "
                    f"valor anterior siguen diciendo «{viejo}».")

    def quitar(self) -> None:
        it = self.lista.currentItem()
        if not it:
            aviso(self, "Seleccioná un valor.")
            return
        if not confirmar(
            self, f"¿Quitar «{it.text()}» de la lista?\n\n"
                  "Los registros que ya lo usan no se modifican."):
            return
        db.execute("DELETE FROM listas WHERE tipo = ? AND valor = ?",
                   (self._tipo(), it.text()))
        self.refrescar()

    def guardar_orden(self) -> None:
        tipo = self._tipo()
        for i in range(self.lista.count()):
            db.execute("UPDATE listas SET orden = ? WHERE tipo = ? AND valor = ?",
                       (i, tipo, self.lista.item(i).text()))


class DialogoGastoFijo(QDialog):
    def __init__(self, datos=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gasto fijo")
        self.setMinimumWidth(460)
        self.id_ = int(datos["id"]) if datos else None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.concepto = ComboLista("concepto_egreso", vacio=False)
        self.moneda = ComboLista("moneda", vacio=False)
        self.importe = MontoEdit()
        self.dia = QSpinBox()
        self.dia.setRange(1, 28)
        self.medio = ComboLista("medio_pago")
        self.periodicidad = QComboBox()
        for p in repo.PERIODICIDADES:
            self.periodicidad.addItem(p, p)
        self.periodicidad.currentIndexChanged.connect(self._cambio_periodicidad)
        self.fecha_inicio = FechaEdit()
        self.fecha_fin = FechaEdit()
        self.cuotas = QSpinBox()
        self.cuotas.setRange(0, 999)
        self.cuotas.setSpecialValueText("(sin límite)")
        self.activo = QCheckBox("Activo")
        self.activo.setChecked(True)

        form.addRow("Concepto *", self.concepto)
        form.addRow("Moneda", self.moneda)
        form.addRow("Importe *", self.importe)
        form.addRow("Día del mes", self.dia)
        form.addRow("Medio de pago", self.medio)
        form.addRow("Periodicidad", self.periodicidad)
        form.addRow("Fecha de inicio", self.fecha_inicio)
        form.addRow("Fecha de fin", self.fecha_fin)
        form.addRow("Cantidad de cuotas", self.cuotas)
        form.addRow("", self.activo)
        lay.addLayout(form)

        nota = QLabel(
            "El día va de 1 a 28 para que exista en todos los meses. Los "
            "gastos se generan desde Cierre contable. Con una periodicidad "
            "distinta de Mensual hace falta cargar la fecha de inicio, para "
            "saber en qué meses corresponde generarlo. Fecha de fin y "
            "cantidad de cuotas son opcionales y pueden usarse juntas: se "
            "corta con lo primero que se cumpla.")
        nota.setObjectName("tarjetaDetalle")
        nota.setWordWrap(True)
        lay.addWidget(nota)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.guardar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        if datos:
            self.concepto.set_valor(datos.get("concepto"))
            self.moneda.set_valor(datos.get("moneda"))
            self.importe.setValue(float(datos.get("importe") or 0))
            self.dia.setValue(int(datos.get("dia_mes") or 1))
            self.medio.set_valor(datos.get("medio_pago"))
            idx = self.periodicidad.findData(datos.get("periodicidad") or "Mensual")
            self.periodicidad.setCurrentIndex(max(idx, 0))
            self.fecha_inicio.set_valor(datos.get("fecha_inicio"))
            self.fecha_fin.set_valor(datos.get("fecha_fin"))
            self.cuotas.setValue(int(datos.get("cantidad_cuotas") or 0))
            self.activo.setChecked(bool(datos.get("activo")))
        self._cambio_periodicidad()

    def _cambio_periodicidad(self) -> None:
        # Con periodicidad distinta de Mensual, la fecha de inicio deja de
        # ser opcional (ver validacion en repo.GastosFijos.guardar).
        mensual = self.periodicidad.currentData() == "Mensual"
        self.fecha_inicio.setToolTip(
            "" if mensual else "Obligatoria: define en qué meses corresponde.")

    def guardar(self) -> None:
        try:
            repo.GastosFijos.guardar({
                "id": self.id_, "concepto": self.concepto.valor(),
                "moneda": self.moneda.valor() or "PESOS",
                "importe": self.importe.value(),
                "dia_mes": self.dia.value(),
                "medio_pago": self.medio.valor(),
                "periodicidad": self.periodicidad.currentData() or "Mensual",
                "fecha_inicio": self.fecha_inicio.valor(),
                "fecha_fin": self.fecha_fin.valor(),
                "cantidad_cuotas": self.cuotas.value() or None,
                "activo": 1 if self.activo.isChecked() else 0,
            })
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class PanelGastosFijos(QWidget):
    cambio_datos = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        ayuda = QLabel(
            "Alquiler, sueldos, internet: lo que pagás todos los meses. Se "
            "cargan una vez y después se generan desde Cierre contable, sin "
            "tener que anotarlos de nuevo.")
        ayuda.setObjectName("tarjetaDetalle")
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)

        barra = QHBoxLayout()
        barra.addWidget(boton("Nuevo gasto fijo", self.nuevo, primario=True))
        barra.addWidget(boton("Editar", self.editar))
        barra.addWidget(boton("Eliminar", self.eliminar, suave=True))
        barra.addStretch(1)
        lay.addLayout(barra)

        self.tabla = Tabla([
            ("concepto", "Concepto"), ("moneda", "Mon."),
            ("importe", "Importe"), ("dia_mes", "Día"),
            ("periodicidad", "Periodicidad"),
            ("vigencia", "Vigencia"),
            ("medio_pago", "Medio"), ("activo", "Activo"),
            ("ultimo_generado", "Último generado"),
        ])
        self.tabla.doubleClicked.connect(lambda _: self.editar())
        lay.addWidget(self.tabla)

    def refrescar(self) -> None:
        filas = repo.GastosFijos.listar()
        for f in filas:
            desde = calculos.dd_mm_yyyy(f.get("fecha_inicio"))
            hasta = calculos.dd_mm_yyyy(f.get("fecha_fin"))
            cuotas = f.get("cantidad_cuotas")
            partes = []
            if desde:
                partes.append(f"desde {desde}")
            if hasta:
                partes.append(f"hasta {hasta}")
            if cuotas:
                gen = f.get("cuotas_generadas") or 0
                partes.append(f"{gen}/{cuotas} cuotas")
            f["vigencia"] = "  ·  ".join(partes) or "sin límite"
        self.tabla.cargar(
            filas,
            formato=lambda f, k: (
                calculos.money(f.get(k), f.get("moneda", "")) if k == "importe"
                else "Sí" if k == "activo" and f.get(k)
                else "No" if k == "activo"
                else calculos.dd_mm_yyyy(f.get(k)) if k == "ultimo_generado"
                else f.get(k)))

    def nuevo(self) -> None:
        if DialogoGastoFijo(None, self).exec():
            self.refrescar()

    def editar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un gasto.")
            return
        if DialogoGastoFijo(f, self).exec():
            self.refrescar()

    def eliminar(self) -> None:
        f = self.tabla.fila_actual()
        if f and confirmar(self, "¿Eliminar el gasto fijo?"):
            repo.GastosFijos.eliminar(int(f["id"]))
            self.refrescar()


class DialogoArqueo(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Arqueo de caja")
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.fecha = FechaEdit(opcional=False)
        self.fecha.hoy()
        self.moneda = ComboLista("moneda", vacio=False)
        self.contado = MontoEdit()
        self.nota = QLineEdit()
        self.lbl_sistema = QLabel("-")
        self.lbl_dif = QLabel("-")

        form.addRow("Fecha", self.fecha)
        form.addRow("Moneda", self.moneda)
        form.addRow("Según el sistema", self.lbl_sistema)
        form.addRow("Efectivo contado *", self.contado)
        form.addRow("Diferencia", self.lbl_dif)
        form.addRow("Nota", self.nota)
        lay.addLayout(form)

        nota = QLabel("Se compara contra los movimientos con medio de pago "
                      "«Efectivo» hasta la fecha indicada.")
        nota.setObjectName("tarjetaDetalle")
        nota.setWordWrap(True)
        lay.addWidget(nota)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Registrar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.guardar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self.contado.valueChanged.connect(self._calcular)
        self.moneda.currentTextChanged.connect(lambda _: self._calcular())
        self.fecha.dateChanged.connect(lambda _: self._calcular())
        self._calcular()

    def _calcular(self) -> None:
        mon = self.moneda.valor() or "PESOS"
        sis = repo.Arqueos.saldo_efectivo(mon, self.fecha.valor())
        dif = self.contado.value() - sis
        self.lbl_sistema.setText(calculos.money(sis, mon))
        self.lbl_dif.setText(calculos.money(dif, mon))
        self.lbl_dif.setStyleSheet(
            "font-weight:700;" +
            ("" if abs(dif) < 0.01 else f"color:{color('alerta')};"))

    def guardar(self) -> None:
        repo.Arqueos.guardar({
            "fecha": self.fecha.valor(),
            "moneda": self.moneda.valor() or "PESOS",
            "saldo_contado": self.contado.value(),
            "nota": self.nota.text().strip(),
        })
        self.accept()


class PanelArqueos(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        ayuda = QLabel(
            "Contás el efectivo que tenés en la caja y lo comparás con lo que "
            "dice el sistema. La diferencia queda registrada.")
        ayuda.setObjectName("tarjetaDetalle")
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)

        barra = QHBoxLayout()
        barra.addWidget(boton("Nuevo arqueo", self.nuevo, primario=True))
        barra.addWidget(boton("Eliminar", self.eliminar, suave=True))
        barra.addStretch(1)
        lay.addLayout(barra)

        self.tabla = Tabla([
            ("fecha", "Fecha"), ("moneda", "Mon."),
            ("saldo_sistema", "Sistema"), ("saldo_contado", "Contado"),
            ("diferencia", "Diferencia"), ("nota", "Nota"),
        ])
        lay.addWidget(self.tabla)

    def refrescar(self) -> None:
        self.tabla.cargar(
            repo.Arqueos.listar(),
            formato=lambda f, k: (
                calculos.dd_mm_yyyy(f.get(k)) if k == "fecha"
                else calculos.money(f.get(k), f.get("moneda", ""))
                if k in ("saldo_sistema", "saldo_contado", "diferencia")
                else f.get(k)))

    def nuevo(self) -> None:
        if DialogoArqueo(self).exec():
            self.refrescar()

    def eliminar(self) -> None:
        f = self.tabla.fila_actual()
        if f and confirmar(self, "¿Eliminar el arqueo?"):
            repo.Arqueos.eliminar(int(f["id"]))
            self.refrescar()


class PanelGastosExtraordinarios(QWidget):
    """Egresos sueltos: ni un gasto fijo generado solo, ni un pago a un file."""

    cambio_datos = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        ayuda = QLabel(
            "Gastos puntuales que no se repiten todos los meses ni están "
            "asociados a un file: una reparación, una compra única. Se "
            "cargan igual que cualquier movimiento de caja, sin file y sin "
            "que vengan de un gasto fijo.")
        ayuda.setObjectName("tarjetaDetalle")
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)

        barra = QHBoxLayout()
        barra.addWidget(boton("Nuevo gasto", self.nuevo, primario=True))
        barra.addWidget(boton("Editar", self.editar))
        barra.addWidget(boton("Exportar", self.exportar, suave=True))
        barra.addStretch(1)
        lay.addLayout(barra)

        self.tabla = Tabla([
            ("fecha", "Fecha"), ("concepto", "Concepto"), ("moneda", "Mon."),
            ("monto", "Monto"), ("medio_pago", "Medio"), ("detalle", "Detalle"),
        ])
        self.tabla.doubleClicked.connect(lambda _: self.editar())
        lay.addWidget(self.tabla)
        self.lbl_totales = QLabel()
        self.lbl_totales.setObjectName("totales")
        lay.addWidget(self.lbl_totales)

    def refrescar(self) -> None:
        filas = [dict(f) for f in repo.Caja.gastos_extraordinarios()]
        self.tabla.cargar(
            filas,
            formato=lambda f, k: (
                calculos.dd_mm_yyyy(f.get(k)) if k == "fecha"
                else calculos.money(f.get(k), f.get("moneda", ""))
                if k == "monto" else f.get(k)))
        acum: dict[str, float] = {}
        for f in filas:
            acum[f["moneda"]] = acum.get(f["moneda"], 0.0) + float(f["monto"])
        self.lbl_totales.setText(
            "  ·  ".join(f"{m}: {calculos.money(v, m)}" for m, v in acum.items())
            or "Sin gastos extraordinarios cargados.")

    def nuevo(self) -> None:
        from .caja import DialogoMovimiento
        if DialogoMovimiento(None, self, tipo="EGRESO").exec():
            self.refrescar()
            self.cambio_datos.emit()

    def editar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un gasto.")
            return
        from .caja import DialogoMovimiento
        if DialogoMovimiento(int(f["id"]), self).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def exportar(self) -> None:
        self.tabla.exportar(self, "Gastos_extraordinarios")


class VistaCajaGastos(QWidget):
    """Gastos fijos, gastos extraordinarios y arqueos de caja, en solapas."""

    cambio_datos = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.cabecera = Cabecera(
            "Caja y gastos",
            "Gastos fijos, gastos extraordinarios y arqueos de caja")
        lay.addWidget(self.cabecera)

        tabs = QTabWidget()
        self.gastos = PanelGastosFijos()
        self.extraordinarios = PanelGastosExtraordinarios()
        self.arqueos = PanelArqueos()
        tabs.addTab(self.gastos, "Gastos fijos")
        tabs.addTab(self.extraordinarios, "Gastos extraordinarios")
        tabs.addTab(self.arqueos, "Arqueos de caja")
        lay.addWidget(tabs)

        self.extraordinarios.cambio_datos.connect(self.cambio_datos.emit)

    def refrescar(self) -> None:
        self.gastos.refrescar()
        self.extraordinarios.refrescar()
        self.arqueos.refrescar()


class VistaConfiguracion(QWidget):
    """Listas desplegables editables."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.cabecera = Cabecera("Ajustes", "Listas desplegables")
        lay.addWidget(self.cabecera)

        self.listas = PanelListas()
        lay.addWidget(self.listas)

    def refrescar(self) -> None:
        self.listas.refrescar()
