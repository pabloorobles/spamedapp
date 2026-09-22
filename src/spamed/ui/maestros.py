"""ABM de Clientes, Vendedores y Proveedores."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QVBoxLayout, QWidget,
)

from ..core import calculos, db, repo
from .comunes import (
    BarraBusqueda, ComboLista, ComboTexto, FechaEdit, Tabla, aviso, boton,
    confirmar, error,
)
from .navegacion import Cabecera


# =============================================================== base

class VistaMaestro(QWidget):
    """Grilla + barra de acciones. Las subclases definen columnas y dialogo."""

    cambio_datos = Signal()

    titulo = ""
    columnas: list[tuple[str, str]] = []

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.cabecera = Cabecera(self.titulo, "")
        self.cabecera.agregar(boton("Nuevo", self.nuevo, primario=True))
        lay.addWidget(self.cabecera)

        barra = QHBoxLayout()
        barra.setSpacing(8)
        self.busqueda = BarraBusqueda(f"Buscar {self.titulo.lower()}...")
        self.busqueda.cambio.connect(lambda _: self.refrescar())
        self.chk_activos = QCheckBox("Solo activos")
        self.chk_activos.stateChanged.connect(lambda _: self.refrescar())
        barra.addWidget(self.busqueda, 1)
        barra.addWidget(self.chk_activos)
        barra.addWidget(boton("Editar", self.editar))
        barra.addWidget(boton("Eliminar", self.eliminar, suave=True))
        barra.addWidget(boton("Exportar", self.exportar, suave=True))
        lay.addLayout(barra)

        self.tabla = Tabla(self.columnas)
        self.tabla.doubleClicked.connect(lambda _: self.editar())
        lay.addWidget(self.tabla)

    # --- a implementar por subclase
    def consultar(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def dialogo(self, datos: dict[str, Any] | None) -> QDialog:
        raise NotImplementedError

    def borrar(self, id_: int) -> None:
        raise NotImplementedError

    def formato(self, fila: dict[str, Any], clave: str) -> Any:
        return fila.get(clave)

    # --- comunes
    def refrescar(self) -> None:
        filas = self.consultar()
        self.tabla.cargar(filas, formato=self.formato)
        self.cabecera.set_bajada(
            f"{len(filas)} registro(s)" if filas
            else "Sin registros. Cargá uno con Nuevo, o importá el Excel "
                 "desde Herramientas.")

    def nuevo(self) -> None:
        if self.dialogo(None).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def editar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná una fila.")
            return
        if self.dialogo(f).exec():
            self.refrescar()
            self.cambio_datos.emit()

    def eliminar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná una fila.")
            return
        if not confirmar(self, "¿Eliminar el registro seleccionado?"):
            return
        try:
            self.borrar(int(f["id"]))
            self.refrescar()
        except repo.ErrorNegocio as e:
            error(self, str(e))

    def exportar(self) -> None:
        self.tabla.exportar(self, self.titulo)


class DialogoBase(QDialog):
    def __init__(self, titulo: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(520)
        self._lay = QVBoxLayout(self)
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._lay.addLayout(self.form)
        self.botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botones.button(
            QDialogButtonBox.StandardButton.Save
        ).setText("Guardar")
        self.botones.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("Cancelar")
        self.botones.accepted.connect(self.guardar)
        self.botones.rejected.connect(self.reject)
        self._lay.addWidget(self.botones)

    def guardar(self) -> None:
        raise NotImplementedError


# =============================================================== clientes

class DialogoCliente(DialogoBase):
    def __init__(self, datos: dict[str, Any] | None, parent=None):
        super().__init__("Cliente", parent)
        self.id_ = int(datos["id"]) if datos else None

        self.dni = QLineEdit()
        self.nombre = QLineEdit()
        self.apellido = QLineEdit()
        self.telefono = QLineEdit()
        self.email = QLineEdit()
        self.direccion = QLineEdit()
        self.fecha_nac = FechaEdit()
        self.dni_vencimiento = FechaEdit()
        self.fecha_alta = FechaEdit(opcional=False)
        self.canal = ComboLista("canal")
        self.detalle_canal = QLineEdit()
        self.observaciones = QPlainTextEdit()
        self.observaciones.setMaximumHeight(70)
        self.activo = QCheckBox("Activo")
        self.activo.setChecked(True)

        self.form.addRow("DNI *", self.dni)
        self.form.addRow("Apellido *", self.apellido)
        self.form.addRow("Nombre *", self.nombre)
        self.form.addRow("Teléfono", self.telefono)
        self.form.addRow("Email", self.email)
        self.form.addRow("Dirección", self.direccion)
        self.form.addRow("Cumpleaños", self.fecha_nac)
        self.form.addRow("Vencimiento del DNI", self.dni_vencimiento)
        self.form.addRow("Fecha de alta", self.fecha_alta)
        self.form.addRow("¿Cómo nos conoció?", self.canal)
        self.form.addRow("Detalle", self.detalle_canal)
        self.form.addRow("Observaciones", self.observaciones)
        self.form.addRow("", self.activo)

        if datos:
            d = repo.Clientes.obtener(self.id_) or {}
            self.dni.setText(str(d["dni"] or ""))
            self.nombre.setText(d["nombre"] or "")
            self.apellido.setText(d["apellido"] or "")
            self.telefono.setText(d["telefono"] or "")
            self.email.setText(d["email"] or "")
            self.direccion.setText(d["direccion"] or "")
            self.fecha_nac.set_valor(d["fecha_nac"])
            self.dni_vencimiento.set_valor(d["dni_vencimiento"])
            self.fecha_alta.set_valor(d["fecha_alta"])
            self.canal.set_valor(d["canal"])
            self.detalle_canal.setText(d["detalle_canal"] or "")
            self.observaciones.setPlainText(d["observaciones"] or "")
            self.activo.setChecked(bool(d["activo"]))

    def guardar(self) -> None:
        datos = {
            "id": self.id_,
            "dni": self.dni.text().strip(),
            "nombre": self.nombre.text().strip(),
            "apellido": self.apellido.text().strip(),
            "telefono": self.telefono.text().strip(),
            "email": self.email.text().strip(),
            "direccion": self.direccion.text().strip(),
            "fecha_nac": self.fecha_nac.valor(),
            "dni_vencimiento": self.dni_vencimiento.valor(),
            "fecha_alta": self.fecha_alta.valor(),
            "canal": self.canal.valor(),
            "detalle_canal": self.detalle_canal.text().strip(),
            "observaciones": self.observaciones.toPlainText().strip(),
            "activo": 1 if self.activo.isChecked() else 0,
        }
        try:
            repo.Clientes.guardar(datos)
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class DialogoSeguimiento(QDialog):
    """Registra un contacto con el cliente y cuándo hay que volver a llamarlo."""

    def __init__(self, cliente_id: int, parent=None):
        super().__init__(parent)
        self.cliente_id = cliente_id
        self.setWindowTitle("Seguimiento del cliente")
        self.setMinimumSize(620, 480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.fecha = FechaEdit(opcional=False)
        self.fecha.hoy()
        self.canal = ComboLista("canal_contacto")
        self.nota = QPlainTextEdit()
        self.nota.setMaximumHeight(80)
        self.nota.setPlaceholderText("Qué se habló")
        self.proximo = FechaEdit()
        form.addRow("Fecha", self.fecha)
        form.addRow("Canal", self.canal)
        form.addRow("Nota *", self.nota)
        form.addRow("Volver a contactar", self.proximo)
        lay.addLayout(form)

        barra = QHBoxLayout()
        barra.addWidget(boton("Registrar contacto", self.registrar,
                              primario=True))
        barra.addWidget(boton("Borrar seleccionado", self.borrar, suave=True))
        barra.addStretch(1)
        lay.addLayout(barra)

        self.tabla = Tabla([
            ("fecha", "Fecha"), ("canal", "Canal"), ("nota", "Nota"),
            ("proximo", "Recontactar"), ("file", "File"),
        ])
        lay.addWidget(self.tabla)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        bb.rejected.connect(self.accept)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)
        self.refrescar()

    def refrescar(self) -> None:
        self.tabla.cargar(
            repo.Seguimientos.listar(self.cliente_id),
            formato=lambda f, k: (calculos.dd_mm_yyyy(f.get(k))
                                  if k in ("fecha", "proximo") else f.get(k)))

    def registrar(self) -> None:
        try:
            repo.Seguimientos.guardar({
                "cliente_id": self.cliente_id,
                "fecha": self.fecha.valor(),
                "canal": self.canal.valor(),
                "nota": self.nota.toPlainText().strip(),
                "proximo": self.proximo.valor(),
            })
            self.nota.clear()
            self.proximo.limpiar()
            self.refrescar()
        except repo.ErrorNegocio as e:
            error(self, str(e))

    def borrar(self) -> None:
        f = self.tabla.fila_actual()
        if f and confirmar(self, "¿Borrar el contacto seleccionado?"):
            repo.Seguimientos.eliminar(int(f["id"]))
            self.refrescar()


class DialogoAdjuntos(QDialog):
    """Documentación de un cliente, un vendedor, o el comprobante de un
    movimiento de caja puntual.

    Sirve para las tres entidades: se le pasa 'cliente', 'vendedor' o
    'movimiento' y arma la consulta con la clave que corresponda.
    """

    def __init__(self, entidad: str, id_: int, nombre: str = "", parent=None):
        super().__init__(parent)
        if entidad not in ("cliente", "vendedor", "movimiento"):
            raise ValueError(f"Entidad no contemplada: {entidad}")
        self.entidad = entidad
        self.id_ = id_
        self.setWindowTitle(
            f"Documentación de {nombre}" if nombre else "Documentación")
        self.setMinimumSize(680, 460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)

        ayuda = QLabel(
            "DNI, pasaporte, contratos, lo que necesites tener a mano. Se "
            "guarda el enlace al archivo, no una copia: si después lo movés "
            "de carpeta, el enlace deja de funcionar.")
        ayuda.setObjectName("tarjetaDetalle")
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)

        barra = QHBoxLayout()
        barra.addWidget(boton("Agregar archivo…", self.agregar, primario=True))
        barra.addWidget(boton("Abrir", self.abrir))
        barra.addWidget(boton("Quitar", self.quitar, suave=True))
        barra.addStretch(1)
        lay.addLayout(barra)

        self.tabla = Tabla([
            ("titulo", "Archivo"), ("ruta", "Ubicación"),
            ("agregado_en", "Agregado"),
        ])
        self.tabla.doubleClicked.connect(lambda _: self.abrir())
        lay.addWidget(self.tabla)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        bb.rejected.connect(self.accept)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)
        self.refrescar()

    def _clave(self) -> dict[str, int]:
        return {f"{self.entidad}_id": self.id_}

    def refrescar(self) -> None:
        self.tabla.cargar(repo.Adjuntos.listar(**self._clave()))

    def agregar(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Elegí los archivos", "",
            "Documentos e imágenes (*.pdf *.jpg *.jpeg *.png *.docx *.xlsx);;"
            "Todos los archivos (*.*)")
        if not rutas:
            return
        try:
            for ruta in rutas:
                repo.Adjuntos.guardar({"ruta": ruta, **self._clave()})
        except repo.ErrorNegocio as e:
            error(self, str(e))
        self.refrescar()

    def abrir(self) -> None:
        import os
        import subprocess
        from pathlib import Path

        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un archivo de la lista.")
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

    def quitar(self) -> None:
        f = self.tabla.fila_actual()
        if f and confirmar(self, "¿Quitar el enlace? El archivo no se borra."):
            repo.Adjuntos.eliminar(int(f["id"]))
            self.refrescar()


class DialogoTarjeta(QDialog):
    """Alta/edicion de una tarjeta de referencia (nunca el numero completo)."""

    def __init__(self, cliente_id: int, datos: dict[str, Any] | None,
                 parent=None):
        super().__init__(parent)
        self.cliente_id = cliente_id
        self.id_ = int(datos["id"]) if datos else None
        self.setWindowTitle("Tarjeta")
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.marca = QLineEdit()
        self.marca.setPlaceholderText("Visa, Mastercard, Amex…")
        self.ultimos4 = QLineEdit()
        self.ultimos4.setMaxLength(4)
        self.ultimos4.setPlaceholderText("1234")
        self.vencimiento = QLineEdit()
        self.vencimiento.setPlaceholderText("MM/AA, ej. 08/27")
        self.nota = QLineEdit()

        form.addRow("Marca", self.marca)
        form.addRow("Últimos 4 dígitos", self.ultimos4)
        form.addRow("Vencimiento", self.vencimiento)
        form.addRow("Nota", self.nota)
        lay.addLayout(form)

        aviso_seg = QLabel(
            "Solo de referencia: nunca cargues el número completo ni el "
            "código de seguridad.")
        aviso_seg.setObjectName("tarjetaDetalle")
        aviso_seg.setWordWrap(True)
        lay.addWidget(aviso_seg)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.guardar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        if datos:
            self.marca.setText(datos.get("marca") or "")
            self.ultimos4.setText(datos.get("ultimos4") or "")
            self.vencimiento.setText(datos.get("vencimiento") or "")
            self.nota.setText(datos.get("nota") or "")

    def guardar(self) -> None:
        try:
            repo.TarjetasCliente.guardar({
                "id": self.id_,
                "cliente_id": self.cliente_id,
                "marca": self.marca.text().strip(),
                "ultimos4": self.ultimos4.text().strip(),
                "vencimiento": self.vencimiento.text().strip(),
                "nota": self.nota.text().strip(),
            })
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class DialogoTarjetas(QDialog):
    """Tarjetas de referencia de un cliente: alta, ver, quitar."""

    def __init__(self, cliente_id: int, nombre: str = "", parent=None):
        super().__init__(parent)
        self.cliente_id = cliente_id
        self.setWindowTitle(f"Tarjetas de {nombre}" if nombre else "Tarjetas")
        self.setMinimumSize(560, 420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)

        ayuda = QLabel(
            "Solo a modo de referencia, para saber con qué tarjeta suele "
            "pagar. Nunca se guarda el número completo ni el código de "
            "seguridad — no sirve para cobrar.")
        ayuda.setObjectName("tarjetaDetalle")
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)

        barra = QHBoxLayout()
        barra.addWidget(boton("Agregar tarjeta", self.nueva, primario=True))
        barra.addWidget(boton("Editar", self.editar))
        barra.addWidget(boton("Quitar", self.quitar, suave=True))
        barra.addStretch(1)
        lay.addLayout(barra)

        self.tabla = Tabla([
            ("marca", "Marca"), ("ultimos4", "Terminada en"),
            ("vencimiento", "Vencimiento"), ("nota", "Nota"),
        ])
        self.tabla.doubleClicked.connect(lambda _: self.editar())
        lay.addWidget(self.tabla)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        bb.rejected.connect(self.accept)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)

        self.refrescar()

    def refrescar(self) -> None:
        self.tabla.cargar(repo.TarjetasCliente.listar(self.cliente_id))

    def nueva(self) -> None:
        if DialogoTarjeta(self.cliente_id, None, self).exec():
            self.refrescar()

    def editar(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná una tarjeta.")
            return
        if DialogoTarjeta(self.cliente_id, f, self).exec():
            self.refrescar()

    def quitar(self) -> None:
        f = self.tabla.fila_actual()
        if f and confirmar(self, "¿Quitar esta tarjeta?"):
            repo.TarjetasCliente.eliminar(int(f["id"]))
            self.refrescar()


MESES_CORTO = ("", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago",
              "Sep", "Oct", "Nov", "Dic")


class VistaClientes(VistaMaestro):
    titulo = "Clientes"
    columnas = [
        ("id", "ID"), ("apellido", "Apellido"), ("nombre", "Nombre"),
        ("dni", "DNI"), ("telefono", "Teléfono"), ("email", "Email"),
        ("canal", "Canal"), ("fecha_nac", "Cumpleaños"),
        ("files", "Files"),
        ("files_en_curso", "En curso"), ("files_finalizados", "Finalizados"),
        ("files_cancelados", "Cancelados"),
        ("facturado", "Facturado"),
        ("ultima_interaccion", "Última interacción"), ("alertas", "Alertas"),
        ("fecha_alta", "Alta"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        # Acciones propias de clientes, ademas del ABM comun.
        self.cabecera.agregar(boton("Seguimiento", self.seguimiento))
        self.cabecera.agregar(boton("Documentación", self.documentacion))
        self.cabecera.agregar(boton("Tarjetas…", self.tarjetas))
        self.cabecera.agregar(boton("Estado de cuenta", self.estado_cuenta))

        filtros = QHBoxLayout()
        filtros.setSpacing(8)
        self.cmb_mes_cumple = QComboBox()
        self.cmb_mes_cumple.addItem("Cumpleaños: todo el año", 0)
        for i, nombre in enumerate(MESES_CORTO):
            if i:
                self.cmb_mes_cumple.addItem(f"Cumple en {nombre}", i)
        self.cmb_mes_cumple.currentIndexChanged.connect(lambda _: self.refrescar())
        self.chk_sin_novedades = QCheckBox(
            f"Sin novedades hace +{repo.Clientes.DIAS_SIN_NOVEDADES // 30} meses")
        self.chk_sin_novedades.stateChanged.connect(lambda _: self.refrescar())
        filtros.addWidget(self.cmb_mes_cumple)
        filtros.addWidget(self.chk_sin_novedades)
        filtros.addStretch(1)
        self.layout().insertLayout(2, filtros)

    def documentacion(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un cliente.")
            return
        DialogoAdjuntos("cliente", int(f["id"]),
                        f"{f['apellido']}, {f['nombre']}", self).exec()

    def tarjetas(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un cliente.")
            return
        DialogoTarjetas(int(f["id"]),
                        f"{f['apellido']}, {f['nombre']}", self).exec()

    def seguimiento(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un cliente.")
            return
        DialogoSeguimiento(int(f["id"]), self).exec()
        self.cambio_datos.emit()

    def estado_cuenta(self) -> None:
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        from ..core import documentos
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un cliente.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar estado de cuenta",
            f"EstadoCuenta_{f['apellido']}.pdf", "PDF (*.pdf)")
        if not ruta:
            return
        try:
            datos = repo.Reportes.estado_cuenta(int(f["id"]))
            p = documentos.estado_cuenta(datos, Path(ruta))
            aviso(self, f"Estado de cuenta generado:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo generar:\n{e}")

    def consultar(self):
        filas = repo.Clientes.listar(
            self.busqueda.texto(), self.chk_activos.isChecked()
        )
        mes = self.cmb_mes_cumple.currentData() or 0
        if mes:
            filas = [f for f in filas
                    if calculos.a_fecha(f.get("fecha_nac"))
                    and calculos.a_fecha(f["fecha_nac"]).month == mes]
        if self.chk_sin_novedades.isChecked():
            filas = [f for f in filas if f.get("sin_novedades")]
        return filas

    def dialogo(self, datos):
        return DialogoCliente(datos, self)

    def borrar(self, id_):
        repo.Clientes.eliminar(id_)

    def formato(self, fila, clave):
        if clave == "facturado":
            return calculos.money(fila.get(clave))
        if clave in ("fecha_alta", "fecha_nac", "ultima_interaccion"):
            return calculos.dd_mm_yyyy(fila.get(clave))
        if clave == "alertas":
            return " · ".join(fila.get(clave) or [])
        return fila.get(clave)


# =============================================================== vendedores

class DialogoVendedor(DialogoBase):
    def __init__(self, datos: dict[str, Any] | None, parent=None):
        super().__init__("Vendedor", parent)
        self.id_ = int(datos["id"]) if datos else None

        self.dni = QLineEdit()
        self.nombre = QLineEdit()
        self.apellido = QLineEdit()
        self.telefono = QLineEdit()
        self.email = QLineEdit()
        self.fecha_nac = FechaEdit()
        self.comision = QDoubleSpinBox()
        self.comision.setRange(0, 100)
        self.comision.setDecimals(2)
        self.comision.setSuffix(" %")
        self.activo = QCheckBox("Activo")
        self.activo.setChecked(True)

        self.form.addRow("DNI *", self.dni)
        self.form.addRow("Apellido *", self.apellido)
        self.form.addRow("Nombre *", self.nombre)
        self.form.addRow("Teléfono", self.telefono)
        self.form.addRow("Email", self.email)
        self.form.addRow("Cumpleaños", self.fecha_nac)
        self.form.addRow("Comisión", self.comision)
        self.form.addRow("", self.activo)

        if datos:
            d = repo.Vendedores.obtener(self.id_) or {}
            self.dni.setText(str(d["dni"] or ""))
            self.nombre.setText(d["nombre"] or "")
            self.apellido.setText(d["apellido"] or "")
            self.telefono.setText(d["telefono"] or "")
            self.email.setText(d["email"] or "")
            self.fecha_nac.set_valor(d["fecha_nac"])
            self.comision.setValue(float(d["comision_pct"] or 0))
            self.activo.setChecked(bool(d["activo"]))

    def guardar(self) -> None:
        try:
            repo.Vendedores.guardar({
                "id": self.id_,
                "dni": self.dni.text().strip(),
                "nombre": self.nombre.text().strip(),
                "apellido": self.apellido.text().strip(),
                "telefono": self.telefono.text().strip(),
                "email": self.email.text().strip(),
                "fecha_nac": self.fecha_nac.valor(),
                "comision_pct": self.comision.value(),
                "activo": 1 if self.activo.isChecked() else 0,
            })
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class VistaVendedores(VistaMaestro):
    titulo = "Vendedores"
    columnas = [
        ("id", "ID"), ("apellido", "Apellido"), ("nombre", "Nombre"),
        ("dni", "DNI"), ("telefono", "Teléfono"), ("email", "Email"),
        ("fecha_nac", "Cumpleaños"), ("comision_pct", "Comisión %"),
        ("files_en_curso", "En curso"), ("files_finalizados", "Finalizados"),
        ("files_cancelados", "Cancelados"),
        ("ultima_venta", "Última venta"),
        ("ganancia_generada", "Ganancia generada"),
        ("alertas", "Alertas"), ("activo", "Activo"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cabecera.agregar(boton("Documentación", self.documentacion))

    def documentacion(self) -> None:
        f = self.tabla.fila_actual()
        if not f:
            aviso(self, "Seleccioná un vendedor.")
            return
        DialogoAdjuntos("vendedor", int(f["id"]),
                        f"{f['apellido']}, {f['nombre']}", self).exec()

    def consultar(self):
        return [
            dict(f) for f in repo.Vendedores.listar(
                self.busqueda.texto(), self.chk_activos.isChecked()
            )
        ]

    def dialogo(self, datos):
        return DialogoVendedor(datos, self)

    def borrar(self, id_):
        repo.Vendedores.eliminar(id_)

    def formato(self, fila, clave):
        if clave == "activo":
            return "Sí" if fila.get(clave) else "No"
        if clave == "comision_pct":
            return calculos.pct(fila.get(clave))
        if clave in ("fecha_nac", "ultima_venta"):
            return calculos.dd_mm_yyyy(fila.get(clave))
        if clave == "ganancia_generada":
            # Nunca un total unico: un vendedor puede tener files en varias
            # monedas y no se consolidan (ver CLAUDE.md).
            por_moneda = fila.get(clave) or {}
            return "  ·  ".join(
                calculos.money(monto, mon) for mon, monto in por_moneda.items()
            ) or "-"
        if clave == "alertas":
            return " · ".join(fila.get(clave) or [])
        return fila.get(clave)


# =============================================================== proveedores

class DialogoProveedor(DialogoBase):
    def __init__(self, datos: dict[str, Any] | None, parent=None):
        super().__init__("Operador", parent)
        if datos:
            self.setMinimumSize(600, 620)
        self.id_ = int(datos["id"]) if datos else None

        self.nombre = QLineEdit()
        self.tipo = ComboLista("tipo_proveedor")
        self.moneda = ComboLista("moneda", vacio=False)
        self.comision = QDoubleSpinBox()
        self.comision.setRange(0, 100)
        self.comision.setDecimals(2)
        self.comision.setSuffix(" %")
        self.chk_neto = QCheckBox("Se le transfiere el neto")
        self.chk_neto.setChecked(True)
        self.chk_neto.setToolTip(
            "Tildado: le pagás la venta menos tu comisión, en un solo egreso.\n"
            "Sin tildar: le pagás el total y él te devuelve la comisión aparte.")
        self.contacto = QLineEdit()
        self.telefono = QLineEdit()
        self.email = QLineEdit()
        self.observaciones = QPlainTextEdit()
        self.observaciones.setMaximumHeight(70)
        self.activo = QCheckBox("Activo")
        self.activo.setChecked(True)

        self.form.addRow("Nombre *", self.nombre)
        self.form.addRow("Tipo", self.tipo)
        self.form.addRow("Moneda habitual", self.moneda)
        self.form.addRow("Comisión general", self.comision)
        self.form.addRow("", self.chk_neto)
        self.form.addRow("Contacto", self.contacto)
        self.form.addRow("Teléfono", self.telefono)
        self.form.addRow("Email", self.email)
        self.form.addRow("Observaciones", self.observaciones)
        self.form.addRow("", self.activo)

        if datos:
            d = repo.Proveedores.obtener(self.id_) or {}
            self.nombre.setText(d["nombre"] or "")
            self.tipo.set_valor(d["tipo"])
            self.moneda.set_valor(d["moneda"])
            self.comision.setValue(float(d["comision_pct"] or 0))
            self.chk_neto.setChecked(bool(d["transfiere_neto"]))
            self.contacto.setText(d["contacto"] or "")
            self.telefono.setText(d["telefono"] or "")
            self.email.setText(d["email"] or "")
            self.observaciones.setPlainText(d["observaciones"] or "")
            self.activo.setChecked(bool(d["activo"]))

            # Las variantes necesitan que el operador ya exista (tienen su
            # propio proveedor_id): solo se muestran al editar uno guardado.
            variantes_box = QGroupBox("Variantes por tipo de viaje y moneda")
            vlay = QVBoxLayout(variantes_box)
            ayuda_var = QLabel(
                "Si este operador cobra distinto según sea un viaje nacional "
                "o internacional, o según la moneda, cargalo acá (hasta 4 "
                "combinaciones). El file elige el tipo de viaje y la "
                "variante que corresponda se usa sola; si no hay ninguna "
                "cargada para esa combinación, se usa la comisión general "
                "de arriba.")
            ayuda_var.setWordWrap(True)
            ayuda_var.setObjectName("tarjetaDetalle")
            vlay.addWidget(ayuda_var)
            self.tabla_var = Tabla([
                ("tipo_viaje", "Tipo de viaje"), ("moneda", "Moneda"),
                ("comision_pct", "Comisión"), ("transfiere_neto", "Paga neto"),
            ])
            self.tabla_var.doubleClicked.connect(lambda _: self._var_editar())
            vlay.addWidget(self.tabla_var)
            barra_var = QHBoxLayout()
            barra_var.addWidget(
                boton("Agregar variante", self._var_nueva, primario=True))
            barra_var.addWidget(boton("Editar", self._var_editar))
            barra_var.addWidget(boton("Quitar", self._var_borrar, suave=True))
            barra_var.addStretch(1)
            vlay.addLayout(barra_var)
            self._lay.insertWidget(1, variantes_box)
            self._cargar_variantes()

    def _cargar_variantes(self) -> None:
        self.tabla_var.cargar(
            repo.ProveedorVariantes.listar(self.id_),
            formato=lambda f, k: (
                calculos.pct(f.get(k)) if k == "comision_pct"
                else "Sí" if k == "transfiere_neto" and f.get(k)
                else "No" if k == "transfiere_neto" else f.get(k)))

    def _var_nueva(self) -> None:
        if DialogoVariante(self.id_, None, self).exec():
            self._cargar_variantes()

    def _var_editar(self) -> None:
        f = self.tabla_var.fila_actual()
        if not f:
            aviso(self, "Seleccioná una variante.")
            return
        if DialogoVariante(self.id_, f, self).exec():
            self._cargar_variantes()

    def _var_borrar(self) -> None:
        f = self.tabla_var.fila_actual()
        if f and confirmar(self, "¿Quitar esta variante? El operador vuelve "
                                 "a usar la comisión general para esa "
                                 "combinación."):
            repo.ProveedorVariantes.eliminar(int(f["id"]))
            self._cargar_variantes()

    def guardar(self) -> None:
        try:
            repo.Proveedores.guardar({
                "id": self.id_,
                "nombre": self.nombre.text().strip(),
                "tipo": self.tipo.valor(),
                "moneda": self.moneda.valor() or "PESOS",
                "comision_pct": self.comision.value(),
                "transfiere_neto": 1 if self.chk_neto.isChecked() else 0,
                "contacto": self.contacto.text().strip(),
                "telefono": self.telefono.text().strip(),
                "email": self.email.text().strip(),
                "observaciones": self.observaciones.toPlainText().strip(),
                "activo": 1 if self.activo.isChecked() else 0,
            })
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class DialogoVariante(QDialog):
    """Comisión y forma de pago de un operador para una combinación puntual
    de tipo de viaje y moneda."""

    def __init__(self, proveedor_id: int, datos: dict[str, Any] | None,
                 parent=None):
        super().__init__(parent)
        self.proveedor_id = proveedor_id
        self.id_ = int(datos["id"]) if datos else None
        self.setWindowTitle("Variante del operador")
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.tipo_viaje = QComboBox()
        self.tipo_viaje.addItem("Nacional", "Nacional")
        self.tipo_viaje.addItem("Internacional", "Internacional")
        self.moneda = ComboLista("moneda", vacio=False)
        self.comision = QDoubleSpinBox()
        self.comision.setRange(0, 100)
        self.comision.setDecimals(2)
        self.comision.setSuffix(" %")
        self.chk_neto = QCheckBox("Se le transfiere el neto")
        self.chk_neto.setChecked(True)

        form.addRow("Tipo de viaje *", self.tipo_viaje)
        form.addRow("Moneda *", self.moneda)
        form.addRow("Comisión *", self.comision)
        form.addRow("", self.chk_neto)
        lay.addLayout(form)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.guardar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        if datos:
            idx = self.tipo_viaje.findData(datos.get("tipo_viaje"))
            if idx >= 0:
                self.tipo_viaje.setCurrentIndex(idx)
            self.moneda.set_valor(datos.get("moneda"))
            self.comision.setValue(float(datos.get("comision_pct") or 0))
            self.chk_neto.setChecked(bool(datos.get("transfiere_neto")))

    def guardar(self) -> None:
        try:
            repo.ProveedorVariantes.guardar({
                "id": self.id_,
                "proveedor_id": self.proveedor_id,
                "tipo_viaje": self.tipo_viaje.currentData(),
                "moneda": self.moneda.valor() or "PESOS",
                "comision_pct": self.comision.value(),
                "transfiere_neto": 1 if self.chk_neto.isChecked() else 0,
            })
            self.accept()
        except repo.ErrorNegocio as e:
            error(self, str(e))


class VistaProveedores(VistaMaestro):
    titulo = "Operadores"
    columnas = [
        ("id", "ID"), ("nombre", "Nombre"), ("tipo", "Tipo"),
        ("moneda", "Moneda"), ("comision_pct", "Comisión"),
        ("transfiere_neto", "Paga neto"), ("contacto", "Contacto"),
        ("telefono", "Teléfono"), ("files", "Files"),
        ("facturado", "Facturación"), ("activo", "Activo"),
    ]

    def consultar(self):
        return [
            dict(f) for f in repo.Proveedores.listar(
                self.busqueda.texto(), self.chk_activos.isChecked()
            )
        ]

    def dialogo(self, datos):
        return DialogoProveedor(datos, self)

    def borrar(self, id_):
        repo.Proveedores.eliminar(id_)

    def formato(self, fila, clave):
        if clave == "activo":
            return "Sí" if fila.get(clave) else "No"
        if clave == "transfiere_neto":
            return "Sí" if fila.get(clave) else "No"
        if clave == "comision_pct":
            return calculos.pct(fila.get(clave))
        if clave == "facturado":
            por_moneda = fila.get(clave) or {}
            return "  ·  ".join(
                calculos.money(monto, mon) for mon, monto in por_moneda.items()
            ) or "-"
        return fila.get(clave)

