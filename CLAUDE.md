# Spamed Travel — contexto para Claude Code

Aplicación de escritorio (Python 3.11 + PySide6 + SQLite) para gestión de una
agencia de viajes. Reemplaza el libro Excel `BaseDatosSpamed.xlsm`. Un solo
desarrollador, un solo usuario final por instalación (no es multiusuario).

## Arrancar rápido

```powershell
.\ejecutar_dev.bat          # corre la app sin compilar (modo desarrollo)
.\build\build.bat           # compila el .exe y, si hay Inno Setup, el instalador
python tests\test_negocio.py    # pruebas de negocio (sin GUI)
python tests\test_interfaz.py   # pruebas de interfaz (Qt en modo offscreen)
.\crear_acceso_directo.ps1  # deja un acceso a la version de desarrollo en el Escritorio
```

El entorno virtual vive en `.venv\`. `build.bat` lo reusa si ya existe —no
hace falta borrarlo entre compilaciones, solo si se corrompe.

## Estructura

```
src/spamed/
├── app.py              arranque, tema, manejo global de errores
├── core/
│   ├── config.py        rutas, versión, constantes
│   ├── schema.sql        esquema SQLite completo + vista v_reservas_saldos
│   ├── db.py             conexión, seed, migraciones, backup/restore
│   ├── calculos.py       estados, alertas, formato de moneda/fecha
│   ├── repo.py            TODO el CRUD y las consultas (una clase por entidad)
│   ├── tema.py            paleta de marca, genera el QSS (claro/oscuro)
│   ├── importador.py      carga desde el Excel viejo y desde la plantilla
│   ├── plantilla.py       genera el .xlsx modelo para la carga inicial
│   ├── exportador.py      salida a Excel/CSV
│   └── documentos.py       PDFs (voucher, recibo, cotización, cierre, etc.)
├── ui/
│   ├── principal.py       ventana, barra lateral, orquesta las 10 páginas
│   ├── navegacion.py      BarraLateral, Cabecera, Vacio
│   ├── comunes.py         widgets reutilizables (Tabla, ComboConAlta, etc.)
│   ├── reservas.py         la pantalla más grande: file con 7 solapas
│   ├── caja.py, maestros.py, tablero.py, cierre.py, ajustes.py, herramientas.py
├── recursos/               logos, ícono .ico, sin hoja .qss (se genera desde tema.py)
└── main.py                 entry point ABSOLUTO para PyInstaller (no confundir
                             con __main__.py, que es para `python -m spamed`)
```

## La regla de negocio central (no romper esto)

```
Importe al cliente
× % comisión del mayorista (se carga en Proveedores)  → comisión de la agencia
− % comisión del vendedor (se carga en Vendedores)     → comisión del vendedor
                                                         = margen neto
