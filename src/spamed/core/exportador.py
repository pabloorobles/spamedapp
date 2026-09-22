"""Exportacion de cualquier grilla a Excel o CSV."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import config


def _valor(v: Any) -> Any:
    if isinstance(v, dict):
        return " | ".join(f"{k}: {x}" for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return " | ".join(str(x) for x in v)
    return v


def a_csv(filas: Iterable[dict[str, Any]], columnas: Sequence[tuple[str, str]],
          destino: Path | None = None, nombre: str = "export") -> Path:
    destino = destino or _destino(nombre, ".csv")
    with open(destino, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow([tit for _, tit in columnas])
        for f in filas:
            w.writerow([_valor(f.get(k)) for k, _ in columnas])
    return destino


def a_excel(filas: Iterable[dict[str, Any]], columnas: Sequence[tuple[str, str]],
            destino: Path | None = None, nombre: str = "export",
            titulo_hoja: str = "Datos") -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return a_csv(filas, columnas, None, nombre)

    destino = destino or _destino(nombre, ".xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = titulo_hoja[:31]

    encabezado = Font(name="Arial", bold=True, color="FFFFFF")
    relleno = PatternFill("solid", fgColor="1F3864")
    for i, (_, tit) in enumerate(columnas, start=1):
        c = ws.cell(1, i, tit)
        c.font = encabezado
        c.fill = relleno
        c.alignment = Alignment(horizontal="center", vertical="center")

    for fila_idx, f in enumerate(filas, start=2):
        for col_idx, (clave, _) in enumerate(columnas, start=1):
            c = ws.cell(fila_idx, col_idx, _valor(f.get(clave)))
            c.font = Font(name="Arial")
            if isinstance(f.get(clave), (int, float)) and not isinstance(f.get(clave), bool):
                c.number_format = "#,##0.00"

    for i, (_, tit) in enumerate(columnas, start=1):
        ancho = max(len(str(tit)) + 4, 12)
        ws.column_dimensions[get_column_letter(i)].width = min(ancho, 45)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    wb.save(destino)
    return destino


def _destino(nombre: str, ext: str) -> Path:
    marca = datetime.now().strftime("%Y%m%d_%H%M")
    return config.dir_exports() / f"{nombre}_{marca}{ext}"
