"""Generacion de voucher de viaje y recibo de pago en PDF.

Usa QPdfWriter + QTextDocument de Qt, asi que no agrega dependencias: lo que
se compone es HTML y Qt lo pagina e imprime a PDF.
"""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QFont, QPageSize, QPdfWriter, QTextDocument

from . import calculos, config, db, tema


def _e(valor: Any) -> str:
    """Escapa para HTML; vacio si no hay dato."""
    if valor is None or valor == "":
        return "—"
    return html.escape(str(valor))


def _fila(etiqueta: str, valor: Any) -> str:
    return (
        f"<tr><td class='et'>{html.escape(etiqueta)}</td>"
        f"<td class='va'>{_e(valor)}</td></tr>"
    )


# Paleta y tipografia del Manual de Marca (core/tema.py::MARCA), mismo
# criterio que la interfaz: un solo lugar define el color/la fuente, todo
# lo demas hereda de aca. "_gris" es el gris calido que el manual no
# nombra pero que hace falta para texto secundario (etiquetas, notas,
# firmas) — no es un color de marca, es una utilidad tipografica.
_AZUL = tema.MARCA["azul_profundo"]
_PETROLEO = tema.MARCA["verde_petroleo"]
_ARENA = tema.MARCA["arena"]
_GRAFITO = tema.MARCA["grafito"]
_GRIS = "#6B6B78"

_CSS = f"""
<style>
  body   {{ font-family: {tema.FUENTE_TEXTO}; font-size: 9.5pt; color: {_GRAFITO}; }}
  .cab   {{ border-bottom: 3px solid {_PETROLEO}; padding-bottom: 8px; }}
  .marca {{ font-family: {tema.FUENTE_TITULOS}; font-size: 17pt;
           font-weight: bold; color: {_AZUL}; }}
  .sub   {{ font-size: 8pt; color: {_GRIS}; }}
  .doc   {{ font-family: {tema.FUENTE_TITULOS}; font-size: 13pt;
           font-weight: bold; color: {_AZUL}; text-align: right; }}
  h2     {{ font-family: {tema.FUENTE_TITULOS}; font-size: 10pt; color: {_AZUL};
           margin: 14px 0 4px 0; border-bottom: 1px solid #E3D9C6;
           padding-bottom: 3px; }}
  table  {{ width: 100%; border-collapse: collapse; }}
  td.et  {{ color: {_GRIS}; width: 30%; padding: 3px 6px 3px 0;
           vertical-align: top; }}
  td.va  {{ width: 70%; padding: 3px 0; font-weight: bold;
           vertical-align: top; }}
  table.imp td {{ padding: 4px 6px; border-bottom: 1px solid #e3e8ef; }}
  table.imp th {{ background: {_AZUL}; color: #ffffff; padding: 6px;
                 text-align: left; font-size: 9pt; }}
  table.imp tr.alt td {{ background: {_ARENA}; }}
  .der   {{ text-align: right; }}
  .tot   {{ font-weight: bold; font-size: 11pt; color: {_AZUL}; }}
  .nota  {{ font-size: 8pt; color: {_GRIS}; }}
  td.lin {{ border-bottom: 1px solid {_GRIS}; height: 46px; }}
  td.fir {{ font-size: 8pt; color: {_GRIS}; padding-top: 4px; }}
</style>
"""


def _ruta_logo() -> str:
    """URL del logo para el membrete, o cadena vacia si no esta."""
    for base in (Path(__file__).resolve().parent.parent / "recursos",
                 config.dir_recursos()):
        p = base / "logo_horizontal.png"
        if p.exists():
            return p.as_uri()
    return ""


