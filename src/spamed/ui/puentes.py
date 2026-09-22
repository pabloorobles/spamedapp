"""Puentes Python <-> JavaScript, uno por pantalla migrada a HTML/CSS/JS.

Cada Puente es una envoltura FINA sobre core/repo.py: no repite logica de
negocio, solo la expone. Las respuestas van como texto JSON (no QVariant
directo) a proposito: es un formato que se puede razonar con precision de
punta a punta sin depender de como PySide6 marshalla cada tipo, algo que
en este proyecto no se pudo verificar contra un QWebEngineView real (ver
MIGRACION_WEB.md).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from ..core import db, documentos, repo


def _json(datos: Any) -> str:
    return json.dumps(datos, default=str, ensure_ascii=False)


def _error(mensaje: str) -> str:
    return _json({"ok": False, "error": mensaje})


class PuenteInicio(QObject):
    """Ver recursos/web/inicio/. Envuelve repo.Reportes.dashboard()."""

    @Slot(result=str)
    def monedas(self) -> str:
        return _json(db.listas("moneda"))

    @Slot(result=str)
    def fechas_mes_actual(self) -> str:
        hoy = date.today()
        return _json({"desde": hoy.replace(day=1).isoformat(),
                      "hasta": hoy.isoformat()})

    @Slot(str, str, str, result=str)
    def dashboard(self, moneda: str, desde: str, hasta: str) -> str:
        try:
            datos = repo.Reportes.dashboard(
                moneda=moneda or "",
                desde=desde or None,
                hasta=hasta or None,
            )
        except Exception as e:  # noqa: BLE001 - nunca dejar el JS colgado
            return _error(str(e))
        datos["ok"] = True
        return _json(datos)


class PuenteCaja(QObject):
    """Ver recursos/web/caja/. Envuelve repo.Caja."""

    # Mismo rol que VistaCaja.cambio_datos en la version de Qt: avisa a
    # VentanaPrincipal para que refresque las demas pantallas cuando algo
    # en Caja pudo afectarlas (ej. el saldo de un file).
    cambio_datos = Signal()

    def __init__(self, ventana=None, parent: QObject | None = None):
        super().__init__(parent)
        # Para centrar los dialogos nativos (guardar recibo, comprobantes)
        # sobre la ventana real. None tambien funciona, solo queda sin
        # parentesco visual.
        self._ventana = ventana

    @Slot(result=str)
    def listas(self) -> str:
        return _json({
            "monedas": db.listas("moneda"),
            "medios_pago": db.listas("medio_pago"),
            "conceptos_ingreso": db.listas("concepto_ingreso"),
            "conceptos_egreso": db.listas("concepto_egreso"),
        })

    @Slot(str, str, str, str, str, result=str)
    def listar(self, texto: str, tipo: str, moneda: str, desde: str,
              hasta: str) -> str:
        try:
            filas = [dict(f) for f in repo.Caja.listar(
                texto=texto, tipo=tipo, moneda=moneda,
                desde=desde or None, hasta=hasta or None)]
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True, "filas": filas})

    @Slot(int, result=str)
    def obtener(self, id_: int) -> str:
        fila = repo.Caja.obtener(id_)
        return _json({"ok": True, "fila": dict(fila) if fila else None})

    @Slot(result=str)
    def reservas_buscables(self) -> str:
        filas = [
            {"id": r["id"], "file": r["file"], "cliente": r["cliente"],
             "destino": r["destino"], "moneda": r["moneda"]}
            for r in repo.Reservas.listar()
        ]
        return _json(filas)

    @Slot(int, result=str)
    def reserva_info(self, reserva_id: int) -> str:
        r = repo.Reservas.obtener(reserva_id) if reserva_id else None
        if not r:
            return _json(None)
        return _json({
            "file": r["file"], "cliente": r["cliente"], "moneda": r["moneda"],
            "saldo_cliente": r["saldo_cliente"], "saldo_proveedor": r["saldo_proveedor"],
        })

    @Slot(str, result=str)
    def guardar(self, datos_json: str) -> str:
        try:
            datos = json.loads(datos_json)
            id_ = repo.Caja.guardar(datos)
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True, "id": id_})

    @Slot(int, result=str)
    def eliminar(self, id_: int) -> str:
        try:
            repo.Caja.eliminar(id_)
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True})

    @Slot(str, result=str)
    def cambio_moneda(self, datos_json: str) -> str:
        try:
            d = json.loads(datos_json)
            repo.Caja.cambio_moneda(
                fecha=d.get("fecha"),
                moneda_origen=d.get("moneda_origen"),
                monto_origen=float(d.get("monto_origen") or 0),
                moneda_destino=d.get("moneda_destino"),
                monto_destino=float(d.get("monto_destino") or 0),
                medio_pago=d.get("medio_pago"),
                detalle=d.get("detalle"),
            )
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True})

    @Slot(int, result=str)
    def recibo(self, mov_id: int) -> str:
        """Genera el PDF del recibo. El diálogo de "guardar como" es
        nativo de Qt -- no hay forma limpia de pedirlo desde JS, asi que
        esta funcion hace todo de punta a punta y solo avisa el
        resultado."""
        f = repo.Caja.obtener(mov_id)
        if not f or f["tipo"] != "INGRESO" or not f["reserva_id"]:
            return _error("El recibo se emite sobre un cobro asociado a un file.")
        r = repo.Reservas.obtener(int(f["reserva_id"]))
        if not r:
            return _error("No se encontró el file asociado.")
        sugerido = f"Recibo_{r['file']}_{f['id']}.pdf"
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Guardar recibo", sugerido, "PDF (*.pdf)")
        if not ruta:
            return _json({"ok": False, "cancelado": True})
        try:
            p = documentos.recibo(dict(r), dict(f), Path(ruta))
        except Exception as e:  # noqa: BLE001
            return _error(f"No se pudo generar el recibo: {e}")
        return _json({"ok": True, "ruta": str(p)})

    @Slot(int)
    def comprobantes(self, mov_id: int) -> None:
        """Todavia no migrado: abre el dialogo de Qt existente tal cual.
        No devuelve nada -- es una accion, no una consulta."""
        from .maestros import DialogoAdjuntos
        DialogoAdjuntos("movimiento", mov_id, "el movimiento",
                        self._ventana).exec()

    _COLUMNAS = [
        ("fecha", "Fecha"), ("tipo", "Tipo"), ("concepto", "Concepto"),
        ("file", "File"), ("cliente", "Cliente"), ("moneda", "Mon."),
        ("monto", "Monto"), ("medio_pago", "Medio"),
        ("cotizacion", "Cotiz."), ("detalle", "Detalle"),
    ]

    @Slot(str)
    def exportar(self, filas_json: str) -> None:
        """Mismo flujo que Tabla.exportar() (ui/comunes.py): dialogo
        nativo de "guardar como" + Excel o CSV segun la extension, con
        el mismo aviso nativo al terminar (no hay pantalla web esperando
        una respuesta aca, es una accion de una sola vez)."""
        from datetime import datetime

        from .comunes import aviso, error as mostrar_error
        from ..core import config, exportador
        filas = json.loads(filas_json)
        if not filas:
            aviso(self._ventana, "No hay datos para exportar.")
            return
        sugerido = config.dir_exports() / f"Caja_{datetime.now():%Y%m%d}.xlsx"
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Exportar", str(sugerido),
            "Excel (*.xlsx);;CSV (*.csv)")
        if not ruta:
            return
        try:
            p = Path(ruta)
            if p.suffix.lower() == ".csv":
                exportador.a_csv(filas, self._COLUMNAS, p)
            else:
                exportador.a_excel(filas, self._COLUMNAS, p, titulo_hoja="Caja")
            aviso(self._ventana, f"Exportado a:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo exportar:\n{e}")


class PuenteClientes(QObject):
    """Ver recursos/web/clientes/. Envuelve repo.Clientes, Seguimientos
    y TarjetasCliente. "Documentación" (adjuntos) sigue siendo el dialogo
    de Qt que ya existia -- es un subsistema compartido con Vendedores y
    Caja, se migra aparte."""

    cambio_datos = Signal()

    _COLUMNAS = [
        ("apellido", "Apellido"), ("nombre", "Nombre"), ("dni", "DNI"),
        ("telefono", "Teléfono"), ("email", "Email"), ("canal", "Canal"),
        ("facturado", "Facturado"), ("fecha_alta", "Alta"),
    ]

    def __init__(self, ventana=None, parent: QObject | None = None):
        super().__init__(parent)
        self._ventana = ventana

    @Slot(result=str)
    def listas(self) -> str:
        return _json({"canales": db.listas("canal")})

    @Slot(str, bool, int, bool, result=str)
    def listar(self, texto: str, solo_activos: bool, mes_cumple: int,
              sin_novedades: bool) -> str:
        try:
            filas = repo.Clientes.listar(texto, solo_activos)
            if mes_cumple:
                filas = [f for f in filas
                        if _mes(f.get("fecha_nac")) == mes_cumple]
            if sin_novedades:
                filas = [f for f in filas if f.get("sin_novedades")]
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True, "filas": filas})

    @Slot(int, result=str)
    def obtener(self, id_: int) -> str:
        fila = repo.Clientes.obtener(id_)
        return _json({"ok": True, "fila": dict(fila) if fila else None})

    @Slot(str, result=str)
    def guardar(self, datos_json: str) -> str:
        try:
            id_ = repo.Clientes.guardar(json.loads(datos_json))
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True, "id": id_})

    @Slot(int, result=str)
    def eliminar(self, id_: int) -> str:
        try:
            repo.Clientes.eliminar(id_)
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True})

    # ---------------------------------------------------------- seguimientos
    @Slot(int, result=str)
    def seguimientos_listar(self, cliente_id: int) -> str:
        return _json([dict(f) for f in repo.Seguimientos.listar(cliente_id)])

    @Slot(str, result=str)
    def seguimiento_guardar(self, datos_json: str) -> str:
        try:
            repo.Seguimientos.guardar(json.loads(datos_json))
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True})

    @Slot(int, result=str)
    def seguimiento_eliminar(self, id_: int) -> str:
        repo.Seguimientos.eliminar(id_)
        return _json({"ok": True})

    # ------------------------------------------------------------- tarjetas
    @Slot(int, result=str)
    def tarjetas_listar(self, cliente_id: int) -> str:
        return _json([dict(f) for f in repo.TarjetasCliente.listar(cliente_id)])

    @Slot(str, result=str)
    def tarjeta_guardar(self, datos_json: str) -> str:
        try:
            repo.TarjetasCliente.guardar(json.loads(datos_json))
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True})

    @Slot(int, result=str)
    def tarjeta_eliminar(self, id_: int) -> str:
        repo.TarjetasCliente.eliminar(id_)
        return _json({"ok": True})

    # -------------------------------------------------- acciones nativas
    @Slot(int, str)
    def documentacion(self, cliente_id: int, nombre: str) -> None:
        from .maestros import DialogoAdjuntos
        DialogoAdjuntos("cliente", cliente_id, nombre, self._ventana).exec()

    @Slot(int, str)
    def estado_cuenta(self, cliente_id: int, apellido: str) -> None:
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Guardar estado de cuenta",
            f"EstadoCuenta_{apellido}.pdf", "PDF (*.pdf)")
        if not ruta:
            return
        from .comunes import aviso, error as mostrar_error
        try:
            datos = repo.Reportes.estado_cuenta(cliente_id)
            p = documentos.estado_cuenta(datos, Path(ruta))
            aviso(self._ventana, f"Estado de cuenta generado:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo generar:\n{e}")

    @Slot(str)
    def exportar(self, filas_json: str) -> None:
        from datetime import datetime

        from .comunes import aviso, error as mostrar_error
        from ..core import config, exportador
        filas = json.loads(filas_json)
        if not filas:
            aviso(self._ventana, "No hay datos para exportar.")
            return
        sugerido = config.dir_exports() / f"Clientes_{datetime.now():%Y%m%d}.xlsx"
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Exportar", str(sugerido),
            "Excel (*.xlsx);;CSV (*.csv)")
        if not ruta:
            return
        try:
            p = Path(ruta)
            if p.suffix.lower() == ".csv":
                exportador.a_csv(filas, self._COLUMNAS, p)
            else:
                exportador.a_excel(filas, self._COLUMNAS, p, titulo_hoja="Clientes")
            aviso(self._ventana, f"Exportado a:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo exportar:\n{e}")


class PuenteVendedores(QObject):
    """Ver recursos/web/vendedores/. Envuelve repo.Vendedores.
    "Documentación" sigue siendo el diálogo nativo de Qt, mismo criterio
    que en Clientes y Caja."""

    cambio_datos = Signal()

    _COLUMNAS = [
        ("apellido", "Apellido"), ("nombre", "Nombre"), ("dni", "DNI"),
        ("telefono", "Teléfono"), ("email", "Email"),
        ("comision_pct", "Comisión %"), ("activo", "Activo"),
    ]

    def __init__(self, ventana=None, parent: QObject | None = None):
        super().__init__(parent)
        self._ventana = ventana

    @Slot(str, bool, result=str)
    def listar(self, texto: str, solo_activos: bool) -> str:
        try:
            filas = [dict(f) for f in repo.Vendedores.listar(texto, solo_activos)]
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True, "filas": filas})

    @Slot(int, result=str)
    def obtener(self, id_: int) -> str:
        fila = repo.Vendedores.obtener(id_)
        return _json({"ok": True, "fila": dict(fila) if fila else None})

    @Slot(str, result=str)
    def guardar(self, datos_json: str) -> str:
        try:
            id_ = repo.Vendedores.guardar(json.loads(datos_json))
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True, "id": id_})

    @Slot(int, result=str)
    def eliminar(self, id_: int) -> str:
        try:
            repo.Vendedores.eliminar(id_)
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True})

    @Slot(int, str)
    def documentacion(self, vendedor_id: int, nombre: str) -> None:
        from .maestros import DialogoAdjuntos
        DialogoAdjuntos("vendedor", vendedor_id, nombre, self._ventana).exec()

    @Slot(str)
    def exportar(self, filas_json: str) -> None:
        from datetime import datetime

        from .comunes import aviso, error as mostrar_error
        from ..core import config, exportador
        filas = json.loads(filas_json)
        if not filas:
            aviso(self._ventana, "No hay datos para exportar.")
            return
        sugerido = config.dir_exports() / f"Vendedores_{datetime.now():%Y%m%d}.xlsx"
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Exportar", str(sugerido),
            "Excel (*.xlsx);;CSV (*.csv)")
        if not ruta:
            return
        try:
            p = Path(ruta)
            if p.suffix.lower() == ".csv":
                exportador.a_csv(filas, self._COLUMNAS, p)
            else:
                exportador.a_excel(filas, self._COLUMNAS, p, titulo_hoja="Vendedores")
            aviso(self._ventana, f"Exportado a:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo exportar:\n{e}")


class PuenteProveedores(QObject):
    """Ver recursos/web/operadores/. Envuelve repo.Proveedores y
    repo.ProveedorVariantes. Las variantes solo aplican a un operador que
    ya existe (necesitan su proveedor_id), igual que en la version de Qt."""

    cambio_datos = Signal()

    _COLUMNAS = [
        ("nombre", "Nombre"), ("tipo", "Tipo"), ("moneda", "Moneda"),
        ("comision_pct", "Comisión"), ("transfiere_neto", "Paga neto"),
        ("contacto", "Contacto"), ("telefono", "Teléfono"),
        ("activo", "Activo"),
    ]

    def __init__(self, ventana=None, parent: QObject | None = None):
        super().__init__(parent)
        self._ventana = ventana

    @Slot(result=str)
    def listas(self) -> str:
        return _json({
            "tipos": db.listas("tipo_proveedor"),
            "monedas": db.listas("moneda"),
        })

    @Slot(str, bool, result=str)
    def listar(self, texto: str, solo_activos: bool) -> str:
        try:
            filas = [dict(f) for f in repo.Proveedores.listar(texto, solo_activos)]
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True, "filas": filas})

    @Slot(int, result=str)
    def obtener(self, id_: int) -> str:
        fila = repo.Proveedores.obtener(id_)
        return _json({"ok": True, "fila": dict(fila) if fila else None})

    @Slot(str, result=str)
    def guardar(self, datos_json: str) -> str:
        try:
            id_ = repo.Proveedores.guardar(json.loads(datos_json))
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True, "id": id_})

    @Slot(int, result=str)
    def eliminar(self, id_: int) -> str:
        try:
            repo.Proveedores.eliminar(id_)
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True})

    # ------------------------------------------------------------- variantes
    @Slot(int, result=str)
    def variantes_listar(self, proveedor_id: int) -> str:
        return _json(repo.ProveedorVariantes.listar(proveedor_id))

    @Slot(str, result=str)
    def variante_guardar(self, datos_json: str) -> str:
        try:
            repo.ProveedorVariantes.guardar(json.loads(datos_json))
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True})

    @Slot(int, result=str)
    def variante_eliminar(self, id_: int) -> str:
        repo.ProveedorVariantes.eliminar(id_)
        return _json({"ok": True})

    @Slot(str)
    def exportar(self, filas_json: str) -> None:
        from datetime import datetime

        from .comunes import aviso, error as mostrar_error
        from ..core import config, exportador
        filas = json.loads(filas_json)
        if not filas:
            aviso(self._ventana, "No hay datos para exportar.")
            return
        sugerido = config.dir_exports() / f"Operadores_{datetime.now():%Y%m%d}.xlsx"
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Exportar", str(sugerido),
            "Excel (*.xlsx);;CSV (*.csv)")
        if not ruta:
            return
        try:
            p = Path(ruta)
            if p.suffix.lower() == ".csv":
                exportador.a_csv(filas, self._COLUMNAS, p)
            else:
                exportador.a_excel(filas, self._COLUMNAS, p, titulo_hoja="Operadores")
            aviso(self._ventana, f"Exportado a:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo exportar:\n{e}")


class PuenteReportes(QObject):
    """Ver recursos/web/reportes/. Envuelve repo.Reportes y los demas
    repos que son fuente de cada informe -- misma dispersion de origenes
    que ya tenia VistaReportes en la version de Qt (ver core/repo.py).
    Los nombres y columnas de cada informe salen de
    tablero.VistaReportes.REPORTES, una sola fuente para las dos capas."""

    def __init__(self, ventana=None, parent: QObject | None = None):
        super().__init__(parent)
        self._ventana = ventana

    @Slot(result=str)
    def metadatos(self) -> str:
        from .tablero import VistaReportes
        reportes = [
            {"nombre": nombre,
             "columnas": [{"campo": c, "titulo": t} for c, t in columnas]}
            for nombre, (_, columnas) in VistaReportes.REPORTES.items()
        ]
        return _json({
            "reportes": reportes,
            "campos_moneda": sorted(VistaReportes.CAMPOS_MONEDA),
        })

    @Slot(str, result=str)
    def datos(self, nombre: str) -> str:
        try:
            filas = self._datos(nombre)
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True, "filas": filas})

    def _clave(self, nombre: str) -> str:
        from .tablero import VistaReportes
        info = VistaReportes.REPORTES.get(nombre)
        if not info:
            raise ValueError(f"Reporte desconocido: {nombre}")
        return info[0]

    def _datos(self, nombre: str) -> list[dict[str, Any]]:
        """Mismo despacho que VistaReportes._datos() (ui/tablero.py) --
        no repetido por gusto: esa version es un metodo de instancia de
        un QWidget, no tiene sentido levantar uno solo para esto."""
        clave = self._clave(nombre)
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

    def _fmt(self, campos_moneda: set[str]):
        def formatear(f: dict[str, Any], k: str) -> Any:
            from ..core import calculos
            if k in campos_moneda:
                return calculos.money(f.get(k), f.get("moneda", ""))
            if k.startswith("fecha_") or k in ("vencimiento", "proximo",
                                               "vto_pasaporte", "dni_vencimiento"):
                return calculos.dd_mm_yyyy(f.get(k))
            if k == "pct_cobrado":
                return calculos.pct(f.get(k))
            return f.get(k)
        return formatear

    @Slot(str)
    def exportar(self, nombre: str) -> None:
        """Excel/CSV con los datos crudos (sin formatear), mismo criterio
        que Tabla.exportar() (ui/comunes.py)."""
        from datetime import datetime

        from .comunes import aviso, error as mostrar_error
        from ..core import config, exportador
        from .tablero import VistaReportes
        try:
            filas = self._datos(nombre)
        except ValueError as e:
            mostrar_error(self._ventana, str(e))
            return
        if not filas:
            aviso(self._ventana, "No hay datos para exportar.")
            return
        _, columnas = VistaReportes.REPORTES[nombre]
        sugerido = config.dir_exports() / (
            f"{nombre.replace(' ', '-')}_{datetime.now():%Y%m%d}.xlsx")
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Exportar", str(sugerido),
            "Excel (*.xlsx);;CSV (*.csv)")
        if not ruta:
            return
        try:
            p = Path(ruta)
            if p.suffix.lower() == ".csv":
                exportador.a_csv(filas, columnas, p)
            else:
                exportador.a_excel(filas, columnas, p, titulo_hoja=nombre)
            aviso(self._ventana, f"Exportado a:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo exportar:\n{e}")

    @Slot(str)
    def exportar_pdf(self, nombre: str) -> None:
        """El mismo informe que se ve en pantalla, con membrete -- mismo
        criterio que VistaReportes.exportar_pdf() en la version de Qt."""
        from .comunes import aviso, error as mostrar_error
        from ..core import documentos
        from .tablero import VistaReportes
        try:
            filas = self._datos(nombre)
        except ValueError as e:
            mostrar_error(self._ventana, str(e))
            return
        if not filas:
            aviso(self._ventana, "No hay datos para exportar.")
            return
        _, columnas = VistaReportes.REPORTES[nombre]
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Guardar informe",
            f"{nombre.replace(' ', '_')}.pdf", "PDF (*.pdf)")
        if not ruta:
            return
        try:
            p = documentos.informe(
                nombre, columnas, filas,
                self._fmt(VistaReportes.CAMPOS_MONEDA),
                subtitulo=f"Generado el {date.today().strftime('%d/%m/%Y')}",
                destino=Path(ruta))
            aviso(self._ventana, f"Informe generado:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo generar el informe:\n{e}")


class PuenteCierre(QObject):
    """Ver recursos/web/cierre/. Envuelve repo.Cierre, repo.Objetivos,
    repo.Liquidaciones, repo.GastosFijos.generar_mes y core/bcra.py (la
    cotizacion ya vivia en este mismo panel en la version de Qt, dentro
    del "Resumen consolidado")."""

    cambio_datos = Signal()

    def __init__(self, ventana=None, parent: QObject | None = None):
        super().__init__(parent)
        self._ventana = ventana

    @Slot(int, int, result=str)
    def comparar(self, anio: int, mes: int) -> str:
        try:
            datos = repo.Cierre.comparar(anio, mes)
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        hoy = date.today()
        en_curso = (anio, mes) >= (hoy.year, hoy.month)
        cerrado = any(d["cerrado"] for d in datos.values())
        estado = ("mes en curso" if en_curso
                  else "cerrado" if cerrado else "abierto, listo para cerrar")
        return _json({"ok": True, "datos": datos, "estado": estado, "cerrado": cerrado})

    @Slot(int, int, result=str)
    def liquidaciones(self, anio: int, mes: int) -> str:
        try:
            filas = repo.Liquidaciones.calcular(anio, mes)
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        for f in filas:
            f["estado"] = "Pagada" if f["pagada"] else "Pendiente"
        return _json({"ok": True, "filas": filas})

    @Slot(int, int, str, result=str)
    def objetivo_obtener(self, anio: int, mes: int, moneda: str) -> str:
        return _json({"ok": True,
                      "importe": repo.Objetivos.obtener(anio, mes, moneda or "PESOS")})

    @Slot(str, result=str)
    def objetivo_guardar(self, datos_json: str) -> str:
        d = json.loads(datos_json)
        try:
            repo.Objetivos.guardar(int(d["anio"]), int(d["mes"]),
                                   d["moneda"] or "PESOS", float(d.get("importe") or 0))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True})

    @Slot(result=str)
    def cotizacion_info(self) -> str:
        from ..core import bcra
        valor, fecha_ = bcra.ultima_guardada()
        return _json({"valor": valor, "fecha": fecha_})

    @Slot(result=str)
    def cotizacion_actualizar(self) -> str:
        from ..core import bcra
        try:
            valor = bcra.actualizar()
        except bcra.ErrorCotizacion as e:
            return _error(str(e))
        return _json({"ok": True, "valor": valor})

    @Slot(float, result=str)
    def cotizacion_guardar_manual(self, valor: float) -> str:
        from ..core import bcra
        if valor <= 0:
            return _error("Cargá un valor mayor a cero.")
        bcra.guardar_manual(valor)
        return _json({"ok": True})

    @Slot(int, int, result=str)
    def generar_gastos(self, anio: int, mes: int) -> str:
        fijos = repo.GastosFijos.listar(solo_activos=True)
        if not fijos:
            return _error(
                "No hay gastos fijos cargados. Se dan de alta en "
                "Caja y gastos → Gastos fijos.")
        n = repo.GastosFijos.generar_mes(anio, mes)
        if n:
            self.cambio_datos.emit()
        return _json({"ok": True, "n": n})

    @Slot(int, int, result=str)
    def cerrar(self, anio: int, mes: int) -> str:
        try:
            n = repo.Cierre.cerrar(anio, mes)
        except repo.ErrorNegocio as e:
            return _error(str(e))
        return _json({"ok": True, "n": n})

    @Slot(int, int, result=str)
    def reabrir(self, anio: int, mes: int) -> str:
        repo.Cierre.reabrir(anio, mes)
        return _json({"ok": True})

    @Slot(str, result=str)
    def pagar_liquidacion(self, datos_json: str) -> str:
        d = json.loads(datos_json)
        try:
            repo.Liquidaciones.marcar_pagada(
                int(d["vendedor_id"]), int(d["anio"]), int(d["mes"]),
                d["moneda"], float(d["importe"]))
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True})

    @Slot(str)
    def pdf_liquidacion(self, datos_json: str) -> None:
        d = json.loads(datos_json)
        anio, mes = int(d["anio"]), int(d["mes"])
        vendedor = d.get("vendedor") or ""
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Guardar liquidación",
            f"Liquidacion_{vendedor.split(',')[0]}_{anio}{mes:02d}.pdf",
            "PDF (*.pdf)")
        if not ruta:
            return
        from .comunes import aviso, error as mostrar_error
        try:
            det = repo.Liquidaciones.detalle(
                int(d["vendedor_id"]), anio, mes, d["moneda"])
            p = documentos.liquidacion(
                vendedor, anio, mes, d["moneda"], det,
                float(d["importe"]), Path(ruta))
            aviso(self._ventana, f"Liquidación generada:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo generar:\n{e}")

    @Slot(int, int)
    def exportar_pdf(self, anio: int, mes: int) -> None:
        from .comunes import aviso, error as mostrar_error
        try:
            datos = repo.Cierre.comparar(anio, mes)
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, str(e))
            return
        if not datos:
            aviso(self._ventana, "No hay datos para exportar en este período.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Guardar cierre", f"Cierre_{anio}{mes:02d}.pdf",
            "PDF (*.pdf)")
        if not ruta:
            return
        try:
            p = documentos.cierre(anio, mes, list(datos.values()), Path(ruta))
            aviso(self._ventana, f"Cierre exportado:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo exportar:\n{e}")


class PuenteCajaGastos(QObject):
    """Ver recursos/web/caja_gastos/. Envuelve repo.GastosFijos,
    repo.Caja (para los gastos extraordinarios) y repo.Arqueos -- las
    tres solapas que tenia VistaCajaGastos en la version de Qt
    (ui/ajustes.py)."""

    cambio_datos = Signal()

    _COLUMNAS_EXTRA = [
        ("fecha", "Fecha"), ("concepto", "Concepto"), ("moneda", "Mon."),
        ("monto", "Monto"), ("medio_pago", "Medio"), ("detalle", "Detalle"),
    ]

    def __init__(self, ventana=None, parent: QObject | None = None):
        super().__init__(parent)
        self._ventana = ventana

    @Slot(result=str)
    def listas(self) -> str:
        return _json({
            "conceptos_egreso": db.listas("concepto_egreso"),
            "monedas": db.listas("moneda"),
            "medios_pago": db.listas("medio_pago"),
            "periodicidades": list(repo.PERIODICIDADES),
        })

    # -------------------------------------------------------- gastos fijos
    @Slot(result=str)
    def gastos_listar(self) -> str:
        from ..core import calculos
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
        return _json({"ok": True, "filas": filas})

    @Slot(int, result=str)
    def gasto_obtener(self, id_: int) -> str:
        for f in repo.GastosFijos.listar():
            if f["id"] == id_:
                return _json({"ok": True, "fila": f})
        return _json({"ok": True, "fila": None})

    @Slot(str, result=str)
    def gasto_guardar(self, datos_json: str) -> str:
        try:
            id_ = repo.GastosFijos.guardar(json.loads(datos_json))
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True, "id": id_})

    @Slot(int, result=str)
    def gasto_eliminar(self, id_: int) -> str:
        repo.GastosFijos.eliminar(id_)
        return _json({"ok": True})

    # -------------------------------------------------- gastos extraordinarios
    @Slot(result=str)
    def extraordinarios_listar(self) -> str:
        filas = [dict(f) for f in repo.Caja.gastos_extraordinarios()]
        return _json({"ok": True, "filas": filas})

    @Slot(int, result=str)
    def extraordinario_obtener(self, id_: int) -> str:
        fila = repo.Caja.obtener(id_)
        return _json({"ok": True, "fila": dict(fila) if fila else None})

    @Slot(str, result=str)
    def extraordinario_guardar(self, datos_json: str) -> str:
        try:
            d = json.loads(datos_json)
            # Un gasto extraordinario es siempre un egreso sin file: eso
            # es lo que lo distingue de un pago a un proveedor o de un
            # gasto fijo generado (ver repo.Caja.gastos_extraordinarios()).
            d["tipo"] = "EGRESO"
            d["reserva_id"] = None
            id_ = repo.Caja.guardar(d)
        except repo.ErrorNegocio as e:
            return _error(str(e))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True, "id": id_})

    @Slot(int, result=str)
    def extraordinario_eliminar(self, id_: int) -> str:
        try:
            repo.Caja.eliminar(id_)
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        self.cambio_datos.emit()
        return _json({"ok": True})

    @Slot(str)
    def extraordinario_exportar(self, filas_json: str) -> None:
        from .comunes import aviso, error as mostrar_error
        from ..core import exportador
        filas = json.loads(filas_json)
        if not filas:
            aviso(self._ventana, "No hay datos para exportar.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self._ventana, "Exportar", "Gastos_extraordinarios.xlsx",
            "Excel (*.xlsx);;CSV (*.csv)")
        if not ruta:
            return
        try:
            p = Path(ruta)
            if p.suffix.lower() == ".csv":
                exportador.a_csv(filas, self._COLUMNAS_EXTRA, p)
            else:
                exportador.a_excel(filas, self._COLUMNAS_EXTRA, p,
                                   titulo_hoja="Gastos_extraordinarios")
            aviso(self._ventana, f"Exportado a:\n{p}")
        except Exception as e:  # noqa: BLE001
            mostrar_error(self._ventana, f"No se pudo exportar:\n{e}")

    # ------------------------------------------------------------- arqueos
    @Slot(result=str)
    def arqueos_listar(self) -> str:
        return _json({"ok": True, "filas": repo.Arqueos.listar()})

    @Slot(str, str, result=str)
    def arqueo_saldo_sistema(self, moneda: str, fecha: str) -> str:
        saldo = repo.Arqueos.saldo_efectivo(moneda or "PESOS", fecha or None)
        return _json({"saldo": saldo})

    @Slot(str, result=str)
    def arqueo_guardar(self, datos_json: str) -> str:
        try:
            id_ = repo.Arqueos.guardar(json.loads(datos_json))
        except Exception as e:  # noqa: BLE001
            return _error(str(e))
        return _json({"ok": True, "id": id_})

    @Slot(int, result=str)
    def arqueo_eliminar(self, id_: int) -> str:
        repo.Arqueos.eliminar(id_)
        return _json({"ok": True})


class PuenteAjustes(QObject):
    """Ver recursos/web/ajustes/. Alta/baja/orden de los valores de las
    listas desplegables (tabla 'listas') -- misma consulta cruda que
    usaba PanelListas en la version de Qt (ui/ajustes.py), no hay un
    repo.py dedicado para esto."""

    @Slot(result=str)
    def tipos(self) -> str:
        from .ajustes import ETIQUETAS
        return _json([{"clave": c, "etiqueta": e} for c, e in ETIQUETAS.items()])

    @Slot(str, result=str)
    def valores(self, tipo: str) -> str:
        return _json(db.listas(tipo or "moneda"))

    @Slot(str, str, result=str)
    def agregar(self, tipo: str, texto: str) -> str:
        texto = (texto or "").strip()
        if not texto:
            return _error("El valor no puede estar vacío.")
        db.execute(
            "INSERT OR IGNORE INTO listas (tipo, valor, orden) VALUES "
            "(?, ?, (SELECT COALESCE(MAX(orden),0)+1 FROM listas WHERE tipo=?))",
            (tipo, texto, tipo))
        return _json({"ok": True})

    @Slot(str, str, str, result=str)
    def renombrar(self, tipo: str, viejo: str, nuevo: str) -> str:
        nuevo = (nuevo or "").strip()
        if not nuevo:
            return _error("El valor no puede estar vacío.")
        db.execute("UPDATE listas SET valor = ? WHERE tipo = ? AND valor = ?",
                   (nuevo, tipo, viejo))
        return _json({"ok": True})

    @Slot(str, str, result=str)
    def quitar(self, tipo: str, valor: str) -> str:
        db.execute("DELETE FROM listas WHERE tipo = ? AND valor = ?", (tipo, valor))
        return _json({"ok": True})

    @Slot(str, str, result=str)
    def guardar_orden(self, tipo: str, valores_json: str) -> str:
        valores = json.loads(valores_json)
        for i, v in enumerate(valores):
            db.execute("UPDATE listas SET orden = ? WHERE tipo = ? AND valor = ?",
                      (i, tipo, v))
        return _json({"ok": True})


class PuenteHerramientas(QObject):
    """Ver recursos/web/herramientas/. Cada boton dispara una accion que
    ya existia en VentanaPrincipal -- esta pantalla no consulta datos
    propios, es un menu de acciones (ui/herramientas.py::VistaHerramientas
    en la version de Qt). self._ventana tiene que ser la ventana real
    (no None): sin ella no hay donde ejecutar import/backup/etc."""

    def __init__(self, ventana, parent: QObject | None = None):
        super().__init__(parent)
        self._ventana = ventana

    @Slot(result=str)
    def info(self) -> str:
        from ..core import config
        from .comunes import tema_actual
        return _json({
            "tema": tema_actual(),
            "app_nombre": config.APP_NAME,
            "app_version": config.APP_VERSION,
            "carpeta_datos": str(config.dir_datos()),
        })

    @Slot()
    def descargar_plantilla(self) -> None:
        self._ventana.descargar_plantilla()

    @Slot()
    def importar_excel(self) -> None:
        self._ventana.importar_excel()

    @Slot()
    def backup(self) -> None:
        self._ventana.backup()

    @Slot()
    def restaurar(self) -> None:
        self._ventana.restaurar()

    @Slot()
    def abrir_carpeta(self) -> None:
        self._ventana.abrir_carpeta()

    @Slot()
    def alternar_tema(self) -> None:
        self._ventana.alternar_tema()

    @Slot()
    def configurar(self) -> None:
        self._ventana.configurar()

    @Slot()
    def diagnostico(self) -> None:
        self._ventana.diagnostico()

    @Slot()
    def acerca_de(self) -> None:
        self._ventana.acerca_de()


def _mes(valor: Any) -> int | None:
    from ..core import calculos
    f = calculos.a_fecha(valor)
    return f.month if f else None
