"""Libro de caja: ingresos y egresos, asociados o no a un file."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QVBoxLayout, QWidget,
)

from ..core import calculos, db, repo
from .comunes import (
    BarraBusqueda, ComboBusqueda, ComboTexto, FechaEdit, MontoEdit, Tabla,
    aviso, boton, color, confirmar, error,
)
from .navegacion import Cabecera


class DialogoMovimiento(QDialog):
    def __init__(self, mov_id: int | None = None, parent: QWidget | None = None,
                 tipo: str = "INGRESO", reserva_id: int | None = None,
                 moneda: str = "", monto_sugerido: float = 0.0):
        super().__init__(parent)
        self.mov_id = mov_id
        self.setWindowTitle("Movimiento de caja")
        self.setMinimumWidth(560)

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.tipo = QComboBox()
        self.tipo.addItem("INGRESO (entra plata)", "INGRESO")
        self.tipo.addItem("EGRESO (sale plata)", "EGRESO")
        self.tipo.currentIndexChanged.connect(self._cambio_tipo)
        self.fecha = FechaEdit(opcional=False)
        self.concepto = ComboTexto(db.listas("concepto_ingreso"))
        self.reserva = ComboBusqueda()
        self.moneda = ComboTexto(db.listas("moneda"), vacio=False)
        self.monto = MontoEdit()
        self.medio = ComboTexto(db.listas("medio_pago"))
        self.detalle = QPlainTextEdit()
        self.detalle.setMaximumHeight(70)

        form.addRow("Tipo *", self.tipo)
        form.addRow("Fecha *", self.fecha)
        form.addRow("Concepto *", self.concepto)
        form.addRow("File asociado", self.reserva)
        form.addRow("Moneda *", self.moneda)
        form.addRow("Monto *", self.monto)
        form.addRow("Medio de pago", self.medio)
        form.addRow("Detalle", self.detalle)
        lay.addLayout(form)

        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setObjectName("tarjetaDetalle")
        lay.addWidget(self.lbl_info)

        # Solo tiene sentido una vez que el movimiento ya existe: antes de
        # guardar no hay movimiento_id al cual engancharle el comprobante.
        self.btn_comprobantes = boton(
            "Comprobantes…", self._comprobantes, suave=True)
        self.btn_comprobantes.setEnabled(bool(mov_id))
        lay.addWidget(self.btn_comprobantes)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.guardar)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)

        self.reserva.cargar([
            (r["id"], f"{r['file']} · {r['cliente']} · {r['destino'] or ''}")
            for r in repo.Reservas.listar()
        ], vacio="(gasto o ingreso general)")
        self.reserva.currentIndexChanged.connect(self._cambio_reserva)

        if mov_id:
            self._cargar(mov_id)
        else:
            self.fecha.hoy()
            self.tipo.setCurrentIndex(0 if tipo == "INGRESO" else 1)
            if reserva_id:
                self.reserva.set_id(reserva_id)
            if moneda:
                self.moneda.set_valor(moneda)
            if monto_sugerido > 0:
                self.monto.setValue(monto_sugerido)
        self._cambio_tipo()
        self._cambio_reserva()

    def _cargar(self, id_: int) -> None:
        d = repo.Caja.obtener(id_)
        if not d:
            return
        self.tipo.setCurrentIndex(0 if d["tipo"] == "INGRESO" else 1)
        self.fecha.set_valor(d["fecha"])
        self.concepto.set_valor(d["concepto"])
        self.reserva.set_id(d["reserva_id"])
        self.moneda.set_valor(d["moneda"])
        self.monto.setValue(float(d["monto"] or 0))
        self.medio.set_valor(d["medio_pago"])
        self.detalle.setPlainText(d["detalle"] or "")

    def _cambio_tipo(self) -> None:
        es_ingreso = self.tipo.currentData() == "INGRESO"
        actual = self.concepto.valor()
        self.concepto.cargar(
            db.listas("concepto_ingreso" if es_ingreso else "concepto_egreso")
        )
        if actual:
            self.concepto.set_valor(actual)

    def _cambio_reserva(self) -> None:
        rid = self.reserva.id_actual()
        if not rid:
            self.lbl_info.setText(
                "Sin file asociado: el movimiento cuenta como gasto o ingreso "
                "general de la agencia."
            )
            return
        r = repo.Reservas.obtener(int(rid))
        if not r:
            return
        self.moneda.set_valor(r["moneda"])
        self.lbl_info.setText(
            f"{r['file']} — {r['cliente']} · {r['moneda']}   "
            f"Saldo cliente: {calculos.money(r['saldo_cliente'], r['moneda'])}   "
            f"Saldo operador: {calculos.money(r['saldo_proveedor'], r['moneda'])}"
        )

    def _comprobantes(self) -> None:
        from .maestros import DialogoAdjuntos
        if not self.mov_id:
            return
        DialogoAdjuntos("movimiento", self.mov_id,
                        f"el movimiento del {self.fecha.valor()}", self).exec()

    def guardar(self) -> None:
        try:
            repo.Caja.guardar({
                "id": self.mov_id,
                "tipo": self.tipo.currentData(),
                "fecha": self.fecha.valor(),
                "concepto": self.concepto.valor(),
                "reserva_id": self.reserva.id_actual(),
                "moneda": self.moneda.valor() or "PESOS",
                "monto": self.monto.value(),
                "medio_pago": self.medio.valor(),
                "detalle": self.detalle.toPlainText().strip(),
            })
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class DialogoCambio(QDialog):
    """Compra o venta de moneda: genera dos movimientos ligados."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Cambio de moneda")
        self.setMinimumWidth(520)

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        monedas = db.listas("moneda")
        self.fecha = FechaEdit(opcional=False)
        self.mon_origen = ComboTexto(monedas, vacio=False)
        self.monto_origen = MontoEdit()
        self.mon_destino = ComboTexto(monedas, vacio=False)
        self.monto_destino = MontoEdit()
        self.medio = ComboTexto(db.listas("medio_pago"))
        self.detalle = QPlainTextEdit()
        self.detalle.setMaximumHeight(60)

        if len(monedas) > 1:
            self.mon_destino.set_valor(monedas[1])

        form.addRow("Fecha *", self.fecha)
        form.addRow("Sale (moneda) *", self.mon_origen)
        form.addRow("Sale (monto) *", self.monto_origen)
        form.addRow("Entra (moneda) *", self.mon_destino)
        form.addRow("Entra (monto) *", self.monto_destino)
        form.addRow("Medio", self.medio)
        form.addRow("Detalle", self.detalle)
        lay.addLayout(form)

        self.lbl_cotiz = QLabel()
        self.lbl_cotiz.setObjectName("tarjetaDetalle")
        self.lbl_cotiz.setWordWrap(True)
        lay.addWidget(self.lbl_cotiz)

        for w in (self.monto_origen, self.monto_destino):
            w.valueChanged.connect(self._cotizacion)
        for c in (self.mon_origen, self.mon_destino):
            c.currentTextChanged.connect(self._cotizacion)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Registrar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.guardar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self.fecha.hoy()
        self._cotizacion()

    def _cotizacion(self) -> None:
        o, d = self.monto_origen.value(), self.monto_destino.value()
        if o <= 0 or d <= 0:
            self.lbl_cotiz.setText(
                "Las monedas no se consolidan: cada una mantiene su saldo "
                "propio en los reportes."
            )
            return
        cot = round(max(o, d) / min(o, d), 4)
        self.lbl_cotiz.setText(
            f"Cotización implícita: {cot}   ·   "
            f"salen {calculos.money(o, self.mon_origen.valor())} y entran "
            f"{calculos.money(d, self.mon_destino.valor())}"
        )

    def guardar(self) -> None:
        try:
            repo.Caja.cambio_moneda(
                fecha=self.fecha.valor(),
                moneda_origen=self.mon_origen.valor(),
                monto_origen=self.monto_origen.value(),
                moneda_destino=self.mon_destino.valor(),
                monto_destino=self.monto_destino.value(),
                medio_pago=self.medio.valor(),
                detalle=self.detalle.toPlainText().strip(),
            )
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class VistaCaja(QWidget):
    cambio_datos = Signal()

    COLUMNAS = [
        ("fecha", "Fecha"), ("tipo", "Tipo"), ("concepto", "Concepto"),
        ("file", "File"), ("cliente", "Cliente"), ("moneda", "Mon."),
        ("monto", "Monto"), ("medio_pago", "Medio"),
        ("cotizacion", "Cotiz."), ("detalle", "Detalle"),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.cabecera = Cabecera("Caja", "")
        self.cabecera.agregar(
            boton("Nuevo movimiento", self.nuevo, primario=True))
        lay.addWidget(self.cabecera)

        filtros = QHBoxLayout()
        self.busqueda = BarraBusqueda("Buscar concepto, file, detalle...")
        self.busqueda.cambio.connect(lambda _: self.refrescar())
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItem("Todos", "")
        self.cmb_tipo.addItem("Ingresos", "INGRESO")
        self.cmb_tipo.addItem("Egresos", "EGRESO")
        self.cmb_tipo.currentIndexChanged.connect(lambda _: self.refrescar())
        self.cmb_moneda = QComboBox()
        self.cmb_moneda.addItem("Todas", "")
        for m in db.listas("moneda"):
            self.cmb_moneda.addItem(m, m)
        self.cmb_moneda.currentIndexChanged.connect(lambda _: self.refrescar())
        self.desde = FechaEdit()
        self.hasta = FechaEdit()
        self.desde.dateChanged.connect(lambda _: self.refrescar())
        self.hasta.dateChanged.connect(lambda _: self.refrescar())

        filtros.addWidget(self.busqueda, 1)
        filtros.addWidget(self.cmb_tipo)
        filtros.addWidget(self.cmb_moneda)
        filtros.addWidget(QLabel("Desde"))
        filtros.addWidget(self.desde)
        filtros.addWidget(QLabel("Hasta"))
        filtros.addWidget(self.hasta)
        lay.addLayout(filtros)

        acciones = QHBoxLayout()
        acciones.setSpacing(8)
        acciones.addWidget(boton("Editar", self.editar))
        acciones.addWidget(boton("Cambio de moneda", self.cambio, acento=True))
        acciones.addWidget(boton("Imprimir recibo", self.recibo))
        acciones.addStretch(1)
        acciones.addWidget(boton("Eliminar", self.eliminar, suave=True))
        acciones.addWidget(boton(
            "Exportar", lambda: self.tabla.exportar(self, "Caja"), suave=True))
        lay.addLayout(acciones)

        self.tabla = Tabla(self.COLUMNAS)
        self.tabla.doubleClicked.connect(lambda _: self.editar())
        lay.addWidget(self.tabla)

        self.lbl_totales = QLabel()
        self.lbl_totales.setObjectName("totales")
        lay.addWidget(self.lbl_totales)

    def refrescar(self) -> None:
        filas = [dict(f) for f in repo.Caja.listar(
            texto=self.busqueda.texto(),
            tipo=self.cmb_tipo.currentData() or "",
            moneda=self.cmb_moneda.currentData() or "",
            desde=self.desde.valor(), hasta=self.hasta.valor(),
        )]
        self.tabla.cargar(filas, formato=self._fmt, color_fila=self._color)
        self.cabecera.set_bajada(
            f"{len(filas)} movimiento(s)" if filas
            else "Sin movimientos para el filtro actual.")
        self._totales(filas)

    @staticmethod
    def _fmt(f: dict[str, Any], k: str) -> Any:
        if k == "fecha":
            return calculos.dd_mm_yyyy(f.get(k))
        if k == "monto":
            signo = "" if f.get("tipo") == "INGRESO" else "-"
            return signo + calculos.money(f.get(k), f.get("moneda", ""))
        return f.get(k)

    @staticmethod
    def _color(f: dict[str, Any]) -> str | None:
        return color("ok") if f.get("tipo") == "INGRESO" else color("error")

    def _totales(self, filas: list[dict[str, Any]]) -> None:
        acum: dict[str, dict[str, float]] = {}
        for f in filas:
            a = acum.setdefault(f["moneda"], {"i": 0.0, "e": 0.0})
            if f["tipo"] == "INGRESO":
                a["i"] += float(f["monto"] or 0)
            else:
                a["e"] += float(f["monto"] or 0)
        partes = [f"{len(filas)} movimiento(s)"]
        for mon, a in acum.items():
            partes.append(
                f"{mon}: ingresos {calculos.money(a['i'])} · "
                f"egresos {calculos.money(a['e'])} · "
                f"neto {calculos.money(a['i'] - a['e'])}"
            )
        self.lbl_totales.setText("      ".join(partes))

    def cambio(self) -> None:
        if DialogoCambio(self).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def recibo(self) -> None:
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        from ..core import documentos
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un movimiento.")
            return
        if f.get("tipo") != "INGRESO" or not f.get("reserva_id"):
            aviso(self, "El recibo se emite sobre un cobro asociado a un file.")
            return
        r = repo.Reservas.obtener(int(f["reserva_id"]))
        if not r:
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar recibo",
            f"Recibo_{r['file']}_{f['id']}.pdf", "PDF (*.pdf)")
        if not ruta:
            return
        try:
            p = documentos.recibo(r, f, Path(ruta))
            aviso(self, f"Recibo generado:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo generar el recibo:\n{e}")

    def nuevo(self) -> None:
        if DialogoMovimiento(None, self).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def editar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un movimiento.")
            return
        if DialogoMovimiento(int(f["id"]), self).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def eliminar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un movimiento.")
            return
        if not confirmar(self, "¿Eliminar el movimiento seleccionado?"):
            return
        repo.Caja.eliminar(int(f["id"]))
        self.refrescar()
        self.cambio_datos.emit()
