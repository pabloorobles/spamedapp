"""Temas visuales de la aplicacion.

La paleta sale del Manual de Marca oficial de SpaMed Travel (v1.0, 2026):
los HEX son los que ese documento define para cada color, no una
aproximacion tomada del logo. Qt no soporta variables en QSS, asi que la
hoja de estilo se genera desde un diccionario: se define el color una sola
vez y de ahi salen las dos variantes (clara y oscura).
"""
from __future__ import annotations

from typing import Any

# --------------------------------------------------------- colores de marca
# HEX tal cual el Manual de Marca, seccion 04 - Sistema visual (paginas 17-18).
MARCA = {
    "azul_profundo":  "#2E2E8C",   # institucional: titulares, fondos plenos, logo
    "verde_petroleo": "#1E7A8C",   # secundario: barras, bloques de interfaz
    "naranja_sol":    "#F0A848",   # acento: botones, precios, destacados
    "arena":          "#F6F2EC",   # neutro calido: fondos de seccion
    "celeste_cielo":  "#1890C0",   # apoyo: salidas grupales, aereos
    "verde_palma":    "#6FA24B",   # apoyo: naturaleza, ecoturismo
    "fucsia_viaje":   "#D6317F",   # apoyo: salidas de mujeres, promociones
    "grafito":        "#16161F",   # texto largo, cuerpos de documento
}

CLARO: dict[str, str] = {
    "nombre":        "claro",
    # superficies
    "fondo":         MARCA["arena"],
    "superficie":    "#FFFFFF",
    "superficie_2":  "#EFE7D8",   # arena mas oscura: cabeceras suaves, barras
    "alterna":       "#F9F5EF",   # filas alternas de tabla
    "borde":         "#E3D9C6",
    "borde_fuerte":  "#CEBFA3",
    # texto
    "texto":         MARCA["grafito"],
    "texto_suave":   "#6B6B78",
    # marca
    "primario":      MARCA["azul_profundo"],
    "primario_alt":  "#3D3DA3",
    "primario_osc":  "#22226A",
    "acento":        MARCA["naranja_sol"],
    "acento_osc":    "#DB9636",
    "seleccion":     "#DCE0F5",
    "sobre_primario": "#FFFFFF",     # blanco sobre azul: combinacion aprobada
    # El manual aprueba "azul sobre naranja" y prohibe expresamente "blanco
    # sobre naranja" (paginas 17 y 19): el texto sobre un boton/fondo acento
    # siempre usa este color, no sobre_primario.
    "sobre_acento":  MARCA["azul_profundo"],
    # semanticos
    "ok":            MARCA["verde_palma"],
    "alerta":        "#CC8F3D",   # naranja sol oscurecido, distinto del acento
    "error":         "#B0403C",
    # barra lateral de navegacion: "secundario, barras" del manual = petroleo
    "nav":           MARCA["verde_petroleo"],
    "nav_alt":       "#28919F",
    "nav_texto":     "#D7ECEF",
    "nav_activo":    "#FFFFFF",
}

OSCURO: dict[str, str] = {
    "nombre":        "oscuro",
    # El fondo baja bastante para que las tarjetas se despeguen de verdad.
    "fondo":         "#0F1120",
    "superficie":    "#1B1F35",
    "superficie_2":  "#252A45",
    "alterna":       "#1F2439",
    "borde":         "#2F3552",
    "borde_fuerte":  "#414868",
    "texto":         "#E8E9F2",
    "texto_suave":   "#9AA0BF",
    "primario":      "#8489DA",   # azul profundo aclarado para que respire
    "primario_alt":  "#9AA0E8",
    "primario_osc":  "#5D62B0",
    "acento":        "#F5B565",   # naranja sol aclarado
    "acento_osc":    "#E0A050",
    "seleccion":     "#2C3358",
    "sobre_primario": "#FFFFFF",
    "sobre_acento":  MARCA["azul_profundo"],
    "ok":            "#8FC46E",
    "alerta":        "#E8B36B",
    "error":         "#E07A76",
    "nav":           "#0F2E34",   # petroleo oscurecido, no negro liso
    "nav_alt":       "#173F47",
    "nav_texto":     "#A9D3D9",
    "nav_activo":    "#FFFFFF",
}

# ------------------------------------------------------- colores de estado
# Se usan los colores de apoyo del manual donde el significado lo permite.
# 'Cancelado' queda fuera de la paleta a proposito: rojo es la unica lectura
# clara, y el propio manual reserva el resto de los colores para otros usos.
ESTADOS_CLARO: dict[str, str] = {
    "Cotizado":   "#7C819E",
    "Reservado":  MARCA["celeste_cielo"],
    "Confirmado": MARCA["verde_palma"],
    "Emitido":    MARCA["verde_petroleo"],
    "En Viaje":   MARCA["azul_profundo"],
    "Finalizado": "#6B7280",
    "Vencido":    MARCA["naranja_sol"],
    "Cancelado":  "#B0403C",
}

