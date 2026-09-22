"""Gestion de reservas (files): grilla, filtros y formulario completo."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ..core import calculos, db, repo
from .comunes import (
    COLOR_ESTADO, BarraBusqueda, ComboConAlta, ComboLista, ComboTexto,
    FechaEdit, FlowLayout, MontoEdit, Tabla, aviso, boton, color, confirmar,
    error,
)
from .navegacion import Cabecera


def _ultimo(tabla: str) -> int | None:
    f = db.query_one(f"SELECT id FROM {tabla} ORDER BY id DESC LIMIT 1")
    return f["id"] if f else None


def alta_cliente(padre) -> int | None:
    from .maestros import DialogoCliente
    return _ultimo("clientes") if DialogoCliente(None, padre).exec() else None


def alta_vendedor(padre) -> int | None:
    from .maestros import DialogoVendedor
    return _ultimo("vendedores") if DialogoVendedor(None, padre).exec() else None


def alta_proveedor(padre) -> int | None:
    from .maestros import DialogoProveedor
    return _ultimo("proveedores") if DialogoProveedor(None, padre).exec() else None


# ============================================================ formulario

class DialogoReserva(QDialog):
    """Alta y edicion de un file, con resumen economico en vivo."""

    def __init__(self, reserva_id: int | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.reserva_id = reserva_id
        self._cargando = True
        self.setWindowTitle("Reserva" if reserva_id else "Nueva reserva")
        self.setMinimumSize(880, 620)

        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._tab_general(), "Datos generales")
        tabs.addTab(self._tab_viaje(), "Detalle del viaje")
        tabs.addTab(self._tab_servicios(), "Servicios")
        tabs.addTab(self._tab_pasajeros(), "Pasajeros")
        tabs.addTab(self._tab_cuotas(), "Plan de pagos")
        tabs.addTab(self._tab_movimientos(), "Movimientos")
        tabs.addTab(self._tab_adjuntos(), "Adjuntos")
        lay.addWidget(tabs)
        lay.addWidget(self._panel_resumen())

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.guardar)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)

        if reserva_id:
            self._cargar_reserva(reserva_id)
        else:
            self.file.setText(repo.Reservas.sugerir_file())
            self.f_cotizacion.hoy()
        self._cargando = False
        self._totales_servicios()
        self._recalcular()

    # ------------------------------------------------------------- tabs
    def _tab_general(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)

        izq = QFormLayout()
        izq.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.file = QLineEdit()
        self.cliente = ComboConAlta(
            lambda: [(f["id"], f"{f['apellido']}, {f['nombre']} ({f['dni']})")
                     for f in repo.Clientes.listar(solo_activos=True)],
            alta_cliente, tooltip="Cargar un cliente nuevo")
        self.vendedor = ComboConAlta(
            lambda: [(f["id"], f"{f['apellido']}, {f['nombre']}")
                     for f in repo.Vendedores.listar(solo_activos=True)],
            alta_vendedor, tooltip="Cargar un vendedor nuevo")
        self.proveedor = ComboConAlta(
            lambda: [(f["id"], f["nombre"])
                     for f in repo.Proveedores.listar(solo_activos=True)],
            alta_proveedor, tooltip="Cargar un operador nuevo")
        self.proveedor.cambio.connect(self._proveedor_cambio)
        self.tipo_viaje = QComboBox()
        self.tipo_viaje.addItem("(no aplica)", "")
        self.tipo_viaje.addItem("Nacional", "Nacional")
        self.tipo_viaje.addItem("Internacional", "Internacional")
        self.tipo_viaje.setToolTip(
            "Si el operador tiene variantes cargadas para esta combinación "
            "de tipo de viaje y moneda, esa comisión se usa sola.")
        self.tipo_viaje.currentIndexChanged.connect(self._proveedor_cambio)
        self.destino = QLineEdit()
        self.pasajeros = QSpinBox()
        self.pasajeros.setRange(1, 99)
        izq.addRow("File *", self.file)
        izq.addRow("Cliente *", self.cliente)
        izq.addRow("Vendedor *", self.vendedor)
        izq.addRow("Operador *", self.proveedor)
        izq.addRow("Tipo de viaje", self.tipo_viaje)
        izq.addRow("Destino", self.destino)
        izq.addRow("Pasajeros", self.pasajeros)

        der = QFormLayout()
        der.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.moneda = ComboLista("moneda", vacio=False)
        # La variante del operador depende de moneda + tipo de viaje: un
        # cambio de moneda tiene que reevaluar cual variante corresponde.
        self.moneda.currentTextChanged.connect(lambda _: self._proveedor_cambio())
        self.importe = MontoEdit()
        self.costo = MontoEdit()
        self.importe.valueChanged.connect(self._recalcular)
        self.costo.valueChanged.connect(self._recalcular)
        self.f_cotizacion = FechaEdit()
        self.f_reserva = FechaEdit()
        self.f_vto_sena = FechaEdit()
        self.f_vto_reserva = FechaEdit()
        self.f_voucher = FechaEdit()
        der.addRow("Moneda *", self.moneda)
        der.addRow("Importe de venta", self.importe)
        der.addRow("Importe neto del operador", self.costo)
        der.addRow("Fecha cotización", self.f_cotizacion)
        der.addRow("Fecha reserva", self.f_reserva)
        der.addRow("Vto. seña", self.f_vto_sena)
        der.addRow("Vto. reserva", self.f_vto_reserva)
        der.addRow("Entrega de voucher", self.f_voucher)

        self.comision_prov = QDoubleSpinBox()
        self.comision_prov.setRange(-1, 100)
        self.comision_prov.setDecimals(2)
        self.comision_prov.setSpecialValueText("(usa la del operador)")
        self.comision_prov.setSuffix(" %")
        self.comision_prov.setValue(-1)
        self.comision_prov.valueChanged.connect(self._recalcular)
        self.chk_neto = QCheckBox("Se le transfiere el neto")
        self.chk_neto.setTristate(False)
        self.chk_neto.setChecked(True)
        self.chk_neto.stateChanged.connect(lambda _: self._recalcular())
        der.addRow("Comisión del mayorista", self.comision_prov)
        der.addRow("", self.chk_neto)

        self.comision_pct = QDoubleSpinBox()
        self.comision_pct.setRange(-1, 100)
        self.comision_pct.setDecimals(2)
        self.comision_pct.setSpecialValueText("(usa la del vendedor)")
        self.comision_pct.setSuffix(" %")
        self.comision_pct.setValue(-1)
        self.comision_monto = MontoEdit()
        self.comision_monto.setSpecialValueText("(calculada por %)")
        self.comision_pct.valueChanged.connect(self._recalcular)
        self.comision_monto.valueChanged.connect(self._recalcular)
        der.addRow("Comisión % del file", self.comision_pct)
        der.addRow("Comisión fija", self.comision_monto)

        lay.addLayout(izq, 1)
        lay.addLayout(der, 1)
        return w

    def _tab_viaje(self) -> QWidget:
        w = QWidget()
        lay = QFormLayout(w)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.f_salida = FechaEdit()
        self.f_regreso = FechaEdit()
        self.transporte = ComboLista("transporte")
        self.hotel = QLineEdit()
        self.regimen = ComboLista("regimen")
        self.excursiones = QPlainTextEdit()
        self.excursiones.setMaximumHeight(70)
        self.notas = QPlainTextEdit()
        self.notas.setMaximumHeight(90)
        lay.addRow("Fecha de salida", self.f_salida)
        lay.addRow("Fecha de regreso", self.f_regreso)
        lay.addRow("Transporte", self.transporte)
        lay.addRow("Hotel", self.hotel)
        lay.addRow("Régimen", self.regimen)
        lay.addRow("Excursiones", self.excursiones)
        lay.addRow("Notas", self.notas)
        return w

    def _sub_tabla(self, columnas, alta, editar, borrar, ayuda):
        """Bloque estandar: ayuda, tabla y botones de ABM."""
        w = QWidget()
        lay = QVBoxLayout(w)
        et = QLabel(ayuda)
        et.setObjectName("tarjetaDetalle")
        et.setWordWrap(True)
        lay.addWidget(et)
        tabla = Tabla(columnas)
        lay.addWidget(tabla)
        barra = QHBoxLayout()
        barra.addWidget(boton("Agregar", alta, primario=True))
        barra.addWidget(boton("Editar", editar))
        barra.addWidget(boton("Quitar", borrar, suave=True))
        barra.addStretch(1)
        lay.addLayout(barra)
        return w, tabla

    def _tab_servicios(self) -> QWidget:
        w, self.tabla_serv = self._sub_tabla(
            [("concepto", "Servicio"), ("proveedor", "Operador"),
             ("detalle", "Detalle"), ("importe_venta", "Venta"),
             ("costo", "Costo")],
            self._serv_nuevo, self._serv_editar, self._serv_borrar,
            "Si el viaje tiene varios operadores (aéreo, hotel, excursiones), "
            "cargá cada uno acá. El costo total del file pasa a ser la suma de "
            "estos servicios en lugar del costo único.")
        self.tabla_serv.doubleClicked.connect(lambda _: self._serv_editar())

        # Totales de la solapa. El importe al cliente lo sigue decidiendo el
        # usuario en Datos generales: aca solo se avisa si no coincide con lo
        # que suman los servicios, y se ofrece copiarlo.
        pie = QHBoxLayout()
        self.lbl_tot_serv = QLabel("Sin servicios cargados.")
        self.lbl_tot_serv.setWordWrap(True)
        self.btn_traer_serv = boton(
            "Traer total al importe", self._serv_traer_total, acento=True)
        self.btn_traer_serv.setToolTip(
            "Copia la suma de las ventas de los servicios al importe al "
            "cliente, en la solapa Datos generales.")
        pie.addWidget(self.lbl_tot_serv, 1)
        pie.addWidget(self.btn_traer_serv)
        w.layout().addLayout(pie)
        return w

    def _totales_servicios(self, recargar: bool = True) -> None:
        """Refresca el pie de la solapa Servicios y avisa si no cuadra.

        Con recargar=False usa el ultimo total leido: lo llama _recalcular(),
        que se dispara en cada tecla del importe y no conviene que consulte
        la base cada vez.
        """
        if not self.reserva_id:
            self.lbl_tot_serv.setText("Guardá el file para cargar servicios.")
            self.btn_traer_serv.setEnabled(False)
            return
        if recargar or not hasattr(self, "_tot_serv"):
            self._tot_serv = repo.Servicios.totales(self.reserva_id)
        venta, costo = self._tot_serv
        mon = self.moneda.valor()
        if venta <= 0 and costo <= 0:
            self.lbl_tot_serv.setText("Sin servicios cargados.")
            self.lbl_tot_serv.setStyleSheet("")
            self.btn_traer_serv.setEnabled(False)
            return

        importe = self.importe.value()
        texto = (f"Suman: venta {calculos.money(venta, mon)} · "
                 f"costo {calculos.money(costo, mon)}")
        # Tolerancia de un centavo, la misma que usa el resto del sistema.
        if venta > 0 and abs(venta - importe) > calculos.TOLERANCIA:
            texto += (f"   ⚠ No coincide con el importe al cliente "
                      f"({calculos.money(importe, mon)})")
            self.lbl_tot_serv.setStyleSheet(
                f"color: {color('alerta')}; font-weight: 600;")
        else:
            self.lbl_tot_serv.setStyleSheet(f"color: {color('ok')};")
        self.lbl_tot_serv.setText(texto)
        self.btn_traer_serv.setEnabled(venta > 0)

    def _serv_traer_total(self) -> None:
        venta, _ = repo.Servicios.totales(self.reserva_id or 0)
        if venta <= 0:
            aviso(self, "Los servicios no tienen importe de venta cargado.")
            return
        self.importe.setValue(venta)
        self._totales_servicios()
        aviso(self, "Importe al cliente actualizado con el total de los "
                    "servicios.\n\nAcordate de guardar el file.")

    def _tab_pasajeros(self) -> QWidget:
        w, self.tabla_pax = self._sub_tabla(
            [("nombre", "Nombre"), ("documento", "Documento"),
             ("pasaporte", "Pasaporte"), ("vto_pasaporte", "Vto. pasaporte")],
            self._pax_nuevo, self._pax_editar, self._pax_borrar,
            "Quiénes viajan. Estos nombres son los que salen en el voucher.")
        self.tabla_pax.doubleClicked.connect(lambda _: self._pax_editar())
        return w

    def _tab_cuotas(self) -> QWidget:
        w, self.tabla_cuotas = self._sub_tabla(
            [("numero", "N°"), ("vencimiento", "Vence"),
             ("importe", "Importe"), ("nota", "Nota")],
            self._cuota_nueva, self._cuota_editar, self._cuota_borrar,
            "Cuándo vence cada pago del cliente. Sirve para el reporte de "
            "cuotas por vencer.")
        lay = w.layout()
        extra = QHBoxLayout()
        extra.addWidget(boton("Generar plan automático", self._plan_auto,
                              acento=True))
        extra.addStretch(1)
        lay.addLayout(extra)
        self.tabla_cuotas.doubleClicked.connect(lambda _: self._cuota_editar())
        return w

    def _tab_adjuntos(self) -> QWidget:
        w, self.tabla_adj = self._sub_tabla(
            [("titulo", "Archivo"), ("ruta", "Ubicación"),
             ("agregado_en", "Agregado")],
            self._adj_nuevo, self._adj_abrir, self._adj_borrar,
            "Vouchers del mayorista, comprobantes, pasaportes. Se guarda el "
            "enlace al archivo, no una copia: si lo movés de carpeta, el "
            "enlace deja de funcionar.")
        self.tabla_adj.doubleClicked.connect(lambda _: self._adj_abrir())
        return w

    def _tab_movimientos(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.tabla_mov = Tabla([
            ("fecha", "Fecha"), ("tipo", "Tipo"), ("concepto", "Concepto"),
            ("medio_pago", "Medio"), ("monto", "Monto"), ("detalle", "Detalle"),
        ])
        lay.addWidget(QLabel(
            "Movimientos de caja asociados a este file. Se cargan desde la "
            "solapa Caja o con el botón Cobrar/Pagar de la grilla."
        ))
        lay.addWidget(self.tabla_mov)
        return w

    def _panel_resumen(self) -> QWidget:
        caja = QGroupBox("Resumen económico")
        lay = QHBoxLayout(caja)
        self.lbl_cobrado = QLabel("-")
        self.lbl_saldo_cli = QLabel("-")
        self.lbl_pagado = QLabel("-")
        self.lbl_saldo_prov = QLabel("-")
        self.lbl_ganancia = QLabel("-")
        self.lbl_comision = QLabel("-")
        self.lbl_margen = QLabel("-")
        self.lbl_estado = QLabel("-")
        neg = QFont()
        neg.setBold(True)
        for etiqueta, lbl in (
            ("Cobrado", self.lbl_cobrado),
            ("Saldo cliente", self.lbl_saldo_cli),
            ("Pagado prov.", self.lbl_pagado),
            ("Saldo prov.", self.lbl_saldo_prov),
            ("Com. agencia", self.lbl_ganancia),
            ("Com. vendedor", self.lbl_comision),
            ("Margen neto", self.lbl_margen),
            ("Estado", self.lbl_estado),
        ):
            col = QVBoxLayout()
            t = QLabel(etiqueta)
            t.setObjectName("tarjetaTitulo")
            lbl.setFont(neg)
            col.addWidget(t)
            col.addWidget(lbl)
            lay.addLayout(col)
        return caja

    # ------------------------------------------------------------ datos
    def _cargar_reserva(self, id_: int) -> None:
        d = repo.Reservas.obtener(id_)
        if not d:
            return
        self._datos = d
        self.file.setText(d["file"])
        self.cliente.set_id(d["cliente_id"])
        self.vendedor.set_id(d["vendedor_id"])
        self.proveedor.set_id(d["proveedor_id"])
        idx_tv = self.tipo_viaje.findData(d.get("tipo_viaje") or "")
        self.tipo_viaje.setCurrentIndex(max(idx_tv, 0))
        self.destino.setText(d["destino"] or "")
        self.pasajeros.setValue(int(d["cant_pasajeros"] or 1))
        self.moneda.set_valor(d["moneda"])
        self.importe.setValue(float(d["importe_cliente"] or 0))
        self.costo.setValue(float(d["costo_proveedor"] or 0))
        self.f_cotizacion.set_valor(d["fecha_cotizacion"])
        self.f_reserva.set_valor(d["fecha_reserva"])
        self.f_vto_sena.set_valor(d["fecha_vto_sena"])
        self.f_vto_reserva.set_valor(d["fecha_vto_reserva"])
        self.f_voucher.set_valor(d["fecha_entrega_voucher"])
        bruto = repo.Reservas.crudo(id_)
        self.comision_pct.setValue(
            float(bruto["comision_pct"]) if bruto and bruto["comision_pct"]
            is not None else -1
        )
        self.comision_monto.setValue(
            float(bruto["comision_monto"]) if bruto and bruto["comision_monto"]
            is not None else 0
        )
        self.comision_prov.setValue(
            float(bruto["comision_prov_pct"])
            if bruto and bruto["comision_prov_pct"] is not None else -1
        )
        self.chk_neto.setChecked(bool(d["transfiere_neto"]))
        self.f_salida.set_valor(d["fecha_salida"])
        self.f_regreso.set_valor(d["fecha_regreso"])
        self.transporte.set_valor(d["transporte"])
        self.hotel.setText(d["hotel"] or "")
        self.regimen.set_valor(d["regimen"])
        self.excursiones.setPlainText(d["excursiones"] or "")
        self.notas.setPlainText(d["notas"] or "")

        self._refrescar_subtablas()
        movs = [dict(m) for m in repo.Caja.listar(reserva_id=id_)]
        self.tabla_mov.cargar(
            movs,
            formato=lambda f, k: (
                calculos.dd_mm_yyyy(f.get(k)) if k == "fecha"
                else calculos.money(f.get(k), f.get("moneda", "")) if k == "monto"
                else f.get(k)
            ),
        )

    def _variante_actual(self) -> dict[str, Any] | None:
        """La variante del operador que corresponde al tipo de viaje y
        moneda elegidos en el file, si existe alguna cargada."""
        pid = self.proveedor.id_actual()
        tipo_viaje = self.tipo_viaje.currentData()
        if not pid or not tipo_viaje:
            return None
        moneda = self.moneda.valor()
        for v in repo.ProveedorVariantes.listar(int(pid)):
            if v["tipo_viaje"] == tipo_viaje and v["moneda"] == moneda:
                return v
        return None

    def _pct_proveedor(self) -> float:
        """% del mayorista: el del file si se cargo, si no la variante que
        corresponda, si no el general del operador."""
        if self.comision_prov.value() >= 0:
            return self.comision_prov.value()
        variante = self._variante_actual()
        if variante:
            return float(variante["comision_pct"])
        pid = self.proveedor.id_actual()
        if pid:
            p = repo.Proveedores.obtener(int(pid))
            if p:
                return float(p["comision_pct"] or 0)
        return 0.0

    def _proveedor_cambio(self) -> None:
        """Al elegir proveedor (o cambiar tipo de viaje/moneda) se toma la
        comision y forma de pago que correspondan."""
        pid = self.proveedor.id_actual()
        if pid:
            p = repo.Proveedores.obtener(int(pid))
            if p:
                variante = self._variante_actual()
                neto = bool(variante["transfiere_neto"]) if variante \
                    else bool(p["transfiere_neto"])
                self.chk_neto.setChecked(neto)
                if p["moneda"] and not self._cargando and not variante:
                    self.moneda.set_valor(p["moneda"])
        self._recalcular()

    def _recalcular(self) -> None:
        moneda = self.moneda.valor()
        importe = self.importe.value()
        d = getattr(self, "_datos", None)
        cobrado = float(d["cobrado_cliente"]) if d else 0.0
        pagado = float(d["pagado_proveedor"]) if d else 0.0

        # Cadena: venta -> comision de la agencia -> comision del vendedor.
        pct_prov = self._pct_proveedor()
        if pct_prov > 0:
            comision_agencia = importe * pct_prov / 100.0
            costo = importe - comision_agencia
            self.costo.setEnabled(False)
            self.costo.blockSignals(True)
            self.costo.setValue(costo)
            self.costo.blockSignals(False)
        else:
            costo = self.costo.value()
            comision_agencia = importe - costo
            self.costo.setEnabled(True)

        if self.comision_monto.value() > 0:
            com_vend = self.comision_monto.value()
        else:
            p = (self.comision_pct.value() if self.comision_pct.value() >= 0
                 else float(d["comision_pct"]) if d else 0.0)
            com_vend = comision_agencia * p / 100.0

        self.lbl_cobrado.setText(calculos.money(cobrado, moneda))
        self.lbl_saldo_cli.setText(calculos.money(importe - cobrado, moneda))
        self.lbl_pagado.setText(calculos.money(pagado, moneda))
        self.lbl_saldo_prov.setText(calculos.money(costo - pagado, moneda))
        self.lbl_ganancia.setText(calculos.money(comision_agencia, moneda))
        self.lbl_comision.setText(calculos.money(com_vend, moneda))
        self.lbl_margen.setText(
            calculos.money(comision_agencia - com_vend, moneda))

        vista = {
            "cancelada": d["cancelada"] if d else 0,
            "importe_cliente": importe,
            "cobrado_cliente": cobrado,
            "saldo_cliente": importe - cobrado,
            "saldo_proveedor": costo - pagado,
            "fecha_salida": self.f_salida.valor(),
            "fecha_regreso": self.f_regreso.valor(),
            "fecha_entrega_voucher": self.f_voucher.valor(),
            "fecha_vto_reserva": self.f_vto_reserva.valor(),
        }
        pct_sena = float(db.parametro("pct_sena", "20") or 20)
        estado = calculos.estado_reserva(vista, pct_sena)
        self.lbl_estado.setText(estado)
        self.lbl_estado.setStyleSheet(
            f"color: {COLOR_ESTADO.get(estado, color('texto'))}; font-weight: 700;"
        )
        # El aviso de descuadre depende del importe, que puede haber cambiado
        # recien: se repinta sin volver a consultar la base.
        if hasattr(self, "lbl_tot_serv"):
            self._totales_servicios(recargar=False)

    # ------------------------------------------- ABM de las sub-tablas

    def _exigir_guardado(self) -> bool:
        """Las sub-tablas necesitan que el file exista en la base."""
        if self.reserva_id:
            return True
        if not confirmar(
            self, "Para cargar esto primero hay que guardar el file.\n"
                  "¿Lo guardo ahora?"):
            return False
        self.guardar(cerrar=False)
        return bool(self.reserva_id)

    def _refrescar_subtablas(self) -> None:
        if not self.reserva_id:
            return
        f = calculos.dd_mm_yyyy
        mon = self.moneda.valor()
        self.tabla_serv.cargar(
            repo.Servicios.listar(self.reserva_id),
            formato=lambda x, k: (calculos.money(x.get(k), mon)
                                  if k in ("importe_venta", "costo")
                                  else x.get(k)))
        self.tabla_pax.cargar(
            repo.Pasajeros.listar(self.reserva_id),
            formato=lambda x, k: (f(x.get(k)) if k == "vto_pasaporte"
                                  else x.get(k)))
        self.tabla_cuotas.cargar(
            repo.Cuotas.listar(self.reserva_id),
            formato=lambda x, k: (f(x.get(k)) if k == "vencimiento"
                                  else calculos.money(x.get(k), mon)
                                  if k == "importe" else x.get(k)))
        self.tabla_adj.cargar(repo.Adjuntos.listar(self.reserva_id))
        self._totales_servicios()
        self._datos = repo.Reservas.obtener(self.reserva_id)
        self._recalcular()

    # servicios
    def _serv_nuevo(self) -> None:
        if self._exigir_guardado() and DialogoServicio(
                self.reserva_id, None, self).exec():
            self._refrescar_subtablas()

    def _serv_editar(self) -> None:
        f = self.tabla_serv.fila_actual()
        if not f:
            aviso(self, "Seleccioná un servicio.")
            return
        if DialogoServicio(self.reserva_id, f, self).exec():
            self._refrescar_subtablas()

    def _serv_borrar(self) -> None:
        f = self.tabla_serv.fila_actual()
        if f and confirmar(self, "¿Quitar el servicio seleccionado?"):
            repo.Servicios.eliminar(int(f["id"]))
            self._refrescar_subtablas()

    # pasajeros
    def _pax_nuevo(self) -> None:
        if self._exigir_guardado() and DialogoPasajero(
                self.reserva_id, None, self).exec():
            self._refrescar_subtablas()

    def _pax_editar(self) -> None:
        f = self.tabla_pax.fila_actual()
        if not f:
            aviso(self, "Seleccioná un pasajero.")
            return
        if DialogoPasajero(self.reserva_id, f, self).exec():
            self._refrescar_subtablas()

    def _pax_borrar(self) -> None:
        f = self.tabla_pax.fila_actual()
        if f and confirmar(self, "¿Quitar el pasajero seleccionado?"):
            repo.Pasajeros.eliminar(int(f["id"]))
            self._refrescar_subtablas()

    # cuotas
    def _cuota_nueva(self) -> None:
        if self._exigir_guardado() and DialogoCuota(
                self.reserva_id, None, self).exec():
            self._refrescar_subtablas()

    def _cuota_editar(self) -> None:
        f = self.tabla_cuotas.fila_actual()
        if not f:
            aviso(self, "Seleccioná una cuota.")
            return
        if DialogoCuota(self.reserva_id, f, self).exec():
            self._refrescar_subtablas()

    def _cuota_borrar(self) -> None:
        f = self.tabla_cuotas.fila_actual()
        if f and confirmar(self, "¿Quitar la cuota seleccionada?"):
            repo.Cuotas.eliminar(int(f["id"]))
            self._refrescar_subtablas()

    def _plan_auto(self) -> None:
        if not self._exigir_guardado():
            return
        if DialogoPlanCuotas(self.reserva_id, self).exec():
            self._refrescar_subtablas()

    # adjuntos
    def _adj_nuevo(self) -> None:
        if not self._exigir_guardado():
            return
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Elegí los archivos a enlazar")
        for ruta in rutas:
            try:
                repo.Adjuntos.guardar(
                    {"reserva_id": self.reserva_id, "ruta": ruta, "titulo": ""})
            except repo.ErrorNegocio as e:
                error(self, str(e))
        if rutas:
            self._refrescar_subtablas()

    def _adj_abrir(self) -> None:
        import os
        import subprocess
        f = self.tabla_adj.fila_actual()
        if not f:
            aviso(self, "Seleccioná un archivo.")
            return
        ruta = f["ruta"]
        if not Path(ruta).exists():
            error(self, f"El archivo ya no está en:\n{ruta}")
            return
        try:
            if os.name == "nt":
                os.startfile(ruta)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", ruta])
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo abrir:\n{e}")

    def _adj_borrar(self) -> None:
        f = self.tabla_adj.fila_actual()
        if f and confirmar(self, "¿Quitar el enlace? El archivo no se borra."):
            repo.Adjuntos.eliminar(int(f["id"]))
            self._refrescar_subtablas()

    # ------------------------------------------------------------ guardar
    def guardar(self, cerrar: bool = True) -> None:
        datos = {
            "id": self.reserva_id,
            "file": self.file.text().strip(),
            "cliente_id": self.cliente.id_actual(),
            "vendedor_id": self.vendedor.id_actual(),
            "proveedor_id": self.proveedor.id_actual(),
            "tipo_viaje": self.tipo_viaje.currentData() or None,
            "destino": self.destino.text().strip(),
            "cant_pasajeros": self.pasajeros.value(),
            "moneda": self.moneda.valor() or "PESOS",
            "importe_cliente": self.importe.value(),
            "costo_proveedor": self.costo.value(),
            "fecha_cotizacion": self.f_cotizacion.valor(),
            "fecha_reserva": self.f_reserva.valor(),
            "fecha_vto_sena": self.f_vto_sena.valor(),
            "fecha_vto_reserva": self.f_vto_reserva.valor(),
            "fecha_entrega_voucher": self.f_voucher.valor(),
            "fecha_salida": self.f_salida.valor(),
            "fecha_regreso": self.f_regreso.valor(),
            "transporte": self.transporte.valor(),
            "hotel": self.hotel.text().strip(),
            "regimen": self.regimen.valor(),
            "excursiones": self.excursiones.toPlainText().strip(),
            "notas": self.notas.toPlainText().strip(),
            "comision_pct": (None if self.comision_pct.value() < 0
                             else self.comision_pct.value()),
            "comision_monto": (None if self.comision_monto.value() <= 0
                               else self.comision_monto.value()),
            "comision_prov_pct": (None if self.comision_prov.value() < 0
                                  else self.comision_prov.value()),
            "transfiere_neto": 1 if self.chk_neto.isChecked() else 0,
        }
        try:
            self.reserva_id = repo.Reservas.guardar(datos)
            if cerrar:
                self.accept()
            else:
                self._datos = repo.Reservas.obtener(self.reserva_id)
                self._refrescar_subtablas()
        except repo.ErrorNegocio as e:
            error(self, str(e))


# ==================================================== dialogos auxiliares

class _DialogoChico(QDialog):
    """Base para los formularios de las sub-tablas."""

    def __init__(self, titulo: str, parent=None, ancho: int = 520):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(ancho)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 20, 20, 16)
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.form.setSpacing(10)
        self._lay.addLayout(self.form)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.guardar)
        bb.rejected.connect(self.reject)
        self._lay.addWidget(bb)

    def guardar(self) -> None:
        raise NotImplementedError


class DialogoServicio(_DialogoChico):
    def __init__(self, reserva_id: int, datos=None, parent=None):
        super().__init__("Servicio del file", parent)
        self.reserva_id = reserva_id
        self.id_ = int(datos["id"]) if datos else None

        self.concepto = ComboLista("servicio", vacio=False)
        self.proveedor = ComboConAlta(
            lambda: [(f["id"], f["nombre"])
                     for f in repo.Proveedores.listar(solo_activos=True)],
            alta_proveedor)
        self.detalle = QLineEdit()
        self.venta = MontoEdit()
        self.costo = MontoEdit()

        self.form.addRow("Servicio *", self.concepto)
        self.form.addRow("Operador *", self.proveedor)
        self.form.addRow("Detalle", self.detalle)
        self.form.addRow("Venta al cliente", self.venta)
        self.form.addRow("Importe neto del operador", self.costo)

        if datos:
            self.concepto.set_valor(datos.get("concepto"))
            self.proveedor.set_id(datos.get("proveedor_id"))
            self.detalle.setText(datos.get("detalle") or "")
            self.venta.setValue(float(datos.get("importe_venta") or 0))
            self.costo.setValue(float(datos.get("costo") or 0))

    def guardar(self) -> None:
        try:
            repo.Servicios.guardar({
                "id": self.id_, "reserva_id": self.reserva_id,
                "proveedor_id": self.proveedor.id_actual(),
                "concepto": self.concepto.valor(),
                "detalle": self.detalle.text().strip(),
                "importe_venta": self.venta.value(),
                "costo": self.costo.value(),
            })
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class DialogoPasajero(_DialogoChico):
    def __init__(self, reserva_id: int, datos=None, parent=None):
        super().__init__("Pasajero", parent)
        self.reserva_id = reserva_id
        self.id_ = int(datos["id"]) if datos else None

        self.nombre = QLineEdit()
        self.documento = QLineEdit()
        self.fecha_nac = FechaEdit()
        self.pasaporte = QLineEdit()
        self.vto = FechaEdit()
        self.obs = QLineEdit()

        self.form.addRow("Nombre completo *", self.nombre)
        self.form.addRow("Documento", self.documento)
        self.form.addRow("Fecha de nacimiento", self.fecha_nac)
        self.form.addRow("Pasaporte", self.pasaporte)
        self.form.addRow("Vencimiento del pasaporte", self.vto)
        self.form.addRow("Observaciones", self.obs)

        if datos:
            self.nombre.setText(datos.get("nombre") or "")
            self.documento.setText(datos.get("documento") or "")
            self.fecha_nac.set_valor(datos.get("fecha_nac"))
            self.pasaporte.setText(datos.get("pasaporte") or "")
            self.vto.set_valor(datos.get("vto_pasaporte"))
            self.obs.setText(datos.get("observaciones") or "")

    def guardar(self) -> None:
        try:
            repo.Pasajeros.guardar({
                "id": self.id_, "reserva_id": self.reserva_id,
                "nombre": self.nombre.text().strip(),
                "documento": self.documento.text().strip(),
                "fecha_nac": self.fecha_nac.valor(),
                "pasaporte": self.pasaporte.text().strip(),
                "vto_pasaporte": self.vto.valor(),
                "observaciones": self.obs.text().strip(),
            })
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class DialogoCuota(_DialogoChico):
    def __init__(self, reserva_id: int, datos=None, parent=None):
        super().__init__("Cuota", parent)
        self.reserva_id = reserva_id
        self.id_ = int(datos["id"]) if datos else None

        self.numero = QSpinBox()
        self.numero.setRange(1, 60)
        self.vence = FechaEdit(opcional=False)
        self.importe = MontoEdit()
        self.nota = QLineEdit()

        self.form.addRow("Número", self.numero)
        self.form.addRow("Vence *", self.vence)
        self.form.addRow("Importe *", self.importe)
        self.form.addRow("Nota", self.nota)

        if datos:
            self.numero.setValue(int(datos.get("numero") or 1))
            self.vence.set_valor(datos.get("vencimiento"))
            self.importe.setValue(float(datos.get("importe") or 0))
            self.nota.setText(datos.get("nota") or "")
        else:
            self.vence.hoy()
            self.numero.setValue(len(repo.Cuotas.listar(reserva_id)) + 1)

    def guardar(self) -> None:
        try:
            repo.Cuotas.guardar({
                "id": self.id_, "reserva_id": self.reserva_id,
                "numero": self.numero.value(),
                "vencimiento": self.vence.valor(),
                "importe": self.importe.value(),
                "nota": self.nota.text().strip(),
            })
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class DialogoPlanCuotas(_DialogoChico):
    """Reparte el saldo pendiente en N cuotas parejas."""

    def __init__(self, reserva_id: int, parent=None):
        super().__init__("Generar plan de pagos", parent)
        self.reserva_id = reserva_id
        r = repo.Reservas.obtener(reserva_id)
        saldo = float(r["saldo_cliente"]) if r else 0.0
        mon = r["moneda"] if r else ""

        self.cantidad = QSpinBox()
        self.cantidad.setRange(1, 36)
        self.cantidad.setValue(3)
        self.primera = FechaEdit(opcional=False)
        self.primera.hoy()
        self.intervalo = QSpinBox()
        self.intervalo.setRange(1, 180)
        self.intervalo.setValue(30)
        self.intervalo.setSuffix(" días")
        self.total = MontoEdit()
        self.total.setValue(max(0.0, saldo))

        self.form.addRow("Cantidad de cuotas", self.cantidad)
        self.form.addRow("Primer vencimiento", self.primera)
        self.form.addRow("Cada", self.intervalo)
        self.form.addRow("Total a repartir", self.total)

        av = QLabel(
            f"Saldo pendiente actual: {calculos.money(saldo, mon)}.\n"
            "Al generar el plan se reemplazan las cuotas que ya tenga el file.")
        av.setObjectName("tarjetaDetalle")
        av.setWordWrap(True)
        self._lay.insertWidget(1, av)

    def guardar(self) -> None:
        try:
            repo.Cuotas.generar_plan(
                self.reserva_id, self.cantidad.value(),
                self.primera.valor(), self.intervalo.value(),
                self.total.value())
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class DialogoCancelar(_DialogoChico):
    """Cancela un file y, si corresponde, registra la devolución al cliente."""

    def __init__(self, reserva_id: int, parent=None):
        super().__init__("Cancelar file", parent)
        self.reserva_id = reserva_id
        r = repo.Reservas.obtener(reserva_id)
        self.r = r
        cobrado = float(r["cobrado_cliente"]) if r else 0.0
        mon = r["moneda"] if r else ""

        self.motivo = ComboLista("motivo_cancelacion")
        self.detalle = QLineEdit()
        self.detalle.setPlaceholderText("Algo más específico (opcional)")
        self.devolucion = MontoEdit()
        self.devolucion.setMaximum(max(0.0, cobrado))
        self.chk_registrar = QCheckBox("Registrar la devolución en la caja")
        self.chk_registrar.setChecked(True)
        self.fecha = FechaEdit(opcional=False)
        self.fecha.hoy()

        self.form.addRow("Motivo", self.motivo)
        self.form.addRow("Detalle", self.detalle)
        self.form.addRow("Devolución al cliente", self.devolucion)
        self.form.addRow("", self.chk_registrar)
        self.form.addRow("Fecha de la devolución", self.fecha)

        av = QLabel(
            f"El cliente pagó {calculos.money(cobrado, mon)}.\n"
            "Si no devolvés nada, dejá el importe en cero. El file queda "
            "cancelado y sale de los totales, pero se conserva el historial.")
        av.setObjectName("tarjetaDetalle")
        av.setWordWrap(True)
        self._lay.insertWidget(0, av)

    def guardar(self) -> None:
        motivo = self.motivo.valor() or ""
        detalle = self.detalle.text().strip()
        completo = f"{motivo}: {detalle}" if motivo and detalle else (motivo or detalle)
        try:
            repo.Reservas.cancelar(
                self.reserva_id, completo,
                self.devolucion.value(),
                self.chk_registrar.isChecked(), self.fecha.valor())
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class DialogoEncuesta(QDialog):
    """Encuesta de satisfacción de un file Finalizado: generarla en PDF y
    cargar la respuesta cuando el cliente contesta. No hay envío ni
    recepción automática, ver PENDIENTES.md.
    """

    def __init__(self, reserva_id: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.reserva_id = reserva_id
        self.r = repo.Reservas.obtener(reserva_id) or {}
        self.setWindowTitle(f"Encuesta — {self.r.get('file', '')}")
        self.setMinimumSize(560, 520)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)

        ayuda = QLabel(
            "Se genera como PDF; la app no la manda sola, la mandás vos por "
            "donde uses siempre (WhatsApp, mail). Cuando el cliente "
            "conteste, elegí la encuesta de la lista y cargá la respuesta "
            "acá abajo.")
        ayuda.setObjectName("tarjetaDetalle")
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)

        lay.addWidget(boton(
            "Generar encuesta en PDF", self._generar, primario=True))

        self.tabla = Tabla([
            ("fecha_generada", "Generada"), ("fecha_respuesta", "Respondida"),
            ("puntaje_atencion", "Atención"),
            ("puntaje_expectativas", "Expectativas"),
            ("puntaje_recomendaria", "Recomienda"),
        ])
        self.tabla.doubleClicked.connect(lambda _: self._cargar_seleccion())
        lay.addWidget(self.tabla)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.sp_atencion = QSpinBox()
        self.sp_atencion.setRange(0, 5)
        self.sp_atencion.setSpecialValueText("(sin responder)")
        self.sp_expectativas = QSpinBox()
        self.sp_expectativas.setRange(0, 5)
        self.sp_expectativas.setSpecialValueText("(sin responder)")
        self.sp_recomendaria = QSpinBox()
        self.sp_recomendaria.setRange(0, 5)
        self.sp_recomendaria.setSpecialValueText("(sin responder)")
        self.comentario = QPlainTextEdit()
        self.comentario.setMaximumHeight(60)
        form.addRow("Atención (1 a 5)", self.sp_atencion)
        form.addRow("Expectativas (1 a 5)", self.sp_expectativas)
        form.addRow("Recomendaría (1 a 5)", self.sp_recomendaria)
        form.addRow("Comentario", self.comentario)
        lay.addLayout(form)
        lay.addWidget(boton(
            "Guardar respuesta", self._guardar_respuesta, acento=True))

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        bb.rejected.connect(self.accept)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)

        self.refrescar()

    def refrescar(self) -> None:
        self.tabla.cargar(
            repo.Encuestas.listar(self.reserva_id),
            formato=lambda f, k: (
                calculos.dd_mm_yyyy(f.get(k))
                if k in ("fecha_generada", "fecha_respuesta") else f.get(k)))

    def _generar(self) -> None:
        from ..core import documentos
        try:
            repo.Encuestas.generar(self.reserva_id)
        except repo.ErrorNegocio as e:
            error(self, str(e))
            return
        self.refrescar()
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar encuesta",
            f"Encuesta_{self.r.get('file', '')}.pdf", "PDF (*.pdf)")
        if not ruta:
            return
        try:
            p = documentos.encuesta(self.r, Path(ruta))
            aviso(self, f"Encuesta generada:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo generar:\n{e}")

    def _cargar_seleccion(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            return
        self.sp_atencion.setValue(int(f.get("puntaje_atencion") or 0))
        self.sp_expectativas.setValue(int(f.get("puntaje_expectativas") or 0))
        self.sp_recomendaria.setValue(int(f.get("puntaje_recomendaria") or 0))
        self.comentario.setPlainText(f.get("comentario") or "")

    def _guardar_respuesta(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Elegí una encuesta de la lista (generá una si "
                        "todavía no hay ninguna).")
            return
        try:
            repo.Encuestas.responder(
                int(f["id"]),
                self.sp_atencion.value() or None,
                self.sp_expectativas.value() or None,
                self.sp_recomendaria.value() or None,
                self.comentario.toPlainText())
            self.refrescar()
            aviso(self, "Respuesta guardada.")
        except repo.ErrorNegocio as e:
            error(self, str(e))


# ================================================================ grilla

# Ayuda de cada pestaña de estado: que significa y que se hace ahi. Ver la
# cadena completa (y por que cambio) en calculos.estado_reserva.
AYUDA_ESTADO: dict[str, str] = {
    "Cotizado": "Se armó la cotización y se le mandó al cliente. Todavía no "
                "dijo que sí.",
    "Reservado": "El cliente dijo que sí, pero todavía no pagó la seña.",
    "Confirmado": "Ya se cobró la seña (o más). Los cobros y pagos se "
                  "registran acá, y se puede adjuntar o exportar el recibo "
                  "de cada uno.",
    "Emitido": "Está todo pagado, cliente y operador. Falta que llegue el "
               "voucher del operador.",
    "En Viaje": "El pasajero está de viaje ahora mismo.",
    "Finalizado": "El viaje ya terminó.",
    "Vencido": "Venció el plazo de reserva y no se llegó a pagar la seña.",
    "Cancelado": "Files cancelados, con el motivo de la cancelación.",
}


class _PanelFiles(QWidget):
    """Filtros + grilla + acciones de un file. Reutilizable: sin
    estado_fijo se comporta como la pestaña "Todos" (con su propio combo de
    estado); con estado_fijo puesto, la pestaña queda anclada a ese estado y
    no hace falta mostrar el combo.
    """

    cambio_datos = Signal()

    def __init__(self, estado_fijo: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.estado_fijo = estado_fijo
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        if estado_fijo:
            ayuda = QLabel(AYUDA_ESTADO.get(estado_fijo, ""))
            ayuda.setObjectName("tarjetaDetalle")
            ayuda.setWordWrap(True)
            lay.addWidget(ayuda)

        filtros = QHBoxLayout()
        self.busqueda = BarraBusqueda("Buscar por file, cliente, destino...")
        self.busqueda.cambio.connect(lambda _: self.refrescar())
        filtros.addWidget(self.busqueda, 1)

        self.cmb_estado: QComboBox | None = None
        if estado_fijo is None:
            self.cmb_estado = QComboBox()
            self.cmb_estado.addItem("Todos los estados", "")
            for e in COLOR_ESTADO:
                self.cmb_estado.addItem(e, e)
            self.cmb_estado.currentIndexChanged.connect(lambda _: self.refrescar())
            filtros.addWidget(self.cmb_estado)

        self.cmb_moneda = QComboBox()
        self.cmb_moneda.addItem("Todas", "")
        for m in db.listas("moneda"):
            self.cmb_moneda.addItem(m, m)
        self.cmb_moneda.currentIndexChanged.connect(lambda _: self.refrescar())
        filtros.addWidget(self.cmb_moneda)
        lay.addLayout(filtros)

        rango = QHBoxLayout()
        self.cmb_campo = QComboBox()
        self.cmb_campo.addItem("Fecha de reserva", "reserva")
        self.cmb_campo.addItem("Fecha de salida", "salida")
        self.cmb_campo.addItem("Vencimiento de reserva", "vencimiento")
        self.cmb_campo.currentIndexChanged.connect(lambda _: self.refrescar())
        self.desde = FechaEdit()
        self.hasta = FechaEdit()
        self.desde.dateChanged.connect(lambda _: self.refrescar())
        self.hasta.dateChanged.connect(lambda _: self.refrescar())
        rango.addWidget(QLabel("Filtrar por"))
        rango.addWidget(self.cmb_campo)
        rango.addWidget(QLabel("desde"))
        rango.addWidget(self.desde)
        rango.addWidget(QLabel("hasta"))
        rango.addWidget(self.hasta)
        rango.addWidget(boton("Limpiar fechas", self._limpiar_fechas,
                              suave=True))
        rango.addStretch(1)
        lay.addLayout(rango)

        # FlowLayout, no QHBoxLayout: con hasta 10 botones en esta fila, un
        # QHBoxLayout los aprieta y recorta el texto en ventanas angostas en
        # vez de acomodarlos en una segunda linea.
        self.acciones = FlowLayout(espacio=8)
        self.acciones.addWidget(boton("Editar", self.editar))
        self.acciones.addWidget(boton("Registrar cobro", self.cobrar, acento=True))
        self.acciones.addWidget(boton("Registrar pago", self.pagar))
        self.acciones.addWidget(boton("Duplicar", self.duplicar))
        self.acciones.addWidget(boton("Cotización", self.cotizacion, suave=True))
        self.acciones.addWidget(boton("Voucher", self.voucher, suave=True))
        self.acciones.addWidget(boton("Cancelar file", self.cancelar, suave=True))
        self.acciones.addWidget(boton("Eliminar", self.eliminar, suave=True))
        self.acciones.addWidget(boton(
            "Exportar", lambda: self.tabla.exportar(self, "Reservas"),
            suave=True))
        if estado_fijo == "Reservado":
            self.acciones.addWidget(boton(
                "Marcar OK del cliente", self._marcar_ok, acento=True))
        elif estado_fijo == "Emitido":
            self.acciones.addWidget(boton(
                "Marcar voucher recibido", self._marcar_voucher, acento=True))
        elif estado_fijo == "Vencido":
            self.acciones.addWidget(boton(
                "Exportar resumen por cliente", self._exportar_vencidos,
                acento=True))
        elif estado_fijo == "Finalizado":
            self.acciones.addWidget(boton(
                "Encuesta de satisfacción", self._encuesta, acento=True))
        lay.addLayout(self.acciones)

        self.COLUMNAS = list(VistaReservas.COLUMNAS)
        if estado_fijo == "Emitido":
            self.COLUMNAS.append(("voucher_recibido", "Voucher operador"))
        elif estado_fijo == "Cancelado":
            self.COLUMNAS.append(("motivo_cancelacion", "Motivo"))

        self.tabla = Tabla(self.COLUMNAS)
        self.tabla.doubleClicked.connect(lambda _: self.editar())
        lay.addWidget(self.tabla)

        self.lbl_totales = QLabel()
        self.lbl_totales.setObjectName("totales")
        lay.addWidget(self.lbl_totales)

    # ------------------------------------------------------------ datos
    def refrescar(self) -> None:
        estado = (self.estado_fijo if self.estado_fijo
                  else (self.cmb_estado.currentData() if self.cmb_estado else ""))
        filas = repo.Reservas.listar(
            texto=self.busqueda.texto(),
            estado=estado or "",
            moneda=self.cmb_moneda.currentData() or "",
            desde=self.desde.valor(), hasta=self.hasta.valor(),
            campo_fecha=self.cmb_campo.currentData() or "reserva",
        )
        for f in filas:
            f["aviso"] = " · ".join(f["alertas"])
        self.tabla.cargar(filas, formato=self._fmt, color_fila=self._color)
        self._totales(filas)

    @staticmethod
    def _fmt(f: dict[str, Any], k: str) -> Any:
        if k in ("importe_cliente", "cobrado_cliente", "saldo_cliente",
                 "costo_proveedor", "saldo_proveedor", "comision_agencia",
                 "ganancia_bruta", "comision_vendedor", "margen_neto"):
            return calculos.money(f.get(k), f.get("moneda", ""))
        if k in ("fecha_vto_reserva", "fecha_salida", "voucher_recibido"):
            return calculos.dd_mm_yyyy(f.get(k))
        return f.get(k)

    @staticmethod
    def _color(f: dict[str, Any]) -> str | None:
        if f.get("cancelada"):
            return color("texto_suave")
        if f.get("alertas"):
            return color("alerta")
        return None

    def _totales(self, filas: list[dict[str, Any]]) -> None:
        acum: dict[str, dict[str, float]] = {}
        for f in filas:
            if f["cancelada"]:
                continue
            a = acum.setdefault(f["moneda"], {"venta": 0, "cobrar": 0, "pagar": 0, "gan": 0})
            a["venta"] += float(f["importe_cliente"] or 0)
            a["cobrar"] += max(0.0, float(f["saldo_cliente"] or 0))
            a["pagar"] += max(0.0, float(f["saldo_proveedor"] or 0))
            a["gan"] += float(f["comision_agencia"] or 0)
        partes = [f"{len(filas)} file(s)"]
        for mon, a in acum.items():
            partes.append(
                f"{mon}: ventas {calculos.money(a['venta'])} · "
                f"a cobrar {calculos.money(a['cobrar'])} · "
                f"a pagar {calculos.money(a['pagar'])} · "
                f"comisión {calculos.money(a['gan'])}"
            )
        self.lbl_totales.setText("      ".join(partes))

    # --------------------------------------------------------- acciones
    def editar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un file.")
            return
        if DialogoReserva(int(f["id"]), self).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def _movimiento(self, tipo: str) -> None:
        from .caja import DialogoMovimiento
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un file.")
            return
        sugerido = (
            max(0.0, float(f["saldo_cliente"])) if tipo == "INGRESO"
            else max(0.0, float(f["saldo_proveedor"]))
        )
        dlg = DialogoMovimiento(
            None, self, tipo=tipo, reserva_id=int(f["id"]),
            moneda=f["moneda"], monto_sugerido=sugerido,
        )
        if dlg.exec():
            self.refrescar()
            self.cambio_datos.emit()

    def cobrar(self) -> None:
        self._movimiento("INGRESO")

    def pagar(self) -> None:
        self._movimiento("EGRESO")

    def voucher(self) -> None:
        from ..core import documentos
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un file.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar voucher", f"Voucher_{f['file']}.pdf", "PDF (*.pdf)")
        if not ruta:
            return
        try:
            rid = int(f["id"])
            movs = [dict(m) for m in repo.Caja.listar(reserva_id=rid)]
            p = documentos.voucher(
                f, movs, repo.Pasajeros.listar(rid),
                repo.Servicios.listar(rid), Path(ruta))
            aviso(self, f"Voucher generado:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo generar el voucher:\n{e}")

    def _limpiar_fechas(self) -> None:
        self.desde.limpiar()
        self.hasta.limpiar()
        self.refrescar()

    def duplicar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná el file a duplicar.")
            return
        nuevo = repo.Reservas.sugerir_file()
        if not confirmar(
            self, f"Se va a crear el file {nuevo} copiando {f['file']}:\n"
                  "servicios, pasajeros y datos del viaje.\n\n"
                  "No se copian los movimientos de caja. ¿Sigo?"):
            return
        try:
            nid = repo.Reservas.duplicar(int(f["id"]), nuevo)
        except repo.ErrorNegocio as e:
            error(self, str(e))
            return
        self.refrescar()
        self.cambio_datos.emit()
        if DialogoReserva(nid, self).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def cotizacion(self) -> None:
        from ..core import documentos
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un file.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar cotización", f"Cotizacion_{f['file']}.pdf",
            "PDF (*.pdf)")
        if not ruta:
            return
        try:
            p = documentos.cotizacion(
                f, repo.Servicios.listar(int(f["id"])),
                repo.Pasajeros.listar(int(f["id"])), Path(ruta))
            aviso(self, f"Cotización generada:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo generar la cotización:\n{e}")

    def cancelar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un file.")
            return
        if f["cancelada"]:
            if confirmar(self, f"¿Reactivar el file {f['file']}?"):
                repo.Reservas.reactivar(int(f["id"]))
                self.refrescar()
                self.cambio_datos.emit()
            return
        if DialogoCancelar(int(f["id"]), self).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def eliminar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un file.")
            return
        if not confirmar(self, f"¿Eliminar definitivamente el file {f['file']}?"):
            return
        try:
            repo.Reservas.eliminar(int(f["id"]))
            self.refrescar()
            self.cambio_datos.emit()
        except repo.ErrorNegocio as e:
            error(self, str(e))

    def _marcar_ok(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un file.")
            return
        if not confirmar(
            self, f"¿Marcar que {f['cliente']} dio el OK a la cotización "
                  f"del file {f['file']}?\n\nTodavía no hace falta que haya "
                  "pagado nada."):
            return
        repo.Reservas.marcar_ok(int(f["id"]))
        self.refrescar()
        self.cambio_datos.emit()

    def _marcar_voucher(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un file.")
            return
        if f.get("voucher_recibido"):
            aviso(self, "Ese file ya tiene el voucher marcado como recibido.")
            return
        if not confirmar(
            self, f"¿Marcar que llegó el voucher del operador para el file "
                  f"{f['file']}?"):
            return
        repo.Reservas.marcar_voucher_recibido(int(f["id"]))
        self.refrescar()
        self.cambio_datos.emit()

    def _exportar_vencidos(self) -> None:
        from ..core import documentos
        filas = sorted(self.tabla.datos(), key=lambda f: f.get("cliente") or "")
        if not filas:
            aviso(self, "No hay files vencidos para exportar.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar resumen de vencidos",
            "Vencidos_por_cliente.pdf", "PDF (*.pdf)")
        if not ruta:
            return
        columnas = [
            ("cliente", "Cliente"), ("cliente_telefono", "Teléfono"),
            ("file", "File"), ("destino", "Destino"), ("moneda", "Mon."),
            ("saldo_cliente", "Saldo"), ("fecha_vto_reserva", "Vto. reserva"),
        ]
        try:
            p = documentos.informe(
                "Files vencidos por cliente", columnas, filas, self._fmt,
                subtitulo=f"Generado el {date.today():%d/%m/%Y}",
                destino=Path(ruta))
            aviso(self, f"Resumen generado:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo generar:\n{e}")

    def _encuesta(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un file.")
            return
        DialogoEncuesta(int(f["id"]), self).exec()


class VistaReservas(QWidget):
    """Files agrupados en pestañas: "Todos" + una por cada estado."""

    cambio_datos = Signal()

    COLUMNAS = [
        ("file", "File"), ("estado", "Estado"), ("cliente", "Cliente"),
        ("destino", "Destino"), ("vendedor", "Vendedor"),
        ("proveedor", "Operador"), ("moneda", "Mon."),
        ("importe_cliente", "Importe de venta"), ("cobrado_cliente", "Cobrado"),
        ("saldo_cliente", "Saldo cli."), ("costo_proveedor", "Importe neto"),
        ("saldo_proveedor", "Saldo oper."), ("ganancia_bruta", "Ganancia bruta"),
        ("comision_vendedor", "Comisión vendedor"),
        ("margen_neto", "Ganancia neta"),
        ("fecha_vto_reserva", "Vto. reserva"), ("fecha_salida", "Salida"),
        ("aviso", "Alertas"),
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.cabecera = Cabecera("Reservas", "")
        self.cabecera.agregar(
            boton("Nueva reserva", self.nueva, primario=True))
        lay.addWidget(self.cabecera)

        self.tabs = QTabWidget()
        self.panel_todos = _PanelFiles(None)
        self.tabs.addTab(self.panel_todos, "Todos")
        self.paneles_estado: dict[str, _PanelFiles] = {}
        for estado in COLOR_ESTADO:
            panel = _PanelFiles(estado)
            self.tabs.addTab(panel, estado)
            self.paneles_estado[estado] = panel
        lay.addWidget(self.tabs)

        for panel in (self.panel_todos, *self.paneles_estado.values()):
            panel.cambio_datos.connect(self._on_cambio)

    def _on_cambio(self) -> None:
        # Un file puede cambiar de estado con la accion de cualquier
        # pestaña (cobrar, marcar OK, etc.): se refrescan todas para que
        # ninguna quede mostrando datos viejos.
        self.refrescar()
        self.cambio_datos.emit()

    def nueva(self) -> None:
        if DialogoReserva(None, self).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def refrescar(self) -> None:
        self.panel_todos.refrescar()
        for panel in self.paneles_estado.values():
            panel.refrescar()
        total = len(self.panel_todos.tabla.datos())
        self.cabecera.set_bajada(
            f"{total} file(s)" if total
            else "Todavía no hay files. Cargá uno o importá el Excel "
                 "desde Herramientas.")