def _encabezado(titulo: str, numero: str) -> str:
    agencia = db.parametro("nombre_agencia", "Spamed Travel")
    pie = db.parametro("datos_agencia", "")
    logo = _ruta_logo()
    marca = (f"<img src='{logo}' width='190'>" if logo
             else f"<div class='marca'>{html.escape(agencia)}</div>")
    return f"""
    <table width='100%' class='cab'><tr>
      <td width='58%'>
        {marca}
        <div class='sub'>{html.escape(pie)}</div>
      </td>
      <td class='doc' width='42%'>{html.escape(titulo)}<br>
        <span style='font-size:10pt'>N° {html.escape(numero)}</span><br>
        <span class='sub'>Emitido el {date.today().strftime('%d/%m/%Y')}</span>
      </td>
    </tr></table>
    """


# --------------------------------------------------------------- voucher

def html_voucher(r: Mapping[str, Any],
                 movimientos: Sequence[Mapping[str, Any]] = (),
                 pasajeros: Sequence[Mapping[str, Any]] = (),
                 servicios: Sequence[Mapping[str, Any]] = ()) -> str:
    mon = r.get("moneda", "")
    m = lambda v: calculos.money(v, mon)  # noqa: E731
    f = calculos.dd_mm_yyyy

    pagos = "".join(
        f"<tr><td>{f(x.get('fecha'))}</td>"
        f"<td>{_e(x.get('concepto'))}</td>"
        f"<td>{_e(x.get('medio_pago'))}</td>"
        f"<td class='der'>{m(x.get('monto'))}</td></tr>"
        for x in movimientos if x.get("tipo") == "INGRESO"
    ) or "<tr><td colspan='4' class='nota'>Sin pagos registrados.</td></tr>"

    saldo = float(r.get("saldo_cliente") or 0)
    leyenda = ("SALDO CANCELADO" if saldo <= 0.01
               else f"SALDO PENDIENTE: {m(saldo)}")

    # Aparte del return: un f-string con comillas triples no puede anidar
    # otro del mismo tipo de comillas en Python < 3.12 (PEP 701).
    bloque_pasajero = f"""
    <table width='100%'>
      {_fila('Nombre', r.get('cliente'))}
      {_fila('Documento', r.get('cliente_dni'))}
      {_fila('Teléfono', r.get('cliente_telefono'))}
      {_fila('Cantidad de pasajeros', r.get('cant_pasajeros'))}
    </table>"""
    seccion_pasajeros = (
        _tabla_pasajeros(pasajeros) if pasajeros else bloque_pasajero
    )

    return f"""<html><head>{_CSS}</head><body>
    {_encabezado('VOUCHER DE VIAJE', str(r.get('file', '')))}

    <h2>{'Pasajeros' if pasajeros else 'Pasajero'}</h2>
    {seccion_pasajeros}

    <h2>Servicios contratados</h2>

    {_tabla_servicios(servicios)}
    <table width='100%'>
      {_fila('Destino', r.get('destino'))}
      {_fila('Operador', r.get('proveedor'))}
      {_fila('Fecha de salida', f(r.get('fecha_salida')))}
      {_fila('Fecha de regreso', f(r.get('fecha_regreso')))}
      {_fila('Transporte', r.get('transporte'))}
      {_fila('Alojamiento', r.get('hotel'))}
      {_fila('Régimen', r.get('regimen'))}
      {_fila('Excursiones', r.get('excursiones'))}
    </table>

    <h2>Condiciones económicas</h2>
    <table width='100%'>
      {_fila('Moneda', mon)}
      {_fila('Importe total', m(r.get('importe_cliente')))}
      {_fila('Total abonado', m(r.get('cobrado_cliente')))}
      {_fila('Vencimiento de seña', f(r.get('fecha_vto_sena')))}
      {_fila('Vencimiento de reserva', f(r.get('fecha_vto_reserva')))}
      {_fila('Estado', r.get('estado'))}
    </table>

    <h2>Detalle de pagos</h2>
    <table width='100%' class='imp' cellspacing='0'>
      <tr><th>Fecha</th><th>Concepto</th><th>Medio</th>
          <th class='der'>Importe</th></tr>
      {pagos}
      <tr><td colspan='3' class='tot'>{leyenda}</td>
          <td class='der tot'>{m(r.get('cobrado_cliente'))}</td></tr>
    </table>

    <p class='nota'>Documento emitido por {html.escape(
        db.parametro('nombre_agencia', 'Spamed Travel'))} como constancia de
    los servicios contratados bajo el file {_e(r.get('file'))}. Presentar ante
    el prestador junto con documento de identidad. Las condiciones de
    cancelación y modificación son las del operador mayorista.</p>

    <br><br>
    <table width='100%' cellspacing='0'>
      <tr><td class='lin' width='45%'></td><td width='10%'></td><td class='lin' width='45%'></td></tr>
      <tr><td class='fir'>Firma y sello de la agencia</td><td></td><td class='fir'>Firma del pasajero</td></tr>
    </table>
    </body></html>"""


