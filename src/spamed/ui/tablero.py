"""Tablero de control y reportes."""
from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QScrollArea,
    QVBoxLayout, QWidget,
)

from ..core import calculos, db, repo
from .comunes import COLOR_ESTADO, FechaEdit, Tabla, Tarjeta, boton, color
from .navegacion import Cabecera


class VistaTablero(QWidget):
    """Resumen del estado del negocio al abrir la aplicacion."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setObjectName("lienzo")
        contenido = QWidget()
        contenido.setObjectName("lienzo")
        scroll.setWidget(contenido)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(scroll)

        lay = QVBoxLayout(contenido)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        self.cabecera = Cabecera("Inicio", "")
        lay.addWidget(self.cabecera)

        filtros = QHBoxLayout()
        self.cmb_moneda = QComboBox()
        self.cmb_moneda.addItem("Todas las monedas", "")
        for m in db.listas("moneda"):
            self.cmb_moneda.addItem(m, m)
        self.cmb_moneda.currentIndexChanged.connect(lambda _: self.refrescar())
        self.desde = FechaEdit()
        self.hasta = FechaEdit()
        self.desde.dateChanged.connect(lambda _: self.refrescar())
        self.hasta.dateChanged.connect(lambda _: self.refrescar())
        filtros.addWidget(QLabel("Moneda:"))
        filtros.addWidget(self.cmb_moneda)
        filtros.addWidget(QLabel("Período (caja) desde"))
        filtros.addWidget(self.desde)
        filtros.addWidget(QLabel("hasta"))
        filtros.addWidget(self.hasta)
        filtros.addWidget(boton("Mes actual", self._mes_actual, suave=True))
        filtros.addStretch(1)
        lay.addLayout(filtros)

        self.grid = QGridLayout()
        self.t_cobrar = Tarjeta("A cobrar a clientes", "-", color=color("ok"))
        self.t_pagar = Tarjeta("A pagar a operadores", "-",
                               color=color("error"))
        self.t_ganancia = Tarjeta("Ganancia bruta en curso", "-",
                                  color=color("primario"))
        self.t_mes = Tarjeta("Caja del período", "-", color=color("acento_osc"))
        for i, t in enumerate((self.t_cobrar, self.t_pagar,
                               self.t_ganancia, self.t_mes)):
            self.grid.addWidget(t, 0, i)
        lay.addLayout(self.grid)

        caja_est = QGroupBox("Files por estado")
        self.lay_estados = QHBoxLayout(caja_est)
        lay.addWidget(caja_est)

        caja_al = QGroupBox("Alertas y vencimientos de clientes")
        lay_al = QVBoxLayout(caja_al)
        self.tabla_alertas = Tabla([
            ("file", "File"), ("cliente", "Cliente"), ("estado", "Estado"),
            ("saldo_cliente", "Saldo cliente"),
            ("fecha_vto_reserva", "Vto. reserva"),
            ("fecha_salida", "Salida"), ("aviso", "Alerta"),
        ])
        self.tabla_alertas.setMinimumHeight(200)
        self.lbl_sin_alertas = QLabel(
            "Sin alertas por ahora.\n\nSi todavía no cargaste datos, entrá a "
            "Herramientas → Importar Excel."
        )
        self.lbl_sin_alertas.setObjectName("vacio")
        self.lbl_sin_alertas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sin_alertas.setMinimumHeight(160)
        lay_al.addWidget(self.lbl_sin_alertas)
        lay_al.addWidget(self.tabla_alertas)
        lay.addWidget(caja_al, 1)

        caja_op = QGroupBox("Pagos pendientes a operadores")
        lay_op = QVBoxLayout(caja_op)
        self.tabla_pagos_op = Tabla([
            ("file", "File"), ("proveedor", "Operador"), ("destino", "Destino"),
            ("moneda", "Mon."), ("saldo_proveedor", "Saldo"),
            ("fecha_salida", "Salida"),
        ])
        self.tabla_pagos_op.setMinimumHeight(160)
        self.lbl_sin_pagos_op = QLabel("Sin pagos pendientes a operadores.")
        self.lbl_sin_pagos_op.setObjectName("vacio")
        self.lbl_sin_pagos_op.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sin_pagos_op.setMinimumHeight(100)
        lay_op.addWidget(self.lbl_sin_pagos_op)
        lay_op.addWidget(self.tabla_pagos_op)
        lay.addWidget(caja_op, 1)

        # Arranca mostrando el mes en curso (mismo default que ya calculaba
        # el dashboard), para que los campos no queden vacios en pantalla.
        self._mes_actual()



    def _pintar_marca(self) -> None:
        """Colores de tarjeta acordes al tema activo."""
        for tarjeta, clave in ((self.t_cobrar, "ok"),
                               (self.t_pagar, "error"),
                               (self.t_ganancia, "primario"),
                               (self.t_mes, "acento_osc")):
            tarjeta.set_color(color(clave))

    def _mes_actual(self) -> None:
        hoy = date.today()
        self.desde.set_valor(hoy.replace(day=1).isoformat())
        self.hasta.set_valor(hoy.isoformat())

    def refrescar(self) -> None:
        self._pintar_marca()
        d = repo.Reportes.dashboard(
            moneda=self.cmb_moneda.currentData() or "",
            desde=self.desde.valor(), hasta=self.hasta.valor())
        hoy = date.today().strftime("%d/%m/%Y")
        self.cabecera.set_bajada(
            f"Situación al {hoy}   ·   caja del "
            f"{calculos.dd_mm_yyyy(d['desde'])} al {calculos.dd_mm_yyyy(d['hasta'])}")

        def resumen(clave: str) -> str:
            partes = [
                f"{mon}: {calculos.money(v[clave])}"
                for mon, v in d["por_moneda"].items() if v[clave]
            ]
            return "  ·  ".join(partes) or "-"

        self.t_cobrar.actualizar(
            resumen("a_cobrar"), f"{d['cant_pendientes']} file(s) con saldo"
        )
        self.t_pagar.actualizar(
            resumen("a_pagar"), f"{d['cant_a_pagar']} file(s) a pagar"
        )
        self.t_ganancia.actualizar(
            resumen("ganancia"), f"{d['cant_activas']} file(s) activos"
        )
        mes = "  ·  ".join(
            f"{t['moneda']}: {calculos.money(t['neto'])}"
            for t in d["totales_mes"]
        ) or "-"
        self.t_mes.actualizar(mes, "Neto del período elegido")

        while self.lay_estados.count():
            item = self.lay_estados.takeAt(0)
            w = item.widget()
            if w:
                # setParent(None) los saca ya; deleteLater solo no alcanza y
                # los widgets viejos quedan pintados encima.
                w.setParent(None)
                w.deleteLater()
        for estado, col in COLOR_ESTADO.items():
            n = d["estados"].get(estado, 0)
            et = QLabel(f"{estado}\n{n}")
            et.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Qt lee #RRGGBBAA como ARGB, asi que la transparencia va en rgba().
            r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
            if n:
                et.setStyleSheet(
                    f"color:{col}; font-weight:700; padding:9px 6px;"
                    f"border:2px solid rgba({r},{g},{b},0.45);"
                    f"background:rgba({r},{g},{b},0.08); border-radius:9px;"
                )
            else:
                et.setStyleSheet(
                    f"color:{color('texto_suave')}; font-weight:500;"
                    f"padding:9px 6px;"
                    f"border:1px solid {color('borde')}; border-radius:9px;"
                )
            self.lay_estados.addWidget(et)

        filas = []
        for r in d["alertas"]:
            f = dict(r)
            f["aviso"] = " · ".join(r["alertas"])
            filas.append(f)
        self.lbl_sin_alertas.setVisible(not filas)
        self.tabla_alertas.setVisible(bool(filas))
        self.tabla_alertas.cargar(
            filas,
            formato=lambda f, k: (
                calculos.money(f.get(k), f.get("moneda", "")) if k == "saldo_cliente"
                else calculos.dd_mm_yyyy(f.get(k))
                if k in ("fecha_vto_reserva", "fecha_salida")
                else f.get(k)
            ),
            color_fila=lambda f: color("alerta"),
        )

        pagos_op = d["pagos_operadores"]
        self.lbl_sin_pagos_op.setVisible(not pagos_op)
        self.tabla_pagos_op.setVisible(bool(pagos_op))
        self.tabla_pagos_op.cargar(
            pagos_op,
            formato=lambda f, k: (
                calculos.money(f.get(k), f.get("moneda", ""))
                if k == "saldo_proveedor"
                else calculos.dd_mm_yyyy(f.get(k)) if k == "fecha_salida"
                else f.get(k)
            ),
        )


class VistaReportes(QWidget):
    """Reportes tabulares con exportacion a Excel."""

    REPORTES: dict[str, tuple[str, list[tuple[str, str]]]] = {
        "Cobros pendientes": ("cobros", [
            ("file", "File"), ("cliente", "Cliente"),
            ("cliente_telefono", "Teléfono"), ("estado", "Estado"),
            ("moneda", "Mon."), ("importe_cliente", "Importe"),
            ("cobrado_cliente", "Cobrado"), ("pct_cobrado", "% cobrado"),
            ("saldo_cliente", "Saldo"), ("fecha_vto_reserva", "Vto. reserva"),
            ("dias_a_reserva", "Días"), ("vendedor", "Vendedor"),
        ]),
        "Pagos pendientes a operadores": ("pagos", [
            ("file", "File"), ("proveedor", "Operador"),
            ("destino", "Destino"), ("moneda", "Mon."),
            ("costo_proveedor", "Costo"), ("pagado_proveedor", "Pagado"),
            ("saldo_proveedor", "Saldo"), ("fecha_salida", "Salida"),
        ]),
        "Caja mensual": ("caja", [
            ("anio", "Año"), ("mes", "Mes"), ("moneda", "Moneda"),
            ("ingresos", "Ingresos"), ("egresos", "Egresos"), ("neto", "Neto"),
        ]),
        "Comisiones por vendedor": ("comisiones", [
            ("vendedor", "Vendedor"), ("moneda", "Mon."), ("files", "Files"),
            ("ventas", "Ventas"), ("ganancia", "Ganancia"),
            ("comision", "Comisión"), ("margen", "Margen neto"),
        ]),
        "Ventas por destino": ("destino", [
            ("destino", "Destino"), ("moneda", "Mon."), ("files", "Files"),
            ("ventas", "Ventas"), ("ganancia", "Ganancia"),
        ]),
        "Volumen por operador": ("proveedor", [
            ("proveedor", "Operador"), ("moneda", "Mon."), ("files", "Files"),
            ("costo", "Costo"), ("saldo", "Saldo pendiente"),
        ]),
        "Cambios de moneda": ("cambios", [
            ("fecha", "Fecha"), ("moneda_origen", "Sale"),
            ("monto_origen", "Monto que sale"),
            ("moneda_destino", "Entra"), ("monto_destino", "Monto que entra"),
            ("cotizacion", "Cotización"), ("medio_pago", "Medio"),
        ]),
        "Cuotas por vencer": ("cuotas", [
            ("file", "File"), ("cliente", "Cliente"),
            ("cliente_telefono", "Teléfono"), ("numero", "Cuota"),
            ("vencimiento", "Vence"), ("dias", "Días"),
            ("moneda", "Mon."), ("importe", "Importe"),
        ]),
        "Cumpleaños del mes": ("cumples", [
            ("dia", "Día"), ("cliente", "Cliente"), ("dni", "DNI"),
            ("telefono", "Teléfono"), ("email", "Email"),
        ]),
        "Seguimientos pendientes": ("seguimientos", [
            ("proximo", "Recontactar"), ("cliente", "Cliente"),
            ("cliente_telefono", "Teléfono"), ("file", "File"),
            ("canal", "Canal"), ("nota", "Última nota"),
        ]),
        "Pasaportes por vencer": ("pasaportes", [
            ("nombre", "Pasajero"), ("file", "File"),
            ("pasaporte", "Pasaporte"), ("vto_pasaporte", "Vence"),
            ("fecha_salida", "Viaja el"),
        ]),
        "DNI por vencer": ("dni", [
            ("cliente", "Cliente"), ("dni", "DNI"), ("telefono", "Teléfono"),
            ("email", "Email"), ("dni_vencimiento", "Vence"),
        ]),
        "Tarjetas por vencer": ("tarjetas", [
            ("cliente", "Cliente"), ("cliente_telefono", "Teléfono"),
            ("marca", "Marca"), ("ultimos4", "Terminada en"),
            # Clave distinta a "vencimiento" (la de Cuotas) a propósito: acá
            # es texto libre "MM/AA", no una fecha ISO, y _fmt() no la tiene
            # que confundir con las fechas que sí formatea como dd/mm/aaaa.
            ("vencimiento_tarjeta", "Vence"),
        ]),
        "Origen de clientes": ("canal", [
            ("canal", "Canal"), ("clientes", "Clientes"), ("files", "Files"),
            ("ventas", "Ventas"),
        ]),
        "Encuestas sin responder": ("encuestas", [
            ("file", "File"), ("cliente", "Cliente"),
            ("cliente_telefono", "Teléfono"), ("destino", "Destino"),
            ("fecha_generada", "Generada"),
        ]),
    }

    CAMPOS_MONEDA = {
        "monto_origen", "monto_destino",
        "importe", "importe_cliente", "cobrado_cliente", "saldo_cliente",
        "costo_proveedor", "pagado_proveedor", "saldo_proveedor",
        "ingresos", "egresos", "neto", "ventas", "ganancia",
        "comision", "margen", "costo", "saldo",
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        self.cabecera = Cabecera("Reportes", "")
        self.cabecera.agregar(boton("Actualizar", self.refrescar, suave=True))
        self.cabecera.agregar(boton("Exportar PDF", self.exportar_pdf))
        self.cabecera.agregar(
            boton("Exportar a Excel", self.exportar, primario=True))
        lay.addWidget(self.cabecera)

        barra = QHBoxLayout()
        self.cmb = QComboBox()
        for nombre in self.REPORTES:
            self.cmb.addItem(nombre)
        self.cmb.currentIndexChanged.connect(lambda _: self.refrescar())
        barra.addWidget(QLabel("Reporte:"))
        barra.addWidget(self.cmb, 1)
        lay.addLayout(barra)

        self.tabla = Tabla([("x", "")])
        lay.addWidget(self.tabla)
        self.lbl_pie = QLabel()
        self.lbl_pie.setObjectName("totales")
        lay.addWidget(self.lbl_pie)

    def refrescar(self) -> None:
        nombre = self.cmb.currentText()
        clave, columnas = self.REPORTES[nombre]
        filas = self._datos(clave)

        self.tabla.columnas = columnas
        self.tabla.setColumnCount(len(columnas))
        self.tabla.setHorizontalHeaderLabels([t for _, t in columnas])
        self.tabla.cargar(filas, formato=self._fmt)
        self.cabecera.set_bajada(nombre)
        self.lbl_pie.setText(f"{len(filas)} fila(s)")

    def _datos(self, clave: str) -> list[dict[str, Any]]:
        if clave == "cobros":
            return repo.Reportes.cobros_pendientes()
        if clave == "pagos":
            return repo.Reportes.pagos_pendientes()
        if clave == "caja":
            return [dict(f) for f in repo.Reportes.caja_mensual()]
        if clave == "comisiones":
            return [dict(f) for f in repo.Reportes.comisiones()]
        if clave == "destino":
            return [dict(f) for f in repo.Reportes.por_destino()]
        if clave == "proveedor":
            return [dict(f) for f in repo.Reportes.por_proveedor()]
        if clave == "cuotas":
            return repo.Reportes.cuotas_pendientes()
        if clave == "cumples":
            return repo.Reportes.cumpleanos()
        if clave == "seguimientos":
            return repo.Reportes.seguimientos_pendientes()
        if clave == "pasaportes":
            return repo.Pasajeros.pasaportes_por_vencer()
        if clave == "cambios":
            return repo.Caja.cambios()
        if clave == "canal":
            return [dict(f) for f in repo.Reportes.por_canal()]
        if clave == "encuestas":
            return repo.Encuestas.pendientes()
        if clave == "dni":
            return repo.Clientes.dni_por_vencer()
        if clave == "tarjetas":
            filas = repo.TarjetasCliente.por_vencer()
            for f in filas:
                f["vencimiento_tarjeta"] = f.get("vencimiento")
            return filas
        return []

    def _fmt(self, f: dict[str, Any], k: str) -> Any:
        if k in self.CAMPOS_MONEDA:
            return calculos.money(f.get(k), f.get("moneda", ""))
        if k.startswith("fecha_") or k in ("vencimiento", "proximo",
                                           "vto_pasaporte", "dni_vencimiento"):
            return calculos.dd_mm_yyyy(f.get(k))
        if k == "pct_cobrado":
            return calculos.pct(f.get(k))
        return f.get(k)

    def exportar(self) -> None:
        self.tabla.exportar(self, self.cmb.currentText().replace(" ", "_"))

    def exportar_pdf(self) -> None:
        """El mismo informe que se ve en pantalla, con membrete."""
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        from ..core import documentos
        from .comunes import aviso, error
        filas = self.tabla.datos()
        if not filas:
            aviso(self, "No hay datos para exportar.")
            return
        nombre = self.cmb.currentText()
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar informe",
            f"{nombre.replace(' ', '_')}.pdf", "PDF (*.pdf)")
        if not ruta:
            return
        try:
            p = documentos.informe(
                nombre, self.tabla.columnas, filas, self._fmt,
                subtitulo=f"Generado el {date.today().strftime('%d/%m/%Y')}",
                destino=Path(ruta))
            aviso(self, f"Informe generado:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo generar el informe:\n{e}")
