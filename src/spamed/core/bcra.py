"""Cotizacion del dolar oficial, para el resumen consolidado del cierre.

Sale de dolarapi.com, un espejo confiable de la cotizacion oficial/BCRA (la
API propia del Banco Central tiene problemas de certificado SSL conocidos,
lo que la hace fragil para conectarse de forma simple y segura). Es la
UNICA llamada de red que hace la aplicacion; todo el resto es local.

La ultima cotizacion obtenida se guarda en 'parametros' con su fecha, para
poder seguir mostrando algo razonable sin conexion ("ultima conocida").
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from . import db

URL = "https://dolarapi.com/v1/dolares/oficial"
TIMEOUT = 6  # segundos: que un cierre no se cuelgue esperando la red


class ErrorCotizacion(Exception):
    """La cotizacion no se pudo obtener (sin internet, sitio caido, etc.)."""


def obtener_online() -> float:
    """Pide la cotizacion a dolarapi.com. Lanza ErrorCotizacion si falla."""
    # Sin User-Agent, algunos servidores rechazan el default de urllib
    # ("Python-urllib/3.x") aunque haya conexion — eso se veia como el
    # mismo error generico de "sin internet".
    pedido = urllib.request.Request(
        URL, headers={"User-Agent": "Mozilla/5.0 (SpamedTravel)"})
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resp:
            datos: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return float(datos["venta"])
    except (urllib.error.URLError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as e:
        # El detalle real (timeout, DNS, HTTP 403/500, JSON invalido, etc.)
        # va en el mensaje: el generico "sin internet" tapaba la causa
        # real y hacia imposible diagnosticar un fallo con conexion.
        raise ErrorCotizacion(
            f"No se pudo obtener la cotización: {e}"
        ) from e


def actualizar() -> float:
    """Pide la cotizacion online y la guarda como la ultima conocida."""
    valor = obtener_online()
    guardar_manual(valor)
    return valor


def guardar_manual(valor: float) -> None:
    """Guarda una cotizacion cargada a mano (o recien bajada) como la
    ultima conocida, con la fecha de ahora."""
    db.set_parametro("cotizacion_dolar", str(float(valor)))
    db.set_parametro(
        "cotizacion_dolar_fecha", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def ultima_guardada() -> tuple[float | None, str | None]:
    """La ultima cotizacion guardada (aunque sea vieja), con su fecha."""
    valor = db.parametro("cotizacion_dolar", "")
    fecha = db.parametro("cotizacion_dolar_fecha", "")
    return (float(valor) if valor else None, fecha or None)
