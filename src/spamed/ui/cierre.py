"""Cierre contable: estado del mes en curso y cierre de meses terminados."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)

from ..core import calculos, db, documentos, repo
from .comunes import (
    MontoEdit, Tabla, aviso, boton, color, confirmar, error,
)
from .navegacion import Cabecera

MESES = ("", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")


class DialogoObjetivo(QDialog):
    def __init__(self, anio: int, mes: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Objetivo de ventas")
        self.setMinimumWidth(420)
        self.anio, self.mes = anio, mes

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.moneda = QComboBox()
        for m in db.listas("moneda"):
            self.moneda.addItem(m, m)
        self.importe = MontoEdit()
        self.moneda.currentIndexChanged.connect(self._cargar)

        form.addRow("Período", QLabel(f"{MESES[mes]} {anio}"))
        form.addRow("Moneda", self.moneda)
        form.addRow("Objetivo de ventas", self.importe)
        lay.addLayout(form)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.guardar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._cargar()

    def _cargar(self) -> None:
        self.importe.setValue(
            repo.Objetivos.obtener(self.anio, self.mes,
                                   self.moneda.currentData() or "PESOS"))

    def guardar(self) -> None:
        repo.Objetivos.guardar(self.anio, self.mes,
                               self.moneda.currentData() or "PESOS",
                               self.importe.value())
        self.accept()


class VistaCierre(QWidget):
    """Estado del mes y cierre contable."""

    cambio_datos = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        hoy = date.today()

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(10)

        self.cabecera = Cabecera("Cierre contable", "")
        self.cabecera.agregar(boton("Objetivo del mes", self.objetivo,
                                    suave=True))
        self.cabecera.agregar(boton("Exportar PDF", self.exportar_pdf,
                                    suave=True))
        self.cabecera.agregar(boton("Cerrar el mes", self.cerrar,
                                    primario=True))
        raiz.addWidget(self.cabecera)

        barra = QHBoxLayout()
        self.cmb_mes = QComboBox()
        for i in range(1, 13):
            self.cmb_mes.addItem(MESES[i], i)
        self.cmb_mes.setCurrentIndex(hoy.month - 1)
        self.spin_anio = QSpinBox()
        self.spin_anio.setRange(2000, 2100)
        self.spin_anio.setValue(hoy.year)
        self.cmb_mes.currentIndexChanged.connect(lambda _: self.refrescar())
        self.spin_anio.valueChanged.connect(lambda _: self.refrescar())
        barra.addWidget(QLabel("Período:"))
        barra.addWidget(self.cmb_mes)
        barra.addWidget(self.spin_anio)
        barra.addWidget(boton("Mes actual", self._mes_actual, suave=True))
        barra.addWidget(boton("Generar gastos fijos", self.generar_gastos,
                              suave=True))
        barra.addStretch(1)
        raiz.addLayout(barra)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setObjectName("lienzo")
        cont = QWidget()
        cont.setObjectName("lienzo")
        scroll.setWidget(cont)
        raiz.addWidget(scroll, 1)

        self.lay_cont = QVBoxLayout(cont)
        self.lay_cont.setContentsMargins(0, 0, 6, 0)
        self.lay_cont.setSpacing(12)

        caja_bcra = QGroupBox("Resumen consolidado (informativo)")
        lay_bcra = QVBoxLayout(caja_bcra)
        aviso_bcra = QLabel(
            "Convierte todo a pesos con la cotización de referencia, solo "
            "para tener una idea del total combinado. Los totales por "
            "moneda de arriba NO cambian, siguen siendo la fuente real — "
            "acá nunca se suma pesos con dólares salvo en este resumen "
            "aparte.")
        aviso_bcra.setObjectName("tarjetaDetalle")
        aviso_bcra.setWordWrap(True)
        lay_bcra.addWidget(aviso_bcra)

        fila_cot = QHBoxLayout()
        fila_cot.addWidget(QLabel("Cotización del dólar ($ por US$):"))
        self.cotizacion = MontoEdit()
        self.cotizacion.setMaximum(9_999_999)
        fila_cot.addWidget(self.cotizacion)
        fila_cot.addWidget(boton("Actualizar de internet",
                                 self._actualizar_cotizacion, suave=True))
        fila_cot.addWidget(boton("Usar este valor",
                                 self._guardar_cotizacion_manual, suave=True))
        fila_cot.addStretch(1)
        lay_bcra.addLayout(fila_cot)

        self.lbl_cotizacion_fecha = QLabel()
        self.lbl_cotizacion_fecha.setObjectName("tarjetaDetalle")
        lay_bcra.addWidget(self.lbl_cotizacion_fecha)

        self.lbl_consolidado = QLabel("-")
        self.lbl_consolidado.setStyleSheet("font-size:12pt; font-weight:700;")
        self.lbl_consolidado.setWordWrap(True)
        lay_bcra.addWidget(self.lbl_consolidado)
        self.lay_cont.addWidget(caja_bcra)

        caja_liq = QGroupBox("Comisiones a liquidar en el período")
        lay_liq = QVBoxLayout(caja_liq)
        self.tabla_liq = Tabla([
            ("vendedor", "Vendedor"), ("moneda", "Mon."), ("files", "Files"),
            ("ventas", "Ventas"), ("comision_agencia", "Com. agencia"),
            ("importe", "Le corresponde"), ("estado", "Estado"),
        ])
        self.tabla_liq.setMinimumHeight(170)
        lay_liq.addWidget(self.tabla_liq)
        bl = QHBoxLayout()
        bl.addWidget(boton("Marcar como pagada", self.pagar_liquidacion,
                           acento=True))
        bl.addWidget(boton("Imprimir liquidación", self.pdf_liquidacion))
        bl.addStretch(1)
        lay_liq.addLayout(bl)
        self.lay_cont.addWidget(caja_liq)
        self.lay_cont.addStretch(1)

        self._tarjetas: list[QWidget] = []
        self.datos: dict[str, dict[str, Any]] = {}
        self._refrescar_consolidado()

    # ------------------------------------------------------------ datos
    def _periodo(self) -> tuple[int, int]:
        return self.spin_anio.value(), self.cmb_mes.currentData()

    def _mes_actual(self) -> None:
        hoy = date.today()
        self.spin_anio.setValue(hoy.year)
        self.cmb_mes.setCurrentIndex(hoy.month - 1)

    def _actualizar_cotizacion(self) -> None:
        from ..core import bcra
        try:
            valor = bcra.actualizar()
        except bcra.ErrorCotizacion as e:
            error(self, str(e))
            self._refrescar_consolidado()
            return
        self.cotizacion.setValue(valor)
        self._refrescar_consolidado()
        aviso(self, f"Cotización actualizada: {calculos.money(valor, 'PESOS')} "
                    "por US$.")

    def _guardar_cotizacion_manual(self) -> None:
        from ..core import bcra
        if self.cotizacion.value() <= 0:
            aviso(self, "Cargá un valor mayor a cero.")
            return
        bcra.guardar_manual(self.cotizacion.value())
        self._refrescar_consolidado()
        aviso(self, "Cotización guardada.")

    def _refrescar_consolidado(self) -> None:
        from ..core import bcra
        valor, fecha = bcra.ultima_guardada()
        if valor and self.cotizacion.value() <= 0:
            self.cotizacion.setValue(valor)
        self.lbl_cotizacion_fecha.setText(
            f"Última cotización guardada: {calculos.money(valor, 'PESOS')} "
            f"por US$ — {fecha}" if valor else
            "Todavía no hay ninguna cotización guardada. Cargala a mano o "
            "traela de internet."
        )

        cot = self.cotizacion.value()
        if not cot:
            self.lbl_consolidado.setText(
                "Cargá una cotización para ver el consolidado.")
            return
        if not self.datos:
            self.lbl_consolidado.setText(
                "Sin datos en este período para consolidar.")
            return
        ventas_cons = 0.0
        margen_cons = 0.0
        for mon, d in self.datos.items():
            factor = 1.0 if mon == "PESOS" else cot
            ventas_cons += d["ventas"] * factor
            margen_cons += d["margen"] * factor
        self.lbl_consolidado.setText(
            f"Ventas consolidadas: {calculos.money(ventas_cons, 'PESOS')}"
            f"   ·   Margen consolidado: {calculos.money(margen_cons, 'PESOS')}"
            f"   (a {calculos.money(cot, 'PESOS')} el dólar)"
        )

    def refrescar(self) -> None:
        anio, mes = self._periodo()
        datos = repo.Cierre.comparar(anio, mes)
        self.datos = datos

        hoy = date.today()
        en_curso = (anio, mes) >= (hoy.year, hoy.month)
        cerrado = any(d["cerrado"] for d in datos.values())
        estado = ("mes en curso" if en_curso
                  else "cerrado" if cerrado else "abierto, listo para cerrar")
        self.cabecera.set_bajada(f"{MESES[mes]} {anio} — {estado}")

        for w in self._tarjetas:
            w.setParent(None)
            w.deleteLater()
        self._tarjetas.clear()

        if not datos:
            vacio = QLabel(
                "No hay movimientos ni ventas en este período.")
            vacio.setObjectName("vacio")
            vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lay_cont.insertWidget(0, vacio)
            self._tarjetas.append(vacio)
        for i, (mon, d) in enumerate(datos.items()):
            w = self._panel_moneda(mon, d)
            self.lay_cont.insertWidget(i, w)
            self._tarjetas.append(w)

        liq = repo.Liquidaciones.calcular(anio, mes)
        for f in liq:
            f["estado"] = "Pagada" if f["pagada"] else "Pendiente"
        self.tabla_liq.cargar(
            liq,
            formato=lambda f, k: (
                calculos.money(f.get(k), f.get("moneda", ""))
                if k in ("ventas", "comision_agencia", "importe")
                else f.get(k)),
            color_fila=lambda f: (color("ok") if f["pagada"]
                                  else color("alerta")))

        self._refrescar_consolidado()

    def _panel_moneda(self, mon: str, d: dict[str, Any]) -> QWidget:
        caja = QGroupBox(f"{mon}")
        lay = QGridLayout(caja)
        lay.setSpacing(10)

        def linea(fila: int, col: int, etiqueta: str, valor: str,
                  destacado: bool = False, tono: str = "") -> None:
            e = QLabel(etiqueta)
            e.setObjectName("tarjetaTitulo")
            v = QLabel(valor)
            if destacado:
                v.setStyleSheet(
                    f"font-size:13pt; font-weight:700;"
                    f"color:{tono or color('primario')};")
            else:
                v.setStyleSheet("font-weight:600;")
            lay.addWidget(e, fila * 2, col)
            lay.addWidget(v, fila * 2 + 1, col)

        m = lambda v: calculos.money(v, mon)  # noqa: E731
        linea(0, 0, f"Ventas ({d['files']} files)", m(d["ventas"]), True)
        linea(0, 1, "Comisión de la agencia", m(d["comision_agencia"]), True)
        linea(0, 2, "Comisión de vendedores", m(d["comision_vendedores"]))
        linea(0, 3, "Margen de la agencia", m(d["margen"]), True,
              color("ok") if d["margen"] >= 0 else color("error"))

        linea(1, 0, "Cobros a clientes", m(d["cobros_clientes"]))
        linea(1, 1, "Pagos a operadores", m(d["pagos_proveedores"]))
        linea(1, 2, "Gastos generales", m(d["gastos_generales"]))
        linea(1, 3, "Resultado de caja", m(d["resultado_caja"]), True,
              color("ok") if d["resultado_caja"] >= 0 else color("error"))

        var = d.get("var_ventas", 0)
        signo = "+" if var > 0 else ""
        linea(2, 0, "Objetivo del mes",
              m(d["objetivo"]) if d["objetivo"] else "sin definir")
        linea(2, 1, "Cumplimiento",
              f"{d['cumplimiento']}%" if d["objetivo"] else "—", True,
              color("ok") if d["cumplimiento"] >= 100 else color("alerta"))
        linea(2, 2, "Vs. mes anterior", f"{signo}{var}%", False)
        linea(2, 3, "Devoluciones", m(d["devoluciones"]))
        return caja

    # --------------------------------------------------------- acciones
    def objetivo(self) -> None:
        anio, mes = self._periodo()
        if DialogoObjetivo(anio, mes, self).exec():
            self.refrescar()

    def generar_gastos(self) -> None:
        anio, mes = self._periodo()
        fijos = repo.GastosFijos.listar(solo_activos=True)
        if not fijos:
            aviso(self, "No hay gastos fijos cargados. Se dan de alta en "
                        "Caja y gastos → Gastos fijos.")
            return
        if not confirmar(
            self, f"Se van a generar los gastos fijos de {MESES[mes]} {anio}.\n"
                  "Los que ya existan no se duplican. ¿Sigo?"):
            return
        n = repo.GastosFijos.generar_mes(anio, mes)
        self.refrescar()
        self.cambio_datos.emit()
        aviso(self, f"{n} movimiento(s) generado(s)." if n
              else "No había gastos pendientes de generar.")

    def cerrar(self) -> None:
        anio, mes = self._periodo()
        try:
            if any(d["cerrado"] for d in self.datos.values()):
                if not confirmar(
                    self, f"{MESES[mes]} {anio} ya está cerrado.\n"
                          "¿Querés reabrirlo para corregir algo?"):
                    return
                repo.Cierre.reabrir(anio, mes)
                self.refrescar()
                aviso(self, "Período reabierto.")
                return
            if not confirmar(
                self, f"Se va a cerrar {MESES[mes]} {anio}.\n\n"
                      "Queda guardada una foto de los números del mes. "
                      "Podés reabrirlo después si hace falta. ¿Sigo?"):
                return
            n = repo.Cierre.cerrar(anio, mes)
            self.refrescar()
            aviso(self, f"Mes cerrado. Se guardó el resumen de {n} moneda(s).")
        except repo.ErrorNegocio as e:
            error(self, str(e))

    def exportar_pdf(self) -> None:
        anio, mes = self._periodo()
        if not self.datos:
            aviso(self, "No hay datos para exportar en este período.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar cierre", f"Cierre_{anio}{mes:02d}.pdf",
            "PDF (*.pdf)")
        if not ruta:
            return
        try:
            p = documentos.cierre(anio, mes, list(self.datos.values()),
                                  Path(ruta))
            aviso(self, f"Cierre exportado:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo exportar:\n{e}")

    def pagar_liquidacion(self) -> None:
        f = self.tabla_liq.fila_actual()
        if not f:
            aviso(self, "Seleccioná una liquidación.")
            return
        if f["pagada"]:
            aviso(self, "Esa liquidación ya está pagada.")
            return
        anio, mes = self._periodo()
        importe = calculos.money(f["importe"], f["moneda"])
        if not confirmar(
            self, f"Se registra el pago de {importe} a {f['vendedor']} "
                  f"por {MESES[mes]} {anio}.\n\n"
                  "Se genera el egreso en la caja. ¿Sigo?"):
            return
        try:
            repo.Liquidaciones.marcar_pagada(
                int(f["vendedor_id"]), anio, mes, f["moneda"],
                float(f["importe"]))
            self.refrescar()
            self.cambio_datos.emit()
            aviso(self, "Liquidación registrada y egreso generado.")
        except repo.ErrorNegocio as e:
            error(self, str(e))

    def pdf_liquidacion(self) -> None:
        f = self.tabla_liq.fila_actual()
        if not f:
            aviso(self, "Seleccioná una liquidación.")
            return
        anio, mes = self._periodo()
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar liquidación",
            f"Liquidacion_{f['vendedor'].split(',')[0]}_{anio}{mes:02d}.pdf",
            "PDF (*.pdf)")
        if not ruta:
            return
        try:
            det = repo.Liquidaciones.detalle(
                int(f["vendedor_id"]), anio, mes, f["moneda"])
            p = documentos.liquidacion(
                f["vendedor"], anio, mes, f["moneda"], det,
                float(f["importe"]), Path(ruta))
            aviso(self, f"Liquidación generada:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo generar:\n{e}")
