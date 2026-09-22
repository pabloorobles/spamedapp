"""Repositorios: CRUD de maestros, reservas, caja y consultas de reportes."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from . import calculos, db


class ErrorNegocio(Exception):
    """Error de validacion o de regla de negocio, mostrable al usuario."""


def _campos(tabla: str) -> list[str]:
    return [f["name"] for f in db.query(f"PRAGMA table_info({tabla})")]


def _insertar(tabla: str, datos: dict[str, Any]) -> int:
    validos = set(_campos(tabla))
    datos = {k: v for k, v in datos.items() if k in validos and k != "id"}
    cols = ", ".join(datos)
    marks = ", ".join("?" for _ in datos)
    return db.execute(
        f"INSERT INTO {tabla} ({cols}) VALUES ({marks})", tuple(datos.values())
    )


def _actualizar(tabla: str, id_: int, datos: dict[str, Any]) -> None:
    validos = set(_campos(tabla))
    datos = {k: v for k, v in datos.items() if k in validos and k != "id"}
    if not datos:
        return
    sets = ", ".join(f"{k} = ?" for k in datos)
    db.execute(
        f"UPDATE {tabla} SET {sets} WHERE id = ?", (*datos.values(), id_)
    )


# =========================================================== CLIENTES

class Clientes:
    # Sin novedades (ni seguimiento ni reserva) durante mas de esto: alerta.
    DIAS_SIN_NOVEDADES = 90

    @staticmethod
    def listar(texto: str = "", solo_activos: bool = False) -> list[dict[str, Any]]:
        sql = """SELECT c.*, c.apellido || ', ' || c.nombre AS nom_completo,
                        (SELECT COUNT(*) FROM reservas r WHERE r.cliente_id = c.id) AS files,
                        (SELECT COALESCE(SUM(importe_cliente),0) FROM reservas r
                          WHERE r.cliente_id = c.id AND r.cancelada = 0) AS facturado,
                        (SELECT MAX(fecha) FROM seguimientos s
                          WHERE s.cliente_id = c.id) AS ultimo_seguimiento,
                        (SELECT MAX(COALESCE(fecha_reserva, fecha_cotizacion))
                           FROM reservas r WHERE r.cliente_id = c.id) AS ultima_reserva,
                        (SELECT COUNT(*) FROM v_reservas_saldos v
                          WHERE v.cliente_id = c.id AND v.cancelada = 0
                            AND v.saldo_cliente > 0.01
                            AND v.fecha_vto_reserva IS NOT NULL
                            AND v.fecha_vto_reserva <= date('now', '+7 days')
                        ) AS pagos_por_vencer
                 FROM clientes c WHERE 1=1"""
        p: list[Any] = []
        if solo_activos:
            sql += " AND c.activo = 1"
        if texto:
            sql += (" AND (c.nombre LIKE ? OR c.apellido LIKE ? OR c.dni LIKE ?"
                    " OR c.email LIKE ? OR c.telefono LIKE ?)")
            p += [f"%{texto}%"] * 5
        sql += " ORDER BY c.apellido, c.nombre"
        hoy = date.today()

        # Mismo criterio que Vendedores.listar(): una sola pasada por todos
        # los files, agrupando en Python (evita N+1 consultas).
        por_estado: dict[int, dict[str, int]] = {}
        for r in Reservas.listar():
            grupo = por_estado.setdefault(r["cliente_id"], {})
            grupo[r["estado"]] = grupo.get(r["estado"], 0) + 1

        out = []
        for f in db.query(sql, tuple(p)):
            d = dict(f)
            pipeline = calculos.resumen_pipeline(por_estado.get(d["id"], {}))
            d["files_en_curso"] = pipeline["en_curso"]
            d["files_finalizados"] = pipeline["finalizados"]
            d["files_cancelados"] = pipeline["cancelados"]
            ultima = max((v for v in (d["ultimo_seguimiento"], d["ultima_reserva"])
                         if v), default=None)
            d["ultima_interaccion"] = ultima
            dias_sin = -calculos.dias_hasta(ultima, hoy) if ultima else None
            d["sin_novedades"] = (dias_sin is None or
                                  dias_sin > Clientes.DIAS_SIN_NOVEDADES)
            dias_cumple = calculos.dias_a_cumple(d.get("fecha_nac"), hoy)

            avisos = []
            if d["pagos_por_vencer"]:
                avisos.append(f"{d['pagos_por_vencer']} pago(s) vencido(s) o "
                              "por vencer")
            if dias_cumple is not None and dias_cumple <= 7:
                avisos.append("Cumple hoy" if dias_cumple == 0
                              else f"Cumple en {dias_cumple} día(s)")
            if d["sin_novedades"] and d["files"]:
                # Solo alerta si ya tuvo alguna interaccion antes; un cliente
                # recien cargado sin reservas todavia no es "abandonado".
                if dias_sin is not None:
                    meses = dias_sin // 30
                    avisos.append(
                        f"Sin novedades hace {meses} mes(es)" if meses
                        else f"Sin novedades hace {dias_sin} día(s)")
            d["alertas"] = avisos
            out.append(d)
        return out

    @staticmethod
    def obtener(id_: int) -> sqlite3.Row | None:
        return db.query_one("SELECT * FROM clientes WHERE id = ?", (id_,))

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        if not str(datos.get("dni") or "").strip():
            raise ErrorNegocio("El DNI es obligatorio.")
        if not str(datos.get("apellido") or "").strip():
            raise ErrorNegocio("El apellido es obligatorio.")
        try:
            if datos.get("id"):
                _actualizar("clientes", int(datos["id"]), datos)
                return int(datos["id"])
            return _insertar("clientes", datos)
        except sqlite3.IntegrityError as e:
            raise ErrorNegocio(f"Ya existe un cliente con ese DNI. ({e})") from e

    @staticmethod
    def eliminar(id_: int) -> None:
        usos = db.query_one(
            "SELECT COUNT(*) n FROM reservas WHERE cliente_id = ?", (id_,)
        )
        if usos and usos["n"]:
            raise ErrorNegocio(
                f"No se puede eliminar: el cliente tiene {usos['n']} reserva(s). "
                "Marcalo como inactivo."
            )
        db.execute("DELETE FROM clientes WHERE id = ?", (id_,))

    @staticmethod
    def dni_por_vencer(dias: int = 90) -> list[dict[str, Any]]:
        limite = (date.today() + timedelta(days=dias)).isoformat()
        return [dict(f) for f in db.query(
            """SELECT apellido || ', ' || nombre AS cliente, dni, telefono,
                      email, dni_vencimiento
               FROM clientes
               WHERE dni_vencimiento IS NOT NULL AND dni_vencimiento <> ''
                 AND dni_vencimiento <= ? AND activo = 1
               ORDER BY dni_vencimiento""", (limite,))]


# =========================================================== VENDEDORES

class Vendedores:
    @staticmethod
    def listar(texto: str = "", solo_activos: bool = False) -> list[dict[str, Any]]:
        sql = """SELECT v.*, v.apellido || ', ' || v.nombre AS nom_completo,
                        (SELECT COUNT(*) FROM reservas r WHERE r.vendedor_id = v.id) AS files,
                        (SELECT MAX(COALESCE(fecha_reserva, fecha_cotizacion))
                           FROM reservas r WHERE r.vendedor_id = v.id) AS ultima_venta,
                        (SELECT COUNT(*) FROM v_reservas_saldos vr
                          WHERE vr.vendedor_id = v.id AND vr.cancelada = 0
                            AND vr.saldo_cliente > 0.01) AS cobros_pendientes,
                        (SELECT COUNT(*) FROM v_reservas_saldos vr
                          WHERE vr.vendedor_id = v.id AND vr.cancelada = 0
                            AND vr.saldo_proveedor > 0.01) AS pagos_operador_pendientes
                 FROM vendedores v WHERE 1=1"""
        p: list[Any] = []
        if solo_activos:
            sql += " AND v.activo = 1"
        if texto:
            sql += " AND (v.nombre LIKE ? OR v.apellido LIKE ? OR v.dni LIKE ?)"
            p += [f"%{texto}%"] * 3
        sql += " ORDER BY v.apellido, v.nombre"

        hoy = date.today()
        # El estado del file es derivado en Python (calculos.estado_reserva),
        # no una columna: se cuenta agrupando una sola pasada por todos los
        # files en vez de consultar por vendedor (evita N+1 consultas).
        por_estado: dict[int, dict[str, int]] = {}
        for r in Reservas.listar():
            grupo = por_estado.setdefault(r["vendedor_id"], {})
            grupo[r["estado"]] = grupo.get(r["estado"], 0) + 1

        # Ganancia por vendedor y moneda, sin mezclar pesos con dolares.
        ganancia_por_vend: dict[int, dict[str, float]] = {}
        for g in db.query(
            """SELECT vendedor_id, moneda, SUM(comision_agencia) monto
               FROM v_reservas_saldos WHERE cancelada = 0
               GROUP BY vendedor_id, moneda"""):
            ganancia_por_vend.setdefault(g["vendedor_id"], {})[g["moneda"]] = (
                g["monto"] or 0.0)

        # Comision del mes en curso todavia no liquidada, por vendedor.
        pendiente_liquidar: set[int] = set()
        for f in Liquidaciones.calcular(hoy.year, hoy.month):
            if not f["pagada"]:
                pendiente_liquidar.add(f["vendedor_id"])

        out = []
        for f in db.query(sql, tuple(p)):
            d = dict(f)
            pipeline = calculos.resumen_pipeline(por_estado.get(d["id"], {}))
            d["files_en_curso"] = pipeline["en_curso"]
            d["files_finalizados"] = pipeline["finalizados"]
            d["files_cancelados"] = pipeline["cancelados"]
            # Por moneda, nunca un total unico: ver ganancia_por_vend arriba.
            d["ganancia_generada"] = ganancia_por_vend.get(d["id"], {})
            dias_cumple = calculos.dias_a_cumple(d.get("fecha_nac"), hoy)

            avisos = []
            if dias_cumple is not None and dias_cumple <= 7:
                avisos.append("Cumple hoy" if dias_cumple == 0
                              else f"Cumple en {dias_cumple} día(s)")
            if d["cobros_pendientes"]:
                avisos.append(f"{d['cobros_pendientes']} cobro(s) pendiente(s) "
                              "de cliente")
            if d["pagos_operador_pendientes"]:
                avisos.append(f"{d['pagos_operador_pendientes']} pago(s) "
                              "pendiente(s) a operador")
            if d["id"] in pendiente_liquidar:
                avisos.append("Ganancia del mes pendiente de liquidar")
            d["alertas"] = avisos
            out.append(d)
        return out

    @staticmethod
    def obtener(id_: int) -> sqlite3.Row | None:
        return db.query_one("SELECT * FROM vendedores WHERE id = ?", (id_,))

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        if not str(datos.get("dni") or "").strip():
            raise ErrorNegocio("El DNI es obligatorio.")
        pctv = float(datos.get("comision_pct") or 0)
        if not 0 <= pctv <= 100:
            raise ErrorNegocio("La comision debe estar entre 0 y 100.")
        try:
            if datos.get("id"):
                _actualizar("vendedores", int(datos["id"]), datos)
                return int(datos["id"])
            return _insertar("vendedores", datos)
        except sqlite3.IntegrityError as e:
            raise ErrorNegocio("Ya existe un vendedor con ese DNI.") from e

    @staticmethod
    def eliminar(id_: int) -> None:
        usos = db.query_one(
            "SELECT COUNT(*) n FROM reservas WHERE vendedor_id = ?", (id_,)
        )
        if usos and usos["n"]:
            raise ErrorNegocio(
                f"No se puede eliminar: tiene {usos['n']} reserva(s) asociada(s)."
            )
        db.execute("DELETE FROM vendedores WHERE id = ?", (id_,))


# =========================================================== PROVEEDORES

class Proveedores:
    @staticmethod
    def listar(texto: str = "", solo_activos: bool = False) -> list[dict[str, Any]]:
        sql = """SELECT p.*,
                        (SELECT COUNT(*) FROM reservas r WHERE r.proveedor_id = p.id) AS files
                 FROM proveedores p WHERE 1=1"""
        par: list[Any] = []
        if solo_activos:
            sql += " AND p.activo = 1"
        if texto:
            sql += " AND (p.nombre LIKE ? OR p.tipo LIKE ? OR p.contacto LIKE ?)"
            par += [f"%{texto}%"] * 3
        sql += " ORDER BY p.nombre"

        # Lo efectivamente pagado, por moneda (nunca se mezclan pesos y
        # dolares). Incluye files cancelados: es plata que ya salio, mas
        # alla de que despues el file se haya anulado.
        facturado_por_prov: dict[int, dict[str, float]] = {}
        for g in db.query(
            """SELECT proveedor_id, moneda, SUM(pagado_proveedor) monto
               FROM v_reservas_saldos GROUP BY proveedor_id, moneda"""):
            if g["monto"]:
                facturado_por_prov.setdefault(g["proveedor_id"], {})[g["moneda"]] = (
                    g["monto"])

        out = []
        for f in db.query(sql, tuple(par)):
            d = dict(f)
            d["facturado"] = facturado_por_prov.get(d["id"], {})
            out.append(d)
        return out

    @staticmethod
    def obtener(id_: int) -> sqlite3.Row | None:
        return db.query_one("SELECT * FROM proveedores WHERE id = ?", (id_,))

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        if not str(datos.get("nombre") or "").strip():
            raise ErrorNegocio("El nombre es obligatorio.")
        pctp = float(datos.get("comision_pct") or 0)
        if not 0 <= pctp <= 100:
            raise ErrorNegocio("La comisión del mayorista debe ir de 0 a 100.")
        try:
            if datos.get("id"):
                _actualizar("proveedores", int(datos["id"]), datos)
                return int(datos["id"])
            return _insertar("proveedores", datos)
        except sqlite3.IntegrityError as e:
            raise ErrorNegocio("Ya existe un proveedor con ese nombre.") from e

    @staticmethod
    def eliminar(id_: int) -> None:
        usos = db.query_one(
            "SELECT COUNT(*) n FROM reservas WHERE proveedor_id = ?", (id_,)
        )
        if usos and usos["n"]:
            raise ErrorNegocio(
                f"No se puede eliminar: tiene {usos['n']} reserva(s) asociada(s)."
            )
        db.execute("DELETE FROM proveedores WHERE id = ?", (id_,))


class ProveedorVariantes:
    """Hasta 4 comisiones distintas por operador, segun si el viaje es
    Nacional/Internacional y en que moneda.

    Si un file no elige tipo_viaje, o no hay variante cargada para esa
    combinacion, se usa la comision general del operador (ver
    v_reservas_saldos, columna pct_proveedor).
    """

    @staticmethod
    def listar(proveedor_id: int) -> list[dict[str, Any]]:
        return [dict(f) for f in db.query(
            "SELECT * FROM proveedor_variantes WHERE proveedor_id = ? "
            "ORDER BY tipo_viaje, moneda", (proveedor_id,))]

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        if not datos.get("proveedor_id"):
            raise ErrorNegocio("La variante tiene que pertenecer a un operador.")
        if datos.get("tipo_viaje") not in ("Nacional", "Internacional"):
            raise ErrorNegocio(
                "El tipo de viaje debe ser Nacional o Internacional.")
        if not str(datos.get("moneda") or "").strip():
            raise ErrorNegocio("Elegí la moneda de la variante.")
        pct = float(datos.get("comision_pct") or 0)
        if not 0 <= pct <= 100:
            raise ErrorNegocio("La comisión debe ir de 0 a 100.")
        try:
            if datos.get("id"):
                _actualizar("proveedor_variantes", int(datos["id"]), datos)
                return int(datos["id"])
            return _insertar("proveedor_variantes", datos)
        except sqlite3.IntegrityError as e:
            raise ErrorNegocio(
                "Ya existe una variante para esa combinación de tipo de "
                "viaje y moneda en este operador."
            ) from e

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM proveedor_variantes WHERE id = ?", (id_,))


# =========================================================== RESERVAS

class Reservas:
    CAMPOS_FECHA = (
        "fecha_cotizacion", "fecha_reserva", "fecha_vto_sena",
        "fecha_vto_reserva", "fecha_entrega_voucher", "voucher_recibido",
        "fecha_salida", "fecha_regreso",
    )

    @staticmethod
    def _enriquecer(filas: list[sqlite3.Row]) -> list[dict[str, Any]]:
        pct_sena = float(db.parametro("pct_sena", "20") or 20)
        hoy = date.today()
        out = []
        for f in filas:
            d = dict(f)
            d["estado"] = calculos.estado_reserva(d, pct_sena, hoy)
            d["pct_cobrado"] = calculos.porcentaje_cobrado(d)
            d["alertas"] = calculos.alertas(d, hoy)
            d["dias_a_sena"] = calculos.dias_hasta(d.get("fecha_vto_sena"), hoy)
            d["dias_a_reserva"] = calculos.dias_hasta(d.get("fecha_vto_reserva"), hoy)
            out.append(d)
        return out

    @staticmethod
    def listar(texto: str = "", estado: str = "", moneda: str = "",
               vendedor_id: int | None = None,
               desde: str | None = None, hasta: str | None = None,
               solo_con_saldo: bool = False,
               campo_fecha: str = "reserva") -> list[dict[str, Any]]:
        sql = "SELECT * FROM v_reservas_saldos WHERE 1=1"
        p: list[Any] = []
        if texto:
            sql += (" AND (file LIKE ? OR cliente LIKE ? OR destino LIKE ?"
                    " OR proveedor LIKE ? OR vendedor LIKE ?)")
            p += [f"%{texto}%"] * 5
        if moneda:
            sql += " AND moneda = ?"
            p.append(moneda)
        if vendedor_id:
            sql += " AND vendedor_id = ?"
            p.append(vendedor_id)
        col = {"salida": "fecha_salida",
               "vencimiento": "fecha_vto_reserva"}.get(
                   campo_fecha, "COALESCE(fecha_reserva, fecha_cotizacion)")
        if desde:
            sql += f" AND {col} >= ?"
            p.append(desde)
        if hasta:
            sql += f" AND {col} <= ?"
            p.append(hasta)
        if solo_con_saldo:
            sql += " AND cancelada = 0 AND saldo_cliente > 0.01"
        sql += " ORDER BY COALESCE(fecha_reserva, fecha_cotizacion) DESC, file DESC"
        filas = Reservas._enriquecer(db.query(sql, tuple(p)))
        if estado:
            filas = [f for f in filas if f["estado"] == estado]
        return filas

    @staticmethod
    def obtener(id_: int) -> dict[str, Any] | None:
        f = db.query_one("SELECT * FROM v_reservas_saldos WHERE id = ?", (id_,))
        if not f:
            return None
        return Reservas._enriquecer([f])[0]

    @staticmethod
    def crudo(id_: int) -> sqlite3.Row | None:
        """Fila tal cual esta en la tabla (sin los campos calculados)."""
        return db.query_one("SELECT * FROM reservas WHERE id = ?", (id_,))

    @staticmethod
    def por_file(file: str) -> dict[str, Any] | None:
        f = db.query_one("SELECT * FROM v_reservas_saldos WHERE file = ?", (file,))
        if not f:
            return None
        return Reservas._enriquecer([f])[0]

    @staticmethod
    def sugerir_file() -> str:
        """Proximo file: toma el mayor numero existente con el prefijo actual."""
        prefijo = (db.parametro("prefijo_file", "R") or "R").upper()
        mejor = None
        for fila in db.query("SELECT file FROM reservas"):
            texto = str(fila["file"] or "").upper()
            if not texto.startswith(prefijo):
                continue
            resto = texto[len(prefijo):]
            if resto.isdigit():
                n = int(resto)
                if mejor is None or n > mejor:
                    mejor = n
        if mejor is not None:
            return f"{prefijo}{mejor + 1}"
        return calculos.siguiente_file(None, prefijo)

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        d = dict(datos)
        if not str(d.get("file") or "").strip():
            raise ErrorNegocio("El numero de file es obligatorio.")
        for campo, etiqueta in (("cliente_id", "cliente"),
                                ("vendedor_id", "vendedor"),
                                ("proveedor_id", "proveedor")):
            if not d.get(campo):
                raise ErrorNegocio(f"Debes seleccionar un {etiqueta}.")
        if float(d.get("importe_cliente") or 0) < 0:
            raise ErrorNegocio("El importe al cliente no puede ser negativo.")
        if float(d.get("costo_proveedor") or 0) < 0:
            raise ErrorNegocio("El costo del proveedor no puede ser negativo.")
        for campo, etiqueta in (("comision_pct", "del vendedor"),
                                ("comision_prov_pct", "del mayorista")):
            if d.get(campo) not in (None, "") and not (
                    0 <= float(d[campo]) <= 100):
                raise ErrorNegocio(
                    f"La comisión {etiqueta} debe estar entre 0 y 100.")

        f_sal = calculos.a_fecha(d.get("fecha_salida"))
        f_reg = calculos.a_fecha(d.get("fecha_regreso"))
        if f_sal and f_reg and f_reg < f_sal:
            raise ErrorNegocio("La fecha de regreso no puede ser anterior a la de salida.")

        for campo in Reservas.CAMPOS_FECHA:
            if campo in d:
                d[campo] = calculos.iso(d[campo])

        d["file"] = str(d["file"]).strip().upper()
        d.pop("actualizado_en", None)  # lo maneja la base

        try:
            if d.get("id"):
                _actualizar("reservas", int(d["id"]), d)
                db.execute(
                    "UPDATE reservas SET actualizado_en = datetime('now','localtime')"
                    " WHERE id = ?", (int(d["id"]),)
                )
                return int(d["id"])
            return _insertar("reservas", d)
        except sqlite3.IntegrityError as e:
            raise ErrorNegocio(
                f"Ya existe una reserva con el file '{d['file']}'."
            ) from e

    @staticmethod
    def duplicar(id_: int, nuevo_file: str | None = None,
                 copiar_pasajeros: bool = True,
                 copiar_servicios: bool = True) -> int:
        """Clona un file con sus servicios y pasajeros. No copia la caja."""
        orig = db.query_one("SELECT * FROM reservas WHERE id = ?", (id_,))
        if not orig:
            raise ErrorNegocio("No se encontró el file a duplicar.")
        d = {k: orig[k] for k in orig.keys()
             if k not in ("id", "file", "creado_en", "actualizado_en",
                          "fecha_entrega_voucher", "devolucion",
                          "cancelada", "motivo_cancelacion")}
        d["file"] = nuevo_file or Reservas.sugerir_file()
        d["fecha_cotizacion"] = date.today().isoformat()
        nuevo = _insertar("reservas", d)
        if copiar_servicios:
            for sv in Servicios.listar(id_):
                Servicios.guardar({
                    "reserva_id": nuevo, "proveedor_id": sv["proveedor_id"],
                    "concepto": sv["concepto"], "detalle": sv["detalle"],
                    "importe_venta": sv["importe_venta"], "costo": sv["costo"],
                    "orden": sv["orden"],
                })
        if copiar_pasajeros:
            for px in Pasajeros.listar(id_):
                Pasajeros.guardar({
                    "reserva_id": nuevo, "nombre": px["nombre"],
                    "documento": px["documento"], "fecha_nac": px["fecha_nac"],
                    "pasaporte": px["pasaporte"],
                    "vto_pasaporte": px["vto_pasaporte"], "orden": px["orden"],
                })
        return nuevo

    @staticmethod
    def cancelar(id_: int, motivo: str = "", devolucion: float = 0.0,
                 registrar_devolucion: bool = False,
                 fecha_devolucion: str | None = None) -> None:
        """Cancela el file y, si corresponde, registra la devolución en caja."""
        r = Reservas.obtener(id_)
        if not r:
            raise ErrorNegocio("No se encontró el file.")
        devolucion = float(devolucion or 0)
        if devolucion < 0:
            raise ErrorNegocio("La devolución no puede ser negativa.")
        if devolucion > float(r["cobrado_cliente"]) + 0.01:
            raise ErrorNegocio(
                "No podés devolver más de lo que el cliente pagó "
                f"({calculos.money(r['cobrado_cliente'], r['moneda'])}).")
        db.execute(
            "UPDATE reservas SET cancelada = 1, motivo_cancelacion = ?,"
            " devolucion = ?, actualizado_en = datetime('now','localtime')"
            " WHERE id = ?",
            (motivo, devolucion, id_),
        )
        if registrar_devolucion and devolucion > 0:
            Caja.guardar({
                "tipo": "EGRESO",
                "fecha": fecha_devolucion or date.today().isoformat(),
                "concepto": "Devolucion a cliente",
                "reserva_id": id_, "moneda": r["moneda"],
                "monto": devolucion,
                "detalle": f"Cancelación del file {r['file']}. {motivo}".strip(),
            })

    @staticmethod
    def reactivar(id_: int) -> None:
        db.execute(
            "UPDATE reservas SET cancelada = 0, motivo_cancelacion = NULL,"
            " actualizado_en = datetime('now','localtime') WHERE id = ?", (id_,)
        )

    @staticmethod
    def marcar_ok(id_: int, fecha: str | None = None) -> None:
        """El cliente dijo que si a la cotizacion (todavia sin pagar nada).

        Reutiliza fecha_reserva, que calculos.estado_reserva() interpreta
        como la marca de aprobacion del cliente.
        """
        db.execute(
            "UPDATE reservas SET fecha_reserva = ?,"
            " actualizado_en = datetime('now','localtime') WHERE id = ?",
            (fecha or date.today().isoformat(), id_),
        )

    @staticmethod
    def marcar_voucher_recibido(id_: int, fecha: str | None = None) -> None:
        """El operador mando el voucher del file."""
        db.execute(
            "UPDATE reservas SET voucher_recibido = ?,"
            " actualizado_en = datetime('now','localtime') WHERE id = ?",
            (fecha or date.today().isoformat(), id_),
        )

    @staticmethod
    def eliminar(id_: int) -> None:
        movs = db.query_one(
            "SELECT COUNT(*) n FROM movimientos WHERE reserva_id = ?", (id_,)
        )
        if movs and movs["n"]:
            raise ErrorNegocio(
                f"No se puede eliminar: el file tiene {movs['n']} movimiento(s) "
                "de caja. Cancelalo en lugar de borrarlo."
            )
        db.execute("DELETE FROM reservas WHERE id = ?", (id_,))


# =========================================================== CAJA

class Caja:
    @staticmethod
    def listar(texto: str = "", tipo: str = "", moneda: str = "",
               desde: str | None = None, hasta: str | None = None,
               reserva_id: int | None = None) -> list[sqlite3.Row]:
        sql = """SELECT m.*, r.file, c.apellido || ', ' || c.nombre AS cliente
                 FROM movimientos m
                 LEFT JOIN reservas r ON r.id = m.reserva_id
                 LEFT JOIN clientes c ON c.id = r.cliente_id
                 WHERE 1=1"""
        p: list[Any] = []
        if texto:
            sql += (" AND (m.concepto LIKE ? OR m.detalle LIKE ? OR r.file LIKE ?"
                    " OR m.medio_pago LIKE ?)")
            p += [f"%{texto}%"] * 4
        if tipo:
            sql += " AND m.tipo = ?"
            p.append(tipo)
        if moneda:
            sql += " AND m.moneda = ?"
            p.append(moneda)
        if desde:
            sql += " AND m.fecha >= ?"
            p.append(desde)
        if hasta:
            sql += " AND m.fecha <= ?"
            p.append(hasta)
        if reserva_id:
            sql += " AND m.reserva_id = ?"
            p.append(reserva_id)
        sql += " ORDER BY m.fecha DESC, m.id DESC"
        return db.query(sql, tuple(p))

    @staticmethod
    def obtener(id_: int) -> sqlite3.Row | None:
        return db.query_one("SELECT * FROM movimientos WHERE id = ?", (id_,))

    @staticmethod
    def gastos_extraordinarios(desde: str | None = None,
                               hasta: str | None = None) -> list[sqlite3.Row]:
        """Egresos sueltos: ni asociados a un file, ni generados por un gasto
        fijo. Para distinguirlos, generar_mes() marca sus movimientos con
        operacion='gasto_fijo'."""
        sql = """SELECT * FROM movimientos
                 WHERE tipo = 'EGRESO' AND reserva_id IS NULL
                   AND COALESCE(operacion, '') <> 'gasto_fijo'"""
        p: list[Any] = []
        if desde:
            sql += " AND fecha >= ?"
            p.append(desde)
        if hasta:
            sql += " AND fecha <= ?"
            p.append(hasta)
        sql += " ORDER BY fecha DESC, id DESC"
        return db.query(sql, tuple(p))

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        d = dict(datos)
        if d.get("tipo") not in ("INGRESO", "EGRESO"):
            raise ErrorNegocio("El tipo debe ser INGRESO o EGRESO.")
        monto = float(d.get("monto") or 0)
        if monto <= 0:
            raise ErrorNegocio("El monto debe ser mayor a cero.")
        d["monto"] = abs(monto)
        if not str(d.get("concepto") or "").strip():
            raise ErrorNegocio("El concepto es obligatorio.")
        d["fecha"] = calculos.iso(d.get("fecha")) or date.today().isoformat()

        # Coherencia de moneda con la reserva asociada.
        if d.get("reserva_id"):
            r = db.query_one(
                "SELECT moneda, file FROM reservas WHERE id = ?", (d["reserva_id"],)
            )
            if r and d.get("moneda") and r["moneda"] != d["moneda"]:
                raise ErrorNegocio(
                    f"El file {r['file']} opera en {r['moneda']}; "
                    "el movimiento debe usar la misma moneda."
                )
        if d.get("id"):
            _actualizar("movimientos", int(d["id"]), d)
            return int(d["id"])
        return _insertar("movimientos", d)

    @staticmethod
    def eliminar(id_: int) -> None:
        """Borra el movimiento. Si es parte de un cambio, borra las dos patas."""
        fila = db.query_one(
            "SELECT operacion FROM movimientos WHERE id = ?", (id_,)
        )
        if fila and fila["operacion"]:
            db.execute(
                "DELETE FROM movimientos WHERE operacion = ?", (fila["operacion"],)
            )
        else:
            db.execute("DELETE FROM movimientos WHERE id = ?", (id_,))

    @staticmethod
    def cambio_moneda(fecha: str, moneda_origen: str, monto_origen: float,
                      moneda_destino: str, monto_destino: float,
                      medio_pago: str = "", detalle: str = "") -> str:
        """Registra una compra/venta de moneda como dos movimientos ligados.

        Sale `monto_origen` en `moneda_origen` y entra `monto_destino` en
        `moneda_destino`. No se consolidan las monedas: cada una sigue su
        propio saldo. Se guarda la cotizacion implicita de la operacion.
        """
        if moneda_origen == moneda_destino:
            raise ErrorNegocio("Las monedas de origen y destino deben ser distintas.")
        if monto_origen <= 0 or monto_destino <= 0:
            raise ErrorNegocio("Los dos montos deben ser mayores a cero.")

        fecha = calculos.iso(fecha) or date.today().isoformat()
        operacion = f"CAMBIO-{uuid.uuid4().hex[:12]}"
        cotizacion = round(max(monto_origen, monto_destino)
                           / min(monto_origen, monto_destino), 4)
        texto = (f"Cambio {moneda_origen} -> {moneda_destino} "
                 f"(cotización {cotizacion})")
        if detalle:
            texto += f". {detalle}"

        con = db.conectar()
        try:
            con.execute(
                """INSERT INTO movimientos
                       (fecha,tipo,concepto,moneda,monto,medio_pago,detalle,
                        operacion,cotizacion)
                   VALUES (?,'EGRESO','Cambio de moneda',?,?,?,?,?,?)""",
                (fecha, moneda_origen, abs(monto_origen), medio_pago,
                 texto, operacion, cotizacion),
            )
            con.execute(
                """INSERT INTO movimientos
                       (fecha,tipo,concepto,moneda,monto,medio_pago,detalle,
                        operacion,cotizacion)
                   VALUES (?,'INGRESO','Cambio de moneda',?,?,?,?,?,?)""",
                (fecha, moneda_destino, abs(monto_destino), medio_pago,
                 texto, operacion, cotizacion),
            )
            con.commit()
        except Exception:
            con.rollback()
            raise
        return operacion

    @staticmethod
    def cambios() -> list[dict[str, Any]]:
        """Lista las operaciones de cambio, una fila por operacion."""
        filas = db.query(
            """SELECT operacion, fecha, cotizacion, medio_pago,
                      MAX(CASE WHEN tipo='EGRESO'  THEN moneda END) moneda_origen,
                      MAX(CASE WHEN tipo='EGRESO'  THEN monto  END) monto_origen,
                      MAX(CASE WHEN tipo='INGRESO' THEN moneda END) moneda_destino,
                      MAX(CASE WHEN tipo='INGRESO' THEN monto  END) monto_destino
               FROM movimientos WHERE operacion IS NOT NULL
               GROUP BY operacion ORDER BY fecha DESC"""
        )
        return [dict(f) for f in filas]

    @staticmethod
    def totales(desde: str | None = None, hasta: str | None = None
                ) -> list[sqlite3.Row]:
        sql = """SELECT moneda,
                        SUM(CASE WHEN tipo='INGRESO' THEN monto ELSE 0 END) ingresos,
                        SUM(CASE WHEN tipo='EGRESO'  THEN monto ELSE 0 END) egresos,
                        SUM(CASE WHEN tipo='INGRESO' THEN monto ELSE -monto END) neto
                 FROM movimientos WHERE 1=1"""
        p: list[Any] = []
        if desde:
            sql += " AND fecha >= ?"
            p.append(desde)
        if hasta:
            sql += " AND fecha <= ?"
            p.append(hasta)
        sql += " GROUP BY moneda ORDER BY moneda"
        return db.query(sql, tuple(p))


# =========================================================== REPORTES

class Reportes:
    @staticmethod
    def caja_mensual(anio: int | None = None) -> list[sqlite3.Row]:
        sql = """SELECT substr(fecha,1,4) anio, substr(fecha,6,2) mes, moneda,
                        SUM(CASE WHEN tipo='INGRESO' THEN monto ELSE 0 END) ingresos,
                        SUM(CASE WHEN tipo='EGRESO'  THEN monto ELSE 0 END) egresos,
                        SUM(CASE WHEN tipo='INGRESO' THEN monto ELSE -monto END) neto
                 FROM movimientos WHERE 1=1"""
        p: list[Any] = []
        if anio:
            sql += " AND substr(fecha,1,4) = ?"
            p.append(str(anio))
        sql += " GROUP BY anio, mes, moneda ORDER BY anio DESC, mes DESC, moneda"
        return db.query(sql, tuple(p))

    @staticmethod
    def cobros_pendientes() -> list[dict[str, Any]]:
        filas = Reservas.listar(solo_con_saldo=True)
        return sorted(
            filas,
            key=lambda r: (r.get("fecha_vto_reserva") or "9999-12-31"),
        )

    @staticmethod
    def pagos_pendientes() -> list[dict[str, Any]]:
        sql = ("SELECT * FROM v_reservas_saldos "
               "WHERE cancelada = 0 AND saldo_proveedor > 0.01")
        filas = Reservas._enriquecer(db.query(sql))
        return sorted(filas, key=lambda r: (r.get("fecha_salida") or "9999-12-31"))

    @staticmethod
    def comisiones(desde: str | None = None, hasta: str | None = None
                   ) -> list[sqlite3.Row]:
        sql = """SELECT vendedor, moneda, COUNT(*) files,
                        SUM(importe_cliente) ventas,
                        SUM(comision_agencia) ganancia,
                        SUM(comision_vendedor) comision,
                        SUM(margen_neto) margen
                 FROM v_reservas_saldos WHERE cancelada = 0"""
        p: list[Any] = []
        if desde:
            sql += " AND COALESCE(fecha_reserva, fecha_cotizacion) >= ?"
            p.append(desde)
        if hasta:
            sql += " AND COALESCE(fecha_reserva, fecha_cotizacion) <= ?"
            p.append(hasta)
        sql += " GROUP BY vendedor, moneda ORDER BY ganancia DESC"
        return db.query(sql, tuple(p))

    @staticmethod
    def por_destino() -> list[sqlite3.Row]:
        return db.query(
            """SELECT COALESCE(destino,'(sin destino)') destino, moneda,
                      COUNT(*) files, SUM(importe_cliente) ventas,
                      SUM(comision_agencia) ganancia
               FROM v_reservas_saldos WHERE cancelada = 0
               GROUP BY destino, moneda ORDER BY ventas DESC"""
        )

    @staticmethod
    def por_proveedor() -> list[sqlite3.Row]:
        return db.query(
            """SELECT proveedor, moneda, COUNT(*) files,
                      SUM(importe_cliente) ventas,
                      SUM(comision_agencia) comision,
                      SUM(costo_proveedor) costo, SUM(saldo_proveedor) saldo
               FROM v_reservas_saldos WHERE cancelada = 0
               GROUP BY proveedor, moneda ORDER BY costo DESC"""
        )

    @staticmethod
    def por_canal() -> list[sqlite3.Row]:
        return db.query(
            """SELECT COALESCE(NULLIF(c.canal,''),'(sin dato)') canal,
                      COUNT(DISTINCT c.id) clientes,
                      COUNT(r.id) files,
                      COALESCE(SUM(r.importe_cliente),0) ventas
               FROM clientes c
               LEFT JOIN reservas r ON r.cliente_id = c.id AND r.cancelada = 0
               GROUP BY canal ORDER BY ventas DESC"""
        )

    @staticmethod
    def cumpleanos(mes: int | None = None) -> list[dict[str, Any]]:
        """Clientes que cumplen anios en el mes indicado (por defecto, este)."""
        mes = mes or date.today().month
        return [dict(f) for f in db.query(
            """SELECT apellido || ', ' || nombre AS cliente, dni, telefono,
                      email, fecha_nac,
                      CAST(strftime('%d', fecha_nac) AS INTEGER) dia
               FROM clientes
               WHERE fecha_nac IS NOT NULL AND fecha_nac <> ''
                 AND CAST(strftime('%m', fecha_nac) AS INTEGER) = ?
               ORDER BY dia""", (mes,))]

    @staticmethod
    def cuotas_pendientes() -> list[dict[str, Any]]:
        filas = Cuotas.pendientes(dias=60)
        for f in filas:
            f["dias"] = calculos.dias_hasta(f["vencimiento"])
        return filas

    @staticmethod
    def seguimientos_pendientes() -> list[dict[str, Any]]:
        return Seguimientos.listar(pendientes=True)

    @staticmethod
    def estado_cuenta(cliente_id: int) -> dict[str, Any]:
        """Todo lo que compró un cliente y lo que debe."""
        cli = Clientes.obtener(cliente_id)
        if not cli:
            raise ErrorNegocio("No se encontró el cliente.")
        files = Reservas.listar()
        files = [f for f in files if f["cliente_id"] == cliente_id]
        movs = [dict(m) for m in db.query(
            """SELECT m.*, r.file FROM movimientos m
               JOIN reservas r ON r.id = m.reserva_id
               WHERE r.cliente_id = ? ORDER BY m.fecha""", (cliente_id,))]
        por_moneda: dict[str, dict[str, float]] = {}
        for f in files:
            if f["cancelada"]:
                continue
            a = por_moneda.setdefault(
                f["moneda"], {"comprado": 0.0, "pagado": 0.0, "saldo": 0.0})
            a["comprado"] += float(f["importe_cliente"] or 0)
            a["pagado"] += float(f["cobrado_cliente"] or 0)
            a["saldo"] += float(f["saldo_cliente"] or 0)
        return {"cliente": dict(cli), "files": files,
                "movimientos": movs, "totales": por_moneda}

    @staticmethod
    def resumen_estados(moneda: str = "") -> dict[str, int]:
        conteo: dict[str, int] = {}
        for r in Reservas.listar(moneda=moneda):
            conteo[r["estado"]] = conteo.get(r["estado"], 0) + 1
        return conteo

    @staticmethod
    def dashboard(moneda: str = "", desde: str | None = None,
                 hasta: str | None = None, ventana_dias: int = 7) -> dict[str, Any]:
        hoy = date.today()
        desde = desde or hoy.replace(day=1).isoformat()
        hasta = hasta or hoy.isoformat()
        # Mismo campo de fecha que usa por default el filtro de Reservas
        # (fecha de reserva o, si todavia no la hay, de cotizacion): el
        # periodo elegido decide QUE files entran en la foto, y de ahi
        # salen todos los numeros de abajo -- incluidos los estados y los
        # pagos a operadores, que antes quedaban fijos sin importar el
        # filtro.
        reservas = Reservas.listar(moneda=moneda, desde=desde, hasta=hasta)
        activas = [r for r in reservas if not r["cancelada"]]
        pendientes = [r for r in activas if float(r["saldo_cliente"]) > 0.01]
        a_pagar = [r for r in activas if float(r["saldo_proveedor"]) > 0.01]
        con_alertas = [r for r in activas if r["alertas"]]

        por_moneda: dict[str, dict[str, float]] = {}
        for r in activas:
            m = por_moneda.setdefault(
                r["moneda"], {"a_cobrar": 0.0, "a_pagar": 0.0, "ganancia": 0.0}
            )
            m["a_cobrar"] += max(0.0, float(r["saldo_cliente"]))
            m["a_pagar"] += max(0.0, float(r["saldo_proveedor"]))
            m["ganancia"] += float(r["comision_agencia"])

        estados: dict[str, int] = {}
        for r in reservas:
            estados[r["estado"]] = estados.get(r["estado"], 0) + 1

        pagos_operadores = sorted(
            a_pagar, key=lambda r: (r.get("fecha_salida") or "9999-12-31"))

        return {
            "desde": desde, "hasta": hasta,
            "totales_mes": [dict(x) for x in Caja.totales(desde, hasta)],
            "estados": estados,
            "por_moneda": por_moneda,
            "cant_activas": len(activas),
            "cant_pendientes": len(pendientes),
            "cant_a_pagar": len(a_pagar),
            "alertas": con_alertas[:50],
            "pagos_operadores": pagos_operadores[:50],
        }


# =========================================================== SERVICIOS

class Servicios:
    """Servicios de un file: permite varios proveedores por reserva."""

    @staticmethod
    def listar(reserva_id: int) -> list[dict[str, Any]]:
        return [dict(f) for f in db.query(
            """SELECT s.*, p.nombre AS proveedor
               FROM reserva_servicios s
               JOIN proveedores p ON p.id = s.proveedor_id
               WHERE s.reserva_id = ? ORDER BY s.orden, s.id""",
            (reserva_id,))]

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        if not datos.get("reserva_id"):
            raise ErrorNegocio("El servicio tiene que pertenecer a un file.")
        if not datos.get("proveedor_id"):
            raise ErrorNegocio("Elegí el proveedor del servicio.")
        if not str(datos.get("concepto") or "").strip():
            raise ErrorNegocio("El concepto del servicio es obligatorio.")
        if float(datos.get("costo") or 0) < 0:
            raise ErrorNegocio("El costo no puede ser negativo.")
        if datos.get("id"):
            _actualizar("reserva_servicios", int(datos["id"]), datos)
            return int(datos["id"])
        return _insertar("reserva_servicios", datos)

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM reserva_servicios WHERE id = ?", (id_,))

    @staticmethod
    def totales(reserva_id: int) -> tuple[float, float]:
        f = db.query_one(
            "SELECT COALESCE(SUM(importe_venta),0) v, COALESCE(SUM(costo),0) c "
            "FROM reserva_servicios WHERE reserva_id = ?", (reserva_id,))
        return (float(f["v"]), float(f["c"])) if f else (0.0, 0.0)


# =========================================================== PASAJEROS

class Pasajeros:
    @staticmethod
    def listar(reserva_id: int) -> list[dict[str, Any]]:
        return [dict(f) for f in db.query(
            "SELECT * FROM pasajeros WHERE reserva_id = ? ORDER BY orden, id",
            (reserva_id,))]

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        if not datos.get("reserva_id"):
            raise ErrorNegocio("El pasajero tiene que pertenecer a un file.")
        if not str(datos.get("nombre") or "").strip():
            raise ErrorNegocio("El nombre del pasajero es obligatorio.")
        d = dict(datos)
        for campo in ("fecha_nac", "vto_pasaporte"):
            if campo in d:
                d[campo] = calculos.iso(d[campo])
        if d.get("id"):
            _actualizar("pasajeros", int(d["id"]), d)
            return int(d["id"])
        return _insertar("pasajeros", d)

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM pasajeros WHERE id = ?", (id_,))

    @staticmethod
    def pasaportes_por_vencer(dias: int = 180) -> list[dict[str, Any]]:
        limite = (date.today() + timedelta(days=dias)).isoformat()
        return [dict(f) for f in db.query(
            """SELECT p.*, r.file, r.fecha_salida
               FROM pasajeros p JOIN reservas r ON r.id = p.reserva_id
               WHERE p.vto_pasaporte IS NOT NULL AND p.vto_pasaporte <> ''
                 AND p.vto_pasaporte <= ? AND r.cancelada = 0
               ORDER BY p.vto_pasaporte""", (limite,))]


# =========================================================== TARJETAS

class TarjetasCliente:
    """Tarjetas del cliente, solo a modo de referencia: nunca el numero
    completo ni el CVV, unicamente los ultimos 4 digitos. No sirve para
    cobrar, es para saber con que tarjeta suele pagar."""

    @staticmethod
    def listar(cliente_id: int) -> list[dict[str, Any]]:
        return [dict(f) for f in db.query(
            "SELECT * FROM tarjetas_cliente WHERE cliente_id = ? "
            "ORDER BY creado_en DESC", (cliente_id,))]

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        if not datos.get("cliente_id"):
            raise ErrorNegocio("La tarjeta tiene que pertenecer a un cliente.")
        ultimos4 = str(datos.get("ultimos4") or "").strip()
        if ultimos4 and not (ultimos4.isdigit() and len(ultimos4) == 4):
            raise ErrorNegocio("Los últimos 4 dígitos tienen que ser 4 números.")
        vencimiento = str(datos.get("vencimiento") or "").strip()
        if vencimiento and calculos.fin_de_mes_tarjeta(vencimiento) is None:
            raise ErrorNegocio(
                "El vencimiento va en formato MM/AA, como figura en la "
                "tarjeta (ej. 08/27).")
        if datos.get("id"):
            _actualizar("tarjetas_cliente", int(datos["id"]), datos)
            return int(datos["id"])
        return _insertar("tarjetas_cliente", datos)

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM tarjetas_cliente WHERE id = ?", (id_,))

    @staticmethod
    def por_vencer(dias: int = 60) -> list[dict[str, Any]]:
        """Tarjetas cuyo MM/AA cae dentro de la ventana. El filtrado es en
        Python porque 'MM/AA' no ordena ni compara como texto ISO."""
        limite = date.today() + timedelta(days=dias)
        salida = []
        for f in db.query(
            """SELECT t.*, c.apellido || ', ' || c.nombre AS cliente,
                      c.telefono AS cliente_telefono
               FROM tarjetas_cliente t JOIN clientes c ON c.id = t.cliente_id
               WHERE t.vencimiento IS NOT NULL AND t.vencimiento <> ''"""):
            fv = calculos.fin_de_mes_tarjeta(f["vencimiento"])
            if fv and fv <= limite:
                d = dict(f)
                d["vencimiento_orden"] = fv.isoformat()
                salida.append(d)
        salida.sort(key=lambda d: d["vencimiento_orden"])
        return salida


# =========================================================== CUOTAS

class Cuotas:
    @staticmethod
    def listar(reserva_id: int) -> list[dict[str, Any]]:
        return [dict(f) for f in db.query(
            "SELECT * FROM cuotas WHERE reserva_id = ? ORDER BY vencimiento, numero",
            (reserva_id,))]

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        d = dict(datos)
        if not d.get("reserva_id"):
            raise ErrorNegocio("La cuota tiene que pertenecer a un file.")
        d["vencimiento"] = calculos.iso(d.get("vencimiento"))
        if not d["vencimiento"]:
            raise ErrorNegocio("La cuota necesita una fecha de vencimiento.")
        if float(d.get("importe") or 0) <= 0:
            raise ErrorNegocio("El importe de la cuota debe ser mayor a cero.")
        if d.get("id"):
            _actualizar("cuotas", int(d["id"]), d)
            return int(d["id"])
        return _insertar("cuotas", d)

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM cuotas WHERE id = ?", (id_,))

    @staticmethod
    def generar_plan(reserva_id: int, cantidad: int, primera: str,
                     intervalo_dias: int = 30,
                     total: float | None = None) -> int:
        """Arma un plan parejo de N cuotas desde una fecha inicial."""
        if cantidad < 1:
            raise ErrorNegocio("La cantidad de cuotas debe ser al menos 1.")
        r = Reservas.obtener(reserva_id)
        if not r:
            raise ErrorNegocio("No se encontró el file.")
        base = float(total if total is not None else r["saldo_cliente"])
        if base <= 0:
            raise ErrorNegocio("No hay saldo pendiente para armar el plan.")
        inicio = calculos.a_fecha(primera) or date.today()
        db.execute("DELETE FROM cuotas WHERE reserva_id = ?", (reserva_id,))
        cuota = round(base / cantidad, 2)
        for i in range(cantidad):
            # La ultima absorbe el redondeo para que la suma cierre exacta.
            importe = cuota if i < cantidad - 1 else round(
                base - cuota * (cantidad - 1), 2)
            Cuotas.guardar({
                "reserva_id": reserva_id, "numero": i + 1,
                "vencimiento": (inicio + timedelta(days=intervalo_dias * i)
                                ).isoformat(),
                "importe": importe,
            })
        return cantidad

    @staticmethod
    def pendientes(dias: int = 30) -> list[dict[str, Any]]:
        limite = (date.today() + timedelta(days=dias)).isoformat()
        return [dict(f) for f in db.query(
            """SELECT c.*, r.file, r.moneda,
                      cl.apellido || ', ' || cl.nombre AS cliente,
                      cl.telefono AS cliente_telefono
               FROM cuotas c
               JOIN reservas r  ON r.id = c.reserva_id
               JOIN clientes cl ON cl.id = r.cliente_id
               WHERE r.cancelada = 0 AND c.vencimiento <= ?
               ORDER BY c.vencimiento""", (limite,))]


# =========================================================== ADJUNTOS

class Adjuntos:
    """Archivos enlazados a un file, a un cliente, a un vendedor o a un
    movimiento de caja puntual (comprobante de pago/transferencia).

    Se guarda la ruta, no una copia: si el usuario mueve el archivo de
    carpeta, el enlace deja de resolver (la interfaz lo avisa al abrirlo).
    """

    @staticmethod
    def listar(reserva_id: int | None = None,
               cliente_id: int | None = None,
               vendedor_id: int | None = None,
               movimiento_id: int | None = None) -> list[dict[str, Any]]:
        if reserva_id:
            sql, p = "SELECT * FROM adjuntos WHERE reserva_id = ?", (reserva_id,)
        elif cliente_id:
            sql, p = "SELECT * FROM adjuntos WHERE cliente_id = ?", (cliente_id,)
        elif vendedor_id:
            sql, p = ("SELECT * FROM adjuntos WHERE vendedor_id = ?",
                      (vendedor_id,))
        elif movimiento_id:
            sql, p = ("SELECT * FROM adjuntos WHERE movimiento_id = ?",
                      (movimiento_id,))
        else:
            sql, p = "SELECT * FROM adjuntos", ()
        return [dict(f) for f in db.query(sql + " ORDER BY agregado_en DESC", p)]

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        if not str(datos.get("ruta") or "").strip():
            raise ErrorNegocio("Falta la ruta del archivo.")
        d = dict(datos)
        if not any(d.get(k) for k in ("reserva_id", "cliente_id", "vendedor_id",
                                      "movimiento_id")):
            raise ErrorNegocio(
                "El adjunto tiene que pertenecer a un file, a un cliente, a "
                "un vendedor o a un movimiento de caja.")
        if not str(d.get("titulo") or "").strip():
            d["titulo"] = Path(str(d["ruta"])).name
        return _insertar("adjuntos", d)

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM adjuntos WHERE id = ?", (id_,))


# =========================================================== SEGUIMIENTOS

class Seguimientos:
    @staticmethod
    def listar(cliente_id: int | None = None,
               pendientes: bool = False) -> list[dict[str, Any]]:
        sql = """SELECT s.*, c.apellido || ', ' || c.nombre AS cliente,
                        c.telefono AS cliente_telefono, r.file
                 FROM seguimientos s
                 JOIN clientes c ON c.id = s.cliente_id
                 LEFT JOIN reservas r ON r.id = s.reserva_id
                 WHERE 1=1"""
        p: list[Any] = []
        if cliente_id:
            sql += " AND s.cliente_id = ?"
            p.append(cliente_id)
        if pendientes:
            sql += " AND s.proximo IS NOT NULL AND s.proximo <> '' AND s.proximo <= ?"
            p.append((date.today() + timedelta(days=7)).isoformat())
        sql += " ORDER BY s.fecha DESC, s.id DESC"
        return [dict(f) for f in db.query(sql, tuple(p))]

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        d = dict(datos)
        if not d.get("cliente_id"):
            raise ErrorNegocio("El seguimiento necesita un cliente.")
        if not str(d.get("nota") or "").strip():
            raise ErrorNegocio("Escribí la nota del contacto.")
        d["fecha"] = calculos.iso(d.get("fecha")) or date.today().isoformat()
        d["proximo"] = calculos.iso(d.get("proximo"))
        if d.get("id"):
            _actualizar("seguimientos", int(d["id"]), d)
            return int(d["id"])
        return _insertar("seguimientos", d)

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM seguimientos WHERE id = ?", (id_,))


# =========================================================== ENCUESTAS

class Encuestas:
    """Encuesta de satisfaccion de un file Finalizado.

    Se genera en PDF (sin envio automatico, ver PENDIENTES) y la respuesta
    se carga a mano cuando el cliente contesta.
    """

    @staticmethod
    def generar(reserva_id: int) -> int:
        """Crea la encuesta pendiente, o devuelve la que ya estaba sin
        responder para no duplicar si se genera el PDF de nuevo."""
        existente = db.query_one(
            "SELECT id FROM encuestas WHERE reserva_id = ? "
            "AND fecha_respuesta IS NULL", (reserva_id,))
        if existente:
            return existente["id"]
        return _insertar("encuestas", {"reserva_id": reserva_id})

    @staticmethod
    def listar(reserva_id: int | None = None) -> list[dict[str, Any]]:
        sql = """SELECT e.*, r.file, r.destino,
                        c.apellido || ', ' || c.nombre AS cliente,
                        c.telefono AS cliente_telefono
                 FROM encuestas e
                 JOIN reservas r ON r.id = e.reserva_id
                 JOIN clientes c ON c.id = r.cliente_id
                 WHERE 1=1"""
        p: list[Any] = []
        if reserva_id:
            sql += " AND e.reserva_id = ?"
            p.append(reserva_id)
        sql += " ORDER BY e.fecha_generada DESC"
        return [dict(f) for f in db.query(sql, tuple(p))]

    @staticmethod
    def pendientes() -> list[dict[str, Any]]:
        return [dict(f) for f in db.query(
            """SELECT e.*, r.file, r.destino,
                      c.apellido || ', ' || c.nombre AS cliente,
                      c.telefono AS cliente_telefono
               FROM encuestas e
               JOIN reservas r ON r.id = e.reserva_id
               JOIN clientes c ON c.id = r.cliente_id
               WHERE e.fecha_respuesta IS NULL
               ORDER BY e.fecha_generada""")]

    @staticmethod
    def responder(id_: int, atencion: int | None, expectativas: int | None,
                 recomendaria: int | None, comentario: str = "",
                 fecha: str | None = None) -> None:
        for etiqueta, valor in (("de atención", atencion),
                                ("de expectativas", expectativas),
                                ("de recomendación", recomendaria)):
            if valor is not None and not (1 <= int(valor) <= 5):
                raise ErrorNegocio(f"El puntaje {etiqueta} va de 1 a 5.")
        db.execute(
            "UPDATE encuestas SET puntaje_atencion = ?, puntaje_expectativas = ?,"
            " puntaje_recomendaria = ?, comentario = ?, fecha_respuesta = ?"
            " WHERE id = ?",
            (atencion, expectativas, recomendaria, comentario.strip(),
             fecha or date.today().isoformat(), id_),
        )

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM encuestas WHERE id = ?", (id_,))


# =========================================================== CIERRE MENSUAL

def _rango_mes(anio: int, mes: int) -> tuple[str, str]:
    desde = date(anio, mes, 1)
    hasta = (date(anio + (mes == 12), (mes % 12) + 1, 1) - timedelta(days=1))
    return desde.isoformat(), hasta.isoformat()


class Cierre:
    """Resumen contable del mes, por moneda."""

    @staticmethod
    def resumen(anio: int, mes: int) -> list[dict[str, Any]]:
        desde, hasta = _rango_mes(anio, mes)
        monedas = [f["valor"] for f in db.query(
            "SELECT valor FROM listas WHERE tipo='moneda' ORDER BY orden")]
        for f in db.query("SELECT DISTINCT moneda FROM movimientos"):
            if f["moneda"] and f["moneda"] not in monedas:
                monedas.append(f["moneda"])

        salida = []
        for mon in monedas:
            mov = db.query_one(
                """SELECT
                     COALESCE(SUM(CASE WHEN tipo='INGRESO' THEN monto END),0) ing,
                     COALESCE(SUM(CASE WHEN tipo='EGRESO'  THEN monto END),0) egr,
                     COALESCE(SUM(CASE WHEN tipo='INGRESO' AND reserva_id IS NOT NULL
                                       THEN monto END),0) cobros,
                     COALESCE(SUM(CASE WHEN tipo='EGRESO' AND reserva_id IS NOT NULL
                                       THEN monto END),0) pagos_prov,
                     COALESCE(SUM(CASE WHEN tipo='EGRESO' AND reserva_id IS NULL
                                       THEN monto END),0) gastos,
                     COALESCE(SUM(CASE WHEN concepto='Devolucion a cliente'
                                       THEN monto END),0) devoluciones,
                     COALESCE(SUM(CASE WHEN concepto='Liquidacion de comision'
                                       THEN monto END),0) comisiones_pagadas
                   FROM movimientos
                   WHERE moneda = ? AND fecha BETWEEN ? AND ?
                     AND operacion IS NULL""",
                (mon, desde, hasta))
            ven = db.query_one(
                """SELECT COUNT(*) files,
                          COALESCE(SUM(importe_cliente),0) ventas,
                          COALESCE(SUM(comision_agencia),0) comision_agencia,
                          COALESCE(SUM(comision_vendedor),0) comision_vendedores,
                          COALESCE(SUM(margen_neto),0) margen
                   FROM v_reservas_saldos
                   WHERE moneda = ? AND cancelada = 0
                     AND COALESCE(fecha_reserva, fecha_cotizacion)
                         BETWEEN ? AND ?""",
                (mon, desde, hasta))
            obj = db.query_one(
                "SELECT importe FROM objetivos WHERE anio=? AND mes=? AND moneda=?",
                (anio, mes, mon))
            cerrado = db.query_one(
                "SELECT * FROM cierres WHERE anio=? AND mes=? AND moneda=?",
                (anio, mes, mon))

            d = {
                "moneda": mon, "anio": anio, "mes": mes,
                "ingresos": float(mov["ing"]) if mov else 0.0,
                "egresos": float(mov["egr"]) if mov else 0.0,
                "cobros_clientes": float(mov["cobros"]) if mov else 0.0,
                "pagos_proveedores": float(mov["pagos_prov"]) if mov else 0.0,
                "gastos_generales": float(mov["gastos"]) if mov else 0.0,
                "devoluciones": float(mov["devoluciones"]) if mov else 0.0,
                "comisiones_pagadas": (
                    float(mov["comisiones_pagadas"]) if mov else 0.0),
                "files": int(ven["files"]) if ven else 0,
                "ventas": float(ven["ventas"]) if ven else 0.0,
                "comision_agencia": (
                    float(ven["comision_agencia"]) if ven else 0.0),
                "comision_vendedores": (
                    float(ven["comision_vendedores"]) if ven else 0.0),
                "margen": float(ven["margen"]) if ven else 0.0,
                "objetivo": float(obj["importe"]) if obj else 0.0,
                "cerrado": bool(cerrado),
                "cerrado_en": cerrado["cerrado_en"] if cerrado else None,
            }
            d["resultado_caja"] = d["ingresos"] - d["egresos"]
            d["cumplimiento"] = (
                round(d["ventas"] / d["objetivo"] * 100, 1)
                if d["objetivo"] else 0.0)
            if d["files"] or d["ingresos"] or d["egresos"] or d["objetivo"]:
                salida.append(d)
        return salida

    @staticmethod
    def comparar(anio: int, mes: int) -> dict[str, dict[str, Any]]:
        """Resumen del mes contra el anterior, indexado por moneda."""
        p_anio, p_mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
        previo = {d["moneda"]: d for d in Cierre.resumen(p_anio, p_mes)}
        actual = {d["moneda"]: d for d in Cierre.resumen(anio, mes)}
        for mon, d in actual.items():
            ant = previo.get(mon)
            d["ventas_prev"] = ant["ventas"] if ant else 0.0
            d["margen_prev"] = ant["margen"] if ant else 0.0
            d["var_ventas"] = (
                round((d["ventas"] - d["ventas_prev"]) / d["ventas_prev"] * 100, 1)
                if d["ventas_prev"] else 0.0)
        return actual

    @staticmethod
    def cerrar(anio: int, mes: int, nota: str = "") -> int:
        import json
        hoy = date.today()
        if (anio, mes) >= (hoy.year, hoy.month):
            raise ErrorNegocio(
                "Solo se pueden cerrar meses ya terminados.")
        filas = Cierre.resumen(anio, mes)
        if not filas:
            raise ErrorNegocio("No hay movimientos para cerrar en ese mes.")
        for d in filas:
            db.execute(
                """INSERT INTO cierres (anio, mes, moneda, resumen, nota)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(anio, mes, moneda) DO UPDATE SET
                       resumen = excluded.resumen, nota = excluded.nota,
                       cerrado_en = datetime('now','localtime')""",
                (anio, mes, d["moneda"], json.dumps(d, default=str), nota))
        return len(filas)

    @staticmethod
    def reabrir(anio: int, mes: int) -> None:
        db.execute("DELETE FROM cierres WHERE anio = ? AND mes = ?", (anio, mes))

    @staticmethod
    def listar_cerrados() -> list[dict[str, Any]]:
        return [dict(f) for f in db.query(
            "SELECT anio, mes, moneda, cerrado_en, nota FROM cierres "
            "ORDER BY anio DESC, mes DESC, moneda")]


# =========================================================== LIQUIDACIONES

class Liquidaciones:
    @staticmethod
    def calcular(anio: int, mes: int) -> list[dict[str, Any]]:
        """Comision que le corresponde a cada vendedor por los files del mes."""
        desde, hasta = _rango_mes(anio, mes)
        filas = db.query(
            """SELECT vendedor_id, vendedor, moneda,
                      COUNT(*) files,
                      SUM(importe_cliente)   ventas,
                      SUM(comision_agencia)  comision_agencia,
                      SUM(comision_vendedor) importe
               FROM v_reservas_saldos
               WHERE cancelada = 0
                 AND COALESCE(fecha_reserva, fecha_cotizacion) BETWEEN ? AND ?
               GROUP BY vendedor_id, moneda
               HAVING importe > 0
               ORDER BY vendedor, moneda""", (desde, hasta))
        salida = []
        for f in filas:
            d = dict(f)
            ya = db.query_one(
                """SELECT id, pagada FROM liquidaciones
                   WHERE vendedor_id=? AND anio=? AND mes=? AND moneda=?""",
                (d["vendedor_id"], anio, mes, d["moneda"]))
            d["anio"], d["mes"] = anio, mes
            d["pagada"] = bool(ya["pagada"]) if ya else False
            d["liquidacion_id"] = ya["id"] if ya else None
            salida.append(d)
        return salida

    @staticmethod
    def detalle(vendedor_id: int, anio: int, mes: int,
                moneda: str) -> list[dict[str, Any]]:
        desde, hasta = _rango_mes(anio, mes)
        return [dict(f) for f in db.query(
            """SELECT file, cliente, destino, importe_cliente,
                      comision_agencia, comision_vendedor,
                      COALESCE(fecha_reserva, fecha_cotizacion) fecha
               FROM v_reservas_saldos
               WHERE vendedor_id = ? AND moneda = ? AND cancelada = 0
                 AND COALESCE(fecha_reserva, fecha_cotizacion) BETWEEN ? AND ?
               ORDER BY fecha""", (vendedor_id, moneda, desde, hasta))]

    @staticmethod
    def marcar_pagada(vendedor_id: int, anio: int, mes: int, moneda: str,
                      importe: float, generar_movimiento: bool = True) -> int:
        """Registra la liquidacion y, si se pide, el egreso en caja."""
        v = db.query_one(
            "SELECT apellido || ', ' || nombre AS n FROM vendedores WHERE id = ?",
            (vendedor_id,))
        nombre = v["n"] if v else f"Vendedor {vendedor_id}"
        mov_id = None
        if generar_movimiento:
            mov_id = Caja.guardar({
                "tipo": "EGRESO",
                "fecha": _rango_mes(anio, mes)[1],
                "concepto": "Liquidacion de comision",
                "moneda": moneda,
                "monto": abs(float(importe)),
                "detalle": f"Comisiones de {nombre} — {mes:02d}/{anio}",
            })
        db.execute(
            """INSERT INTO liquidaciones
                   (vendedor_id, anio, mes, moneda, importe, pagada, movimiento_id)
               VALUES (?,?,?,?,?,1,?)
               ON CONFLICT(vendedor_id, anio, mes, moneda) DO UPDATE SET
                   importe = excluded.importe, pagada = 1,
                   movimiento_id = excluded.movimiento_id""",
            (vendedor_id, anio, mes, moneda, float(importe), mov_id))
        return mov_id or 0


# =========================================================== GASTOS FIJOS

PERIODICIDADES = ("Mensual", "Bimestral", "Trimestral", "Semestral", "Anual")
_INTERVALO_MESES = {"Mensual": 1, "Bimestral": 2, "Trimestral": 3,
                    "Semestral": 6, "Anual": 12}


def _corresponde_mes(periodicidad: str, fecha_inicio: str | None,
                     anio: int, mes: int) -> bool:
    """Si la periodicidad no es mensual, solo corresponde generar en los
    meses que caen justo cada N meses contados desde fecha_inicio. Sin
    fecha_inicio cargada, se comporta como siempre (mensual sin limite)."""
    intervalo = _INTERVALO_MESES.get(periodicidad, 1)
    if intervalo == 1:
        return True
    f = calculos.a_fecha(fecha_inicio)
    if f is None:
        return True
    meses_desde = (anio * 12 + mes) - (f.year * 12 + f.month)
    return meses_desde >= 0 and meses_desde % intervalo == 0


class GastosFijos:
    @staticmethod
    def listar(solo_activos: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM gastos_fijos"
        if solo_activos:
            sql += " WHERE activo = 1"
        return [dict(f) for f in db.query(sql + " ORDER BY concepto")]

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        if not str(datos.get("concepto") or "").strip():
            raise ErrorNegocio("El concepto es obligatorio.")
        if float(datos.get("importe") or 0) <= 0:
            raise ErrorNegocio("El importe debe ser mayor a cero.")
        dia = int(datos.get("dia_mes") or 1)
        if not 1 <= dia <= 28:
            raise ErrorNegocio(
                "El día debe estar entre 1 y 28, para que exista en todos los meses.")
        periodicidad = datos.get("periodicidad") or "Mensual"
        if periodicidad not in PERIODICIDADES:
            raise ErrorNegocio("Periodicidad inválida.")
        if periodicidad != "Mensual" and not str(datos.get("fecha_inicio") or "").strip():
            raise ErrorNegocio(
                "Con una periodicidad distinta de Mensual hace falta una "
                "fecha de inicio, para saber en qué meses corresponde.")
        cant = datos.get("cantidad_cuotas")
        if cant not in (None, "") and int(cant) <= 0:
            raise ErrorNegocio("La cantidad de cuotas debe ser mayor a cero.")
        if datos.get("id"):
            _actualizar("gastos_fijos", int(datos["id"]), datos)
            return int(datos["id"])
        return _insertar("gastos_fijos", datos)

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM gastos_fijos WHERE id = ?", (id_,))

    @staticmethod
    def generar_mes(anio: int, mes: int) -> int:
        """Crea los movimientos del mes. No duplica si ya se generaron."""
        creados = 0
        for g in GastosFijos.listar(solo_activos=True):
            if not _corresponde_mes(g["periodicidad"], g["fecha_inicio"],
                                    anio, mes):
                continue
            fecha = date(anio, mes, min(int(g["dia_mes"] or 1), 28)).isoformat()
            if g["fecha_inicio"] and fecha < g["fecha_inicio"]:
                continue
            if g["fecha_fin"] and fecha > g["fecha_fin"]:
                continue
            cant = g.get("cantidad_cuotas")
            if cant and int(g.get("cuotas_generadas") or 0) >= int(cant):
                continue
            ya = db.query_one(
                """SELECT id FROM movimientos
                   WHERE concepto = ? AND fecha = ? AND moneda = ?
                     AND reserva_id IS NULL""",
                (g["concepto"], fecha, g["moneda"]))
            if ya:
                continue
            Caja.guardar({
                "tipo": "EGRESO", "fecha": fecha, "concepto": g["concepto"],
                "moneda": g["moneda"], "monto": float(g["importe"]),
                "medio_pago": g["medio_pago"] or "",
                "detalle": "Gasto fijo generado automáticamente",
                "operacion": "gasto_fijo",
            })
            db.execute(
                "UPDATE gastos_fijos SET ultimo_generado = ?, "
                "cuotas_generadas = cuotas_generadas + 1 WHERE id = ?",
                (fecha, g["id"]))
            creados += 1
        return creados


# =========================================================== ARQUEO

class Arqueos:
    @staticmethod
    def saldo_efectivo(moneda: str, hasta: str | None = None) -> float:
        sql = ("SELECT COALESCE(SUM(CASE WHEN tipo='INGRESO' THEN monto "
               "ELSE -monto END),0) s FROM movimientos "
               "WHERE moneda = ? AND COALESCE(medio_pago,'') = 'Efectivo'")
        p: list[Any] = [moneda]
        if hasta:
            sql += " AND fecha <= ?"
            p.append(hasta)
        f = db.query_one(sql, tuple(p))
        return float(f["s"]) if f else 0.0

    @staticmethod
    def listar() -> list[dict[str, Any]]:
        return [dict(f) for f in db.query(
            "SELECT * FROM arqueos ORDER BY fecha DESC, id DESC LIMIT 200")]

    @staticmethod
    def guardar(datos: dict[str, Any]) -> int:
        d = dict(datos)
        d["fecha"] = calculos.iso(d.get("fecha")) or date.today().isoformat()
        d["saldo_sistema"] = Arqueos.saldo_efectivo(
            d.get("moneda", "PESOS"), d["fecha"])
        d["diferencia"] = round(
            float(d.get("saldo_contado") or 0) - d["saldo_sistema"], 2)
        return _insertar("arqueos", d)

    @staticmethod
    def eliminar(id_: int) -> None:
        db.execute("DELETE FROM arqueos WHERE id = ?", (id_,))


# =========================================================== OBJETIVOS

class Objetivos:
    @staticmethod
    def obtener(anio: int, mes: int, moneda: str) -> float:
        f = db.query_one(
            "SELECT importe FROM objetivos WHERE anio=? AND mes=? AND moneda=?",
            (anio, mes, moneda))
        return float(f["importe"]) if f else 0.0

    @staticmethod
    def guardar(anio: int, mes: int, moneda: str, importe: float) -> None:
        db.execute(
            """INSERT INTO objetivos (anio, mes, moneda, importe)
               VALUES (?,?,?,?)
               ON CONFLICT(anio, mes, moneda) DO UPDATE SET
                   importe = excluded.importe""",
            (anio, mes, moneda, float(importe)))

    @staticmethod
    def listar(anio: int) -> list[dict[str, Any]]:
        return [dict(f) for f in db.query(
            "SELECT * FROM objetivos WHERE anio = ? ORDER BY mes, moneda",
            (anio,))]
