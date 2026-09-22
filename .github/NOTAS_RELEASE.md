Version **__VERSION__** de Spamed Travel para Windows de 64 bits.

## Cual bajar

| Archivo | Para que |
|---|---|
| `SpamedTravel_Setup___VERSION__.exe` | **Lo normal.** Instalador con asistente en espanol. No pide permisos de administrador, crea el acceso directo y se desinstala desde "Agregar o quitar programas". |
| `SpamedTravel___VERSION___portable.zip` | Sin instalar: descomprimir donde sea y ejecutar `SpamedTravel.exe`. Sirve para probarlo o para llevarlo en un pendrive. |

Los dos traen exactamente el mismo programa. Lo unico que agrega el
instalador es el asistente, el acceso directo y el desinstalador.

## Como instalar

1. Bajar `SpamedTravel_Setup___VERSION__.exe` de la lista de abajo.
2. Ejecutarlo. Windows SmartScreen puede avisar que el programa no esta
   firmado: es lo esperable, el ejecutable no tiene firma digital de pago.
   Clic en **Mas informacion** y despues en **Ejecutar de todas formas**.
3. Seguir el asistente. Se instala en la carpeta del usuario, sin pedir
   permisos de administrador.

## Primer uso

Herramientas -> Importar desde Excel, elegir `BaseDatosSpamed.xlsm` y
responder que si a reemplazar todo (es la primera carga). Al terminar
conviene revisar los avisos que muestra.

## Donde quedan los datos

En `%LOCALAPPDATA%\SpamedTravel\`: la base `spamed.db`, los backups y las
exportaciones. **Desinstalar o actualizar no borra nada de eso.** Para
llevar los datos a otra PC alcanza con copiar `spamed.db`.

## Si algo falla

| Sintoma | Causa | Solucion |
|---|---|---|
| El antivirus bloquea el `.exe` | Falso positivo tipico de PyInstaller: el ejecutable trae adentro el interprete de Python | Agregar la carpeta como excepcion |
| La ventana no abre y no dice nada | Falta el runtime de Visual C++ | Instalar *Microsoft Visual C++ Redistributable x64* |
| Una pantalla queda en blanco | QtWebEngine no pudo arrancar en esa PC | Pasar el detalle desde Herramientas -> Diagnostico (o Ctrl+Shift+D) |
