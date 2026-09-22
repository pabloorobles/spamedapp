"""Conexion SQLite, creacion de esquema, seed de listas y backups."""
from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from . import config

_conn: sqlite3.Connection | None = None

SEED_LISTAS: dict[str, list[str]] = {
    "moneda": ["PESOS", "DOLAR"],
    "concepto_ingreso": [
        "Sena Cliente", "Pago Cliente", "Saldo Cliente",
        "Comision de proveedor", "Ajuste a favor", "Otro ingreso",
    ],
    "concepto_egreso": [
        "Pago Proveedor", "Sueldos", "Comisiones", "Alquiler", "Luz",
        "Internet", "Publicidad", "Impuestos", "Devolucion a cliente",
        "Liquidacion de comision", "Otro gasto",
    ],
    "medio_pago": [
        "Efectivo", "Transferencia", "Deposito", "Tarjeta",
        "Mercado Pago", "Cheque",
    ],
    "canal": [
        "Familiar", "Amigo/Conocido", "Redes", "Calle", "Barrio",
        "Vendedor", "Instagram", "Facebook", "Google", "Otro",
    ],
    "tipo_proveedor": [
        "Mayorista", "Hotel", "Aerolinea", "Ferry", "Transporte",
        "Excursiones", "Asistencia", "Otro",
    ],
    "transporte": ["Aereo", "Bus", "Ferry", "Auto", "Tren", "Combinado"],
    "servicio": [
        "Aereo", "Alojamiento", "Traslados", "Excursiones", "Asistencia",
        "Crucero", "Alquiler de auto", "Paquete completo", "Otro",
    ],
    "canal_contacto": [
        "Llamada", "WhatsApp", "Email", "Visita", "Instagram", "Otro",
    ],
    "regimen": [
        "Solo alojamiento", "Desayuno", "Media pension",
        "Pension completa", "All inclusive",
    ],
    "motivo_cancelacion": [
        "Cambio de planes", "Problema economico",
        "Mejor oferta de la competencia", "Problema de salud", "Otro",
    ],
}

SEED_PARAMETROS = {
    "pct_sena": str(config.PCT_SENA_DEFAULT),
    "moneda_default": "PESOS",
    "nombre_agencia": "Spamed Travel",
    "prefijo_file": "R",
    "datos_agencia": "",
    "tema": "claro",
    "schema_version": "1",
    # Vacio = carpeta Descargas del usuario (ver config.dir_exports).
    "carpeta_exportaciones": "",
}


def conectar(ruta: Path | None = None) -> sqlite3.Connection:
    """Devuelve la conexion global, creandola e inicializandola si hace falta."""
    global _conn
    if _conn is not None:
        return _conn
    destino = Path(ruta) if ruta else config.ruta_db()
    destino.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(destino), check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.execute("PRAGMA journal_mode = WAL")
    inicializar(_conn)
    return _conn


def cerrar() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def _sql_esquema() -> str:
    """Devuelve el contenido de schema.sql, empaquetado o no.

    En modo congelado el archivo viaja en <_MEIPASS>/recursos. En desarrollo
    esta al lado de este modulo. Se prueban ambas rutas y, si ninguna existe,
    se falla con un mensaje que dice donde se busco.
    """
    candidatos = [
        Path(__file__).resolve().parent / "schema.sql",
        config.dir_recursos() / "schema.sql",
    ]
    if config.es_congelado():
        base = Path(getattr(sys, "_MEIPASS", ""))
        candidatos[:0] = [base / "recursos" / "schema.sql", base / "schema.sql"]
    for candidato in candidatos:
        if candidato.exists():
            return candidato.read_text(encoding="utf-8")
    rutas = "\n  ".join(str(c) for c in candidatos)
    raise FileNotFoundError(
        f"No se encontro schema.sql. Se busco en:\n  {rutas}")


def inicializar(con: sqlite3.Connection) -> None:
    con.executescript(_sql_esquema())
    _migrar(con)
    for clave, valor in SEED_PARAMETROS.items():
        con.execute(
            "INSERT OR IGNORE INTO parametros (clave, valor) VALUES (?, ?)",
            (clave, valor),
        )
    for tipo, valores in SEED_LISTAS.items():
        for orden, valor in enumerate(valores):
            con.execute(
                "INSERT OR IGNORE INTO listas (tipo, valor, orden) VALUES (?, ?, ?)",
                (tipo, valor, orden),
            )
    con.commit()


