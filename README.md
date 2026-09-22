# Spamed Travel — aplicación de escritorio

Reemplazo del libro `BaseDatosSpamed.xlsm` por una aplicación Windows con base
de datos real. Gestiona reservas (files), caja, clientes, vendedores,
proveedores, comisiones y reportes.

---

## Cómo generar el instalable (una sola vez, en tu PC Windows)

### Requisitos previos

| Herramienta | Para qué | Dónde |
|---|---|---|
| **Python 3.11+ 64 bits** | compilar | https://www.python.org/downloads/ — tildar *Add python.exe to PATH* |
| **Inno Setup 6** (opcional) | armar el `.exe` instalador | `winget install --id JRSoftware.InnoSetup -e` |

Sin Inno Setup igual obtenés el programa funcionando; lo que no obtenés es el
instalador de un solo clic.

### Pasos

```bat
:: 1. Descomprimir el zip donde quieras, por ejemplo C:\dev\spamed-desktop
:: 2. Abrir esa carpeta y ejecutar:
build\build.bat
```

El script hace todo solo: crea el entorno virtual, instala dependencias,
compila con PyInstaller y arma el instalador. Tarda entre 3 y 8 minutos la
primera vez.

**Resultado:**

```
dist\SpamedTravel\SpamedTravel.exe             <- el programa, listo para usar
dist\SpamedTravel_portable.zip                 <- misma cosa, para copiar a otra PC
dist\instalador\SpamedTravel_Setup_1.0.3.exe   <- solo si tenes Inno Setup
```