ESTADOS_OSCURO: dict[str, str] = {
    "Cotizado":   "#9AA0BF",
    "Reservado":  "#4FB4DE",
    "Confirmado": "#8FC46E",
    "Emitido":    "#3FA6B8",
    "En Viaje":   "#8489DA",
    "Finalizado": "#8A90AB",
    "Vencido":    "#F5B565",
    "Cancelado":  "#E07A76",
}


def paleta(nombre: str) -> dict[str, str]:
    return OSCURO if str(nombre).lower() == "oscuro" else CLARO


def estados(nombre: str) -> dict[str, str]:
    return ESTADOS_OSCURO if str(nombre).lower() == "oscuro" else ESTADOS_CLARO


def color_fila_alerta(nombre: str) -> str:
    return paleta(nombre)["alerta"]


def color_ingreso(nombre: str) -> str:
    return paleta(nombre)["ok"]


def color_egreso(nombre: str) -> str:
    return paleta(nombre)["error"]


def color_apagado(nombre: str) -> str:
    return paleta(nombre)["texto_suave"]


# ------------------------------------------------------------------ QSS
# Tipografia del Manual de Marca: Outfit para titulares, Instrument Sans
# para texto de cuerpo. Los archivos van en recursos/fuentes/ y se cargan en
# app.py; si todavia no estan (o la instalacion no los tiene), Qt sigue la
# lista y cae en una fuente de sistema — el mismo mecanismo de "alternativa
# de sistema" que el propio manual describe para Word y mail.
FUENTE_TEXTO = '"Instrument Sans", "Segoe UI", Verdana, Arial'
FUENTE_TITULOS = '"Outfit", "Segoe UI Variable Display", Verdana, Arial'

