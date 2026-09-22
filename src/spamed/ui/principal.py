"""Ventana principal: navegacion lateral, paginas y acciones por boton."""
from __future__ import annotations

from pathlib import Path

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QStackedWidget, QVBoxLayout, QWidget,
)

from ..core import config, db, importador
from .ajustes import VistaCajaGastos, VistaConfiguracion
from .caja import VistaCaja
from .cierre import VistaCierre
from .comunes import aviso, boton, confirmar, error
from .herramientas import VistaHerramientas
from .maestros import VistaClientes, VistaProveedores, VistaVendedores
from .navegacion import BarraLateral
from .puentes import (
    PuenteAjustes, PuenteCaja, PuenteCajaGastos, PuenteCierre,
    PuenteClientes, PuenteHerramientas, PuenteInicio, PuenteProveedores,
    PuenteReportes, PuenteVendedores,
)
from .reservas import VistaReservas
from .tablero import VistaReportes, VistaTablero


class DialogoConfiguracion(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self.agencia = QLineEdit(db.parametro("nombre_agencia", "Spamed Travel"))
        self.pct = QDoubleSpinBox()
        self.pct.setRange(0, 100)
        self.pct.setSuffix(" %")
        self.pct.setValue(float(db.parametro("pct_sena", "20") or 20))
        self.prefijo = QLineEdit(db.parametro("prefijo_file", "R"))
        self.datos = QLineEdit(db.parametro("datos_agencia", ""))
        self.datos.setPlaceholderText(
            "Dirección · Tel. · Legajo EVT · CUIT (sale en vouchers y recibos)")

        self.carpeta = QLineEdit(db.parametro("carpeta_exportaciones", ""))
        self.carpeta.setPlaceholderText(str(config.dir_descargas()))
        fila_carpeta = QWidget()
        lay_carpeta = QHBoxLayout(fila_carpeta)
        lay_carpeta.setContentsMargins(0, 0, 0, 0)
        lay_carpeta.setSpacing(6)
        lay_carpeta.addWidget(self.carpeta, 1)
        lay_carpeta.addWidget(boton("Examinar…", self.elegir_carpeta))

        form.addRow("Nombre de la agencia", self.agencia)
        form.addRow("% mínimo para 'Reservado'", self.pct)
        form.addRow("Prefijo de file", self.prefijo)
        form.addRow("Datos para documentos", self.datos)
        form.addRow("Carpeta de exportaciones", fila_carpeta)
        lay.addLayout(form)

        nota = QLabel(
            "Ahí van los PDF y las exportaciones a Excel. Si lo dejás vacío, "
            "se usa la carpeta Descargas. Las copias de seguridad no se "
            "guardan acá: van siempre a la carpeta de datos de la aplicación.")
        nota.setObjectName("tarjetaDetalle")
        nota.setWordWrap(True)
        lay.addWidget(nota)

        info = QLabel(f"Base de datos:\n{config.ruta_db()}")
        info.setWordWrap(True)
        info.setObjectName("tarjetaDetalle")
        lay.addWidget(info)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.guardar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def elegir_carpeta(self) -> None:
        inicial = self.carpeta.text().strip() or str(config.dir_descargas())
        elegida = QFileDialog.getExistingDirectory(
            self, "Carpeta para PDF y exportaciones", inicial)
        if elegida:
            self.carpeta.setText(elegida)

    def guardar(self) -> None:
        db.set_parametro("nombre_agencia", self.agencia.text().strip())
        db.set_parametro("pct_sena", str(self.pct.value()))
        db.set_parametro("prefijo_file", self.prefijo.text().strip() or "R")
        db.set_parametro("datos_agencia", self.datos.text().strip())
        db.set_parametro("carpeta_exportaciones", self.carpeta.text().strip())
        self.accept()


class DialogoDiagnostico(QDialog):
    """Estado de la instalación y últimos errores, para pasarlo a soporte.

    Es la única cosa de la aplicación con atajo de teclado (Ctrl+Shift+D), y
    a propósito: no forma parte de la operación diaria, es la herramienta
    para cuando algo falla. Ver la nota en CLAUDE.md.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diagnóstico")
        self.setMinimumSize(760, 560)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)

        titulo = QLabel("Información técnica")
        titulo.setStyleSheet("font-weight: 700; font-size: 12pt;")
        lay.addWidget(titulo)
        detalle = QLabel(
            "Si algo falla, copiá todo esto y pasámelo: dice qué versión "
            "corre, dónde está la base y qué error se registró último.")
        detalle.setObjectName("tarjetaDetalle")
        detalle.setWordWrap(True)
        lay.addWidget(detalle)

        self.texto = QPlainTextEdit()
        self.texto.setReadOnly(True)
        self.texto.setStyleSheet("font-family: Consolas, monospace;")
        self.texto.setPlainText(self._informe())
        lay.addWidget(self.texto)

        barra = QHBoxLayout()
        barra.addWidget(boton("Copiar todo", self.copiar, primario=True))
        barra.addWidget(boton("Abrir carpeta de datos", self.abrir_carpeta))
        # Etapa 0 de MIGRACION_WEB.md: humo para confirmar que
        # PySide6-Addons quedo bien instalado antes de migrar una
        # pantalla de verdad. Sacar este boton en cuanto la Etapa 1 tenga
        # su propia pantalla (ya no hace falta un lugar aparte para
        # probar el plomero).
        barra.addWidget(boton("Probar pantallas web (beta)", self.probar_web))
        barra.addStretch(1)
        lay.addLayout(barra)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        bb.rejected.connect(self.accept)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)

    def _informe(self) -> str:
        import platform

        from PySide6 import __version__ as version_pyside

        lineas = [
            f"{config.APP_NAME} {config.APP_VERSION}",
            f"Empaquetado: {'si' if config.es_congelado() else 'no (desarrollo)'}",
            f"Python: {sys.version.split()[0]}   PySide6: {version_pyside}",
            f"Sistema: {platform.platform()}",
            "",
            f"Base de datos: {config.ruta_db()}",
            f"Carpeta de datos: {config.dir_datos()}",
            f"Exportaciones: {config.dir_exports()}",
            f"Copias de seguridad: {config.dir_backups()}",
            f"Tema: {db.parametro('tema', 'claro')}",
            "",
            "Registros cargados:",
        ]

        tablas = ("clientes", "vendedores", "proveedores", "reservas",
                  "movimientos", "reserva_servicios", "pasajeros", "cuotas",
                  "adjuntos", "cierres", "liquidaciones")
        for tabla in tablas:
            try:
                fila = db.query_one(f"SELECT COUNT(*) n FROM {tabla}")
                lineas.append(f"   {tabla:20} {fila['n']}")
            except Exception as e:  # noqa: BLE001
                lineas.append(f"   {tabla:20} error: {e}")

        try:
            copias = sorted(config.dir_backups().glob("*.db"))
            lineas.append(f"\nCopias de seguridad guardadas: {len(copias)}")
            if copias:
                lineas.append(f"   la más reciente: {copias[-1].name}")
        except Exception:  # noqa: BLE001
            pass

        lineas.append("\n" + "-" * 60)
        registro = config.dir_datos() / "errores.log"
        if registro.exists():
            texto = registro.read_text(encoding="utf-8", errors="replace")
            # Solo la cola: el archivo puede tener meses de historial.
            cola = texto[-6000:]
            lineas.append(f"Últimos errores ({registro}):")
            lineas.append(cola if len(texto) <= 6000
                          else "[...]\n" + cola)
        else:
            lineas.append("No hay errores registrados. 👌")
        return "\n".join(lineas)

    def copiar(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.clipboard().setText(self.texto.toPlainText())
            aviso(self, "Copiado. Ya lo podés pegar donde lo necesites.")

    def probar_web(self) -> None:
        """Ver MIGRACION_WEB.md, Etapa 0."""
        try:
            from .web import PuenteHumo, VistaWeb
        except ImportError:
            error(self, "Todavía no está instalado PySide6-Addons (hace "
                        "falta para las pantallas nuevas en HTML/CSS/JS).\n\n"
                        "Corré en una consola, en la carpeta del proyecto:\n"
                        "pip install -r requirements.txt\n\n"
                        "y volvé a abrir la app.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Humo — pantallas web (Etapa 0)")
        dlg.resize(760, 560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        puente = PuenteHumo(dlg)
        vista = VistaWeb("humo/index.html", puente, dlg)
        lay.addWidget(vista)
        dlg.exec()

    def abrir_carpeta(self) -> None:
        import os
        try:
            os.startfile(str(config.dir_datos()))  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            aviso(self, str(config.dir_datos()))


class VentanaPrincipal(QMainWindow):

    PAGINAS = (
        ("Inicio",      "Situación general del negocio"),
        ("Reservas",    "Todos los files y su estado"),
        ("Caja",        "Ingresos, egresos y cambio de moneda"),
        ("Clientes",    "Quiénes compran"),
        ("Vendedores",  "El equipo y sus comisiones"),
        ("Operadores", "Mayoristas y prestadores"),
        ("Reportes",    "Cobros, pagos, comisiones y más"),
        ("Cierre",      "Estado del mes y cierre contable"),
        ("Caja y gastos", "Gastos fijos, extraordinarios y arqueos"),
        ("Ajustes",     "Listas desplegables"),
        ("Herramientas", "Datos, copias y preferencias"),
    )

    # Iconos de recursos/iconos/, en el mismo orden que PAGINAS.
    ICONOS = (
        "inicio", "reservas", "caja", "clientes", "vendedores",
        "operadores", "reportes", "cierre", "caja_gastos", "ajustes",
        "herramientas",
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} — Gestión de agencia")
        self.resize(1420, 880)
        self.setMinimumSize(1120, 700)

        from ..app import recurso
        ico = recurso("spamed.ico")
        if ico:
            self.setWindowIcon(QIcon(str(ico)))

        # ------------------------------------------------------- vistas
        self.tablero = self._crear_inicio()
        self.reservas = VistaReservas()
        self.caja = self._crear_caja()
        self.clientes = self._crear_clientes()
        self.vendedores = self._crear_vendedores()
        self.proveedores = self._crear_proveedores()
        self.reportes = self._crear_reportes()
        self.cierre = self._crear_cierre()
        self.caja_gastos = self._crear_caja_gastos()
        self.ajustes = self._crear_ajustes()
        self.herramientas = self._crear_herramientas()

        self.vistas = [
            self.tablero, self.reservas, self.caja, self.clientes,
            self.vendedores, self.proveedores, self.reportes,
            self.cierre, self.caja_gastos, self.ajustes, self.herramientas,
        ]

        self.paginas = QStackedWidget()
        for v in self.vistas:
            self.paginas.addWidget(v)

        # -------------------------------------------------- navegacion
        self.nav = BarraLateral()
        self.nav.seccion("Operación")
        for (nombre, _), icono in zip(self.PAGINAS[:3], self.ICONOS[:3]):
            self.nav.item(nombre, icono=icono)
        self.nav.seccion("Maestros")
        for (nombre, _), icono in zip(self.PAGINAS[3:6], self.ICONOS[3:6]):
            self.nav.item(nombre, icono=icono)
        self.nav.seccion("Análisis")
        self.nav.item("Reportes", icono=self.ICONOS[6])
        self.nav.item("Cierre contable", icono=self.ICONOS[7])
        self.nav.espacio()
        self.nav.item("Caja y gastos", icono=self.ICONOS[8])
        self.nav.item("Ajustes", icono=self.ICONOS[9])
        self.nav.item("Herramientas", icono=self.ICONOS[10])
        self.nav.navegar.connect(self.ir_a)

        # ------------------------------------------------------ layout
        central = QWidget()
        central.setObjectName("lienzo")
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.nav)

        derecha = QWidget()
        derecha.setObjectName("lienzo")
        lay_der = QVBoxLayout(derecha)
        lay_der.setContentsMargins(24, 20, 24, 12)
        lay_der.addWidget(self.paginas)
        lay.addWidget(derecha, 1)
        self.setCentralWidget(central)

        self.reservas.cambio_datos.connect(self.refrescar_todo)
        # Caja: el signal esta en el puente cuando es la version web (la
        # propia VistaWeb no tiene cambio_datos), o en la vista misma si
        # se cayo a la version de Qt (ver _crear_caja()).
        if hasattr(self, "puente_caja"):
            self.puente_caja.cambio_datos.connect(self.refrescar_todo)
        else:
            self.caja.cambio_datos.connect(self.refrescar_todo)
        if hasattr(self, "puente_cierre"):
            self.puente_cierre.cambio_datos.connect(self.refrescar_todo)
        else:
            self.cierre.cambio_datos.connect(self.refrescar_todo)
        if hasattr(self, "puente_clientes"):
            self.puente_clientes.cambio_datos.connect(self.refrescar_todo)
        else:
            self.clientes.cambio_datos.connect(self.refrescar_todo)
        if hasattr(self, "puente_caja_gastos"):
            self.puente_caja_gastos.cambio_datos.connect(self.refrescar_todo)
        else:
            self.caja_gastos.cambio_datos.connect(self.refrescar_todo)

        # Unico atajo de teclado de la aplicacion, y a proposito: no es una
        # accion de la operacion diaria (esa va siempre por boton visible),
        # es la herramienta para cuando algo falla. Tambien esta como boton
        # en Herramientas, asi que no hay nada que dependa solo del teclado.
        self.atajo_diag = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        self.atajo_diag.activated.connect(self.diagnostico)

        self.statusBar().showMessage(f"Base de datos: {config.ruta_db()}")
        self.aplicar_marca()
        self.ir_a(0)
        self.refrescar_todo()

    def _crear_inicio(self) -> QWidget:
        """Inicio: primera pantalla migrada a HTML/CSS/JS (ver
        MIGRACION_WEB.md, Etapa 1). Si PySide6-Addons no esta instalado
        -no deberia pasar, es una dependencia obligatoria desde esta
        etapa, pero una base vieja sin reinstalar no tiene por que
        romperse del todo- se cae a la version en Qt en vez de no poder
        abrir la app."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaTablero()
        return VistaWeb("inicio/index.html", PuenteInicio(),
                        tema=db.parametro("tema", "claro"))

    def _crear_caja(self) -> QWidget:
        """Caja: Etapa 2 de MIGRACION_WEB.md. Mismo criterio de fallback
        que _crear_inicio()."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaCaja()
        self.puente_caja = PuenteCaja(self)
        return VistaWeb("caja/index.html", self.puente_caja,
                        tema=db.parametro("tema", "claro"))

    def _crear_clientes(self) -> QWidget:
        """Clientes: Etapa 3 de MIGRACION_WEB.md. Mismo criterio de
        fallback que _crear_inicio()."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaClientes()
        self.puente_clientes = PuenteClientes(self)
        return VistaWeb("clientes/index.html", self.puente_clientes,
                        tema=db.parametro("tema", "claro"))

    def _crear_vendedores(self) -> QWidget:
        """Vendedores: Etapa 4 de MIGRACION_WEB.md. Mismo criterio de
        fallback que _crear_inicio()."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaVendedores()
        self.puente_vendedores = PuenteVendedores(self)
        return VistaWeb("vendedores/index.html", self.puente_vendedores,
                        tema=db.parametro("tema", "claro"))

    def _crear_proveedores(self) -> QWidget:
        """Operadores: Etapa 5 de MIGRACION_WEB.md. Mismo criterio de
        fallback que _crear_inicio()."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaProveedores()
        self.puente_proveedores = PuenteProveedores(self)
        return VistaWeb("operadores/index.html", self.puente_proveedores,
                        tema=db.parametro("tema", "claro"))

    def _crear_reportes(self) -> QWidget:
        """Reportes: Etapa 6 de MIGRACION_WEB.md. Mismo criterio de
        fallback que _crear_inicio()."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaReportes()
        self.puente_reportes = PuenteReportes(self)
        return VistaWeb("reportes/index.html", self.puente_reportes,
                        tema=db.parametro("tema", "claro"))

    def _crear_cierre(self) -> QWidget:
        """Cierre: Etapa 7 de MIGRACION_WEB.md. Mismo criterio de
        fallback que _crear_inicio()."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaCierre()
        self.puente_cierre = PuenteCierre(self)
        return VistaWeb("cierre/index.html", self.puente_cierre,
                        tema=db.parametro("tema", "claro"))

    def _crear_caja_gastos(self) -> QWidget:
        """Caja y gastos: Etapa 8 de MIGRACION_WEB.md. Mismo criterio de
        fallback que _crear_inicio()."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaCajaGastos()
        self.puente_caja_gastos = PuenteCajaGastos(self)
        return VistaWeb("caja_gastos/index.html", self.puente_caja_gastos,
                        tema=db.parametro("tema", "claro"))

    def _crear_ajustes(self) -> QWidget:
        """Ajustes: Etapa 9 de MIGRACION_WEB.md. Mismo criterio de
        fallback que _crear_inicio()."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaConfiguracion()
        self.puente_ajustes = PuenteAjustes()
        return VistaWeb("ajustes/index.html", self.puente_ajustes,
                        tema=db.parametro("tema", "claro"))

    def _crear_herramientas(self) -> QWidget:
        """Herramientas: Etapa 9 de MIGRACION_WEB.md. Mismo criterio de
        fallback que _crear_inicio() -- el puente necesita la ventana
        real (no None), cada boton dispara un metodo de VentanaPrincipal."""
        try:
            from .web import VistaWeb
        except ImportError:
            return VistaHerramientas(self)
        self.puente_herramientas = PuenteHerramientas(self)
        return VistaWeb("herramientas/index.html", self.puente_herramientas,
                        tema=db.parametro("tema", "claro"))

    # ----------------------------------------------------------- marca
    def aplicar_marca(self) -> None:
        """Logo de la barra lateral segun el tema (la barra siempre es oscura)."""
        from ..app import recurso
        logo = recurso("logo_horizontal_claro.png") or recurso("logo_horizontal.png")
        self.nav.set_logo(str(logo) if logo else None)

    # ------------------------------------------------------ navegacion
    def ir_a(self, indice: int) -> None:
        indice = max(0, min(indice, len(self.vistas) - 1))
        self.paginas.setCurrentIndex(indice)
        self.nav.seleccionar(indice)
        vista = self.vistas[indice]
        if hasattr(vista, "refrescar"):
            try:
                vista.refrescar()
            except Exception as e:  # noqa: BLE001
                self.statusBar().showMessage(f"Error al refrescar: {e}", 6000)

    def refrescar_todo(self) -> None:
        for v in self.vistas:
            if hasattr(v, "refrescar"):
                try:
                    v.refrescar()
                except Exception as e:  # noqa: BLE001
                    self.statusBar().showMessage(f"Error al refrescar: {e}", 6000)

    # ------------------------------------------------------------ tema
    def cambiar_tema(self, nombre: str) -> None:
        from ..app import aplicar_tema
        app = QApplication.instance()
        if app is None:
            return
        db.set_parametro("tema", nombre)
        aplicar_tema(app, nombre)
        self.aplicar_marca()
        self.refrescar_todo()
        # Las pantallas migradas a HTML/CSS/JS (ver MIGRACION_WEB.md) no
        # escuchan el QSS de Qt: hay que avisarles el tema nuevo aparte.
        try:
            from .web import VistaWeb
        except ImportError:
            return
        for v in self.vistas:
            if isinstance(v, VistaWeb):
                v.aplicar_tema(nombre)

    def alternar_tema(self) -> None:
        actual = db.parametro("tema", "claro")
        self.cambiar_tema("claro" if actual == "oscuro" else "oscuro")

    # -------------------------------------------------------- acciones
    def importar_excel(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccioná el Excel de Spamed", "",
            "Excel con macros (*.xlsm);;Excel (*.xlsx);;Todos (*.*)",
        )
        if not ruta:
            return
        limpiar = QMessageBox.question(
            self, "Importar",
            "¿Querés reemplazar todos los datos actuales?\n\n"
            "Sí = borra la base y carga el Excel desde cero.\n"
            "No = agrega o actualiza sobre lo existente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if limpiar == QMessageBox.StandardButton.Cancel:
            return
        try:
            db.backup()
            res = importador.importar(
                ruta, limpiar=(limpiar == QMessageBox.StandardButton.Yes)
            )
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo importar:\n{e}")
            return
        self.refrescar_todo()
        texto = "Importación finalizada.\n\n" + res.resumen()
        if res.avisos:
            texto += "\n\nAvisos:\n- " + "\n- ".join(res.avisos[:15])
            if len(res.avisos) > 15:
                texto += f"\n(+{len(res.avisos) - 15} más)"
        aviso(self, texto, "Importar")
        self.ir_a(0)

    def descargar_plantilla(self) -> None:
        from ..core import plantilla
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar la plantilla",
            str(config.dir_exports() / "Plantilla_SpamedTravel.xlsx"),
            "Excel (*.xlsx)")
        if not ruta:
            return
        try:
            p = plantilla.generar(Path(ruta))
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo generar la plantilla:\n{e}")
            return
        if confirmar(
            self, f"Plantilla guardada en:\n{p}\n\n¿Querés abrirla ahora?"
        ):
            try:
                import os
                os.startfile(str(p))  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                aviso(self, str(p))

    def backup(self) -> None:
        try:
            p = db.backup()
            aviso(self, f"Copia creada:\n{p}")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo crear la copia:\n{e}")

    def restaurar(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Elegí la copia", str(config.dir_backups()),
            "Base de datos (*.db)",
        )
        if not ruta:
            return
        if not confirmar(
            self, "Se va a reemplazar la base actual por la copia.\n"
                  "Se guarda un resguardo previo por las dudas. ¿Continuar?"
        ):
            return
        try:
            db.restaurar(Path(ruta))
            self.refrescar_todo()
            aviso(self, "Copia restaurada.")
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo restaurar:\n{e}")

    def abrir_carpeta(self) -> None:
        import os
        import subprocess
        carpeta = str(config.dir_datos())
        try:
            if os.name == "nt":
                os.startfile(carpeta)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", carpeta])
        except Exception:  # noqa: BLE001
            aviso(self, carpeta)

    def configurar(self) -> None:
        if DialogoConfiguracion(self).exec():
            self.refrescar_todo()

    def diagnostico(self) -> None:
        DialogoDiagnostico(self).exec()

    def acerca_de(self) -> None:
        from ..app import recurso
        logo = recurso("logo_horizontal.png")
        img = (f"<img src='{logo.as_posix()}' width='230'><br><br>"
               if logo else "")
        QMessageBox.about(
            self, "Acerca de",
            f"{img}<b>{config.APP_NAME}</b> v{config.APP_VERSION}<br><br>"
            "Gestión de reservas, caja y comisiones para agencia de viajes.<br>"
            "Reemplaza el libro Excel BaseDatosSpamed.<br><br>"
            f"Base de datos:<br><code>{config.ruta_db()}</code>",
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            db.backup()
        except Exception:  # noqa: BLE001
            pass
        db.cerrar()
        super().closeEvent(event)