# ---------------------------------------------------------------- recibo

def html_recibo(r: Mapping[str, Any], mov: Mapping[str, Any]) -> str:
    mon = mov.get("moneda", r.get("moneda", ""))
    m = lambda v: calculos.money(v, mon)  # noqa: E731
    numero = f"{r.get('file', '')}-{mov.get('id', '')}"

    return f"""<html><head>{_CSS}</head><body>
    {_encabezado('RECIBO DE PAGO', numero)}

    <h2>Recibimos de</h2>
    <table width='100%'>
      {_fila('Nombre', r.get('cliente'))}
      {_fila('Documento', r.get('cliente_dni'))}
    </table>

    <h2>Concepto</h2>
    <table width='100%'>
      {_fila('File', r.get('file'))}
      {_fila('Destino', r.get('destino'))}
      {_fila('Concepto', mov.get('concepto'))}
      {_fila('Medio de pago', mov.get('medio_pago'))}
      {_fila('Fecha de pago', calculos.dd_mm_yyyy(mov.get('fecha')))}
      {_fila('Detalle', mov.get('detalle'))}
    </table>

    <h2>Importe</h2>
    <table width='100%' class='imp' cellspacing='0'>
      <tr><th>Descripción</th><th class='der'>Importe</th></tr>
      <tr><td>Pago recibido</td>
          <td class='der tot'>{m(mov.get('monto'))}</td></tr>
      <tr><td>Total del file</td>
          <td class='der'>{calculos.money(r.get('importe_cliente'), mon)}</td></tr>
      <tr><td>Abonado a la fecha</td>
          <td class='der'>{calculos.money(r.get('cobrado_cliente'), mon)}</td></tr>
      <tr><td>Saldo pendiente</td>
          <td class='der tot'>{calculos.money(r.get('saldo_cliente'), mon)}</td></tr>
    </table>

    <p class='nota'>Este recibo es constancia del pago detallado. No constituye
    factura. Válido con firma y sello de la agencia.</p>

    <br><br>
    <table width='100%' cellspacing='0'>
      <tr><td class='lin' width='45%'></td><td width='10%'></td><td class='lin' width='45%'></td></tr>
      <tr><td class='fir'>Firma y sello de la agencia</td><td></td><td class='fir'>Recibí conforme</td></tr>
    </table>
    </body></html>"""


