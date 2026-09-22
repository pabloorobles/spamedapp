"""Pruebas de las reglas de negocio (no requiere interfaz grafica).

Uso:
    set SPAMED_DATA_DIR=%TEMP%\\spamed_test
    python tests\\test_negocio.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

TMP = Path(tempfile.gettempdir()) / "spamed_pruebas"
shutil.rmtree(TMP, ignore_errors=True)
os.environ["SPAMED_DATA_DIR"] = str(TMP)

from spamed.core import bcra, calculos, db, repo  # noqa: E402

fallos: list[str] = []


def check(condicion: bool, descripcion: str) -> None:
    estado = "OK  " if condicion else "FALLA"
    print(f"  [{estado}] {descripcion}")
    if not condicion:
        fallos.append(descripcion)


def seccion(titulo: str) -> None:
    print(f"\n{titulo}")


def main() -> int:
    db.conectar()
    hoy = date.today()

    seccion("Maestros")
    cid = repo.Clientes.guardar(
        {"dni": "30111222", "nombre": "Lucia", "apellido": "Martinez"}
    )
    vid = repo.Vendedores.guardar(
        {"dni": "54654524", "nombre": "Rosa", "apellido": "Medrano",
         "comision_pct": 10}
    )
    pid = repo.Proveedores.guardar({"nombre": "Amichi", "moneda": "PESOS"})
    check(all((cid, vid, pid)), "alta de cliente, vendedor y proveedor")

    try:
        repo.Clientes.guardar({"dni": "30111222", "nombre": "X", "apellido": "Y"})
        check(False, "rechaza DNI duplicado")
    except repo.ErrorNegocio:
        check(True, "rechaza DNI duplicado")

    seccion("Ciclo de vida de una reserva")
    rid = repo.Reservas.guardar({
        "file": "R2601", "cliente_id": cid, "vendedor_id": vid,
        "proveedor_id": pid, "moneda": "PESOS",
        "importe_cliente": 1000, "costo_proveedor": 800,
        "fecha_vto_reserva": (hoy + timedelta(days=10)).isoformat(),
        "fecha_salida": (hoy + timedelta(days=60)).isoformat(),
        "fecha_regreso": (hoy + timedelta(days=70)).isoformat(),
    })
    r = repo.Reservas.obtener(rid)
    check(r["estado"] == "Cotizado", "alta -> Cotizado")
    check(r["saldo_cliente"] == 1000, "saldo cliente inicial = importe")
    check(r["saldo_proveedor"] == 800, "saldo proveedor inicial = costo")
    check(r["comision_vendedor"] == 20, "comision = 10% de la ganancia (200)")

    repo.Reservas.guardar({**dict(repo.Reservas.crudo(rid)),
                           "fecha_reserva": hoy.isoformat()})
    check(repo.Reservas.obtener(rid)["estado"] == "Reservado",
          "el cliente dice que si, sin pagar nada -> Reservado")

    repo.Caja.guardar({"tipo": "INGRESO", "fecha": hoy.isoformat(),
                       "concepto": "Sena", "reserva_id": rid,
                       "moneda": "PESOS", "monto": 250})
    r = repo.Reservas.obtener(rid)
    check(r["estado"] == "Confirmado", "cobro del 25% (la sena) -> Confirmado")
    check(r["saldo_cliente"] == 750, "el saldo baja al cobrar")

    repo.Caja.guardar({"tipo": "INGRESO", "fecha": hoy.isoformat(),
                       "concepto": "Saldo", "reserva_id": rid,
                       "moneda": "PESOS", "monto": 750})
    check(repo.Reservas.obtener(rid)["estado"] == "Confirmado",
          "cobro total del cliente, proveedor sin pagar -> sigue Confirmado")

    repo.Caja.guardar({"tipo": "EGRESO", "fecha": hoy.isoformat(),
                       "concepto": "Pago Proveedor", "reserva_id": rid,
                       "moneda": "PESOS", "monto": 800})
    r = repo.Reservas.obtener(rid)
    check(r["saldo_proveedor"] == 0,
          "el pago RESTA del saldo del proveedor (bug del Excel)")
    check(r["estado"] == "Emitido",
          "las dos puntas pagadas (cliente y proveedor) -> Emitido")

    check(not r["voucher_recibido"],
          "el voucher del operador todavia no llego")
    repo.Reservas.guardar({**dict(repo.Reservas.crudo(rid)),
                           "voucher_recibido": hoy.isoformat()})
    check(repo.Reservas.obtener(rid)["estado"] == "Emitido",
          "marcar el voucher recibido no cambia el estado (es un dato dentro"
          " de Emitido, no un gatillo)")

    seccion("Estados por fecha")
    base = {"importe_cliente": 100, "cobrado_cliente": 100,
            "saldo_cliente": 0, "saldo_proveedor": 0, "cancelada": 0}
    check(calculos.estado_reserva(
        {**base, "fecha_salida": (hoy - timedelta(days=1)).isoformat(),
         "fecha_regreso": (hoy + timedelta(days=5)).isoformat()}) == "En Viaje",
        "entre salida y regreso -> En Viaje")
    check(calculos.estado_reserva(
        {**base, "fecha_regreso": (hoy - timedelta(days=1)).isoformat()}
    ) == "Finalizado", "despues del regreso -> Finalizado")
    check(calculos.estado_reserva(
        {"importe_cliente": 100, "cobrado_cliente": 0, "saldo_cliente": 100,
         "saldo_proveedor": 100, "cancelada": 0,
         "fecha_vto_reserva": (hoy - timedelta(days=1)).isoformat()}
    ) == "Vencido", "vencimiento pasado sin cobros -> Vencido")
    check(calculos.estado_reserva(
        {"importe_cliente": 100, "cobrado_cliente": 0, "saldo_cliente": 100,
         "saldo_proveedor": 100, "cancelada": 0,
         "fecha_reserva": hoy.isoformat(),
         "fecha_vto_reserva": (hoy - timedelta(days=1)).isoformat()}
    ) == "Vencido",
        "vencido gana sobre Reservado: haber dicho que si no protege del "
        "vencimiento si no hay plata")
    check(calculos.estado_reserva({**base, "cancelada": 1}) == "Cancelado",
          "cancelada gana sobre todo lo demas")

    seccion("Validaciones")
    casos = [
        ("file duplicado", lambda: repo.Reservas.guardar(
            {"file": "R2601", "cliente_id": cid, "vendedor_id": vid,
             "proveedor_id": pid})),
        ("reserva sin cliente", lambda: repo.Reservas.guardar(
            {"file": "R9999", "vendedor_id": vid, "proveedor_id": pid})),
        ("monto cero en caja", lambda: repo.Caja.guardar(
            {"tipo": "INGRESO", "fecha": hoy.isoformat(),
             "concepto": "x", "monto": 0})),
        ("moneda cruzada", lambda: repo.Caja.guardar(
            {"tipo": "INGRESO", "fecha": hoy.isoformat(), "concepto": "x",
             "monto": 10, "reserva_id": rid, "moneda": "DOLAR"})),
        ("regreso antes de salida", lambda: repo.Reservas.guardar(
            {"file": "R9998", "cliente_id": cid, "vendedor_id": vid,
             "proveedor_id": pid,
             "fecha_salida": "2026-12-10", "fecha_regreso": "2026-12-01"})),
        ("borrar file con movimientos", lambda: repo.Reservas.eliminar(rid)),
        ("borrar cliente con files", lambda: repo.Clientes.eliminar(cid)),
    ]
    for nombre, fn in casos:
        try:
            fn()
            check(False, f"rechaza {nombre}")
        except repo.ErrorNegocio:
            check(True, f"rechaza {nombre}")

    seccion("Numeracion y formato")
    check(repo.Reservas.sugerir_file() == "R2602",
          "sugiere el file siguiente (R2601 -> R2602)")
    check(calculos.money(1234567.89, "PESOS") == "$ 1.234.567,89",
          "formato de moneda argentino")
    check(calculos.dd_mm_yyyy("2026-03-09") == "09/03/2026",
          "formato de fecha dd/mm/aaaa")

    seccion("Caja general y reportes")
    repo.Caja.guardar({"tipo": "EGRESO", "fecha": hoy.isoformat(),
                       "concepto": "Sueldos", "moneda": "PESOS", "monto": 500})
    tot = {t["moneda"]: t for t in repo.Caja.totales()}
    check(tot["PESOS"]["ingresos"] == 1000 and tot["PESOS"]["egresos"] == 1300,
          "totales de caja separados por moneda")
    check(len(repo.Reportes.comisiones()) == 1, "reporte de comisiones")
    check(repo.Reportes.dashboard()["cant_activas"] == 1, "tablero responde")

    seccion("Comisión del mayorista")
    pid2 = repo.Proveedores.guardar(
        {"nombre": "Mayorista12", "comision_pct": 12, "transfiere_neto": 1})
    rid2 = repo.Reservas.guardar({
        "file": "R2610", "cliente_id": cid, "vendedor_id": vid,
        "proveedor_id": pid2, "moneda": "PESOS", "importe_cliente": 1000000,
        "fecha_reserva": hoy.isoformat(),
    })
    r2 = repo.Reservas.obtener(rid2)
    check(abs(r2["comision_agencia"] - 120000) < 0.01,
          "comisión de la agencia = 12% de la venta")
    check(abs(r2["costo_proveedor"] - 880000) < 0.01,
          "costo del proveedor = venta - comisión")
    check(abs(r2["comision_vendedor"] - 12000) < 0.01,
          "comisión del vendedor = 10% de la comisión de la agencia")
    check(abs(r2["margen_neto"] - 108000) < 0.01,
          "margen de la agencia = comisión - parte del vendedor")
    check(r2["transfiere_neto"] == 1, "hereda el flag de pago neto")

    seccion("Variantes de operador (nacional/internacional x moneda)")
    check(repo.Reservas.obtener(rid2)["pct_proveedor"] == 12,
          "sin tipo_viaje, sigue usando la comisión general")
    repo.ProveedorVariantes.guardar({
        "proveedor_id": pid2, "tipo_viaje": "Nacional", "moneda": "PESOS",
        "comision_pct": 20, "transfiere_neto": 0})
    rid_var = repo.Reservas.guardar({
        "file": "R2611", "cliente_id": cid, "vendedor_id": vid,
        "proveedor_id": pid2, "moneda": "PESOS", "tipo_viaje": "Nacional",
        "importe_cliente": 100000})
    r_var = repo.Reservas.obtener(rid_var)
    check(r_var["pct_proveedor"] == 20,
          "con tipo_viaje que matchea la variante, usa su comisión")
    check(r_var["transfiere_neto"] == 0, "y también su forma de pago")
    check(repo.Reservas.obtener(rid2)["pct_proveedor"] == 12,
          "un file sin tipo_viaje no se ve afectado por la variante")
    rid_var2 = repo.Reservas.guardar({
        "file": "R2612", "cliente_id": cid, "vendedor_id": vid,
        "proveedor_id": pid2, "moneda": "PESOS", "tipo_viaje": "Internacional",
        "importe_cliente": 100000})
    check(repo.Reservas.obtener(rid_var2)["pct_proveedor"] == 12,
          "sin variante para Internacional, cae a la general")
    try:
        repo.ProveedorVariantes.guardar({
            "proveedor_id": pid2, "tipo_viaje": "Nacional", "moneda": "PESOS",
            "comision_pct": 5})
        check(False, "rechaza una variante duplicada")
    except repo.ErrorNegocio:
        check(True, "rechaza una variante duplicada")

    seccion("Servicios (varios proveedores)")
    repo.Servicios.guardar({"reserva_id": rid2, "proveedor_id": pid2,
                            "concepto": "Aereo", "costo": 500000})
    repo.Servicios.guardar({"reserva_id": rid2, "proveedor_id": pid,
                            "concepto": "Hotel", "costo": 300000})
    r2 = repo.Reservas.obtener(rid2)
    check(r2["cant_servicios"] == 2, "se cargan dos servicios")
    check(abs(r2["costo_proveedor"] - 800000) < 0.01,
          "el costo pasa a ser la suma de los servicios")

    seccion("Pasajeros y plan de cuotas")
    repo.Pasajeros.guardar({"reserva_id": rid2, "nombre": "Ana Perez",
                            "vto_pasaporte": (hoy + timedelta(days=60)).isoformat()})
    check(len(repo.Pasajeros.listar(rid2)) == 1, "alta de pasajero")
    check(len(repo.Pasajeros.pasaportes_por_vencer()) == 1,
          "detecta pasaportes por vencer")
    repo.Cuotas.generar_plan(rid2, 4, hoy.isoformat(), 30)
    cs = repo.Cuotas.listar(rid2)
    check(len(cs) == 4, "genera 4 cuotas")
    check(abs(sum(c["importe"] for c in cs) - 1000000) < 0.01,
          "las cuotas suman el saldo exacto")

    seccion("Duplicar")
    nid = repo.Reservas.duplicar(rid2)
    n = repo.Reservas.obtener(nid)
    check(n["file"] != r2["file"], "el duplicado recibe un file nuevo")
    check(n["cant_servicios"] == 2, "copia los servicios")
    check(len(repo.Pasajeros.listar(nid)) == 1, "copia los pasajeros")
    check(n["cobrado_cliente"] == 0, "no copia los movimientos de caja")

    seccion("Cancelación con devolución")
    repo.Caja.guardar({"tipo": "INGRESO", "fecha": hoy.isoformat(),
                       "concepto": "Sena", "reserva_id": nid,
                       "moneda": "PESOS", "monto": 200000})
    try:
        repo.Reservas.cancelar(nid, "prueba", 500000, True)
        check(False, "rechaza devolver más de lo cobrado")
    except repo.ErrorNegocio:
        check(True, "rechaza devolver más de lo cobrado")
    repo.Reservas.cancelar(nid, "se arrepintió", 150000, True)
    n = repo.Reservas.obtener(nid)
    check(n["estado"] == "Cancelado", "el file queda cancelado")
    check(abs(n["devuelto"] - 150000) < 0.01, "registra la devolución en caja")

    seccion("Cierre y liquidaciones")
    res = repo.Cierre.resumen(hoy.year, hoy.month)
    check(bool(res), "arma el resumen del mes")
    pesos = [d for d in res if d["moneda"] == "PESOS"]
    check(bool(pesos) and pesos[0]["files"] >= 1, "cuenta los files del mes")
    liq = repo.Liquidaciones.calcular(hoy.year, hoy.month)
    check(bool(liq), "calcula comisiones a liquidar")
    if liq:
        l = liq[0]
        repo.Liquidaciones.marcar_pagada(
            l["vendedor_id"], hoy.year, hoy.month, l["moneda"], l["importe"])
        check(repo.Liquidaciones.calcular(
            hoy.year, hoy.month)[0]["pagada"], "marca la liquidación pagada")
    try:
        repo.Cierre.cerrar(hoy.year, hoy.month)
        check(False, "no deja cerrar el mes en curso")
    except repo.ErrorNegocio:
        check(True, "no deja cerrar el mes en curso")

    seccion("Gastos fijos y arqueo")
    repo.GastosFijos.guardar({"concepto": "Internet", "moneda": "PESOS",
                              "importe": 45000, "dia_mes": 10})
    n1 = repo.GastosFijos.generar_mes(hoy.year, hoy.month)
    n2 = repo.GastosFijos.generar_mes(hoy.year, hoy.month)
    check(n1 == 1 and n2 == 0, "genera el gasto una sola vez por mes")
    try:
        repo.GastosFijos.guardar({"concepto": "X", "importe": 1, "dia_mes": 31})
        check(False, "rechaza día 31")
    except repo.ErrorNegocio:
        check(True, "rechaza día 31")
    try:
        repo.GastosFijos.guardar({"concepto": "Seguro", "importe": 1000,
                                  "periodicidad": "Anual"})
        check(False, "rechaza periodicidad no mensual sin fecha de inicio")
    except repo.ErrorNegocio:
        check(True, "rechaza periodicidad no mensual sin fecha de inicio")

    gid_seguro = repo.GastosFijos.guardar({
        "concepto": "Seguro", "moneda": "PESOS", "importe": 50000,
        "dia_mes": 10, "periodicidad": "Trimestral",
        "fecha_inicio": f"{hoy.year}-01-01"})
    # Ojo: generar_mes() tambien reevalua "Internet" (mensual, ya cargado
    # arriba) en cada mes del loop, asi que el conteo hay que hacerlo por
    # concepto (via cuotas_generadas de ESTE gasto), no sumando el total
    # que devuelve generar_mes().
    for m in range(1, 13):
        repo.GastosFijos.generar_mes(hoy.year, m)
    fila_seguro = [g for g in repo.GastosFijos.listar() if g["id"] == gid_seguro][0]
    check(fila_seguro["cuotas_generadas"] == 4,
          "trimestral genera exactamente 4 veces en el año")

    gid_cuota = repo.GastosFijos.guardar({
        "concepto": "Cuota equipo", "moneda": "PESOS", "importe": 20000,
        "dia_mes": 1, "cantidad_cuotas": 3})
    for m in range(1, 6):
        repo.GastosFijos.generar_mes(2030, m)
    fila_cuota = [g for g in repo.GastosFijos.listar() if g["id"] == gid_cuota][0]
    check(fila_cuota["cuotas_generadas"] == 3,
          "con cantidad_cuotas=3 se corta después de la tercera")

    repo.Arqueos.guardar({"fecha": hoy.isoformat(), "moneda": "PESOS",
                          "saldo_contado": 0})
    check(repo.Arqueos.listar()[0]["diferencia"] is not None,
          "el arqueo calcula la diferencia")

    seccion("DNI y tarjetas de referencia del cliente")
    repo.Clientes.guardar({
        "id": cid, "dni": "30111222", "apellido": "Martinez", "nombre": "Lucia",
        "dni_vencimiento": (hoy + timedelta(days=30)).isoformat()})
    check(len(repo.Clientes.dni_por_vencer(dias=90)) == 1,
          "detecta el DNI por vencer")
    mm_aa = f"{(hoy.month % 12) + 1:02d}/{str(hoy.year)[2:]}"
    repo.TarjetasCliente.guardar({
        "cliente_id": cid, "marca": "Visa", "ultimos4": "1234",
        "vencimiento": mm_aa})
    check(len(repo.TarjetasCliente.listar(cid)) == 1, "alta de tarjeta")
    check(len(repo.TarjetasCliente.por_vencer(dias=60)) == 1,
          "detecta tarjetas por vencer (MM/AA dentro de la ventana)")
    try:
        repo.TarjetasCliente.guardar({"cliente_id": cid, "ultimos4": "12"})
        check(False, "rechaza últimos 4 dígitos inválidos")
    except repo.ErrorNegocio:
        check(True, "rechaza últimos 4 dígitos inválidos")
    try:
        repo.TarjetasCliente.guardar({"cliente_id": cid, "vencimiento": "2027-08"})
        check(False, "rechaza vencimiento con formato distinto de MM/AA")
    except repo.ErrorNegocio:
        check(True, "rechaza vencimiento con formato distinto de MM/AA")

    seccion("Cotización del BCRA (guardado local, sin depender de internet)")
    bcra.guardar_manual(1234.5)
    valor, fecha = bcra.ultima_guardada()
    check(valor == 1234.5 and fecha is not None,
          "guarda y recupera la última cotización")
    url_original = bcra.URL
    bcra.URL = "https://esto-no-deberia-existir.invalido/x"
    try:
        bcra.obtener_online()
        check(False, "una URL inválida debería fallar")
    except bcra.ErrorCotizacion:
        check(True, "un fallo de red cae en ErrorCotizacion, no rompe")
    bcra.URL = url_original
    valor2, _ = bcra.ultima_guardada()
    check(valor2 == 1234.5,
          "la última cotización guardada no se toca si falla la red")

    seccion("Seguimiento y estado de cuenta")
    repo.Seguimientos.guardar({
        "cliente_id": cid, "fecha": hoy.isoformat(), "canal": "WhatsApp",
        "nota": "Lo piensa", "proximo": (hoy + timedelta(days=2)).isoformat()})
    check(len(repo.Seguimientos.listar(pendientes=True)) == 1,
          "detecta seguimientos por recontactar")
    ec = repo.Reportes.estado_cuenta(cid)
    check(bool(ec["files"]) and bool(ec["totales"]),
          "arma el estado de cuenta del cliente")

    seccion("Backup")
    ruta = db.backup()
    check(ruta.exists() and ruta.stat().st_size > 0, "genera archivo de backup")

    print("\n" + "=" * 58)
    if fallos:
        print(f"  {len(fallos)} PRUEBA(S) FALLIDA(S):")
        for f in fallos:
            print(f"   - {f}")
        return 1
    print("  TODAS LAS PRUEBAS PASARON")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
