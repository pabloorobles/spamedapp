"""Reglas de negocio: derivacion de estados, alertas y formateo."""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from typing import Any, Mapping

TOLERANCIA = 0.01  # pesos/dolares: por debajo de esto se considera saldado


# ------------------------------------------------------------------ fechas

def a_fecha(valor: Any) -> date | None:
    """Convierte texto ISO / datetime / date a date. None si no se puede."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto[:19], fmt).date()
        except ValueError:
            continue
    return None


def iso(valor: Any) -> str | None:
    f = a_fecha(valor)
    return f.isoformat() if f else None


def dd_mm_yyyy(valor: Any) -> str:
    f = a_fecha(valor)
    return f.strftime("%d/%m/%Y") if f else ""


def dias_hasta(valor: Any, hoy: date | None = None) -> int | None:
    f = a_fecha(valor)
    if f is None:
        return None
    return (f - (hoy or date.today())).days


def dias_a_cumple(fecha_nac: Any, hoy: date | None = None) -> int | None:
    """Dias hasta el proximo cumpleanos, ignorando el anio de nacimiento."""
    f = a_fecha(fecha_nac)
    if f is None:
        return None
    hoy = hoy or date.today()
    try:
        proximo = f.replace(year=hoy.year)
    except ValueError:  # 29 de febrero en un anio no bisiesto
        proximo = f.replace(year=hoy.year, day=28)
    if proximo < hoy:
        try:
            proximo = proximo.replace(year=hoy.year + 1)
        except ValueError:
            proximo = proximo.replace(year=hoy.year + 1, day=28)
    return (proximo - hoy).days


def fin_de_mes_tarjeta(texto: Any) -> date | None:
    """Convierte 'MM/AA' o 'MM/AAAA' (como figura impreso en una tarjeta) al
    ultimo dia de ese mes. None si el texto no tiene ese formato."""
    m = re.match(r"^\s*(\d{1,2})\s*/\s*(\d{2}|\d{4})\s*$", str(texto or ""))
    if not m:
        return None
    mes, anio = int(m.group(1)), int(m.group(2))
    if anio < 100:
        anio += 2000
    if not 1 <= mes <= 12:
        return None
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, ultimo_dia)


# ------------------------------------------------------------------ estados

def estado_reserva(r: Mapping[str, Any], pct_sena: float = 20.0,
                   hoy: date | None = None) -> str:
    """Deriva el estado del file a partir de cobros, pagos y fechas.

    Prioridad: Cancelado > Finalizado > En Viaje > Emitido > Confirmado >
               Vencido > Reservado > Cotizado

    Cadena acordada en la Etapa 2 del rediseño (ver REDISENO.md):
      Reservado  = el cliente dijo que si (fecha_reserva cargada), sin haber
                   pagado nada todavia. Reutiliza 'fecha_reserva', que antes
                   no intervenia en el calculo del estado.
      Confirmado = se cobro la sena (esto es lo que ANTES se llamaba
                   'Reservado': cobrado >= % de sena configurado).
      Vencido    = vencio el plazo de reserva sin llegar a pagar la sena.
                   Pasa por ENCIMA de Reservado a proposito: haber dicho que
                   si no protege del vencimiento si no hay plata en juego.
      Emitido    = esta TODO pagado -- cliente Y proveedor, las dos puntas
                   (antes 'Confirmado' solo miraba el lado del cliente).
                   'voucher_recibido' (del operador a la agencia) NO mueve
                   el estado: es un dato operativo dentro de Emitido, para
                   saber a cuales todavia les falta el voucher. La vieja
                   'fecha_entrega_voucher' (al cliente) ya no participa del
                   calculo, queda como dato informativo nomas.
    """
    hoy = hoy or date.today()

    if int(r.get("cancelada") or 0):
        return "Cancelado"

    importe = float(r.get("importe_cliente") or 0)
    cobrado = float(r.get("cobrado_cliente") or 0)
    saldo_cli = float(r.get("saldo_cliente") or 0)
    saldo_prov = float(r.get("saldo_proveedor") or 0)

    f_salida = a_fecha(r.get("fecha_salida"))
    f_regreso = a_fecha(r.get("fecha_regreso"))
    f_vto_res = a_fecha(r.get("fecha_vto_reserva"))
    aprobado = a_fecha(r.get("fecha_reserva")) is not None

    if f_regreso and f_regreso < hoy:
        return "Finalizado"
    if f_salida and f_salida <= hoy and (f_regreso is None or f_regreso >= hoy):
        return "En Viaje"
    if importe > 0 and saldo_cli <= TOLERANCIA and saldo_prov <= TOLERANCIA:
        return "Emitido"
    if importe > 0 and cobrado >= importe * pct_sena / 100.0 and cobrado > 0:
        return "Confirmado"
    if f_vto_res and f_vto_res < hoy:
        return "Vencido"
    if aprobado:
        return "Reservado"
    return "Cotizado"


def resumen_pipeline(conteo_por_estado: Mapping[str, int]) -> dict[str, int]:
    """Colapsa un conteo por estado (8 valores) a 3: en curso, finalizados
    y cancelados. 'En curso' es todo lo que todavia puede seguir avanzando
    (Cotizado, Reservado, Vencido, Confirmado, Emitido, En Viaje); Finalizado
    y Cancelado son los dos unicos estados terminales."""
    finalizados = int(conteo_por_estado.get("Finalizado", 0))
    cancelados = int(conteo_por_estado.get("Cancelado", 0))
    en_curso = sum(
        n for estado, n in conteo_por_estado.items()
        if estado not in ("Finalizado", "Cancelado")
    )
    return {"en_curso": en_curso, "finalizados": finalizados,
            "cancelados": cancelados}


def alertas(r: Mapping[str, Any], hoy: date | None = None,
            ventana: int = 7) -> list[str]:
    """Avisos operativos para el file (vencimientos y saldos)."""
    hoy = hoy or date.today()
    avisos: list[str] = []
    if int(r.get("cancelada") or 0):
        return avisos

    saldo_cli = float(r.get("saldo_cliente") or 0)
    saldo_prov = float(r.get("saldo_proveedor") or 0)
    cobrado = float(r.get("cobrado_cliente") or 0)

    d_sena = dias_hasta(r.get("fecha_vto_sena"), hoy)
    if d_sena is not None and cobrado <= TOLERANCIA:
        if d_sena < 0:
            avisos.append(f"Sena vencida hace {abs(d_sena)} dia(s)")
        elif d_sena <= ventana:
            avisos.append(f"Vence la sena en {d_sena} dia(s)")

    d_res = dias_hasta(r.get("fecha_vto_reserva"), hoy)
    if d_res is not None and saldo_cli > TOLERANCIA:
        if d_res < 0:
            avisos.append(f"Reserva vencida hace {abs(d_res)} dia(s)")
        elif d_res <= ventana:
            avisos.append(f"Vence la reserva en {d_res} dia(s)")

    d_sal = dias_hasta(r.get("fecha_salida"), hoy)
    if d_sal is not None and 0 <= d_sal <= ventana and saldo_prov > TOLERANCIA:
        avisos.append(f"Sale en {d_sal} dia(s) y falta pagar al proveedor")
    if (d_sal is not None and 0 <= d_sal <= ventana
            and not r.get("voucher_recibido")):
        avisos.append(f"Sale en {d_sal} dia(s) y no llego el voucher del operador")

    if saldo_cli < -TOLERANCIA:
        avisos.append("El cliente pago de mas")
    if saldo_prov < -TOLERANCIA:
        avisos.append("Se pago de mas al proveedor")
    return avisos


def porcentaje_cobrado(r: Mapping[str, Any]) -> float:
    importe = float(r.get("importe_cliente") or 0)
    if importe <= 0:
        return 0.0
    return round(float(r.get("cobrado_cliente") or 0) / importe * 100, 1)


# ------------------------------------------------------------------ formato

def money(valor: Any, moneda: str = "") -> str:
    """Formato argentino: 1.234.567,89"""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        return ""
    texto = f"{n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    simbolo = {"PESOS": "$", "DOLAR": "US$"}.get(moneda.upper(), "")
    return f"{simbolo} {texto}".strip()


def pct(valor: Any) -> str:
    try:
        return f"{float(valor or 0):.1f}%"
    except (TypeError, ValueError):
        return ""


def siguiente_file(ultimo: str | None, prefijo: str = "R") -> str:
    """Genera el proximo numero de file: R2601 -> R2602."""
    anio = date.today().strftime("%y")
    if ultimo:
        digitos = "".join(c for c in ultimo if c.isdigit())
        if digitos:
            try:
                return f"{prefijo}{int(digitos) + 1}"
            except ValueError:
                pass
    return f"{prefijo}{anio}01"