def html_encuesta(r: Mapping[str, Any]) -> str:
    """Encuesta de satisfaccion para el file Finalizado. Preguntas fijas de
    1 a 5 + un espacio para comentarios; se responde a mano (por telefono,
    whatsapp, etc.) y despues se carga en la app."""
    def pregunta(texto: str) -> str:
        celdas = "".join(f"<td class='esc'>{n}</td>" for n in range(1, 6))
        return f"<tr><td class='preg'>{html.escape(texto)}</td>{celdas}</tr>"

    return f"""<html><head>{_CSS}
    <style>
      table.enc td.esc  {{ border: 1px solid {_GRIS}; width: 26px;
                           text-align: center; }}
      table.enc td.preg {{ padding: 8px 6px; }}
      table.enc th      {{ font-size: 8pt; color: {_GRIS}; text-align: center; }}
    </style>
    </head><body>
    {_encabezado('ENCUESTA DE SATISFACCIÓN', r.get('file', ''))}

    <h2>Sobre tu viaje</h2>
    <table width='100%'>
      {_fila('Cliente', r.get('cliente'))}
      {_fila('File', r.get('file'))}
      {_fila('Destino', r.get('destino'))}
    </table>

    <h2>Contanos cómo te fue</h2>
    <p class='nota'>Marcá de 1 (muy en desacuerdo) a 5 (muy de acuerdo).</p>
    <table width='100%' class='enc' cellspacing='0'>
      <tr><th></th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th></tr>
      {pregunta('La atención que recibiste fue buena')}
      {pregunta('El destino cumplió tus expectativas')}
      {pregunta('Nos recomendarías a un amigo o familiar')}
    </table>

    <h2>Comentarios</h2>
    <table width='100%' cellspacing='0'>
      <tr><td class='lin'></td></tr>
      <tr><td class='lin'></td></tr>
    </table>

    <p class='nota'>Gracias por viajar con nosotros.</p>
    </body></html>"""


# ------------------------------------------------------------ impresion

