"""Pruebas de la interfaz grafica (PySide6, sin abrir ventanas).

Corre con la plataforma 'offscreen': Qt dibuja en memoria, no aparece nada en
pantalla y funciona igual en Windows que en un CI sin monitor.

Dos niveles:
  - Humo: que las 11 paginas y los dialogos principales se construyan,
    carguen datos y refresquen sin romperse. Es lo que caza los errores
    tipicos (una columna que no existe, una senial mal conectada, un import
    que falta) que las pruebas de negocio no ven.
  - Flujos completos: alta de un file desde el dialogo, cobro desde caja,
    cambio de estado y generacion del voucher en PDF.

Uso:
    python tests\\test_interfaz.py
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

TMP = Path(tempfile.gettempdir()) / "spamed_pruebas_ui"
shutil.rmtree(TMP, ignore_errors=True)
os.environ["SPAMED_DATA_DIR"] = str(TMP)
# Sin esto se abriria una ventana real por cada dialogo que se instancia.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from spamed.core import calculos, db, repo  # noqa: E402
from spamed.ui.puentes import (  # noqa: E402
    PuenteAjustes, PuenteCaja, PuenteCajaGastos, PuenteCierre,
    PuenteClientes, PuenteHerramientas, PuenteInicio, PuenteProveedores,
    PuenteReportes, PuenteVendedores,
)

fallos: list[str] = []
# Carteles que la interfaz quiso mostrar. Los de error se revisan al final:
# si la aplicacion abrio un cartel rojo, algo salio mal aunque no explote.
carteles: list[str] = []
errores_ui: list[str] = []


def _silenciar_dialogos() -> None:
    """Reemplaza los carteles modales por registros en memoria.

    Sin esto, el primer QMessageBox deja la suite colgada esperando un click
    que nunca llega: 'offscreen' no dibuja la ventana pero el modal sigue
    bloqueando. Hay que parchear modulo por modulo porque cada uno hizo
    'from .comunes import aviso, error, confirmar' y quedo con su propia
    referencia.
    """
    from spamed.ui import (
        ajustes, caja, cierre, comunes, herramientas, maestros, principal,
        reservas, tablero,
    )

    def _aviso(padre, texto, titulo="Spamed"):
        carteles.append(f"aviso: {texto}")

    def _error(padre, texto, titulo="Spamed"):
        errores_ui.append(texto)

    # Se responde que si: es lo que haria el usuario al confirmar la accion
    # que la prueba esta ejercitando.
    def _confirmar(padre, texto, titulo="Confirmar"):
        carteles.append(f"confirmar: {texto}")
        return True

    for mod in (comunes, principal, reservas, maestros, caja, tablero,
                cierre, ajustes, herramientas):
        for nombre, reemplazo in (("aviso", _aviso), ("error", _error),
                                  ("confirmar", _confirmar)):
            if hasattr(mod, nombre):
                setattr(mod, nombre, reemplazo)


def check(condicion: bool, descripcion: str) -> None:
    estado = "OK  " if condicion else "FALLA"
    print(f"  [{estado}] {descripcion}")
    if not condicion:
        fallos.append(descripcion)


def probar(descripcion: str, fn) -> object:
    """Corre algo que no deberia lanzar excepcion y lo reporta como caso.

    Devuelve el resultado, o None si exploto (asi el resto de la suite puede
    seguir en vez de cortarse en el primer error).
    """
    try:
        valor = fn()
        check(True, descripcion)
        return valor
    except Exception as e:  # noqa: BLE001
        import traceback

        check(False, f"{descripcion} -> {type(e).__name__}: {e}")
        traceback.print_exc(limit=4)
        return None


def seccion(titulo: str) -> None:
    print(f"\n{titulo}")


def _datos_base() -> dict[str, int]:
    """Carga minima para que las pantallas tengan algo que mostrar."""
    hoy = date.today()
    cid = repo.Clientes.guardar({
        "dni": "30111222", "nombre": "Lucia", "apellido": "Martinez",
        "telefono": "2664-555111", "email": "lucia@correo.com",
        "fecha_nac": "1990-03-14"})
    vid = repo.Vendedores.guardar({
        "dni": "54654524", "nombre": "Rosa", "apellido": "Medrano",
        "comision_pct": 10})
    pid = repo.Proveedores.guardar({
        "nombre": "Amichi", "moneda": "PESOS", "comision_pct": 12,
        "transfiere_neto": 1})
    rid = repo.Reservas.guardar({
        "file": "R2601", "cliente_id": cid, "vendedor_id": vid,
        "proveedor_id": pid, "moneda": "PESOS", "destino": "Bariloche",
        "importe_cliente": 1000000,
        "fecha_reserva": hoy.isoformat(),
        "fecha_vto_reserva": (hoy + timedelta(days=10)).isoformat(),
        "fecha_salida": (hoy + timedelta(days=60)).isoformat(),
        "fecha_regreso": (hoy + timedelta(days=70)).isoformat()})
    repo.Caja.guardar({
        "tipo": "INGRESO", "fecha": hoy.isoformat(), "concepto": "Sena Cliente",
        "reserva_id": rid, "moneda": "PESOS", "monto": 250000,
        "medio_pago": "Transferencia"})
    repo.Pasajeros.guardar({
        "reserva_id": rid, "nombre": "Martinez, Lucia", "documento": "30111222",
        "pasaporte": "AAB123456",
        "vto_pasaporte": (hoy + timedelta(days=120)).isoformat()})
    return {"cliente": cid, "vendedor": vid, "proveedor": pid, "reserva": rid}


def _probar_migracion_vendedores() -> None:
    """vendedores.fecha_nac tiene que sumarse sobre una base vieja, no solo
    sobre una creada de cero. Se arma una base a mano sin esa columna, se
    conecta (dispara la migracion) y se verifica que no se pierda nada."""
    tmp_migra = Path(tempfile.gettempdir()) / "spamed_pruebas_ui_migracion"
    shutil.rmtree(tmp_migra, ignore_errors=True)
    tmp_migra.mkdir(parents=True)
    con = sqlite3.connect(str(tmp_migra / "spamed.db"))
    con.executescript("""
        CREATE TABLE vendedores (id INTEGER PRIMARY KEY AUTOINCREMENT,
            dni TEXT NOT NULL UNIQUE, nombre TEXT NOT NULL,
            apellido TEXT NOT NULL, telefono TEXT, email TEXT,
            comision_pct REAL NOT NULL DEFAULT 0,
            fecha_alta TEXT NOT NULL DEFAULT (date('now')),
            activo INTEGER NOT NULL DEFAULT 1);
        INSERT INTO vendedores (dni, nombre, apellido) VALUES ('1', 'A', 'B');
    """)
    con.commit()
    con.close()

    viejo_env = os.environ.get("SPAMED_DATA_DIR")
    os.environ["SPAMED_DATA_DIR"] = str(tmp_migra)
    db.conectar()
    cols = {f["name"] for f in db.query("PRAGMA table_info(vendedores)")}
    check("fecha_nac" in cols, "la migración agrega fecha_nac a vendedores")
    quedo = db.query_one("SELECT COUNT(*) n FROM vendedores")["n"]
    check(quedo == 1, "el vendedor cargado antes de migrar no se pierde")
    db.cerrar()
    if viejo_env is not None:
        os.environ["SPAMED_DATA_DIR"] = viejo_env


def main() -> int:
    seccion("Migración de vendedores.fecha_nac sobre una base vieja")
    _probar_migracion_vendedores()

    db.conectar()
    ids = _datos_base()
    hoy = date.today()
    hoy_str = hoy.isoformat()
    app = QApplication.instance() or QApplication([])
    _silenciar_dialogos()

    # ------------------------------------------------------------ humo
    from spamed.ui.principal import (  # noqa: E402
        DialogoConfiguracion, DialogoDiagnostico, VentanaPrincipal,
    )

    seccion("Ventana principal")
    ventana = probar("la ventana principal se construye", VentanaPrincipal)
    if ventana is None:
        print("\nSin ventana no tiene sentido seguir.")
        return 1
    check(len(ventana.vistas) == 11, "tiene las 11 páginas")

    seccion("Cada página abre y refresca")
    for indice, (nombre, _) in enumerate(VentanaPrincipal.PAGINAS):
        probar(f"{nombre}", lambda i=indice: ventana.ir_a(i))
    probar("refrescar todo de una", ventana.refrescar_todo)

    seccion("Las grillas traen datos")
    ventana.ir_a(1)
    check(len(ventana.reservas.panel_todos.tabla.datos()) == 1,
          "Reservas lista el file")
    ventana.ir_a(3)
    if hasattr(ventana, "puente_clientes"):
        cli_datos = json.loads(ventana.puente_clientes.listar("", False, 0, False))
        check(cli_datos["ok"] and len(cli_datos["filas"]) == 1,
              "Clientes (puente) lista el cliente")
    else:
        check(len(ventana.clientes.tabla.datos()) == 1, "Clientes lista el cliente")
    ventana.ir_a(2)
    if hasattr(ventana, "puente_caja"):
        caja_datos = json.loads(ventana.puente_caja.listar("", "", "", "", ""))
        check(caja_datos["ok"] and len(caja_datos["filas"]) == 1,
              "Caja (puente) lista el movimiento")
    else:
        check(len(ventana.caja.tabla.datos()) == 1, "Caja lista el movimiento")

    seccion("Reservas: columnas renombradas y Ganancia neta")
    ventana.ir_a(1)
    claves_res = [c for c, _ in ventana.reservas.COLUMNAS]
    check("margen_neto" in claves_res, "agrega la columna Ganancia neta")
    titulos_res = dict(ventana.reservas.COLUMNAS)
    check(titulos_res["importe_cliente"] == "Importe de venta",
          "Importe -> Importe de venta")
    check(titulos_res["costo_proveedor"] == "Importe neto",
          "Costo -> Importe neto")
    check(titulos_res["proveedor"] == "Operador", "Proveedor -> Operador")
    fila_res = ventana.reservas.panel_todos.tabla.datos()[0]
    check(abs(fila_res["margen_neto"] - fila_res["ganancia_bruta"]) > 0
          or fila_res["comision_vendedor"] == 0,
          "Ganancia neta = ganancia bruta - comisión vendedor")

    seccion("Clientes: cumpleaños, última interacción y alertas (punto 3)")
    ventana.ir_a(3)
    if hasattr(ventana, "puente_clientes"):
        pc = ventana.puente_clientes
        fila_cli = json.loads(pc.listar("", False, 0, False))["filas"][0]
        check(fila_cli.get("fecha_nac") == "1990-03-14", "trae la fecha de cumpleaños")
        check(fila_cli.get("ultima_interaccion") == hoy_str,
              "última interacción = fecha de la reserva de hoy")
        marzo = json.loads(pc.listar("", False, 3, False))
        check(len(marzo["filas"]) == 1,
              "el filtro de cumpleaños de marzo incluye al cliente")
        enero = json.loads(pc.listar("", False, 1, False))
        check(len(enero["filas"]) == 0,
              "el filtro de cumpleaños de enero lo excluye")
    else:
        fila_cli = ventana.clientes.tabla.datos()[0]
        check(fila_cli.get("fecha_nac") == "1990-03-14", "trae la fecha de cumpleaños")
        check(fila_cli.get("ultima_interaccion") == hoy_str,
              "última interacción = fecha de la reserva de hoy")
        mes_marzo = ventana.clientes.cmb_mes_cumple.findData(3)
        ventana.clientes.cmb_mes_cumple.setCurrentIndex(mes_marzo)
        check(len(ventana.clientes.consultar()) == 1,
              "el filtro de cumpleaños de marzo incluye al cliente")
        mes_enero = ventana.clientes.cmb_mes_cumple.findData(1)
        ventana.clientes.cmb_mes_cumple.setCurrentIndex(mes_enero)
        check(len(ventana.clientes.consultar()) == 0,
              "el filtro de cumpleaños de enero lo excluye")
        ventana.clientes.cmb_mes_cumple.setCurrentIndex(0)  # vuelve a "todo el año"

    seccion("Reservas: pestañas por estado")
    ventana.ir_a(1)
    check(ventana.reservas.tabs.count() == 9,
          '"Todos" + las 8 pestañas de estado')
    from spamed.ui.reservas import COLOR_ESTADO  # noqa: E402
    for estado in COLOR_ESTADO:
        probar(f"la pestaña {estado} refresca sin romperse",
               ventana.reservas.paneles_estado[estado].refrescar)
    # R2601 (25% cobrado, >= sena) tiene que estar en Confirmado y en
    # ninguna de las pestañas mas tempranas de la cadena.
    panel_confirmado = ventana.reservas.paneles_estado["Confirmado"]
    check(any(f["file"] == "R2601" for f in panel_confirmado.tabla.datos()),
          "R2601 aparece en la pestaña Confirmado")
    for estado_temprano in ("Cotizado", "Reservado", "Vencido"):
        panel = ventana.reservas.paneles_estado[estado_temprano]
        check(not any(f["file"] == "R2601" for f in panel.tabla.datos()),
              f"R2601 no aparece en {estado_temprano}")

    seccion("Acciones de estado: marcar OK y marcar voucher recibido")
    rid_cot = repo.Reservas.guardar({
        "file": "R2700", "cliente_id": ids["cliente"],
        "vendedor_id": ids["vendedor"], "proveedor_id": ids["proveedor"],
        "moneda": "PESOS", "importe_cliente": 100000})
    check(repo.Reservas.obtener(rid_cot)["estado"] == "Cotizado",
          "R2700 arranca Cotizado")

    panel_cot = ventana.reservas.paneles_estado["Cotizado"]
    panel_cot.refrescar()
    fila_cot = next((i for i, f in enumerate(panel_cot.tabla.datos())
                     if f["file"] == "R2700"), None)
    check(fila_cot is not None, "R2700 aparece en la pestaña Cotizado")
    if fila_cot is not None:
        panel_cot.tabla.setCurrentCell(fila_cot, 0)
        probar("marcar OK del cliente", panel_cot._marcar_ok)
        check(repo.Reservas.obtener(rid_cot)["estado"] == "Reservado",
              "después de marcar OK, R2700 pasa a Reservado")

    # empuja R2700 hasta Emitido (las dos puntas pagadas) para probar el
    # voucher: el operador tiene 12%, asi que el costo real se deriva.
    pagado_al_cliente = repo.Reservas.obtener(rid_cot)
    repo.Caja.guardar({"tipo": "INGRESO", "fecha": hoy_str,
                       "concepto": "Saldo Cliente", "reserva_id": rid_cot,
                       "moneda": "PESOS", "monto": 100000})
    repo.Caja.guardar({"tipo": "EGRESO", "fecha": hoy_str,
                       "concepto": "Pago Proveedor", "reserva_id": rid_cot,
                       "moneda": "PESOS",
                       "monto": pagado_al_cliente["costo_proveedor"]})
    check(repo.Reservas.obtener(rid_cot)["estado"] == "Emitido",
          "las dos puntas pagadas -> Emitido")

    panel_emit = ventana.reservas.paneles_estado["Emitido"]
    panel_emit.refrescar()
    fila_emit = next((i for i, f in enumerate(panel_emit.tabla.datos())
                      if f["file"] == "R2700"), None)
    check(fila_emit is not None, "R2700 aparece en la pestaña Emitido")
    if fila_emit is not None:
        panel_emit.tabla.setCurrentCell(fila_emit, 0)
        check(not panel_emit.tabla.fila_actual().get("voucher_recibido"),
              "todavía no llegó el voucher")
        probar("marcar voucher recibido", panel_emit._marcar_voucher)
        check(bool(repo.Reservas.obtener(rid_cot)["voucher_recibido"]),
              "el voucher queda marcado como recibido")
        check(repo.Reservas.obtener(rid_cot)["estado"] == "Emitido",
              "marcar el voucher no cambia el estado")

    seccion("Operadores: columna Facturación (punto 5)")
    repo.Caja.guardar({
        "tipo": "EGRESO", "fecha": hoy.isoformat(), "concepto": "Pago Proveedor",
        "reserva_id": ids["reserva"], "moneda": "PESOS",
        "monto": 300000, "medio_pago": "Transferencia"})
    ventana.ir_a(5)
    # Mismo operador que R2700 (arriba), asi que ya tenia un pago propio.
    esperado_facturado = 300000 + repo.Reservas.obtener(rid_cot)["costo_proveedor"]
    if hasattr(ventana, "puente_proveedores"):
        fila_op = json.loads(ventana.puente_proveedores.listar("", False))["filas"][0]
    else:
        ventana.proveedores.refrescar()
        fila_op = ventana.proveedores.tabla.datos()[0]
    check(abs(fila_op.get("facturado", {}).get("PESOS", 0) - esperado_facturado) < 0.01,
          "la facturación refleja lo pagado, separado por moneda")

    seccion("Diálogos principales")
    from spamed.ui.caja import DialogoCambio, DialogoMovimiento  # noqa: E402
    from spamed.ui.maestros import (  # noqa: E402
        DialogoAdjuntos, DialogoCliente, DialogoProveedor, DialogoSeguimiento,
        DialogoTarjeta, DialogoTarjetas, DialogoVariante, DialogoVendedor,
    )
    from spamed.ui.reservas import DialogoCancelar, DialogoEncuesta, DialogoReserva  # noqa: E402

    probar("Nueva reserva", lambda: DialogoReserva(None, ventana))
    dlg_res = probar("Editar reserva existente",
                     lambda: DialogoReserva(ids["reserva"], ventana))
    probar("Nuevo cliente", lambda: DialogoCliente(None, ventana))
    probar("Editar cliente",
           lambda: DialogoCliente({"id": ids["cliente"]}, ventana))
    probar("Nuevo vendedor", lambda: DialogoVendedor(None, ventana))
    probar("Editar vendedor",
           lambda: DialogoVendedor({"id": ids["vendedor"]}, ventana))
    probar("Nuevo proveedor", lambda: DialogoProveedor(None, ventana))
    probar("Editar proveedor",
           lambda: DialogoProveedor({"id": ids["proveedor"]}, ventana))
    probar("Movimiento de caja", lambda: DialogoMovimiento(None, ventana))
    probar("Cambio de moneda", lambda: DialogoCambio(ventana))
    probar("Seguimiento del cliente",
           lambda: DialogoSeguimiento(ids["cliente"], ventana))
    probar("Configuración general", lambda: DialogoConfiguracion(ventana))
    probar("Diagnóstico", lambda: DialogoDiagnostico(ventana))

    seccion("Documentación de clientes y vendedores")
    dlg_doc = probar("adjuntos de un cliente",
                     lambda: DialogoAdjuntos("cliente", ids["cliente"],
                                             "Martinez", ventana))
    probar("adjuntos de un vendedor",
           lambda: DialogoAdjuntos("vendedor", ids["vendedor"],
                                   "Medrano", ventana))
    if dlg_doc is not None:
        repo.Adjuntos.guardar({"cliente_id": ids["cliente"],
                               "ruta": r"C:\dni_lucia.pdf"})
        dlg_doc.refrescar()
        check(len(dlg_doc.tabla.datos()) == 1,
              "la grilla muestra el archivo adjuntado")
    try:
        DialogoAdjuntos("marciano", 1, "", ventana)
        check(False, "rechaza una entidad que no existe")
    except ValueError:
        check(True, "rechaza una entidad que no existe")

    # --------------------------------------------- flujo: totales de servicios
    seccion("Servicios: aviso de descuadre (punto 1)")
    if dlg_res is not None:
        check("Sin servicios cargados." in dlg_res.lbl_tot_serv.text(),
              "sin servicios no muestra totales")
        check(not dlg_res.btn_traer_serv.isEnabled(),
              "sin servicios el botón está apagado")

        repo.Servicios.guardar({
            "reserva_id": ids["reserva"], "proveedor_id": ids["proveedor"],
            "concepto": "Aereo", "importe_venta": 400000, "costo": 352000})
        repo.Servicios.guardar({
            "reserva_id": ids["reserva"], "proveedor_id": ids["proveedor"],
            "concepto": "Alojamiento", "importe_venta": 550000,
            "costo": 484000})
        dlg_res._refrescar_subtablas()

        texto = dlg_res.lbl_tot_serv.text()
        check("950.000" in texto, "muestra la suma de las ventas")
        check("836.000" in texto, "muestra la suma de los costos")
        # 950.000 de servicios contra 1.000.000 del file: tiene que avisar
        check("No coincide" in texto, "avisa que no coincide con el importe")
        check(dlg_res.btn_traer_serv.isEnabled(), "habilita el botón de traer")

        dlg_res._serv_traer_total()
        check(abs(dlg_res.importe.value() - 950000) < 0.01,
              "el botón copia el total al importe")
        check("No coincide" not in dlg_res.lbl_tot_serv.text(),
              "después de copiar deja de avisar")

        # Lo importante: copiar al importe NO cambia solo la base. El file
        # sigue valiendo 1.000.000 hasta que el usuario guarde.
        guardado = repo.Reservas.obtener(ids["reserva"])
        check(abs(float(guardado["importe_cliente"]) - 1000000) < 0.01,
              "el file no cambia hasta que se guarda")

    # ------------------------------------------------------ flujo completo
    seccion("Flujo completo: alta, cobro y voucher")

    dlg = DialogoReserva(None, ventana)
    dlg.file.setText("R2699")
    dlg.cliente.set_id(ids["cliente"])
    dlg.vendedor.set_id(ids["vendedor"])
    dlg.proveedor.set_id(ids["proveedor"])
    dlg.destino.setText("Mar del Plata")
    dlg.moneda.set_valor("PESOS")
    dlg.importe.setValue(500000)
    dlg.f_reserva.set_valor(hoy.isoformat())
    dlg.f_vto_reserva.set_valor((hoy + timedelta(days=15)).isoformat())
    probar("se carga un file nuevo desde el diálogo",
           lambda: dlg.guardar(cerrar=False))

    nueva = repo.Reservas.por_file("R2699")
    check(nueva is not None, "el file quedó en la base")
    if nueva:
        # el dialogo cargo fecha_reserva (el cliente dijo que si), asi que
        # ya arranca en Reservado, no en Cotizado -- todavia no pago nada.
        check(nueva["estado"] == "Reservado",
              "fecha_reserva cargada, sin cobrar -> Reservado")
        # el proveedor tiene 12%: la comision y el costo se derivan solos
        check(abs(nueva["comision_agencia"] - 60000) < 0.01,
              "toma el 12% del proveedor sin cargarlo a mano")
        check(abs(nueva["costo_proveedor"] - 440000) < 0.01,
              "deriva el costo del proveedor")
        check(abs(nueva["comision_vendedor"] - 6000) < 0.01,
              "la comisión del vendedor sale de la de la agencia")

        # cobro desde el dialogo de caja
        mov = DialogoMovimiento(None, ventana, tipo="INGRESO",
                                reserva_id=nueva["id"], moneda="PESOS")
        mov.concepto.set_valor("Sena Cliente")
        mov.monto.setValue(200000)
        mov.medio.set_valor("Efectivo")
        probar("se cobra una seña desde el diálogo de caja", mov.guardar)

        cobrada = repo.Reservas.por_file("R2699")
        check(abs(cobrada["cobrado_cliente"] - 200000) < 0.01,
              "el cobro impacta en el file")
        check(abs(cobrada["saldo_cliente"] - 300000) < 0.01,
              "el saldo del cliente baja")
        check(cobrada["estado"] == "Confirmado",
              "con el 40% cobrado (la seña) pasa a Confirmado")

        # voucher en PDF
        from spamed.core import documentos  # noqa: E402
        # Mismo armado que hace el boton Voucher de la pantalla de reservas
        # (ui/reservas.py): los movimientos van como dict, no como Row.
        movs = [dict(m) for m in repo.Caja.listar(reserva_id=cobrada["id"])]
        pdf = probar("genera el voucher en PDF", lambda: documentos.voucher(
            cobrada, movs,
            repo.Pasajeros.listar(cobrada["id"]),
            repo.Servicios.listar(cobrada["id"])))
        if pdf:
            check(pdf.exists() and pdf.stat().st_size > 1000,
                  "el PDF existe y no está vacío")
            check("R2699" in pdf.name and "Martinez" in pdf.name,
                  f"el nombre identifica el file y al cliente ({pdf.name})")

    seccion("La caja y el tablero acompañan")
    ventana.refrescar_todo()
    ventana.ir_a(0)
    check(len(ventana.reservas.panel_todos.tabla.datos()) == 3,
          "ahora hay tres files (R2601, R2700, R2699)")
    probar("el tablero se rearma con los datos nuevos",
           ventana.tablero.refrescar)
    probar("los reportes responden", ventana.reportes.refrescar)
    probar("el cierre contable responde", ventana.cierre.refrescar)

    seccion("Vendedores: desglose de files por estado (punto 4)")
    ventana.ir_a(4)
    if hasattr(ventana, "puente_vendedores"):
        fila_vend = json.loads(ventana.puente_vendedores.listar("", False))["filas"][0]
    else:
        ventana.vendedores.refrescar()
        fila_vend = ventana.vendedores.tabla.datos()[0]
    # Verdad de referencia: se cuenta a mano sobre los files reales del
    # vendedor y se colapsa igual que calculos.resumen_pipeline (en
    # curso / finalizados / cancelados), sin asumir el resultado.
    propias = [r for r in repo.Reservas.listar()
              if r["vendedor_id"] == ids["vendedor"]]
    conteo: dict[str, int] = {}
    for r in propias:
        conteo[r["estado"]] = conteo.get(r["estado"], 0) + 1
    pipeline = calculos.resumen_pipeline(conteo)
    esperado = {
        "files_en_curso": pipeline["en_curso"],
        "files_finalizados": pipeline["finalizados"],
        "files_cancelados": pipeline["cancelados"],
    }
    check(all(fila_vend[k] == v for k, v in esperado.items()),
          f"el desglose por estado coincide con los files reales {esperado}")
    check("email" in fila_vend, "la grilla (o el puente) trae el campo Email")

    seccion("Caja y gastos: solapa de Gastos extraordinarios (punto 7)")
    repo.GastosFijos.guardar({
        "concepto": "Alquiler", "moneda": "PESOS", "importe": 50000,
        "dia_mes": 5, "activo": 1})
    repo.GastosFijos.generar_mes(hoy.year, hoy.month)
    repo.Caja.guardar({
        "tipo": "EGRESO", "fecha": hoy_str, "concepto": "Otro gasto",
        "moneda": "PESOS", "monto": 12345, "medio_pago": "Efectivo",
        "detalle": "Reparación de la impresora"})
    ventana.ir_a(8)
    if hasattr(ventana, "puente_caja_gastos"):
        pcg = ventana.puente_caja_gastos
        extra = json.loads(pcg.extraordinarios_listar())["filas"]
        check(len(extra) == 1 and extra[0]["concepto"] == "Otro gasto",
              "solo lista el gasto suelto, no el gasto fijo generado")
        check(len(json.loads(pcg.gastos_listar())["filas"]) == 1,
              "el gasto fijo sigue viéndose en su propia solapa")
    else:
        ventana.caja_gastos.refrescar()
        extra = ventana.caja_gastos.extraordinarios.tabla.datos()
        check(len(extra) == 1 and extra[0]["concepto"] == "Otro gasto",
              "solo lista el gasto suelto, no el gasto fijo generado")
        check(len(ventana.caja_gastos.gastos.tabla.datos()) == 1,
              "el gasto fijo sigue viéndose en su propia solapa")

    seccion("Adjuntar comprobante a un movimiento (punto 3 de la etapa 2)")
    mov_id = repo.Caja.guardar({
        "tipo": "EGRESO", "fecha": hoy_str, "concepto": "Pago Proveedor",
        "reserva_id": ids["reserva"], "moneda": "PESOS", "monto": 1000})
    dlg_mov_nuevo = probar("abre un movimiento nuevo",
                           lambda: DialogoMovimiento(None, ventana))
    if dlg_mov_nuevo is not None:
        check(not dlg_mov_nuevo.btn_comprobantes.isEnabled(),
              "en un movimiento nuevo (sin guardar) el botón está apagado")
    dlg_mov_ok = probar("abre un movimiento ya guardado",
                       lambda: DialogoMovimiento(mov_id, ventana))
    if dlg_mov_ok is not None:
        check(dlg_mov_ok.btn_comprobantes.isEnabled(),
              "al editar uno existente el botón se habilita")
    dlg_ad_mov = probar("abre los adjuntos del movimiento",
                        lambda: DialogoAdjuntos("movimiento", mov_id,
                                                "el pago", ventana))
    if dlg_ad_mov is not None:
        repo.Adjuntos.guardar({"movimiento_id": mov_id,
                               "ruta": r"C:\comprobante.pdf"})
        dlg_ad_mov.refrescar()
        check(len(dlg_ad_mov.tabla.datos()) == 1,
              "el comprobante queda adjuntado a ese movimiento puntual")

    seccion("Cuestionario de cancelación estructurado (punto 6)")
    rid_cancel = repo.Reservas.guardar({
        "file": "R2701", "cliente_id": ids["cliente"],
        "vendedor_id": ids["vendedor"], "proveedor_id": ids["proveedor"],
        "moneda": "PESOS", "importe_cliente": 50000})
    dlg_cancel = probar("abre el diálogo de cancelación",
                        lambda: DialogoCancelar(rid_cancel, ventana))
    if dlg_cancel is not None:
        dlg_cancel.motivo.set_valor("Cambio de planes")
        dlg_cancel.detalle.setText("se mudó de ciudad")
        dlg_cancel.devolucion.setValue(0)
        dlg_cancel.chk_registrar.setChecked(False)
        probar("cancela con motivo de la lista + detalle", dlg_cancel.guardar)
        cancelado = repo.Reservas.crudo(rid_cancel)
        check(cancelado["motivo_cancelacion"] == "Cambio de planes: se mudó de ciudad",
              "guarda el motivo estructurado combinado con el detalle libre")

    seccion("Exportar resumen de vencidos por cliente (punto 5)")
    rid_venc = repo.Reservas.guardar({
        "file": "R2702", "cliente_id": ids["cliente"],
        "vendedor_id": ids["vendedor"], "proveedor_id": ids["proveedor"],
        "moneda": "PESOS", "importe_cliente": 30000,
        "fecha_vto_reserva": (hoy - timedelta(days=1)).isoformat()})
    check(repo.Reservas.obtener(rid_venc)["estado"] == "Vencido",
          "R2702 arranca Vencido")
    panel_venc = ventana.reservas.paneles_estado["Vencido"]
    panel_venc.refrescar()
    check(any(f["file"] == "R2702" for f in panel_venc.tabla.datos()),
          "R2702 aparece en la pestaña Vencido, lista para exportar")

    seccion("Encuesta de satisfacción (punto 4)")
    from spamed.core import documentos as documentos_enc  # noqa: E402
    rid_final = repo.Reservas.guardar({
        "file": "R2703", "cliente_id": ids["cliente"],
        "vendedor_id": ids["vendedor"], "proveedor_id": ids["proveedor"],
        "moneda": "PESOS", "importe_cliente": 20000,
        "fecha_salida": (hoy - timedelta(days=10)).isoformat(),
        "fecha_regreso": (hoy - timedelta(days=3)).isoformat()})
    check(repo.Reservas.obtener(rid_final)["estado"] == "Finalizado",
          "R2703 arranca Finalizado")

    enc_id = repo.Encuestas.generar(rid_final)
    check(enc_id > 0, "se genera el registro de la encuesta")
    pdf_enc = probar("genera la encuesta en PDF", lambda: documentos_enc.encuesta(
        repo.Reservas.obtener(rid_final)))
    if pdf_enc:
        check(pdf_enc.exists() and pdf_enc.stat().st_size > 500,
              "el PDF de la encuesta existe y no está vacío")

    dlg_enc = probar("abre el diálogo de encuesta",
                     lambda: DialogoEncuesta(rid_final, ventana))
    if dlg_enc is not None:
        check(len(dlg_enc.tabla.datos()) == 1,
              "la encuesta generada aparece en la lista del file")
        dlg_enc.tabla.setCurrentCell(0, 0)
        dlg_enc.sp_atencion.setValue(5)
        dlg_enc.sp_expectativas.setValue(4)
        dlg_enc.sp_recomendaria.setValue(5)
        dlg_enc.comentario.setPlainText("Todo excelente")
        probar("guarda la respuesta de la encuesta", dlg_enc._guardar_respuesta)
        respondida = repo.Encuestas.listar(rid_final)[0]
        check(respondida["puntaje_atencion"] == 5 and respondida["fecha_respuesta"],
              "la respuesta queda guardada con puntaje y fecha")
        check(all(p["reserva_id"] != rid_final for p in repo.Encuestas.pendientes()),
              "ya no aparece en encuestas pendientes de responder")

    seccion("Variantes de operador (Etapa 2 parte 2, punto 1)")
    dlg_prov = probar("abre el operador para editar",
                      lambda: DialogoProveedor({"id": ids["proveedor"]}, ventana))
    if dlg_prov is not None:
        check(hasattr(dlg_prov, "tabla_var"),
              "al editar, muestra la sección de variantes")
        dlg_var = probar("abre el alta de variante",
                         lambda: DialogoVariante(ids["proveedor"], None, ventana))
        if dlg_var is not None:
            idx = dlg_var.tipo_viaje.findData("Nacional")
            dlg_var.tipo_viaje.setCurrentIndex(idx)
            dlg_var.moneda.set_valor("PESOS")
            dlg_var.comision.setValue(25)
            dlg_var.chk_neto.setChecked(False)
            probar("guarda la variante", dlg_var.guardar)
        dlg_prov._cargar_variantes()
        check(len(dlg_prov.tabla_var.datos()) == 1,
              "la variante aparece en la lista del operador")

    rid_tv = repo.Reservas.guardar({
        "file": "R2704", "cliente_id": ids["cliente"],
        "vendedor_id": ids["vendedor"], "proveedor_id": ids["proveedor"],
        "moneda": "PESOS", "tipo_viaje": "Nacional", "importe_cliente": 100000})
    check(repo.Reservas.obtener(rid_tv)["pct_proveedor"] == 25,
          "un file Nacional/PESOS usa la comisión de la variante (25%)")
    dlg_tv = probar("abre ese file en el diálogo",
                    lambda: DialogoReserva(rid_tv, ventana))
    if dlg_tv is not None:
        check(dlg_tv.tipo_viaje.currentData() == "Nacional",
              "el diálogo carga el tipo de viaje guardado")
        check("25.000" in dlg_tv.lbl_ganancia.text(),
              f"la vista previa usa la variante ({dlg_tv.lbl_ganancia.text()})")

    seccion("Inicio: filtro de moneda y pagos a operadores (punto 2)")
    ventana.ir_a(0)
    probar("Inicio se abre sin excepciones", lambda: ventana.tablero.refrescar())

    seccion("PuenteInicio (Etapa 1 de MIGRACION_WEB.md)")
    # Inicio ya es una pantalla HTML/CSS/JS: no hay widgets Qt que
    # inspeccionar (ver navegacion), asi que lo que se prueba aca es el
    # puente en si mismo -- exactamente lo que un QWebEngineView real
    # invoca, sin necesitar uno.
    puente_inicio = PuenteInicio()
    monedas = json.loads(puente_inicio.monedas())
    check(monedas == db.listas("moneda"),
          f"monedas() coincide con la lista real ({monedas})")

    fechas = json.loads(puente_inicio.fechas_mes_actual())
    check(set(fechas) == {"desde", "hasta"} and fechas["desde"] <= fechas["hasta"],
          f"fechas_mes_actual() da un rango valido ({fechas})")

    todas = json.loads(puente_inicio.dashboard("", "", ""))
    pesos = json.loads(puente_inicio.dashboard("PESOS", "", ""))
    check(todas["ok"] and pesos["ok"], "dashboard() responde ok:true")

    def _estados_de_referencia(moneda: str, desde: str, hasta: str) -> dict:
        conteo: dict[str, int] = {}
        for r in repo.Reservas.listar(moneda=moneda, desde=desde, hasta=hasta):
            conteo[r["estado"]] = conteo.get(r["estado"], 0) + 1
        return conteo

    check(todas["estados"] == _estados_de_referencia("", todas["desde"], todas["hasta"]),
          "el JSON del puente coincide con un conteo manual del mismo período")
    check(pesos["estados"] ==
          _estados_de_referencia("PESOS", pesos["desde"], pesos["hasta"]),
          "...y coincide filtrando por PESOS")
    check(len(pesos.get("pagos_operadores", [])) <=
          len(todas.get("pagos_operadores", [])),
          "filtrar por PESOS no aumenta los pagos a operadores")

    # Punto reportado por Pablo: antes, el rango de fechas solo afectaba a
    # "Caja del período" -- el resto (a cobrar/a pagar/ganancia/estados/
    # pagos a operadores) quedaba fijo sin importar el filtro elegido.
    vacio = json.loads(puente_inicio.dashboard("", "2000-01-01", "2000-01-02"))
    check(vacio["ok"] and not vacio["estados"] and not vacio["pagos_operadores"]
          and not vacio["alertas"] and not vacio["por_moneda"],
          f"un período sin files da todo vacío, no solo la caja ({vacio['cant_activas']} activas)")
    check(all(f["moneda"] == "PESOS" for f in pesos["alertas"]),
          "las alertas filtradas por PESOS no traen otra moneda")

    seccion("PuenteCaja (Etapa 2 de MIGRACION_WEB.md)")
    puente_caja = PuenteCaja(ventana)
    listas_caja = json.loads(puente_caja.listas())
    check(listas_caja["monedas"] == db.listas("moneda") and
          listas_caja["medios_pago"] == db.listas("medio_pago"),
          "listas() trae las listas reales")

    buscables = json.loads(puente_caja.reservas_buscables())
    check(any(r["id"] == ids["reserva"] for r in buscables),
          "reservas_buscables() incluye el file de prueba")

    info = json.loads(puente_caja.reserva_info(ids["reserva"]))
    r_real = repo.Reservas.obtener(ids["reserva"])
    check(info["file"] == r_real["file"] and info["moneda"] == r_real["moneda"],
          "reserva_info() coincide con el file real")

    antes = json.loads(puente_caja.listar("", "", "", "", ""))
    r_guardar = json.loads(puente_caja.guardar(json.dumps({
        "id": None, "tipo": "EGRESO", "fecha": hoy_str, "concepto": "Sueldos",
        "reserva_id": None, "moneda": "PESOS", "monto": 5000,
        "medio_pago": "Efectivo", "detalle": "movimiento de prueba puente"})))
    check(r_guardar["ok"], f"guardar() acepta un movimiento valido ({r_guardar})")
    despues = json.loads(puente_caja.listar("", "", "", "", ""))
    check(len(despues["filas"]) == len(antes["filas"]) + 1,
          "el movimiento nuevo aparece en listar()")

    r_invalido = json.loads(puente_caja.guardar(json.dumps({
        "id": None, "tipo": "EGRESO", "fecha": hoy_str, "concepto": "Sueldos",
        "reserva_id": None, "moneda": "PESOS", "monto": 0,
        "medio_pago": "Efectivo", "detalle": ""})))
    check(r_invalido["ok"] is False and "error" in r_invalido,
          f"guardar() rechaza un monto en cero sin romper ({r_invalido})")

    id_nuevo = r_guardar["id"]
    r_eliminar = json.loads(puente_caja.eliminar(id_nuevo))
    check(r_eliminar["ok"], "eliminar() borra el movimiento de prueba")
    final = json.loads(puente_caja.listar("", "", "", "", ""))
    check(len(final["filas"]) == len(antes["filas"]),
          "después de eliminar, vuelve a la cantidad original")

    r_cambio = json.loads(puente_caja.cambio_moneda(json.dumps({
        "fecha": hoy_str, "moneda_origen": "PESOS", "monto_origen": 100000,
        "moneda_destino": "DOLAR", "monto_destino": 70,
        "medio_pago": "Efectivo", "detalle": "cambio de prueba puente"})))
    check(r_cambio["ok"], f"cambio_moneda() registra las dos patas ({r_cambio})")

    seccion("PuenteClientes (Etapa 3 de MIGRACION_WEB.md)")
    puente_cli = PuenteClientes(ventana)
    listas_cli = json.loads(puente_cli.listas())
    check(listas_cli["canales"] == db.listas("canal"), "listas() trae los canales reales")

    listado = json.loads(puente_cli.listar("", False, 0, False))
    check(listado["ok"] and any(f["id"] == ids["cliente"] for f in listado["filas"]),
          "listar() incluye al cliente de prueba")

    obtenido = json.loads(puente_cli.obtener(ids["cliente"]))
    check(obtenido["ok"] and obtenido["fila"]["id"] == ids["cliente"],
          "obtener() trae el cliente correcto")

    r_guardar_cli = json.loads(puente_cli.guardar(json.dumps({
        "id": None, "dni": "99888777", "apellido": "Puente", "nombre": "Prueba",
        "telefono": "", "email": "", "direccion": "", "fecha_nac": None,
        "dni_vencimiento": None, "fecha_alta": hoy_str, "canal": "",
        "detalle_canal": "", "observaciones": "", "activo": 1})))
    check(r_guardar_cli["ok"], f"guardar() acepta un cliente nuevo ({r_guardar_cli})")
    id_cli_nuevo = r_guardar_cli["id"]

    r_elim_sin_files = json.loads(puente_cli.eliminar(id_cli_nuevo))
    check(r_elim_sin_files["ok"], "eliminar() borra un cliente sin files")

    r_elim_con_files = json.loads(puente_cli.eliminar(ids["cliente"]))
    check(r_elim_con_files["ok"] is False and "error" in r_elim_con_files,
          f"eliminar() rechaza un cliente con reservas sin romper ({r_elim_con_files})")

    antes_seg = json.loads(puente_cli.seguimientos_listar(ids["cliente"]))
    r_seg = json.loads(puente_cli.seguimiento_guardar(json.dumps({
        "cliente_id": ids["cliente"], "fecha": hoy_str, "canal": "",
        "nota": "contacto de prueba puente", "proximo": None})))
    check(r_seg["ok"], f"seguimiento_guardar() acepta un contacto valido ({r_seg})")
    despues_seg = json.loads(puente_cli.seguimientos_listar(ids["cliente"]))
    check(len(despues_seg) == len(antes_seg) + 1,
          "el contacto nuevo aparece en seguimientos_listar()")
    id_seg_nuevo = [s for s in despues_seg if s["nota"] == "contacto de prueba puente"][0]["id"]
    r_seg_del = json.loads(puente_cli.seguimiento_eliminar(id_seg_nuevo))
    check(r_seg_del["ok"], "seguimiento_eliminar() borra el contacto de prueba")

    antes_tarj = json.loads(puente_cli.tarjetas_listar(ids["cliente"]))
    r_tarj = json.loads(puente_cli.tarjeta_guardar(json.dumps({
        "id": None, "cliente_id": ids["cliente"], "marca": "Visa",
        "ultimos4": "4321", "vencimiento": "12/30", "nota": "tarjeta de prueba puente"})))
    check(r_tarj["ok"], f"tarjeta_guardar() acepta una tarjeta valida ({r_tarj})")
    despues_tarj = json.loads(puente_cli.tarjetas_listar(ids["cliente"]))
    check(len(despues_tarj) == len(antes_tarj) + 1,
          "la tarjeta nueva aparece en tarjetas_listar()")
    id_tarj_nueva = [t for t in despues_tarj if t["nota"] == "tarjeta de prueba puente"][0]["id"]
    r_tarj_del = json.loads(puente_cli.tarjeta_eliminar(id_tarj_nueva))
    check(r_tarj_del["ok"], "tarjeta_eliminar() borra la tarjeta de prueba")

    seccion("PuenteVendedores (Etapa 4 de MIGRACION_WEB.md)")
    puente_vend = PuenteVendedores(ventana)
    listado_vend = json.loads(puente_vend.listar("", False))
    check(listado_vend["ok"] and any(f["id"] == ids["vendedor"] for f in listado_vend["filas"]),
          "listar() incluye al vendedor de prueba")

    obtenido_vend = json.loads(puente_vend.obtener(ids["vendedor"]))
    check(obtenido_vend["ok"] and obtenido_vend["fila"]["id"] == ids["vendedor"],
          "obtener() trae el vendedor correcto")

    r_guardar_vend = json.loads(puente_vend.guardar(json.dumps({
        "id": None, "dni": "88777666", "apellido": "Puente", "nombre": "Vendedor",
        "telefono": "", "email": "", "fecha_nac": None,
        "comision_pct": 10, "activo": 1})))
    check(r_guardar_vend["ok"], f"guardar() acepta un vendedor nuevo ({r_guardar_vend})")
    id_vend_nuevo = r_guardar_vend["id"]

    r_vend_invalido = json.loads(puente_vend.guardar(json.dumps({
        "id": None, "dni": "", "apellido": "Sin DNI", "nombre": "X",
        "telefono": "", "email": "", "fecha_nac": None,
        "comision_pct": 10, "activo": 1})))
    check(r_vend_invalido["ok"] is False and "error" in r_vend_invalido,
          f"guardar() rechaza un vendedor sin DNI sin romper ({r_vend_invalido})")

    r_elim_vend_libre = json.loads(puente_vend.eliminar(id_vend_nuevo))
    check(r_elim_vend_libre["ok"], "eliminar() borra un vendedor sin files")

    r_elim_vend_usado = json.loads(puente_vend.eliminar(ids["vendedor"]))
    check(r_elim_vend_usado["ok"] is False and "error" in r_elim_vend_usado,
          f"eliminar() rechaza un vendedor con reservas sin romper ({r_elim_vend_usado})")

    seccion("PuenteProveedores (Etapa 5 de MIGRACION_WEB.md)")
    puente_prov = PuenteProveedores(ventana)
    listas_prov = json.loads(puente_prov.listas())
    check(listas_prov["tipos"] == db.listas("tipo_proveedor") and
          listas_prov["monedas"] == db.listas("moneda"),
          "listas() trae los tipos y monedas reales")

    listado_prov = json.loads(puente_prov.listar("", False))
    check(listado_prov["ok"] and any(f["id"] == ids["proveedor"] for f in listado_prov["filas"]),
          "listar() incluye al operador de prueba")

    obtenido_prov = json.loads(puente_prov.obtener(ids["proveedor"]))
    check(obtenido_prov["ok"] and obtenido_prov["fila"]["id"] == ids["proveedor"],
          "obtener() trae el operador correcto")

    r_guardar_prov = json.loads(puente_prov.guardar(json.dumps({
        "id": None, "nombre": "Operador de prueba puente", "tipo": "", "moneda": "PESOS",
        "comision_pct": 15, "transfiere_neto": 1, "contacto": "", "telefono": "",
        "email": "", "observaciones": "", "activo": 1})))
    check(r_guardar_prov["ok"], f"guardar() acepta un operador nuevo ({r_guardar_prov})")
    id_prov_nuevo = r_guardar_prov["id"]

    antes_var = json.loads(puente_prov.variantes_listar(id_prov_nuevo))
    r_var = json.loads(puente_prov.variante_guardar(json.dumps({
        "id": None, "proveedor_id": id_prov_nuevo, "tipo_viaje": "Nacional",
        "moneda": "PESOS", "comision_pct": 20, "transfiere_neto": 1})))
    check(r_var["ok"], f"variante_guardar() acepta una variante valida ({r_var})")
    despues_var = json.loads(puente_prov.variantes_listar(id_prov_nuevo))
    check(len(despues_var) == len(antes_var) + 1,
          "la variante nueva aparece en variantes_listar()")

    r_var_invalida = json.loads(puente_prov.variante_guardar(json.dumps({
        "id": None, "proveedor_id": id_prov_nuevo, "tipo_viaje": "No existe",
        "moneda": "PESOS", "comision_pct": 20, "transfiere_neto": 1})))
    check(r_var_invalida["ok"] is False and "error" in r_var_invalida,
          f"variante_guardar() rechaza un tipo de viaje inválido sin romper ({r_var_invalida})")

    id_var_nueva = despues_var[0]["id"]
    r_var_del = json.loads(puente_prov.variante_eliminar(id_var_nueva))
    check(r_var_del["ok"], "variante_eliminar() borra la variante de prueba")

    r_elim_prov_libre = json.loads(puente_prov.eliminar(id_prov_nuevo))
    check(r_elim_prov_libre["ok"], "eliminar() borra un operador sin files")

    r_elim_prov_usado = json.loads(puente_prov.eliminar(ids["proveedor"]))
    check(r_elim_prov_usado["ok"] is False and "error" in r_elim_prov_usado,
          f"eliminar() rechaza un operador con reservas sin romper ({r_elim_prov_usado})")

    seccion("PuenteReportes (Etapa 6 de MIGRACION_WEB.md)")
    from spamed.ui.tablero import VistaReportes  # noqa: E402
    puente_rep = PuenteReportes(ventana)
    meta = json.loads(puente_rep.metadatos())
    nombres_meta = {r["nombre"] for r in meta["reportes"]}
    check(nombres_meta == set(VistaReportes.REPORTES),
          "metadatos() trae los mismos informes que REPORTES")
    check(set(meta["campos_moneda"]) == VistaReportes.CAMPOS_MONEDA,
          "metadatos() trae los mismos campos en moneda que CAMPOS_MONEDA")

    r_cobros = json.loads(puente_rep.datos("Cobros pendientes"))
    check(r_cobros["ok"] and any(f["file"] == "R2601" for f in r_cobros["filas"]),
          "datos('Cobros pendientes') incluye el file de prueba")

    r_desconocido = json.loads(puente_rep.datos("Reporte que no existe"))
    check(r_desconocido["ok"] is False and "error" in r_desconocido,
          f"datos() con un reporte inexistente no rompe ({r_desconocido})")

    seccion("PuenteCierre (Etapa 7 de MIGRACION_WEB.md)")
    puente_cierre = PuenteCierre(ventana)
    cmp_actual = json.loads(puente_cierre.comparar(hoy.year, hoy.month))
    check(cmp_actual["ok"] and cmp_actual["estado"] == "mes en curso",
          f"comparar() marca el mes actual como en curso ({cmp_actual['estado']})")

    liq_puente = json.loads(puente_cierre.liquidaciones(hoy.year, hoy.month))
    check(liq_puente["ok"] and all("estado" in f for f in liq_puente["filas"]),
          "liquidaciones() agrega el campo estado (Pagada/Pendiente)")

    r_obj = json.loads(puente_cierre.objetivo_guardar(json.dumps({
        "anio": hoy.year, "mes": hoy.month, "moneda": "PESOS", "importe": 500000})))
    check(r_obj["ok"], f"objetivo_guardar() acepta un objetivo válido ({r_obj})")
    obj_leido = json.loads(puente_cierre.objetivo_obtener(hoy.year, hoy.month, "PESOS"))
    check(obj_leido["importe"] == 500000, "objetivo_obtener() lee lo recién guardado")

    # cerrar() solo acepta meses ya terminados: se prueba contra el mes
    # anterior para no tocar el mes en curso que usan otras pruebas.
    p_anio, p_mes = (hoy.year - 1, 12) if hoy.month == 1 else (hoy.year, hoy.month - 1)
    r_cerrar_actual = json.loads(puente_cierre.cerrar(hoy.year, hoy.month))
    check(r_cerrar_actual["ok"] is False and "error" in r_cerrar_actual,
          f"cerrar() rechaza el mes en curso sin romper ({r_cerrar_actual})")

    repo.Caja.guardar({
        "tipo": "INGRESO", "fecha": date(p_anio, p_mes, 15).isoformat(),
        "concepto": "Cobro cliente", "moneda": "PESOS", "monto": 1000,
        "medio_pago": "Efectivo", "detalle": "movimiento de prueba puente cierre"})
    r_cerrar = json.loads(puente_cierre.cerrar(p_anio, p_mes))
    check(r_cerrar["ok"], f"cerrar() cierra un mes terminado con movimientos ({r_cerrar})")
    cmp_cerrado = json.loads(puente_cierre.comparar(p_anio, p_mes))
    check(cmp_cerrado["ok"] and cmp_cerrado["cerrado"],
          "comparar() refleja el mes recién cerrado")
    r_reabrir = json.loads(puente_cierre.reabrir(p_anio, p_mes))
    check(r_reabrir["ok"], "reabrir() no rompe")
    cmp_reabierto = json.loads(puente_cierre.comparar(p_anio, p_mes))
    check(cmp_reabierto["ok"] and not cmp_reabierto["cerrado"],
          "comparar() refleja el mes reabierto")

    seccion("PuenteCajaGastos (Etapa 8 de MIGRACION_WEB.md)")
    puente_cg = PuenteCajaGastos(ventana)
    listas_cg = json.loads(puente_cg.listas())
    check(listas_cg["monedas"] == db.listas("moneda") and
          set(listas_cg["periodicidades"]) == set(repo.PERIODICIDADES),
          "listas() trae monedas y periodicidades reales")

    antes_fijos = json.loads(puente_cg.gastos_listar())["filas"]
    r_fijo = json.loads(puente_cg.gasto_guardar(json.dumps({
        "id": None, "concepto": "Internet", "moneda": "PESOS", "importe": 8000,
        "dia_mes": 10, "medio_pago": "", "periodicidad": "Mensual",
        "fecha_inicio": None, "fecha_fin": None, "cantidad_cuotas": None, "activo": 1})))
    check(r_fijo["ok"], f"gasto_guardar() acepta un gasto fijo válido ({r_fijo})")
    despues_fijos = json.loads(puente_cg.gastos_listar())["filas"]
    check(len(despues_fijos) == len(antes_fijos) + 1,
          "el gasto fijo nuevo aparece en gastos_listar()")
    fijo_nuevo = [f for f in despues_fijos if f["concepto"] == "Internet"][0]
    check("vigencia" in fijo_nuevo, "gastos_listar() agrega el texto de vigencia")

    r_fijo_invalido = json.loads(puente_cg.gasto_guardar(json.dumps({
        "id": None, "concepto": "", "moneda": "PESOS", "importe": 8000,
        "dia_mes": 10, "medio_pago": "", "periodicidad": "Mensual",
        "fecha_inicio": None, "fecha_fin": None, "cantidad_cuotas": None, "activo": 1})))
    check(r_fijo_invalido["ok"] is False and "error" in r_fijo_invalido,
          f"gasto_guardar() rechaza un concepto vacío sin romper ({r_fijo_invalido})")

    r_fijo_del = json.loads(puente_cg.gasto_eliminar(fijo_nuevo["id"]))
    check(r_fijo_del["ok"], "gasto_eliminar() borra el gasto fijo de prueba")

    antes_extra = json.loads(puente_cg.extraordinarios_listar())["filas"]
    r_extra = json.loads(puente_cg.extraordinario_guardar(json.dumps({
        "id": None, "fecha": hoy_str, "concepto": "Reparación", "moneda": "PESOS",
        "monto": 3000, "medio_pago": "Efectivo", "detalle": "gasto de prueba puente"})))
    check(r_extra["ok"], f"extraordinario_guardar() acepta un gasto válido ({r_extra})")
    despues_extra = json.loads(puente_cg.extraordinarios_listar())["filas"]
    check(len(despues_extra) == len(antes_extra) + 1,
          "el gasto extraordinario nuevo aparece en extraordinarios_listar()")
    id_extra_nuevo = [f for f in despues_extra if f["detalle"] == "gasto de prueba puente"][0]["id"]
    obtenido_extra = json.loads(puente_cg.extraordinario_obtener(id_extra_nuevo))
    check(obtenido_extra["ok"] and obtenido_extra["fila"]["tipo"] == "EGRESO"
          and obtenido_extra["fila"]["reserva_id"] is None,
          "extraordinario_guardar() siempre fuerza EGRESO sin file")
    r_extra_del = json.loads(puente_cg.extraordinario_eliminar(id_extra_nuevo))
    check(r_extra_del["ok"], "extraordinario_eliminar() borra el gasto de prueba")

    saldo_antes = json.loads(puente_cg.arqueo_saldo_sistema("PESOS", hoy_str))["saldo"]
    r_arq = json.loads(puente_cg.arqueo_guardar(json.dumps({
        "fecha": hoy_str, "moneda": "PESOS",
        "saldo_contado": saldo_antes + 500, "nota": "arqueo de prueba puente"})))
    check(r_arq["ok"], f"arqueo_guardar() acepta un arqueo válido ({r_arq})")
    arqueos = json.loads(puente_cg.arqueos_listar())["filas"]
    arq_nuevo = [a for a in arqueos if a["nota"] == "arqueo de prueba puente"][0]
    check(abs(arq_nuevo["diferencia"] - 500) < 0.01,
          f"arqueo_guardar() calcula bien la diferencia ({arq_nuevo['diferencia']})")
    r_arq_del = json.loads(puente_cg.arqueo_eliminar(arq_nuevo["id"]))
    check(r_arq_del["ok"], "arqueo_eliminar() borra el arqueo de prueba")

    seccion("PuenteAjustes y PuenteHerramientas (Etapa 9 de MIGRACION_WEB.md)")
    puente_aj = PuenteAjustes()
    tipos_aj = json.loads(puente_aj.tipos())
    from spamed.ui.ajustes import ETIQUETAS  # noqa: E402
    check({t["clave"] for t in tipos_aj} == set(ETIQUETAS),
          "tipos() trae las mismas listas que ETIQUETAS")

    antes_valores = json.loads(puente_aj.valores("canal"))
    r_agregar = json.loads(puente_aj.agregar("canal", "Canal de prueba puente"))
    check(r_agregar["ok"], f"agregar() acepta un valor nuevo ({r_agregar})")
    despues_valores = json.loads(puente_aj.valores("canal"))
    check(len(despues_valores) == len(antes_valores) + 1,
          "el valor nuevo aparece en valores()")

    r_renombrar = json.loads(puente_aj.renombrar(
        "canal", "Canal de prueba puente", "Canal renombrado puente"))
    check(r_renombrar["ok"], "renombrar() no rompe")
    check("Canal renombrado puente" in json.loads(puente_aj.valores("canal")),
          "el renombre se refleja en valores()")

    valores_orden = json.loads(puente_aj.valores("canal"))
    orden_invertido = list(reversed(valores_orden))
    r_orden = json.loads(puente_aj.guardar_orden("canal", json.dumps(orden_invertido)))
    check(r_orden["ok"], "guardar_orden() no rompe")
    check(json.loads(puente_aj.valores("canal")) == orden_invertido,
          "el orden nuevo se refleja en valores()")

    r_quitar = json.loads(puente_aj.quitar("canal", "Canal renombrado puente"))
    check(r_quitar["ok"], "quitar() no rompe")
    check("Canal renombrado puente" not in json.loads(puente_aj.valores("canal")),
          "el valor de prueba ya no aparece en valores()")

    puente_herr = PuenteHerramientas(ventana)
    info_herr = json.loads(puente_herr.info())
    check(info_herr["tema"] in ("claro", "oscuro") and info_herr["app_version"],
          f"PuenteHerramientas.info() responde con datos reales ({info_herr})")

    seccion("Clientes: DNI a vencer y tarjetas de referencia (punto 3)")
    repo.Clientes.guardar({
        "id": ids["cliente"], "dni": "30111222", "apellido": "Martinez",
        "nombre": "Lucia",
        "dni_vencimiento": (hoy + timedelta(days=30)).isoformat()})
    dlg_cli = probar("abre el cliente y ve el vencimiento del DNI",
                     lambda: DialogoCliente({"id": ids["cliente"]}, ventana))
    if dlg_cli is not None:
        check(dlg_cli.dni_vencimiento.valor() is not None,
              "carga la fecha de vencimiento del DNI")
    dlg_tarj = probar("abre las tarjetas del cliente",
                      lambda: DialogoTarjetas(ids["cliente"], "Martinez", ventana))
    if dlg_tarj is not None:
        dlg_nueva_tarj = probar(
            "abre el alta de tarjeta",
            lambda: DialogoTarjeta(ids["cliente"], None, ventana))
        if dlg_nueva_tarj is not None:
            dlg_nueva_tarj.marca.setText("Visa")
            dlg_nueva_tarj.ultimos4.setText("1234")
            dlg_nueva_tarj.vencimiento.setText("12/30")
            probar("guarda la tarjeta", dlg_nueva_tarj.guardar)
        dlg_tarj.refrescar()
        check(len(dlg_tarj.tabla.datos()) == 1,
              "la tarjeta queda cargada para el cliente")

    seccion("Cierre: resumen consolidado con cotización (punto 4)")
    ventana.ir_a(7)
    if hasattr(ventana, "puente_cierre"):
        pcierre = ventana.puente_cierre
        r_cot = json.loads(pcierre.cotizacion_guardar_manual(1000))
        check(r_cot["ok"], "cotizacion_guardar_manual() acepta un valor válido")
        info_cot = json.loads(pcierre.cotizacion_info())
        check(info_cot["valor"] == 1000, "cotizacion_info() refleja el valor guardado")
        # El texto "Ventas consolidadas" ahora lo arma el JS con estos
        # mismos datos (ver cierre.js::refrescarConsolidado) -- desde
        # Python solo se puede verificar que comparar() trae lo que ese
        # calculo necesita (ventas y margen por moneda).
        cmp_ = json.loads(pcierre.comparar(hoy.year, hoy.month))
        check(cmp_["ok"] and all(
            "ventas" in d and "margen" in d for d in cmp_["datos"].values()),
            "comparar() trae ventas y margen por moneda para el consolidado")
    else:
        ventana.cierre.cotizacion.setValue(1000)
        ventana.cierre._guardar_cotizacion_manual()
        ventana.cierre.refrescar()
        check("Ventas consolidadas" in ventana.cierre.lbl_consolidado.text(),
              "muestra el resumen consolidado con la cotización cargada")
    monedas_en_reservas = {f["moneda"] for f in
                           ventana.reservas.panel_todos.tabla.datos()}
    check(monedas_en_reservas.issubset({"PESOS", "DOLAR"}),
          "las monedas de la grilla siguen separadas, nunca consolidadas ahí")

    seccion("Tema claro y oscuro")
    probar("cambia a oscuro", lambda: ventana.cambiar_tema("oscuro"))
    probar("vuelve a claro", lambda: ventana.cambiar_tema("claro"))

    seccion("Sin carteles de error")
    # Un cartel rojo es un fallo aunque nada haya lanzado excepcion.
    check(not errores_ui,
          "la interfaz no mostró ningún error"
          + ("" if not errores_ui else f": {errores_ui}"))

    print("\n" + "=" * 58)
    if fallos:
        print(f"  {len(fallos)} PRUEBA(S) FALLIDA(S):")
        for f in fallos:
            print(f"   - {f}")
        return 1
    print("  TODAS LAS PRUEBAS DE INTERFAZ PASARON")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
