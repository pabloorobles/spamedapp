# Spamed Travel — aplicación de escritorio

Reemplazo del libro `BaseDatosSpamed.xlsm` por una aplicación Windows con base
de datos real. Gestiona reservas (files), caja, clientes, vendedores,
proveedores, comisiones y reportes.

---

## Instalar la app (lo que necesita el usuario final)

**No hace falta compilar nada ni instalar Python.** Cada versión publicada
deja el instalador listo para bajar:

### 👉 [Descargar la última versión](https://github.com/pabloorobles/spamedapp/releases/latest)

En esa página, abajo de todo, en **Assets**, hay dos archivos:

| Archivo | Para qué |
|---|---|
| `SpamedTravel_Setup_1.1.0.exe` | **Lo normal.** Instalador con asistente en español. No pide permisos de administrador. |
| `SpamedTravel_1.1.0_portable.zip` | Sin instalar: descomprimir y ejecutar `SpamedTravel.exe`. Para probarlo o llevarlo en un pendrive. |

Los dos traen el mismo programa. El instalador agrega el asistente, el acceso
directo y el desinstalador.

**Pasos:** bajar el `.exe`, ejecutarlo y seguir el asistente. Windows
SmartScreen puede avisar que el programa no está firmado — es lo esperable,
el ejecutable no tiene firma digital de pago: *Más información* → *Ejecutar de
todas formas*.

Requisitos: **Windows de 64 bits**. Si la ventana no abre y no dice nada,
falta el *Microsoft Visual C++ Redistributable x64*.

---

## Publicar una versión nueva

El instalador lo compila GitHub Actions en un runner de Windows
(`.github/workflows/release.yml`), no hace falta una PC Windows a mano.

```bash
# 1. Subir el número de versión en los TRES archivos (el workflow verifica
#    que coincidan y corta si no):
#      src/spamed/core/config.py   APP_VERSION
#      build/version_info.txt      filevers / prodvers / los dos strings
#      build/installer.iss         MiVersion
# 2. Commitear ese cambio y etiquetar:
git tag v1.1.1
git push origin v1.1.1
```

El tag dispara la compilación y, cuando termina, el Release queda publicado
con el instalador y el zip adjuntos. Desde *Actions → Release de Windows →
Run workflow* también se puede compilar sin publicar nada, para probar un
cambio del `.spec`.

---

## Compilar en tu propia PC Windows

Solo hace falta para desarrollar o si querés el `.exe` sin pasar por GitHub.

| Herramienta | Para qué | Dónde |
|---|---|---|
| **Python 3.11 de 64 bits** | compilar | https://www.python.org/downloads/ — tildar *Add python.exe to PATH* |
| **Inno Setup 6** (opcional) | armar el `.exe` instalador | `winget install --id JRSoftware.InnoSetup -e` |

```bat
build\build.bat
```

El script hace todo solo: entorno virtual, dependencias, chequeo de sintaxis,
PyInstaller y, si encuentra Inno Setup, el instalador. Tarda entre 3 y 8
minutos la primera vez (QtWebEngine es pesado).

**Resultado:**

```
dist\SpamedTravel\SpamedTravel.exe             <- el programa, listo para usar
dist\SpamedTravel_portable.zip                 <- misma cosa, para copiar a otra PC
dist\instalador\SpamedTravel_Setup_1.1.0.exe   <- solo si tenés Inno Setup
```

Sin Inno Setup igual obtenés el programa funcionando; lo que no obtenés es el
instalador de un solo clic. El script te lo avisa al final.

### Probar sin compilar

```bat
ejecutar_dev.bat
```

### Si la compilación falla

| Síntoma | Causa | Solución |
|---|---|---|
| `SyntaxError` en el paso 4 | Python 3.12+ acepta f-strings triples anidadas, 3.11 no | corregir la f-string; el paso de `compileall` está justamente para que el error aparezca con su traceback real y no enmascarado por PyInstaller |
| `ImportError: attempted relative import` | el entry point del `.spec` quedó mal | tiene que ser `src\main.py`, no `src\spamed\__main__.py` |
| Quedó `dist\SpamedTravel\_internal\spamed\` | algo volvió a materializar el paquete en disco | revisar `build\spamed.spec`: `schema.sql` va solo a `recursos/`. `build.bat` y el workflow ya cortan solos si esto pasa |
| Una pantalla web queda en blanco en el `.exe` | falta `recursos/web/` en el bundle | el `.spec` lo empaqueta con `Tree(...)`; el workflow lo verifica |

---

## Primer uso

1. Abrir el programa.
2. **Herramientas → Importar desde Excel…** y elegir `BaseDatosSpamed.xlsm`.
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