def guardar_pdf(contenido_html: str, destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    escritor = QPdfWriter(str(destino))
    escritor.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    escritor.setPageMargins(QMarginsF(15, 15, 15, 15))
    escritor.setResolution(300)

    doc = QTextDocument()
    # Sin esto el layout asume 96 dpi y, contra un dispositivo de 300 dpi,
    # el texto sale a un tercio del tamano en una hoja casi vacia.
    doc.documentLayout().setPaintDevice(escritor)
    doc.setDefaultFont(QFont("Instrument Sans", 10))
    doc.setPageSize(QSizeF(escritor.width(), escritor.height()))
    doc.setHtml(contenido_html)
    doc.print_(escritor)
    return destino


def _limpiar(texto: Any, tope: int = 24) -> str:
    """Deja un texto usable como parte de un nombre de archivo."""
    limpio = "".join(
        c for c in str(texto or "").strip() if c.isalnum() or c in "-_ "
    ).strip().replace(" ", "-")
    return limpio[:tope]


def _nombre(prefijo: str, file: str, quien: Any = "") -> Path:
    # Con resolucion de minuto, dos documentos del mismo file generados
    # seguidos (p.ej. reimprimir un voucher) pisan el mismo archivo en disco.
    # Los microsegundos evitan la colision sin cambiar el formato visible.
    marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    partes = [prefijo, _limpiar(file)]
    # El apellido hace que el archivo se reconozca de un vistazo en Descargas,
    # donde convive con todo lo demas que baja el usuario.
    apellido = _limpiar(str(quien or "").split(",")[0])
    if apellido:
        partes.append(apellido)
    partes.append(marca)
    return config.dir_exports() / ("_".join(p for p in partes if p) + ".pdf")


def voucher(reserva: Mapping[str, Any],
            movimientos: Sequence[Mapping[str, Any]] = (),
            pasajeros: Sequence[Mapping[str, Any]] = (),
            servicios: Sequence[Mapping[str, Any]] = (),
            destino: Path | None = None) -> Path:
    return guardar_pdf(
        html_voucher(reserva, movimientos, pasajeros, servicios),
        destino or _nombre("Voucher", reserva.get("file", ""),
                           reserva.get("cliente", "")),
    )


def recibo(reserva: Mapping[str, Any], movimiento: Mapping[str, Any],
           destino: Path | None = None) -> Path:
    return guardar_pdf(
        html_recibo(reserva, movimiento),
        destino or _nombre("Recibo", reserva.get("file", ""),
                           reserva.get("cliente", "")),
    )


def encuesta(reserva: Mapping[str, Any], destino: Path | None = None) -> Path:
    return guardar_pdf(
        html_encuesta(reserva),
        destino or _nombre("Encuesta", reserva.get("file", ""),
                           reserva.get("cliente", "")),
    )


# ------------------------------------------------- bloques reutilizables

def _tabla_pasajeros(pax: Sequence[Mapping[str, Any]]) -> str:
    filas = "".join(
        f"<tr><td>{_e(p.get('nombre'))}</td>"
        f"<td>{_e(p.get('documento'))}</td>"
        f"<td>{_e(p.get('pasaporte'))}</td>"
        f"<td>{calculos.dd_mm_yyyy(p.get('vto_pasaporte')) or '—'}</td></tr>"
        for p in pax
    )
    return f"""<table width='100%' class='imp' cellspacing='0'>
      <tr><th>Nombre</th><th>Documento</th><th>Pasaporte</th>
          <th>Vto. pasaporte</th></tr>{filas}</table>"""


def _tabla_servicios(servicios: Sequence[Mapping[str, Any]]) -> str:
    if not servicios:
        return ""
    filas = "".join(
        f"<tr><td>{_e(s.get('concepto'))}</td>"
        f"<td>{_e(s.get('proveedor'))}</td>"
        f"<td>{_e(s.get('detalle'))}</td></tr>"
        for s in servicios
    )
    return f"""<table width='100%' class='imp' cellspacing='0'>
      <tr><th>Servicio</th><th>Operador</th><th>Detalle</th></tr>
      {filas}</table><br>"""


def _pie(texto: str) -> str:
    return f"<p class='nota'>{html.escape(texto)}</p>"


def _firmas(a: str, b: str) -> str:
    return (
        "<table width='100%' cellspacing='0'>"
        "<tr><td class='lin' width='45%'></td><td width='10%'></td>"
        "<td class='lin' width='45%'></td></tr>"
        f"<tr><td class='fir'>{a}</td><td></td><td class='fir'>{b}</td></tr>"
        "</table>"
    )


# ------------------------------------------------------------ cotizacion

def html_cotizacion(r: Mapping[str, Any],
                    servicios: Sequence[Mapping[str, Any]] = (),
                    pasajeros: Sequence[Mapping[str, Any]] = (),
                    validez_dias: int = 7) -> str:
    """Presupuesto para mandarle al cliente antes de que sea reserva."""
    mon = r.get("moneda", "")
    m = lambda v: calculos.money(v, mon)  # noqa: E731
    f = calculos.dd_mm_yyyy
    vence = date.today() + timedelta(days=validez_dias)

    detalle = _tabla_servicios(servicios) if servicios else ""
    pax = (f"<h2>Pasajeros</h2>{_tabla_pasajeros(pasajeros)}"
           if pasajeros else "")

    return f"""<html><head>{_CSS}</head><body>
    {_encabezado('COTIZACIÓN', str(r.get('file', '')))}

    <h2>Cliente</h2>
    <table width='100%'>
      {_fila('Nombre', r.get('cliente'))}
      {_fila('Teléfono', r.get('cliente_telefono'))}
      {_fila('Email', r.get('cliente_email'))}
      {_fila('Asesor', r.get('vendedor'))}
    </table>

    <h2>Propuesta</h2>
    {detalle}
    <table width='100%'>
      {_fila('Destino', r.get('destino'))}
      {_fila('Fecha de salida', f(r.get('fecha_salida')))}
      {_fila('Fecha de regreso', f(r.get('fecha_regreso')))}
      {_fila('Cantidad de pasajeros', r.get('cant_pasajeros'))}
      {_fila('Transporte', r.get('transporte'))}
      {_fila('Alojamiento', r.get('hotel'))}
      {_fila('Régimen', r.get('regimen'))}
      {_fila('Excursiones', r.get('excursiones'))}
    </table>
    {pax}

    <h2>Inversión</h2>
    <table width='100%' class='imp' cellspacing='0'>
      <tr><th>Concepto</th><th class='der'>Importe</th></tr>
      <tr><td>Total del viaje ({_e(mon)})</td>
          <td class='der tot'>{m(r.get('importe_cliente'))}</td></tr>
      <tr><td>Seña sugerida para reservar</td>
          <td class='der'>{m(float(r.get('importe_cliente') or 0) * 0.2)}</td></tr>
    </table>

    <table width='100%'>
      {_fila('Válida hasta', vence.strftime('%d/%m/%Y'))}
      {_fila('Vencimiento de seña', f(r.get('fecha_vto_sena')))}
      {_fila('Vencimiento de reserva', f(r.get('fecha_vto_reserva')))}
    </table>

    {_pie('Cotización sujeta a disponibilidad y a confirmación del operador '
          'al momento de la reserva. Las tarifas pueden variar hasta la '
          'emisión. No constituye reserva ni comprobante de pago.')}
    <br><br>
    {_firmas('Firma y sello de la agencia', 'Conformidad del cliente')}
    </body></html>"""


# ------------------------------------------------- estado de cuenta

def html_estado_cuenta(datos: Mapping[str, Any]) -> str:
    cli = datos["cliente"]
    files = datos["files"]
    totales = datos["totales"]

    filas = "".join(
        f"<tr><td>{_e(x.get('file'))}</td>"
        f"<td>{_e(x.get('destino'))}</td>"
        f"<td>{_e(x.get('estado'))}</td>"
        f"<td>{_e(x.get('moneda'))}</td>"
        f"<td class='der'>{calculos.money(x.get('importe_cliente'))}</td>"
        f"<td class='der'>{calculos.money(x.get('cobrado_cliente'))}</td>"
        f"<td class='der'>{calculos.money(x.get('saldo_cliente'))}</td></tr>"
        for x in files
    ) or "<tr><td colspan='7' class='nota'>Sin operaciones.</td></tr>"

    resumen = "".join(
        f"<tr><td>{_e(mon)}</td>"
        f"<td class='der'>{calculos.money(v['comprado'], mon)}</td>"
        f"<td class='der'>{calculos.money(v['pagado'], mon)}</td>"
        f"<td class='der tot'>{calculos.money(v['saldo'], mon)}</td></tr>"
        for mon, v in totales.items()
    ) or "<tr><td colspan='4' class='nota'>Sin saldos.</td></tr>"

    return f"""<html><head>{_CSS}</head><body>
    {_encabezado('ESTADO DE CUENTA', str(cli.get('dni', '')))}

    <h2>Cliente</h2>
    <table width='100%'>
      {_fila('Nombre', f"{cli.get('apellido', '')}, {cli.get('nombre', '')}")}
      {_fila('Documento', cli.get('dni'))}
      {_fila('Teléfono', cli.get('telefono'))}
      {_fila('Email', cli.get('email'))}
    </table>

    <h2>Operaciones</h2>
    <table width='100%' class='imp' cellspacing='0'>
      <tr><th>File</th><th>Destino</th><th>Estado</th><th>Mon.</th>
          <th class='der'>Importe</th><th class='der'>Pagado</th>
          <th class='der'>Saldo</th></tr>
      {filas}
    </table>

    <h2>Resumen</h2>
    <table width='100%' class='imp' cellspacing='0'>
      <tr><th>Moneda</th><th class='der'>Comprado</th>
          <th class='der'>Pagado</th><th class='der'>Saldo</th></tr>
      {resumen}
    </table>

    {_pie('Estado de cuenta emitido a la fecha indicada. Ante cualquier '
          'diferencia, comunicate con la agencia.')}
    </body></html>"""


# ------------------------------------------------- liquidacion de comision

def html_liquidacion(vendedor: str, anio: int, mes: int, moneda: str,
                     filas: Sequence[Mapping[str, Any]],
                     total: float) -> str:
    detalle = "".join(
        f"<tr><td>{calculos.dd_mm_yyyy(x.get('fecha'))}</td>"
        f"<td>{_e(x.get('file'))}</td>"
        f"<td>{_e(x.get('cliente'))}</td>"
        f"<td>{_e(x.get('destino'))}</td>"
        f"<td class='der'>{calculos.money(x.get('importe_cliente'), moneda)}</td>"
        f"<td class='der'>{calculos.money(x.get('comision_agencia'), moneda)}</td>"
        f"<td class='der'>{calculos.money(x.get('comision_vendedor'), moneda)}</td>"
        "</tr>"
        for x in filas
    ) or "<tr><td colspan='7' class='nota'>Sin operaciones en el período.</td></tr>"

    return f"""<html><head>{_CSS}</head><body>
    {_encabezado('LIQUIDACIÓN DE COMISIONES', f'{mes:02d}/{anio}')}

    <h2>Vendedor</h2>
    <table width='100%'>
      {_fila('Nombre', vendedor)}
      {_fila('Período', f'{mes:02d}/{anio}')}
      {_fila('Moneda', moneda)}
      {_fila('Operaciones', len(filas))}
    </table>

    <h2>Detalle</h2>
    <table width='100%' class='imp' cellspacing='0'>
      <tr><th>Fecha</th><th>File</th><th>Cliente</th><th>Destino</th>
          <th class='der'>Venta</th><th class='der'>Com. agencia</th>
          <th class='der'>Le corresponde</th></tr>
      {detalle}
      <tr><td colspan='6' class='tot'>TOTAL A LIQUIDAR</td>
          <td class='der tot'>{calculos.money(total, moneda)}</td></tr>
    </table>

    {_pie('Liquidación calculada sobre la comisión que la agencia percibe de '
          'cada operador, según el porcentaje acordado con el vendedor.')}
    <br><br>
    {_firmas('Firma y sello de la agencia', 'Recibí conforme')}
    </body></html>"""


# --------------------------------------------------- informe generico

def html_informe(titulo: str, columnas: Sequence[tuple[str, str]],
                 filas: Sequence[Mapping[str, Any]],
                 formato=None, subtitulo: str = "") -> str:
    """Convierte cualquier grilla de la aplicacion en un informe imprimible."""
    def celda(f, clave):
        v = formato(f, clave) if formato else f.get(clave)
        return "—" if v in (None, "") else html.escape(str(v))

    cab = "".join(f"<th>{html.escape(t)}</th>" for _, t in columnas)
    cuerpo = "".join(
        "<tr>" + "".join(
            f"<td>{celda(f, k)}</td>" for k, _ in columnas) + "</tr>"
        for f in filas
    ) or f"<tr><td colspan='{len(columnas)}' class='nota'>Sin datos.</td></tr>"

    sub = f"<div class='sub'>{html.escape(subtitulo)}</div>" if subtitulo else ""
    return f"""<html><head>{_CSS}
    <style>
      table.imp td, table.imp th {{ font-size: 8pt; padding: 4px 5px; }}
    </style></head><body>
    {_encabezado('INFORME', titulo)}
    <h2>{html.escape(titulo)}</h2>
    {sub}
    <table width='100%' class='imp' cellspacing='0'>
      <tr>{cab}</tr>
      {cuerpo}
    </table>
    {_pie(f'{len(filas)} registro(s). Generado por Spamed Travel.')}
    </body></html>"""


# ------------------------------------------------------ cierre mensual

MESES = ("", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def html_cierre(anio: int, mes: int, filas: Sequence[Mapping[str, Any]]) -> str:
    bloques = []
    for d in filas:
        mon = d["moneda"]
        m = lambda v: calculos.money(v, mon)  # noqa: E731
        var = d.get("var_ventas", 0)
        signo = "+" if var > 0 else ""
        bloques.append(f"""
        <h2>{html.escape(mon)}</h2>
        <table width='100%' class='imp' cellspacing='0'>
          <tr><th>Concepto</th><th class='der'>Importe</th></tr>
          <tr><td>Ventas del mes ({d['files']} files)</td>
              <td class='der'>{m(d['ventas'])}</td></tr>
          <tr><td>Comisión de la agencia</td>
              <td class='der'>{m(d['comision_agencia'])}</td></tr>
          <tr><td>Comisión de vendedores</td>
              <td class='der'>− {m(d['comision_vendedores'])}</td></tr>
          <tr><td class='tot'>Margen de la agencia</td>
              <td class='der tot'>{m(d['margen'])}</td></tr>
          <tr><td colspan='2'></td></tr>
          <tr><td>Cobros a clientes</td>
              <td class='der'>{m(d['cobros_clientes'])}</td></tr>
          <tr><td>Pagos a operadores</td>
              <td class='der'>− {m(d['pagos_proveedores'])}</td></tr>
          <tr><td>Gastos generales</td>
              <td class='der'>− {m(d['gastos_generales'])}</td></tr>
          <tr><td>Devoluciones a clientes</td>
              <td class='der'>− {m(d['devoluciones'])}</td></tr>
          <tr><td class='tot'>Resultado de caja</td>
              <td class='der tot'>{m(d['resultado_caja'])}</td></tr>
          <tr><td colspan='2'></td></tr>
          <tr><td>Objetivo del mes</td>
              <td class='der'>{m(d['objetivo']) if d['objetivo'] else '—'}</td></tr>
          <tr><td>Cumplimiento</td>
              <td class='der'>{f"{d['cumplimiento']}%" if d['objetivo'] else '—'}</td></tr>
          <tr><td>Variación de ventas vs. mes anterior</td>
              <td class='der'>{signo}{var}%</td></tr>
        </table>""")

    return f"""<html><head>{_CSS}</head><body>
    {_encabezado('CIERRE CONTABLE', f'{MESES[mes].capitalize()} {anio}')}
    {''.join(bloques) or _pie('Sin movimientos en el período.')}
    {_pie('Las monedas no se consolidan: cada una mantiene su propio '
          'resultado. Los cambios de moneda no generan resultado, solo '
          'trasladan saldo entre monedas.')}
    <br><br>
    {_firmas('Responsable administrativo', 'Conformidad')}
    </body></html>"""


# ------------------------------------------------------------ atajos

def cotizacion(reserva, servicios=(), pasajeros=(), destino=None) -> Path:
    return guardar_pdf(
        html_cotizacion(reserva, servicios, pasajeros),
        destino or _nombre("Cotizacion", reserva.get("file", ""),
                           reserva.get("cliente", "")))


def estado_cuenta(datos, destino=None) -> Path:
    cli = datos["cliente"]
    return guardar_pdf(
        html_estado_cuenta(datos),
        destino or _nombre("EstadoCuenta", cli.get("dni", ""),
                           cli.get("apellido", "")))


def liquidacion(vendedor, anio, mes, moneda, filas, total, destino=None) -> Path:
    return guardar_pdf(
        html_liquidacion(vendedor, anio, mes, moneda, filas, total),
        destino or _nombre("Liquidacion", f"{anio}{mes:02d}", vendedor))


def informe(titulo, columnas, filas, formato=None, subtitulo="",
            destino=None) -> Path:
    return guardar_pdf(
        html_informe(titulo, columnas, filas, formato, subtitulo),
        destino or _nombre("Informe", titulo.replace(" ", "_")[:30]))


def cierre(anio, mes, filas, destino=None) -> Path:
    return guardar_pdf(
        html_cierre(anio, mes, filas),
        destino or _nombre("Cierre", f"{anio}{mes:02d}"))