# Columnas agregadas despues de la v1. Se aplican solo si faltan.
MIGRACIONES: list[tuple[str, str, str]] = [
    ("reservas", "comision_pct", "REAL"),
    ("reservas", "comision_monto", "REAL"),
    ("reservas", "comision_prov_pct", "REAL"),
    ("reservas", "transfiere_neto", "INTEGER"),
    ("reservas", "devolucion", "REAL NOT NULL DEFAULT 0"),
    ("proveedores", "comision_pct", "REAL NOT NULL DEFAULT 0"),
    ("proveedores", "transfiere_neto", "INTEGER NOT NULL DEFAULT 1"),
    ("movimientos", "operacion", "TEXT"),
    ("movimientos", "cotizacion", "REAL"),
    ("vendedores", "fecha_nac", "TEXT"),
    ("reservas", "voucher_recibido", "TEXT"),
    # El ON DELETE CASCADE tiene que estar tambien aca, no solo en schema.sql:
    # si no, en una base migrada borrar un vendedor con documentacion fallaria
    # por la clave foranea, y en una base nueva funcionaria. Mismo esquema en
    # los dos casos.
    ("adjuntos", "vendedor_id",
     "INTEGER REFERENCES vendedores(id) ON DELETE CASCADE"),
    ("adjuntos", "movimiento_id",
     "INTEGER REFERENCES movimientos(id) ON DELETE CASCADE"),
    ("reservas", "tipo_viaje", "TEXT"),
    ("clientes", "dni_vencimiento", "TEXT"),
    ("gastos_fijos", "periodicidad", "TEXT NOT NULL DEFAULT 'Mensual'"),
    ("gastos_fijos", "fecha_inicio", "TEXT"),
    ("gastos_fijos", "fecha_fin", "TEXT"),
    ("gastos_fijos", "cantidad_cuotas", "INTEGER"),
    ("gastos_fijos", "cuotas_generadas", "INTEGER NOT NULL DEFAULT 0"),
]


def _migrar(con: sqlite3.Connection) -> None:
    """Agrega columnas nuevas a bases creadas con versiones anteriores.

    CREATE TABLE IF NOT EXISTS no toca tablas existentes, asi que los campos
    nuevos hay que sumarlos a mano. Al final se recrea la vista de saldos.
    """
    for tabla, columna, tipo in MIGRACIONES:
        existentes = {
            f["name"] for f in con.execute(f"PRAGMA table_info({tabla})")
        }
        if not existentes:  # la tabla todavia no existe
            continue
        if columna not in existentes:
            con.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
    # Indices sobre columnas migradas: van aca y no en schema.sql, porque ese
    # script corre completo antes que estas migraciones y la columna todavia
    # podria no existir.
    con.execute("CREATE INDEX IF NOT EXISTS ix_adj_vendedor "
                "ON adjuntos(vendedor_id)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_adj_movimiento "
                "ON adjuntos(movimiento_id)")
    # La vista se recrea siempre: su definicion cambia entre versiones y
    # CREATE VIEW IF NOT EXISTS no actualiza una vista que ya existe.
    con.execute("DROP VIEW IF EXISTS v_reservas_saldos")
    sql = _sql_esquema()
    inicio = sql.find("CREATE VIEW IF NOT EXISTS v_reservas_saldos")
    if inicio >= 0:
        con.executescript(sql[inicio:])
    con.commit()


# ---------------------------------------------------------------- utilidades

def query(sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
    return conectar().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
    return conectar().execute(sql, params).fetchone()


def execute(sql: str, params: tuple | dict = ()) -> int:
    con = conectar()
    cur = con.execute(sql, params)
    con.commit()
    return cur.lastrowid or cur.rowcount


def listas(tipo: str) -> list[str]:
    filas = query(
        "SELECT valor FROM listas WHERE tipo = ? ORDER BY orden, valor", (tipo,)
    )
    return [f["valor"] for f in filas]


def parametro(clave: str, defecto: str = "") -> str:
    fila = query_one("SELECT valor FROM parametros WHERE clave = ?", (clave,))
    return fila["valor"] if fila else defecto


def set_parametro(clave: str, valor: str) -> None:
    execute(
        "INSERT INTO parametros (clave, valor) VALUES (?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (clave, valor),
    )


def backup(destino: Path | None = None) -> Path:
    """Copia consistente de la base (usa la API de backup de SQLite)."""
    con = conectar()
    if destino is None:
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = config.dir_backups() / f"spamed_{marca}.db"
    destino.parent.mkdir(parents=True, exist_ok=True)
    otro = sqlite3.connect(str(destino))
    with otro:
        con.backup(otro)
    otro.close()
    return destino


def restaurar(origen: Path) -> None:
    """Reemplaza la base actual por un backup. Cierra la conexion global."""
    origen = Path(origen)
    if not origen.exists():
        raise FileNotFoundError(origen)
    backup()  # resguardo previo
    actual = config.ruta_db()
    cerrar()
    for sufijo in ("-wal", "-shm"):
        extra = Path(str(actual) + sufijo)
        if extra.exists():
            extra.unlink()
    shutil.copy2(origen, actual)
    conectar()