```

El costo del proveedor se **deriva**: `importe − comisión_agencia`. Si el file
tiene servicios cargados (varios proveedores), el costo pasa a ser la suma de
`reserva_servicios` en lugar del cálculo por porcentaje. Todo esto vive en la
vista `v_reservas_saldos` de `schema.sql` — es la fuente de verdad, no
recalcular esto en Python en otro lado.

El flag `transfiere_neto` en proveedores define si se registra un solo egreso
(neto) o dos movimientos (pago total + ingreso de la comisión devuelta).

Las monedas **nunca se consolidan**. Ningún total debe sumar PESOS + DOLAR.

## Convenciones del proyecto

- **Español en todo**: nombres de tablas, columnas, comentarios, mensajes de
  error al usuario. Los identificadores internos también van en español
  (`reserva`, `cliente`, no `booking`, `customer`).
- **Sin atajos de teclado**, con una única excepción. Decisión explícita del
  usuario: todo se opera con botones visibles, no agregar `setShortcut` ni
  `QShortcut` en ningún widget. La excepción es **Ctrl+Shift+D**, que abre el
  panel de diagnóstico (`ui/principal.py::DialogoDiagnostico`): no es una
  acción de la operación diaria sino la herramienta para cuando algo falla, y
  el usuario la pidió para poder pasar el detalle de un error. Igual está
  duplicada como botón visible en Herramientas → Diagnóstico, así que ninguna
  función depende del teclado. **No borrar este atajo "para cumplir la
  regla"** — está acordado.
- **Sin barra de menú horizontal.** La navegación es la barra lateral
  (`ui/navegacion.py::BarraLateral`). No reintroducir un `QMenuBar` con
  Archivo/Edición/etc.
- **Combos cerrados, no editables**, salvo que exista una razón explícita.
  `ComboBusqueda` y `ComboTexto` son de solo-selección. Para permitir alta
  rápida se usa `ComboConAlta` (entidades con tabla propia) o `ComboLista`
  (valores de la tabla `listas`, con botón "+" que agrega en el momento).
- **Migraciones manuales**: `schema.sql` usa `CREATE TABLE IF NOT EXISTS`, que
  no modifica tablas existentes. Un campo nuevo en una tabla que ya existe se
  agrega a mano en la lista `MIGRACIONES` de `core/db.py`. La vista
  `v_reservas_saldos` se recrea siempre en cada arranque (ver `_migrar()`).
  Tres detalles que ya mordieron:
  1. La definición en `MIGRACIONES` tiene que coincidir con la de
     `schema.sql`, cláusula `ON DELETE` incluida. Si no, una base migrada y
     una recién creada se comportan distinto ante un borrado.
  2. **Un índice sobre una columna migrada no va en `schema.sql`.**
     `inicializar()` corre ese script entero *antes* que `_migrar()`, así que
     en una base vieja la columna todavía no existe y el `CREATE INDEX`
     tumba el `executescript` completo. Va después del `ALTER`, dentro de
     `_migrar()` (ver `ix_adj_vendedor`).
  3. Después de tocar migraciones, probar contra una base *vieja*, no sólo
     contra una nueva: las pruebas crean la base desde cero y no ven este
     tipo de error.
- **Carpeta de salida**: los PDF y las exportaciones van a
  `config.dir_exports()`, que por defecto es `Descargas\Spamed Travel` y el
  usuario puede cambiar desde Configuración general (parámetro
  `carpeta_exportaciones`). `config` no puede importar `db` arriba de todo
  (sería circular): el parámetro se lee con import diferido. Los **backups
  no** van ahí, siguen en `%LOCALAPPDATA%`.
- **Tema**: los colores nunca van hardcodeados en `ui/*.py`. Se piden con
  `from .comunes import color; color("primario")`, que lee la paleta activa
  de `core/tema.py`. Ojo con `#RRGGBBAA`: Qt lo interpreta como ARGB, no como
  RGB+alfa — usar `rgba(r,g,b,a)` en QSS si hace falta transparencia.
- **PDFs**: HTML renderizado con `QTextDocument` + `QPdfWriter` (no hay
  dependencia externa tipo weasyprint). El layout necesita
  `doc.documentLayout().setPaintDevice(escritor)` o el texto sale a un tercio
  del tamaño esperado.

## Bugs ya resueltos (no reintroducir)

1. **F-strings triples anidadas.** Python 3.12 acepta anidar `f"""..."""`
   dentro de otro `f"""..."""` (PEP 701); Python 3.11 —la versión objetivo—
   no. Esto causó un `SyntaxError` que PyInstaller enmascaraba como
   `ImportError: circular import`, larguísimo de diagnosticar. **Si el
   entorno de Claude Code corre 3.12 o superior, este tipo de error NO se
   va a detectar acá.** Antes de dar por buena una función con f-strings
   compuestas, revisar a mano que no anide comillas triples del mismo tipo,
   o correr `python -m compileall src` con un intérprete 3.11 si está
   disponible.
2. **`schema.sql` no debe copiarse a `spamed/core/` en el `.spec`.** Solo va a
   `recursos/`. Copiarlo dentro del paquete crea una carpeta real en el
   bundle que puede interferir con la resolución de imports.
3. **`_nombre()` en `documentos.py`** usa timestamp con microsegundos, no solo
   minutos — dos PDFs del mismo file generados en el mismo minuto pisaban el
   archivo anterior.
4. **`core/__init__.py` va vacío.** Se intentó importar los submódulos ahí de
   forma eager pensando que blindaba contra imports faltantes; el efecto real
   era que cualquier submódulo roto tumbaba toda la app al arrancar en vez de
   fallar solo donde se usa. No reintroducir imports eager ahí.
5. **Los encabezados de la plantilla van en la fila 1.** El importador toma
   la primera fila con contenido como nombres de columna
   (`importador._leer_rango_usado`). Una fila de título o de ayuda arriba
   hace que no reconozca ninguna columna y la importación entre en silencio
   sin cargar nada. La explicación de cada hoja va como comentario de celda,
   no como fila.
6. **`documentos.*` espera `Mapping`, y `repo.Caja.listar()` devuelve
   `sqlite3.Row`**, que no tiene `.get()`. Los llamadores convierten con
   `[dict(m) for m in ...]` — ver `ui/reservas.py::voucher`. Si aparece un
   `AttributeError: 'sqlite3.Row' object has no attribute 'get'`, falta esa
   conversión en el llamador nuevo.

## Build y empaquetado

- `build/spamed.spec` usa `collect_submodules("spamed")` para los
  hiddenimports — no enumerar módulos a mano, es frágil.
- `build/build.bat` corre `python -m compileall src` **antes** de invocar a
  PyInstaller (paso 4 de 6). Si eso falla, el error de sintaxis real aparece
  ahí; si se saltea este paso, PyInstaller lo enmascara como "invalid
  module" sin decir la causa.
- Después de compilar, verificar `Test-Path .\dist\SpamedTravel\_internal\spamed`
  → tiene que dar `False`. Si da `True`, algo volvió a materializar el
  paquete en disco.
- Versión actual: **1.1.0**. Se define en tres lugares que hay que mantener
  sincronizados: `src/spamed/core/config.py` (`APP_VERSION`),
  `build/version_info.txt`, `build/installer.iss` (`MiVersion`).
- Datos del usuario en `%LOCALAPPDATA%\SpamedTravel\` — nunca dentro de la
  carpeta del proyecto ni del build. Recompilar no los toca.

## Testing

Dos suites, las dos standalone (no requieren pytest), cada una contra su
propia base temporal. Correr las dos después de cualquier cambio en `core/`;
la de interfaz además después de tocar `ui/`.

`tests/test_negocio.py` — **57 casos**. Base en `%TEMP%\spamed_pruebas`.
Verifica: cadena de comisiones, transiciones de estado, servicios
multi-proveedor, cuotas, duplicar reserva, cancelación con devolución, cierre
contable, liquidaciones, gastos fijos, arqueo, validaciones de negocio.

`tests/test_interfaz.py` — **62 casos**. Base en `%TEMP%\spamed_pruebas_ui`.
Fuerza `QT_QPA_PLATFORM=offscreen` (Qt dibuja en memoria; sirve igual en
Windows que en un CI sin monitor). Cubre humo de las 10 páginas y de todos
los diálogos, y flujos completos: alta de file desde el diálogo → cobro desde
caja → cambio de estado → voucher en PDF.

**Al escribir pruebas de interfaz, silenciar los carteles modales.** Un
`QMessageBox` deja la suite colgada esperando un click que nunca llega, aun
en modo offscreen, y sin `python -u` no se ve ni dónde se colgó.
`test_interfaz.py::_silenciar_dialogos()` reemplaza `aviso`, `error` y
`confirmar` **módulo por módulo** — cada uno hizo `from .comunes import ...`
y tiene su propia referencia, así que parchear sólo `comunes` no alcanza.
Los `error` quedan registrados y se revisan al final: un cartel rojo es un
fallo aunque nada haya lanzado excepción.

## Lo que el usuario explícitamente no quiere (por ahora)

- Multiusuario / base compartida entre PCs. Un solo usuario, sin login.
- Unificar pesos y dólares en un solo total.
- Nada que no se pueda operar con el mouse (ver la excepción de Ctrl+Shift+D
  más arriba: es diagnóstico, no operación, y tiene su botón equivalente).

Si una tarea nueva empuja hacia alguna de estas tres cosas, avisar antes de
implementar.

Pospuesto a propósito, con el detalle y el motivo en **`PENDIENTES.md`**:
facturación electrónica ARCA/AFIP y purga automática de backups viejos.
Mientras la app esté en demo, no se tocan.

## Decisión de diseño: los servicios no mandan sobre el importe

En un file con servicios cargados, el **costo** del proveedor sí pasa a ser
la suma de los costos de los servicios (eso vive en `v_reservas_saldos`). El
**importe al cliente**, en cambio, lo sigue escribiendo el usuario a mano: la
solapa Servicios sólo muestra los totales y avisa en color cuando la suma de
las ventas no coincide con el importe del file, con un botón para copiarlo si
se quiere (`ui/reservas.py::_totales_servicios`). Se evaluó hacerlo
automático y se descartó: habría cambiado el valor de los files ya cargados
que tienen servicios con la venta en cero. No convertirlo en automático sin
preguntar.