Las tres opciones sirven; no hace falta el instalador para usar el programa.
Si `dist\instalador\` no aparece es porque **no tenés Inno Setup instalado** —
el script te lo avisa al final. No es un error: el `.exe` de
`dist\SpamedTravel\` ya funciona. Inno Setup solo agrega el asistente de
instalación, el acceso directo automático y el desinstalador.

El instalador no necesita permisos de administrador: instala en la carpeta del
usuario, crea el acceso directo, aparece en «Agregar o quitar programas» y trae
su propio desinstalador. El asistente está en español y con la marca de SpaMed
(las imágenes salen de `build/instalador/`).

Al desinstalar **no se borra la base de datos**: el desinstalador avisa dónde
quedó por si se quiere conservar.

### Probar sin compilar

```bat
ejecutar_dev.bat
```

### La causa real de los ImportError anteriores (resuelta en 1.0.3)

Las versiones 1.0.1 y 1.0.2 diagnosticaron mal un `ImportError: cannot import
name 'documentos'`. La causa real era un **`SyntaxError`**: `documentos.py`
tenía un f-string con comillas triples anidado dentro de otro del mismo tipo
de comillas, algo que Python 3.12 acepta (PEP 701) pero 3.11 rechaza.
PyInstaller, al no poder importar el módulo durante el análisis, lo marca
como "invalid module" sin mostrar el error real — de ahí el mensaje confuso
de "circular import" que en realidad no lo era.

`build.bat` ahora corre `python -m compileall src` antes de invocar a
PyInstaller, así cualquier problema de sintaxis aparece con su traceback real
en vez de quedar enmascarado.

### Comprobar qué versión estás compilando

Antes de reportar un problema de arranque, conviene confirmar que se compiló lo
que se cree:

```powershell
Select-String -Path .\src\spamed\core\config.py -Pattern 'APP_VERSION'
Test-Path .\dist\SpamedTravel\_internal\spamed
```

El primero tiene que decir `1.0.2`. El segundo tiene que dar **False**: si da
True, quedó un paquete duplicado en disco y el `.exe` va a fallar al importar.

### Si algo falla

| Síntoma | Causa | Solución |
|---|---|---|
| No aparece `dist\instalador\` | falta Inno Setup | usar el `.exe` de `dist\SpamedTravel\`, o instalar Inno Setup |
| `ImportError: attempted relative import` | versión vieja del `.spec` | el entry point debe ser `src\main.py`, no `src\spamed\__main__.py` |
| El antivirus bloquea el `.exe` | falso positivo típico de PyInstaller | agregar la carpeta como excepción |
| `ImportError: cannot import name X from 'spamed.core'` | un paquete materializado en `_internal\spamed\` tapaba al del bundle | corregido en 1.0.2, con dos defensas: el `.spec` ya no crea esa carpeta, y `core/__init__.py` importa sus submódulos explícitamente |
| La ventana no abre y no dice nada | falta el runtime de Visual C++ | instalar *Microsoft Visual C++ Redistributable x64* |

---

## Primer uso

1. Abrir el programa.
2. **Archivo → Importar desde Excel…** y elegir `BaseDatosSpamed.xlsm`.
3. Elegir *Sí* para reemplazar todo (es la primera carga).
4. Revisar los avisos que muestra al terminar.

La importación trae clientes, vendedores, proveedores, reservas y los 75
movimientos de caja, corrigiendo el signo de los montos y los saldos de
proveedor que estaban invertidos en el Excel.

---

## Dónde viven los datos

```
%LOCALAPPDATA%\SpamedTravel\
├── spamed.db              <- la base (SQLite, un solo archivo)
├── backups\               <- copia automática al cerrar + manuales
└── exportaciones\         <- Excel y CSV generados
```

Para llevarte los datos a otra PC alcanza con copiar `spamed.db`.
Desinstalar el programa **no** borra esta carpeta.

---

## Estructura del proyecto

```
src/spamed/
├── app.py              arranque, estilo, manejo de errores
├── core/
│   ├── config.py       rutas y constantes
│   ├── schema.sql      esquema de la base + vista de saldos
│   ├── db.py           conexión, seed, backup y restore
│   ├── calculos.py     reglas de negocio (estados, alertas, formato)
│   ├── repo.py         CRUD y consultas de reportes
│   ├── importador.py   carga desde el Excel viejo
│   ├── exportador.py   salida a Excel y CSV
│   ├── documentos.py   voucher y recibo en PDF (QPdfWriter)
│   └── tema.py         paleta de marca y generador de QSS (claro/oscuro)
├── ui/
│   ├── principal.py    ventana, navegación lateral, acciones
│   ├── navegacion.py   barra lateral, cabecera de página
│   ├── herramientas.py página de datos, copias y preferencias
│   ├── cierre.py       cierre contable y liquidaciones
│   ├── ajustes.py      listas, gastos fijos y arqueos
│   ├── tablero.py      dashboard y reportes
│   ├── reservas.py     grilla y formulario de files
│   ├── caja.py         libro de caja
│   ├── maestros.py     clientes, vendedores, proveedores
│   └── comunes.py      widgets reutilizables
└── recursos/           logos e íconos
```

---

## Cómo agregar cosas

**Un campo nuevo en reservas:** agregar la columna en `schema.sql`, exponerla en
la vista `v_reservas_saldos`, y sumar el control en `ui/reservas.py`.
Como el esquema usa `CREATE TABLE IF NOT EXISTS`, para bases ya creadas hay que
sumar la columna en la lista `MIGRACIONES` de `db.py`: se aplica sola en el
próximo arranque y recrea la vista de saldos.

**Cambiar el diseño de un PDF:** todo el voucher y el recibo son HTML en
`core/documentos.py` (funciones `html_voucher` y `html_recibo`). Se edita el
HTML y listo, no hay plantillas externas.

**Cambiar un color:** todo está en `core/tema.py`. Los diccionarios `CLARO` y
`OSCURO` definen las superficies y `ESTADOS_*` los ocho estados; el QSS se
genera desde ahí, así que un color se toca en un solo lugar. No hay `.qss`
suelto que mantener.

**Un reporte nuevo:** agregar el método en `repo.Reportes` y registrarlo en el
diccionario `REPORTES` de `ui/tablero.py`. La exportación a Excel sale gratis.

**Una lista desplegable nueva:** agregar el tipo en `SEED_LISTAS` (`db.py`) y
leerla con `db.listas("mi_tipo")`.