_PLANTILLA = """
/* Spamed Travel - tema {nombre} (generado desde core/tema.py) */

QWidget {{
    font-family: {fuente_texto};
    font-size: 9.5pt;
    color: {texto};
}}

QMainWindow, QDialog {{ background: {fondo}; }}
QScrollArea {{ background: {fondo}; border: none; }}
QScrollArea > QWidget > QWidget {{ background: {fondo}; }}
QWidget#lienzo {{ background: {fondo}; }}
QStackedWidget {{ background: {fondo}; }}

/* ------------------------------------------------ barra de navegacion */
QFrame#nav {{
    background: {nav};
    border: none;
    border-top-right-radius: 22px;
    border-bottom-right-radius: 22px;
}}
QLabel#navMarca {{
    color: {nav_activo};
    font-family: {fuente_titulos};
    font-size: 11pt;
    font-weight: 700;
}}
QPushButton#navToggle {{
    background: transparent;
    color: {nav_texto};
    border: 1px solid transparent;
    border-radius: 9px;
    font-family: {fuente_titulos};
    font-size: 13pt;
    font-weight: 700;
    min-width: 30px;
    max-width: 30px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
}}
QPushButton#navToggle:hover {{ background: {nav_alt}; color: {nav_activo}; }}
QLabel#navSeccion {{
    color: {nav_texto};
    font-family: {fuente_titulos};
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 4px 14px 2px 14px;
}}
QPushButton#navItem {{
    background: transparent;
    color: {nav_texto};
    border: none;
    border-radius: 12px;
    padding: 11px 14px;
    text-align: left;
    font-size: 10pt;
    font-weight: 500;
}}
QPushButton#navItem:hover {{ background: {nav_alt}; color: {nav_activo}; }}
QPushButton#navItem:checked {{
    background: {nav_alt};
    color: {nav_activo};
    font-weight: 700;
    border-left: 3px solid {acento};
}}

/* --------------------------------------------------------- cabeceras */
QLabel#tituloPagina {{
    font-family: {fuente_titulos};
    font-size: 19pt;
    font-weight: 700;
    color: {texto};
}}
QLabel#bajadaPagina {{ color: {texto_suave}; font-size: 9.5pt; }}
QLabel#titulo {{
    font-family: {fuente_titulos};
    font-size: 15pt;
    font-weight: 700;
    color: {primario};
}}
QLabel#marca {{
    font-family: {fuente_titulos};
    color: {primario};
    font-size: 12pt;
    font-weight: 700;
}}

/* ------------------------------------------------------------- cajas */
QGroupBox {{
    background: {superficie};
    border: 1px solid {borde};
    border-radius: 18px;
    margin-top: 18px;
    padding: 16px 14px 14px 14px;
    font-weight: 600;
    color: {texto_suave};
    font-size: 8.5pt;
    letter-spacing: 0.6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 18px;
    padding: 0 8px;
    color: {texto_suave};
}}

QFrame#tarjeta {{
    background: {superficie};
    border: 1px solid {borde};
    border-radius: 18px;
}}
QFrame#panel {{
    background: {superficie};
    border: 1px solid {borde};
    border-radius: 18px;
}}
QFrame#separador {{ color: {borde}; }}

QLabel#tarjetaTitulo {{
    color: {texto_suave};
    font-family: {fuente_titulos};
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.9px;
    text-transform: uppercase;
}}
QLabel#tarjetaDetalle {{ color: {texto_suave}; font-size: 8.5pt; }}
QLabel#totales {{
    color: {texto};
    background: {superficie_2};
    border: 1px solid {borde};
    border-radius: 14px;
    padding: 10px 16px;
    font-weight: 600;
}}
QLabel#vacio {{ color: {texto_suave}; font-size: 10.5pt; }}

/* ----------------------------------------------------------- botones */
QPushButton {{
    background: {superficie};
    border: 1px solid {borde_fuerte};
    border-radius: 12px;
    padding: 9px 18px;
    font-weight: 500;
}}
QPushButton:hover  {{ background: {seleccion}; border-color: {primario}; }}
QPushButton:pressed {{ background: {superficie_2}; }}
QPushButton:disabled {{ color: {texto_suave}; background: {superficie_2};
                        border-color: {borde}; }}

QPushButton#primario {{
    background: {primario};
    color: {sobre_primario};
    border: 1px solid {primario};
    border-radius: 12px;
    font-weight: 600;
}}
QPushButton#primario:hover   {{ background: {primario_alt};
                                border-color: {primario_alt}; }}
QPushButton#primario:pressed {{ background: {primario_osc}; }}

QPushButton#acento {{
    background: {acento};
    color: {sobre_acento};
    border: 1px solid {acento};
    border-radius: 12px;
    font-weight: 600;
}}
QPushButton#acento:hover {{ background: {acento_osc}; }}

/* Boton "+" de los combos: cuadrado y sin relleno lateral, si no el
   simbolo queda recortado por el padding general de los botones. */
QPushButton#mas {{
    background: transparent;
    border: 1px solid {borde_fuerte};
    color: {primario};
    border-radius: 10px;
    padding: 0px;
    font-size: 14pt;
    font-weight: 700;
    min-width: 36px;
    min-height: 30px;
}}
QPushButton#mas:hover {{
    background: {acento};
    border-color: {acento};
    color: {sobre_acento};
}}

QPushButton#suave {{
    background: transparent;
    border: 1px solid {borde};
    color: {texto_suave};
    border-radius: 12px;
}}
QPushButton#suave:hover {{ color: {primario}; border-color: {primario};
                           background: {seleccion}; }}

/* ------------------------------------------------------------ campos */
QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QPlainTextEdit,
QTextEdit {{
    background: {superficie};
    border: 1px solid {borde_fuerte};
    border-radius: 12px;
    padding: 8px 12px;
    selection-background-color: {primario};
    selection-color: {sobre_primario};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus,
QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px solid {acento};
    padding: 7px 11px;
}}
QLineEdit:disabled, QComboBox:disabled {{
    background: {superficie_2}; color: {texto_suave};
}}
QLineEdit#busqueda {{ border-radius: 14px; padding: 9px 16px; }}

QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {superficie};
    color: {texto};
    border: 1px solid {borde};
    border-radius: 12px;
    selection-background-color: {seleccion};
    selection-color: {texto};
    outline: none;
    padding: 5px;
}}
QComboBox QAbstractItemView::item {{
    color: {texto};
    min-height: 22px;
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {borde_fuerte};
    border-radius: 5px;
    background: {superficie};
}}
QCheckBox::indicator:checked {{ background: {acento}; border-color: {acento}; }}

/* ------------------------------------------------------------ tablas */
QTableWidget, QTableView {{
    background: {superficie};
    alternate-background-color: {alterna};
    gridline-color: {borde};
    border: 1px solid {borde};
    border-radius: 16px;
    selection-background-color: {seleccion};
    selection-color: {texto};
    outline: none;
}}
QTableWidget::item, QTableView::item {{ padding: 7px 5px; }}

QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {superficie_2};
    color: {texto_suave};
    padding: 10px 10px;
    border: none;
    border-bottom: 2px solid {borde};
    font-weight: 700;
    font-size: 8.5pt;
    letter-spacing: 0.4px;
}}
QHeaderView::section:first {{ border-top-left-radius: 15px; }}
QHeaderView::section:last  {{ border-top-right-radius: 15px; }}
QTableCornerButton::section {{ background: {superficie_2}; border: none; }}

/* ------------------------------------------------------------ varios */
QStatusBar {{ background: transparent; color: {texto_suave}; border: none; }}
QStatusBar::item {{ border: none; }}

QTabWidget::pane {{
    border: 1px solid {borde};
    background: {superficie};
    border-radius: 16px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {texto_suave};
    padding: 10px 22px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}}
QTabBar::tab:hover {{ color: {primario}; }}
QTabBar::tab:selected {{
    color: {primario};
    font-weight: 700;
    border-bottom: 2px solid {acento};
}}

QScrollBar:vertical   {{ background: transparent; width: 12px; margin: 3px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 3px; }}
QScrollBar::handle {{ background: {borde_fuerte}; border-radius: 6px;
                      min-height: 34px; min-width: 34px; }}
QScrollBar::handle:hover {{ background: {primario}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {superficie_2};
    color: {texto};
    border: 1px solid {borde};
    border-radius: 8px;
    padding: 6px 10px;
}}

QMessageBox {{ background: {fondo}; }}
"""


