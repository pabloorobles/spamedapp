"""Genera el Excel modelo para la carga inicial de datos.

Es el formato que espera 'importador.py'. Las cinco primeras hojas replican
las del libro viejo BaseDatosSpamed (por eso los encabezados raros: se
mantienen tal cual para que ese libro siga entrando sin tocarlo). Las tres
ultimas son nuevas: no existian en el Excel original.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

from . import config

# (hoja, [(encabezado, ancho)], [filas de ejemplo], ayuda)
HOJAS: list[tuple[str, list[tuple[str, int]], list[list[Any]], str]] = []


def _hoy(dias: int = 0) -> str:
    return (date.today() + timedelta(days=dias)).strftime("%d/%m/%Y")


def _definir() -> None:
    if HOJAS:
        return

    HOJAS.append((
        "Clientes",
        [("dni", 14), ("nombre", 18), ("apellido", 18), ("telefono", 16),
         ("email", 26), ("direccion", 26), ("Cumple", 13), ("FechaAlta", 13),
         ("Referido", 16), ("Detalle_referido", 22), ("Observaciones", 30)],
        [["30111222", "Lucia", "Martinez", "2664-555111",
          "lucia@correo.com", "San Martin 123", "14/03/1990", _hoy(-120),
          "Instagram", "Campaña verano", ""]],
        "Una fila por cliente. El DNI no se puede repetir: es lo que usa la "
        "aplicación para no cargar dos veces a la misma persona.",
    ))

    HOJAS.append((
        "Vendedores",
        [("dni", 14), ("nombre", 18), ("apellido", 18), ("telefono", 16),
         ("comision%", 12), ("estado", 12)],
        [["54654524", "Rosa", "Medrano", "2664-555222", 10, "Activo"]],
        "La comisión va en porcentaje (10 = 10%) y se calcula sobre la "
        "comisión que deja el mayorista, no sobre el total de la venta. "
        "En estado poné Activo o Inactivo.",
    ))

    HOJAS.append((
        "Proveedores",
        [("nombre", 24), ("tipo", 16), ("moneda", 12), ("contacto", 22),
         ("comision%", 12), ("transfiere_neto", 16)],
        [["Amichi", "Mayorista", "PESOS", "ventas@amichi.com", 12, "SI"]],
        "El nombre no se puede repetir. La comisión es la que el mayorista "
        "le reconoce a la agencia. En transfiere_neto poné SI si le "
        "mandás la venta menos tu comisión en un solo pago, o NO si le "
        "pagás el total y después te devuelve la comisión.",
    ))

    HOJAS.append((
        "Reservas",
        [("file", 12), ("id_cli", 30), ("id_vend", 30), ("id_prov", 20),
         ("destino", 20), ("moneda", 10), ("importe_cli", 14),
         ("costo_prov", 14), ("inicio de cotizacion", 18),
         ("fecha reserva", 14), ("vto_seña", 13), ("vto_reserva", 13),
         ("Entrega Voucher", 15), ("transporte", 14), ("hotel", 20),
         ("regimen", 18), ("excursiones", 24), ("Cancelada", 11)],
        [["R2601", "Martinez Lucia (30.111.222)",
          "Medrano Rosa (54.654.524)", "Amichi", "Bariloche", "PESOS",
          1000000, 880000, _hoy(-30), _hoy(-25), _hoy(-20), _hoy(10),
          "", "Aereo", "Hotel Nahuel", "Media pension", "City tour", ""]],
        "El file no se puede repetir: es el número que identifica la "
        "operación. En id_cli e id_vend escribí 'Apellido Nombre (DNI)' — "
        "si el DNI está entre paréntesis, la aplicación engancha con el "
        "cliente que ya cargaste. Las fechas van en dd/mm/aaaa. Dejá "
        "Cancelada vacío salvo que el file esté anulado.",
    ))

    HOJAS.append((
        "Caja",
        [("fecha", 13), ("concepto", 22), ("asociado", 12), ("moneda", 10),
         ("monto", 14), ("tipo_pago", 16), ("detalle", 28)],
        [[_hoy(-25), "Sena Cliente", "R2601", "PESOS", 250000,
          "Transferencia", "Seña del 25%"],
         [_hoy(-20), "Pago Proveedor", "R2601", "PESOS", -880000,
          "Transferencia", "Pago a Amichi"]],
        "Monto positivo = entra plata; monto negativo = sale. En asociado "
        "poné el file al que corresponde, o dejalo vacío si es un gasto "
        "general de la agencia.",
    ))

    # ------------------------------------------------ hojas nuevas (v1.1)
    HOJAS.append((
        "Servicios",
        [("file", 12), ("concepto", 18), ("proveedor", 20), ("detalle", 26),
         ("importe_venta", 14), ("costo", 14)],
        [["R2601", "Aereo", "Amichi", "AEP-BRC ida y vuelta", 400000, 352000],
         ["R2601", "Alojamiento", "Amichi", "7 noches", 600000, 528000]],
        "Sólo si el file tiene varios proveedores o querés abrir el viaje "
        "por servicio. Ojo: si un file tiene servicios cargados, el costo "
        "del proveedor pasa a ser la suma de estos costos.",
    ))

    HOJAS.append((
        "Pasajeros",
        [("file", 12), ("nombre", 26), ("documento", 14), ("fecha_nac", 13),
         ("pasaporte", 16), ("vto_pasaporte", 14), ("observaciones", 26)],
        [["R2601", "Martinez, Lucia", "30111222", "14/03/1990",
          "AAB123456", _hoy(400), ""]],
        "Quiénes viajan. Estos son los nombres que salen impresos en el "
        "voucher. El vencimiento del pasaporte alimenta el aviso de "
        "pasaportes por vencer del tablero.",
    ))

    HOJAS.append((
        "Cuotas",
        [("file", 12), ("numero", 9), ("vencimiento", 13), ("importe", 14),
         ("nota", 26)],
        [["R2601", 1, _hoy(5), 375000, "Primera cuota"],
         ["R2601", 2, _hoy(35), 375000, ""]],
        "Plan de pagos del cliente: cuándo tendría que pagar cada parte. "
        "No son cobros hechos — los cobros van en la hoja Caja.",
    ))


def hojas_de_datos() -> list[str]:
    _definir()
    return [nombre for nombre, _, _, _ in HOJAS]


def generar(destino: Path | None = None) -> Path:
    """Escribe el .xlsx modelo y devuelve la ruta."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Falta la libreria openpyxl para generar la plantilla."
        ) from e

    _definir()
    destino = Path(destino) if destino else (
        config.dir_exports() / "Plantilla_SpamedTravel.xlsx")
    destino.parent.mkdir(parents=True, exist_ok=True)

    from openpyxl.comments import Comment

    wb = Workbook()
    wb.remove(wb.active)

    _hoja_instrucciones(wb)

    fuente_enc = Font(name="Arial", bold=True, color="FFFFFF")
    relleno = PatternFill("solid", fgColor="1F3864")
    fuente_ej = Font(name="Arial", italic=True, color="808080")

    for nombre, columnas, ejemplos, ayuda in HOJAS:
        ws = wb.create_sheet(nombre)

        # Los titulos van en la PRIMERA fila, sin nada arriba: el importador
        # toma la primera fila con contenido como encabezados. Una fila de
        # ayuda arriba haria que no reconozca ninguna columna.
        for i, (titulo, ancho) in enumerate(columnas, start=1):
            c = ws.cell(1, i, titulo)
            c.font = fuente_enc
            c.fill = relleno
            c.alignment = Alignment(horizontal="center", vertical="center")
            ws.column_dimensions[get_column_letter(i)].width = ancho

        # La explicacion de la hoja va como comentario de la primera celda
        # (se ve al pasar el mouse) y repetida en la hoja Instrucciones.
        ws.cell(1, 1).comment = Comment(f"{nombre}\n\n{ayuda}", config.APP_NAME,
                                        height=160, width=340)

        for fila_idx, ejemplo in enumerate(ejemplos, start=2):
            for col_idx, valor in enumerate(ejemplo, start=1):
                ws.cell(fila_idx, col_idx, valor).font = fuente_ej

        ws.freeze_panes = "A2"

    wb.save(destino)
    return destino


