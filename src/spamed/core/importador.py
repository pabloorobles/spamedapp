"""Importa la base historica desde el Excel BaseDatosSpamed (.xlsm/.xlsx).

Mapea las tablas Clientes, Vendedores, Proveedores, Reservas y Caja del libro
original al modelo relacional. Corrige de paso los problemas conocidos del
Excel: montos de caja con signo mezclado y saldos de proveedor invertidos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import calculos, db

RE_DNI = re.compile(r"\((\d[\d.\s]*)\)")


@dataclass
class Resultado:
    clientes: int = 0
    vendedores: int = 0
    proveedores: int = 0
    reservas: int = 0
    movimientos: int = 0
    servicios: int = 0
    pasajeros: int = 0
    cuotas: int = 0
    avisos: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        lineas = [
            f"Clientes: {self.clientes}",
            f"Vendedores: {self.vendedores}",
            f"Proveedores: {self.proveedores}",
            f"Reservas: {self.reservas}",
            f"Movimientos de caja: {self.movimientos}",
        ]
        # Las hojas nuevas son opcionales: si el libro no las trae, no se
        # nombran para no dar a entender que falto cargar algo.
        for etiqueta, valor in (("Servicios", self.servicios),
                                ("Pasajeros", self.pasajeros),
                                ("Cuotas", self.cuotas)):
            if valor:
                lineas.append(f"{etiqueta}: {valor}")
        return "\n".join(lineas)


def _norm(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _num(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    txt = str(v).replace(".", "").replace(",", ".")
    txt = re.sub(r"[^0-9.\-]", "", txt)
    try:
        return float(txt or 0)
    except ValueError:
        return 0.0


def _dni_de_id_completo(texto: str) -> str:
    """'Rios Valentina (35.555.999)' -> '35555999'"""
    m = RE_DNI.search(texto or "")
    if not m:
        return ""
    return re.sub(r"\D", "", m.group(1))


def _nombre_de_id_completo(texto: str) -> tuple[str, str]:
    """'Rios Valentina (35.555.999)' -> ('Valentina', 'Rios')  (apellido primero)"""
    base = RE_DNI.sub("", texto or "").strip()
    partes = base.split()
    if not partes:
        return ("", "")
    if len(partes) == 1:
        return (partes[0], "")
    return (" ".join(partes[1:]), partes[0])


def _leer_tabla(ws, nombre_tabla: str) -> list[dict[str, Any]]:
    """Lee un ListObject de la hoja como lista de dicts."""
    ref = None
    for nom, rango in getattr(ws, "tables", {}).items():
        if nom.lower() == nombre_tabla.lower():
            ref = rango if isinstance(rango, str) else getattr(rango, "ref", None)
            break
    if ref is None:
        return _leer_rango_usado(ws)
    filas = list(ws[ref])
    if not filas:
        return []
    encabezados = [_norm(c.value) for c in filas[0]]
    datos = []
    for fila in filas[1:]:
        d = {h: c.value for h, c in zip(encabezados, fila) if h}
        if any(v is not None and v != "" for v in d.values()):
            datos.append(d)
    return datos


def _leer_rango_usado(ws) -> list[dict[str, Any]]:
    filas = list(ws.iter_rows(values_only=True))
    filas = [f for f in filas if any(v not in (None, "") for v in f)]
    if not filas:
        return []
    encabezados = [_norm(v) for v in filas[0]]
    return [
        {h: v for h, v in zip(encabezados, f) if h}
        for f in filas[1:]
    ]


def importar(ruta: str | Path, limpiar: bool = False) -> Resultado:
    try:
        import openpyxl
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Falta la libreria openpyxl para leer archivos Excel."
        ) from e

    res = Resultado()
    wb = openpyxl.load_workbook(str(ruta), data_only=True, read_only=False)
    con = db.conectar()

    if limpiar:
        for tabla in ("movimientos", "reservas", "clientes",
                      "vendedores", "proveedores"):
            con.execute(f"DELETE FROM {tabla}")
        con.commit()

    # ---------------------------------------------------------- CLIENTES
    map_cliente: dict[str, int] = {}   # dni -> id
    if "Clientes" in wb.sheetnames:
        for f in _leer_tabla(wb["Clientes"], "Clientes"):
            dni = re.sub(r"\D", "", _norm(f.get("dni")))
            if not dni:
                continue
            datos = {
                "dni": dni,
                "nombre": _norm(f.get("nombre")),
                "apellido": _norm(f.get("apellido")),
                "telefono": _norm(f.get("teléfono") or f.get("telefono")),
                "email": _norm(f.get("email")),
                "direccion": _norm(f.get("dirección") or f.get("direccion")),
                "fecha_nac": calculos.iso(f.get("Cumple")),
                "fecha_alta": calculos.iso(f.get("FechaAlta")),
                "canal": _norm(f.get("Referido")),
                "detalle_canal": _norm(f.get("Detalle_referido")),
                "observaciones": _norm(f.get("Observaciones")),
            }
            cur = con.execute(
                """INSERT INTO clientes (dni,nombre,apellido,telefono,email,
                       direccion,fecha_nac,fecha_alta,canal,detalle_canal,observaciones)
                   VALUES (:dni,:nombre,:apellido,:telefono,:email,:direccion,
                           :fecha_nac,COALESCE(:fecha_alta,date('now','localtime')),
                           :canal,:detalle_canal,:observaciones)
                   ON CONFLICT(dni) DO UPDATE SET
                       nombre=excluded.nombre, apellido=excluded.apellido,
                       telefono=excluded.telefono, email=excluded.email""",
                datos,
            )
            fila = con.execute(
                "SELECT id FROM clientes WHERE dni = ?", (dni,)
            ).fetchone()
            map_cliente[dni] = fila["id"]
            if cur.rowcount:
                res.clientes += 1
        con.commit()

    # -------------------------------------------------------- VENDEDORES
    map_vendedor: dict[str, int] = {}  # "apellido nombre" normalizado -> id
    if "Vendedores" in wb.sheetnames:
        for f in _leer_tabla(wb["Vendedores"], "Vendedores"):
            dni = re.sub(r"\D", "", _norm(f.get("dni")))
            nombre = _norm(f.get("nombre"))
            apellido = _norm(f.get("apellido"))
            if not (dni or nombre or apellido):
                continue
            dni = dni or f"S/D-{apellido}{nombre}"[:20]
            datos = {
                "dni": dni,
                "nombre": nombre,
                "apellido": apellido,
                "telefono": _norm(f.get("teléfono") or f.get("telefono")),
                "comision_pct": _num(f.get("comision%") or f.get("comision")),
                "activo": 0 if _norm(f.get("estado")).lower().startswith("inact") else 1,
            }
            con.execute(
                """INSERT INTO vendedores (dni,nombre,apellido,telefono,
                        comision_pct,activo)
                   VALUES (:dni,:nombre,:apellido,:telefono,:comision_pct,:activo)
                   ON CONFLICT(dni) DO UPDATE SET
                        nombre=excluded.nombre, apellido=excluded.apellido,
                        comision_pct=excluded.comision_pct""",
                datos,
            )
            vid = con.execute(
                "SELECT id FROM vendedores WHERE dni = ?", (dni,)
            ).fetchone()["id"]
            map_vendedor[f"{apellido} {nombre}".lower().strip()] = vid
            map_vendedor[f"{nombre} {apellido}".lower().strip()] = vid
            res.vendedores += 1
        con.commit()

    # ------------------------------------------------------- PROVEEDORES
    map_prov: dict[str, int] = {}
    if "Proveedores" in wb.sheetnames:
        for f in _leer_tabla(wb["Proveedores"], "Proveedores"):
            nombre = _norm(f.get("nombre"))
            if not nombre:
                continue
            # 'transfiere_neto': SI/NO en la plantilla; por defecto SI, que es
            # lo mas comun (se le gira la venta menos la comision).
            neto_txt = _norm(f.get("transfiere_neto")).upper()
            neto = 0 if neto_txt.startswith(("N", "0", "F")) else 1
            con.execute(
                """INSERT INTO proveedores
                       (nombre,tipo,moneda,contacto,comision_pct,transfiere_neto)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(nombre) DO UPDATE SET
                        tipo=excluded.tipo, moneda=excluded.moneda,
                        comision_pct=excluded.comision_pct,
                        transfiere_neto=excluded.transfiere_neto""",
                (nombre, _norm(f.get("tipo")),
                 _norm(f.get("moneda")) or "PESOS", _norm(f.get("contacto")),
                 _num(f.get("comision%") or f.get("comision")), neto),
            )
            map_prov[nombre.lower()] = con.execute(
                "SELECT id FROM proveedores WHERE nombre = ?", (nombre,)
            ).fetchone()["id"]
            res.proveedores += 1
        con.commit()

    # ---------------------------------------------------------- RESERVAS
    map_file: dict[str, int] = {}
    if "Reservas" in wb.sheetnames:
        for f in _leer_tabla(wb["Reservas"], "Reservas"):
            file_ = _norm(f.get("file")).upper()
            if not file_:
                continue

            id_cli = _norm(f.get("id_cli"))
            dni = _dni_de_id_completo(id_cli)
            cliente_id = map_cliente.get(dni)
            if cliente_id is None:
                nombre, apellido = _nombre_de_id_completo(id_cli)
                if not (nombre or apellido):
                    res.avisos.append(f"{file_}: sin cliente identificable, omitido")
                    continue
                dni = dni or f"S/D-{file_}"
                cur = con.execute(
                    "INSERT OR IGNORE INTO clientes (dni,nombre,apellido) VALUES (?,?,?)",
                    (dni, nombre, apellido),
                )
                cliente_id = con.execute(
                    "SELECT id FROM clientes WHERE dni = ?", (dni,)
                ).fetchone()["id"]
                map_cliente[dni] = cliente_id
                if cur.rowcount:
                    res.clientes += 1
                    res.avisos.append(f"{file_}: cliente '{id_cli}' creado desde la reserva")

            id_vend = _norm(f.get("id_vend"))
            vendedor_id = map_vendedor.get(
                RE_DNI.sub("", id_vend).strip().lower()
            )
            if vendedor_id is None:
                nombre, apellido = _nombre_de_id_completo(id_vend)
                dni_v = _dni_de_id_completo(id_vend) or f"S/D-{apellido}{nombre}"[:20]
                con.execute(
                    "INSERT OR IGNORE INTO vendedores (dni,nombre,apellido) VALUES (?,?,?)",
                    (dni_v, nombre, apellido),
                )
                vendedor_id = con.execute(
                    "SELECT id FROM vendedores WHERE dni = ?", (dni_v,)
                ).fetchone()["id"]
                map_vendedor[f"{apellido} {nombre}".lower().strip()] = vendedor_id
                res.vendedores += 1
                res.avisos.append(f"{file_}: vendedor '{id_vend}' creado desde la reserva")

            nom_prov = _norm(f.get("id_prov"))
            proveedor_id = map_prov.get(nom_prov.lower())
            if proveedor_id is None:
                nom_prov = nom_prov or "(sin proveedor)"
                con.execute(
                    "INSERT OR IGNORE INTO proveedores (nombre) VALUES (?)", (nom_prov,)
                )
                proveedor_id = con.execute(
                    "SELECT id FROM proveedores WHERE nombre = ?", (nom_prov,)
                ).fetchone()["id"]
                map_prov[nom_prov.lower()] = proveedor_id
                res.proveedores += 1

            datos = {
                "file": file_,
                "cliente_id": cliente_id,
                "vendedor_id": vendedor_id,
                "proveedor_id": proveedor_id,
                "destino": _norm(f.get("destino")),
                "moneda": _norm(f.get("moneda")) or "PESOS",
                "importe_cliente": _num(f.get("importe_cli")),
                "costo_proveedor": _num(f.get("costo_prov")),
                "fecha_cotizacion": calculos.iso(f.get("inicio de cotizacion")),
                "fecha_reserva": calculos.iso(f.get("fecha reserva")),
                "fecha_vto_sena": calculos.iso(f.get("vto_seña") or f.get("vto_sena")),
                "fecha_vto_reserva": calculos.iso(f.get("vto_reserva")),
                "fecha_entrega_voucher": calculos.iso(f.get("Entrega Voucher")),
                "transporte": _norm(f.get("transporte")),
                "hotel": _norm(f.get("hotel")),
                "regimen": _norm(f.get("regimen")),
                "excursiones": _norm(f.get("excursiones")),
                "cancelada": 1 if f.get("Cancelada") is True else 0,
            }
            cols = ",".join(datos)
            marks = ",".join(f":{k}" for k in datos)
            con.execute(
                f"INSERT INTO reservas ({cols}) VALUES ({marks}) "
                f"ON CONFLICT(file) DO UPDATE SET "
                f"destino=excluded.destino, importe_cliente=excluded.importe_cliente, "
                f"costo_proveedor=excluded.costo_proveedor",
                datos,
            )
            map_file[file_] = con.execute(
                "SELECT id FROM reservas WHERE file = ?", (file_,)
            ).fetchone()["id"]
            res.reservas += 1
        con.commit()

    # -------------------------------------------------------------- CAJA
    if "Caja" in wb.sheetnames:
        for f in _leer_tabla(wb["Caja"], "Caja"):
            monto = _num(f.get("monto"))
            fecha = calculos.iso(f.get("fecha"))
            if not fecha or monto == 0:
                continue
            asociado = _norm(f.get("asociado")).upper()
            reserva_id = map_file.get(asociado)
            if asociado and reserva_id is None:
                res.avisos.append(
                    f"Movimiento del {fecha}: el file '{asociado}' no existe, "
                    "se importa como gasto general"
                )
            con.execute(
                """INSERT INTO movimientos
                       (fecha,tipo,concepto,reserva_id,moneda,monto,medio_pago,detalle)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    fecha,
                    "INGRESO" if monto > 0 else "EGRESO",
                    _norm(f.get("concepto")) or "Importado",
                    reserva_id,
                    _norm(f.get("moneda")) or "PESOS",
                    abs(monto),
                    _norm(f.get("tipo_pago")),
                    _norm(f.get("detalle")),
                ),
            )
            res.movimientos += 1
        con.commit()

    # ============================================ hojas nuevas (opcionales)
    # No existian en el libro viejo: si no estan, no pasa nada. Todas se
    # enganchan al file por el numero de reserva.

    def _reserva_de(fila: dict[str, Any], hoja: str) -> int | None:
        file_ = _norm(fila.get("file")).upper()
        if not file_:
            return None
        rid = map_file.get(file_)
        if rid is None:
            # El file puede existir de una importacion anterior.
            existente = con.execute(
                "SELECT id FROM reservas WHERE file = ?", (file_,)
            ).fetchone()
            if existente:
                rid = existente["id"]
                map_file[file_] = rid
        if rid is None:
            res.avisos.append(
                f"{hoja}: el file '{file_}' no existe, se omite la fila")
        return rid

    # ------------------------------------------------------- SERVICIOS
    if "Servicios" in wb.sheetnames:
        vistos: set[int] = set()
        for f in _leer_tabla(wb["Servicios"], "Servicios"):
            reserva_id = _reserva_de(f, "Servicios")
            if reserva_id is None:
                continue
            concepto = _norm(f.get("concepto"))
            if not concepto:
                continue
            # Reimportar no debe duplicar: se limpian los servicios del file
            # la primera vez que aparece en esta corrida.
            if reserva_id not in vistos:
                con.execute("DELETE FROM reserva_servicios WHERE reserva_id = ?",
                            (reserva_id,))
                vistos.add(reserva_id)

            nom_prov = _norm(f.get("proveedor"))
            proveedor_id = map_prov.get(nom_prov.lower())
            if proveedor_id is None:
                nom_prov = nom_prov or "(sin proveedor)"
                con.execute(
                    "INSERT OR IGNORE INTO proveedores (nombre) VALUES (?)",
                    (nom_prov,))
                proveedor_id = con.execute(
                    "SELECT id FROM proveedores WHERE nombre = ?", (nom_prov,)
                ).fetchone()["id"]
                map_prov[nom_prov.lower()] = proveedor_id
                res.proveedores += 1
            con.execute(
                """INSERT INTO reserva_servicios
                       (reserva_id,proveedor_id,concepto,detalle,
                        importe_venta,costo)
                   VALUES (?,?,?,?,?,?)""",
                (reserva_id, proveedor_id, concepto, _norm(f.get("detalle")),
                 _num(f.get("importe_venta")), _num(f.get("costo"))),
            )
            res.servicios += 1
        con.commit()

    # ------------------------------------------------------- PASAJEROS
    if "Pasajeros" in wb.sheetnames:
        vistos = set()
        for f in _leer_tabla(wb["Pasajeros"], "Pasajeros"):
            reserva_id = _reserva_de(f, "Pasajeros")
            if reserva_id is None:
                continue
            nombre = _norm(f.get("nombre"))
            if not nombre:
                continue
            if reserva_id not in vistos:
                con.execute("DELETE FROM pasajeros WHERE reserva_id = ?",
                            (reserva_id,))
                vistos.add(reserva_id)
            con.execute(
                """INSERT INTO pasajeros
                       (reserva_id,nombre,documento,fecha_nac,pasaporte,
                        vto_pasaporte,observaciones)
                   VALUES (?,?,?,?,?,?,?)""",
                (reserva_id, nombre, _norm(f.get("documento")),
                 calculos.iso(f.get("fecha_nac")), _norm(f.get("pasaporte")),
                 calculos.iso(f.get("vto_pasaporte")),
                 _norm(f.get("observaciones"))),
            )
            res.pasajeros += 1
        con.commit()

    # ---------------------------------------------------------- CUOTAS
    if "Cuotas" in wb.sheetnames:
        vistos = set()
        for f in _leer_tabla(wb["Cuotas"], "Cuotas"):
            reserva_id = _reserva_de(f, "Cuotas")
            if reserva_id is None:
                continue
            vencimiento = calculos.iso(f.get("vencimiento"))
            importe = _num(f.get("importe"))
            if not vencimiento or importe <= 0:
                continue
            if reserva_id not in vistos:
                con.execute("DELETE FROM cuotas WHERE reserva_id = ?",
                            (reserva_id,))
                vistos.add(reserva_id)
            numero = int(_num(f.get("numero")) or (len(
                [c for c in con.execute(
                    "SELECT id FROM cuotas WHERE reserva_id = ?",
                    (reserva_id,))]) + 1))
            con.execute(
                "INSERT INTO cuotas (reserva_id,numero,vencimiento,importe,nota) "
                "VALUES (?,?,?,?,?)",
                (reserva_id, numero, vencimiento, importe, _norm(f.get("nota"))),
            )
            res.cuotas += 1
        con.commit()

    wb.close()
    return res