def qss(nombre: str = "claro") -> str:
    """Devuelve la hoja de estilo completa para el tema pedido."""
    return _PLANTILLA.format(
        **paleta(nombre),
        fuente_texto=FUENTE_TEXTO,
        fuente_titulos=FUENTE_TITULOS,
    )


# ------------------------------------------------------------------ Web
# Tercera salida del mismo diccionario de colores/fuentes que ya alimenta
# el QSS de arriba y el CSS de los PDFs (core/documentos.py): variables
# CSS para las pantallas migradas a HTML/CSS/JS (ver MIGRACION_WEB.md).
# Los tres mundos leen de MARCA/CLARO/OSCURO/ESTADOS_* y no se pueden
# desincronizar entre si.
#
# Sigue el patron de temas de tres estados que exige un tema claro/oscuro
# bien hecho en la web: :root (claro, sin marcar) es el que ve la mayoria
# de los navegadores con el sistema en modo claro o sin preferencia;
# @media(prefers-color-scheme:dark) cubre el sistema en oscuro, pero
# queda anulado si hay una eleccion explicita a claro (":not([data-theme=
# light])"); y el selector [data-theme] gana siempre que la propia pagina
# fuerza un tema (el boton de modo claro/oscuro del piloto de Inicio).

def _slug(nombre: str) -> str:
    return nombre.lower().replace(" ", "-").replace("_", "-")


def _variables(paleta_: dict[str, str], estados_: dict[str, str]) -> str:
    lineas = [f"    --{_slug(k)}: {v};" for k, v in paleta_.items()
              if k != "nombre"]
    lineas += [f"    --estado-{_slug(k)}: {v};" for k, v in estados_.items()]
    return "\n".join(lineas)


def tokens_css() -> str:
    """Variables CSS (:root) para las paginas web embebidas."""
    # color-scheme le dice a Chromium con que paleta dibujar lo que el CSS
    # de la pagina no puede tocar (el desplegable nativo de un <select>, el
    # calendario de un <input type=date>). Sin esto sigue el color-scheme
    # del sistema operativo, no el data-theme de la app: si el SO esta en
    # claro y la app en oscuro, esos popups nativos salian blancos --
    # "cajas blancas atras de los desplegables" -- sin importar el resto
    # de la paleta. Mismo patron de tres estados que el resto del archivo.
    return f"""/* Spamed Travel - variables de marca (generado desde core/tema.py) */

:root {{
    color-scheme: light;
{_variables(CLARO, ESTADOS_CLARO)}
    --fuente-texto: {FUENTE_TEXTO};
    --fuente-titulos: {FUENTE_TITULOS};
    --sombra-1: 0 1px 2px rgba(30,20,10,.05);
    --sombra-2: 0 12px 28px -14px rgba(30,20,10,.22);
    --sombra-3: 0 24px 48px -18px rgba(30,20,10,.32);
}}

@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
{_variables(OSCURO, ESTADOS_OSCURO)}
    --sombra-1: 0 1px 2px rgba(0,0,0,.3);
    --sombra-2: 0 14px 32px -16px rgba(0,0,0,.55);
    --sombra-3: 0 28px 56px -20px rgba(0,0,0,.65);
  }}
}}

:root[data-theme="dark"] {{
    color-scheme: dark;
{_variables(OSCURO, ESTADOS_OSCURO)}
    --sombra-1: 0 1px 2px rgba(0,0,0,.3);
    --sombra-2: 0 14px 32px -16px rgba(0,0,0,.55);
    --sombra-3: 0 28px 56px -20px rgba(0,0,0,.65);
}}
"""