def _hoja_instrucciones(wb) -> None:
    from openpyxl.styles import Alignment, Font

    ws = wb.create_sheet("Instrucciones")
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 104

    lineas: list[tuple[str, str]] = [
        ("titulo", f"{config.APP_NAME} — plantilla de carga inicial"),
        ("", ""),
        ("texto", "Cargá tus datos en las hojas de este archivo y después "
                  "importalo desde la aplicación: Herramientas → Importar "
                  "Excel."),
        ("", ""),
        ("sub", "Cómo usarla"),
        ("texto", "1. Las filas grises son un ejemplo. Borralas antes de "
                  "importar, o quedarán cargadas como datos reales."),
        ("texto", "2. No cambies los nombres de las hojas ni los títulos de "
                  "las columnas (fila 1), y no agregues filas arriba de los "
                  "títulos: son los que busca la aplicación."),
        ("texto", "3. Podés dejar hojas enteras vacías. Si no tenés "
                  "servicios, pasajeros o cuotas para cargar, no pasa nada."),
        ("texto", "4. Cargá primero clientes, vendedores y proveedores. Las "
                  "reservas se enganchan con ellos."),
        ("texto", "5. Las fechas van en formato dd/mm/aaaa."),
        ("texto", "6. Los importes van sin símbolo de moneda ni puntos de "
                  "miles: 1000000, no $ 1.000.000."),
        ("", ""),
        ("sub", "Al importar, la aplicación te pregunta"),
        ("texto", "• Sí = borra todo lo que haya cargado y deja únicamente "
                  "lo de este archivo."),
        ("texto", "• No = agrega lo nuevo y actualiza lo que ya existe, sin "
                  "borrar nada."),
        ("texto", "Antes de importar se guarda una copia de seguridad "
                  "automática, así que siempre se puede volver atrás."),
        ("", ""),
        ("sub", "Cómo se calcula la ganancia"),
        ("texto", "El mayorista le reconoce a la agencia un porcentaje de la "
                  "venta (se carga en Proveedores): esa es la comisión de la "
                  "agencia. De ahí sale el porcentaje del vendedor (se carga "
                  "en Vendedores). Lo que queda es el margen de la agencia."),
        ("texto", "El costo del proveedor no hace falta calcularlo: la "
                  "aplicación lo deduce como venta menos comisión."),
        ("", ""),
        ("sub", "Las monedas no se mezclan"),
        ("texto", "Pesos y dólares se informan siempre por separado. Un file "
                  "en dólares sólo admite movimientos de caja en dólares."),
        ("", ""),
        ("sub", "Qué va en cada hoja"),
    ]
    for nombre, _, _, ayuda in HOJAS:
        lineas.append(("texto", f"{nombre}: {ayuda}"))

    fila = 2
    for tipo, texto in lineas:
        c = ws.cell(fila, 2, texto)
        if tipo == "titulo":
            c.font = Font(name="Arial", size=15, bold=True, color="1F3864")
        elif tipo == "sub":
            c.font = Font(name="Arial", size=11, bold=True, color="1F3864")
        else:
            c.font = Font(name="Arial", size=10)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if len(texto) > 95:
                ws.row_dimensions[fila].height = 30
        fila += 1

    ws.sheet_view.showGridLines = False
