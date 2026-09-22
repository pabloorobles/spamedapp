# Migración a HTML/CSS/JS embebido — seguimiento

Roadmap de la migración de la interfaz de Spamed Travel de widgets de Qt a
páginas HTML/CSS/JS reales, embebidas en la misma app de escritorio vía
`QWebEngineView`. Decidido el 27/08/2026, después de que a Pablo le gustó
mucho más un piloto de la pantalla Inicio hecho en HTML/CSS/JS que la
versión en Qt. El detalle completo de la arquitectura (el puente
Python↔JS, cómo se sirven los archivos, qué pasa con las pruebas) vive en
el plan de la sesión que armó esta etapa; acá queda el resumen y el
estado.

**Lo que no cambia**: toda la lógica de negocio (`core/repo.py`,
`core/calculos.py`, `core/schema.sql`, `core/documentos.py`) sigue
exactamente igual. Solo se reemplaza la capa de interfaz, pantalla por
pantalla.

**Cómo se usa este archivo**: mismo criterio que `REDISENO.md` — un
casillero se tilda `[x]` solo cuando está *verificado* (compila, pasan
las pruebas, y Pablo confirmó en su máquina que se ve y funciona bien),
no apenas escrito.

---

## Etapa 0 — Cimientos

**Estado: en curso**

La única etapa donde la verificación final depende de Pablo: este entorno
no tiene `PySide6-Addons` instalado ni acceso a internet para instalarlo,
así que no puedo confirmar yo mismo que el plomero funciona de punta a
punta.

- [x] `requirements.txt`: sumar `PySide6-Addons`
- [x] `ui/web.py`: `VistaWeb` (QWebEngineView + QWebChannel) y el
      `QWebEngineUrlSchemeHandler` custom (esquema `spamed://`)
- [x] `core/tema.py`: `tokens_css()` — tercera salida del mismo
      diccionario de colores/fuentes que ya alimenta el QSS y los PDFs
- [x] Página de humo (`recursos/web/humo/`) para probar que el esquema
      sirve archivos y que `QWebChannel` responde — accesible desde
      Herramientas → Diagnóstico → "Probar pantallas web (beta)"
      (se borra en la Etapa 1)
- [x] `build/spamed.spec`: sacar QtWebEngine de `excludes`, empaquetar
      `recursos/web/` completo
- [x] La app arranca igual de bien SIN `PySide6-Addons` instalado
      (verificado acá: se salta el plomero web sin romper nada)
- [ ] **Pablo confirma en su PC** que, después de instalar
      `PySide6-Addons`, el botón de Diagnóstico abre la página de humo
      con los colores de marca y el saludo de Python

## Etapa 1 — Inicio

**Estado: código completo, falta tu confirmación visual**

Etapa 0 confirmada por Pablo (17/08 → en realidad 27/08/2026, vio la
página de humo con los colores de marca). Durante esta etapa se descubrió
que este entorno de desarrollo comparte el mismo `.venv` que la máquina
de Pablo, así que `PySide6-Addons` ya estaba instalado acá — pero
**QWebEngineView no puede renderizar sin GPU real** (4 intentos con
distintas banderas de Chromium, mismo error de contexto GL). Es una
limitación del entorno headless, no del código: en la PC de Pablo, con
pantalla y GPU de verdad, no debería pasar — pero es la confirmación de
que el "humo de página vía QWebEngineView offscreen" que preveía el plan
no es viable acá. La verificación quedó así, un escalón más fuerte de lo
planeado en las dos primeras capas, más floja en la tercera:

- [x] `recursos/web/inicio/` (`index.html`, `inicio.css`, `inicio.js`) —
      mismo diseño aprobado en el piloto, sin la barra lateral propia (la
      sigue dando Qt) y sin selector de tema propio (sigue el de la app,
      vía `VistaWeb.aplicar_tema()` empujado desde
      `VentanaPrincipal.cambiar_tema()`)
- [x] `PuenteInicio` (`ui/puentes.py`) — envoltura fina sobre
      `repo.Reportes.dashboard()`, `db.listas("moneda")` y el cálculo de
      "mes actual"; responde JSON, nunca deja el JS colgado si algo falla
- [x] `ui/principal.py`: Inicio pasa a ser `VistaWeb`, con caída
      automática a la `VistaTablero` de Qt si `PySide6-Addons` no está
      instalado (no debería hacer falta desde ahora, pero protege una
      instalación vieja sin reinstalar)
- [x] Lógica del puente probada en Python puro (sin Qt, sin navegador) —
      `monedas()`, `fechas_mes_actual()`, `dashboard()` con y sin filtro
      de moneda, comparado contra `repo.Reportes.resumen_estados()`
      directo
- [x] HTML/CSS/JS verificados visualmente con datos reales de la base
      (mismos valores que tus capturas) mediante un arnés con un `puente`
      simulado en JavaScript — nunca se pudo cargar en un
      `QWebEngineView` de verdad en este entorno
- [ ] **Pablo confirma en su PC** que Inicio se ve y funciona como el
      piloto, con datos reales (no los de prueba del mockup)

## Etapa 2 — Caja

**Estado: código completo, falta tu confirmación visual**

Primera pantalla con mutaciones de verdad (alta/baja/edición) y dos
diálogos. Antes de construirla se extrajeron los estilos y funciones JS
que se iban a repetir en cada pantalla nueva a `recursos/web/comun/`:
`base.css` (cabecera, filtros, botones, panel, tablas, badges, modales) y
`util.js` (formato de moneda/fecha, helpers de selects). Inicio se
actualizó para usarlos también, sin cambios de comportamiento (reverificado).

Los dos diálogos (Movimiento, Cambio de moneda) pasaron a ser overlays
HTML dentro de la misma página, no ventanas de Qt aparte — con la misma
lógica dinámica que tenían antes (cambiar tipo reordena la lista de
conceptos, elegir un file autocompleta la moneda y muestra el saldo,
cotización implícita recalculada en vivo). Dos cosas se quedan como
diálogos nativos de Qt a propósito, porque necesitan el selector de
archivos del sistema operativo: exportar a Excel/CSV y guardar el PDF del
recibo. "Comprobantes…" tampoco se migró todavía (abre el diálogo de Qt
que ya existía) — es del subsistema de adjuntos, que se migra en otra
etapa.

- [x] `recursos/web/comun/base.css` y `util.js` (compartidos, reusados
      por Inicio también)
- [x] `recursos/web/caja/` (`index.html`, `caja.css`, `caja.js`)
- [x] `PuenteCaja` (`ui/puentes.py`) — listar/guardar/eliminar/
      cambio_moneda envolviendo `repo.Caja` sin cambiarlo; `exportar()` y
      `recibo()` abren dialogos nativos de Qt (selector de archivo)
      porque no hay forma limpia de pedirlos desde JS; señal
      `cambio_datos` (mismo rol que el `Signal` que ya tenía `VistaCaja`)
      para que las demás pantallas se refresquen solas
- [x] `ui/principal.py`: Caja pasa a ser `VistaWeb`, con la misma caída a
      Qt si `PySide6-Addons` no está instalado
- [x] Lógica del puente probada en Python puro: listas reales, búsqueda
      de files, `guardar()` válido e inválido (rechaza monto en cero sin
      romper), `eliminar()`, `cambio_moneda()`
- [x] HTML/CSS/JS verificados con un arnés de `puente` simulado — esta
      vez además interactivo de verdad (clicks reales, no solo la foto
      inicial): selección de fila habilitando botones, los dos modales
      abriendo con los valores por defecto correctos, recálculo en vivo
      de la cotización implícita
- [ ] **Pablo confirma en su PC**: cargar un movimiento nuevo, editar uno
      existente, hacer un cambio de moneda, y confirmar que el recibo en
      PDF y la exportación a Excel siguen funcionando igual que antes

## Etapa 3 — Clientes

**Estado: código completo, falta tu confirmación visual**

La pantalla con más diálogos hasta ahora. "Documentación" (adjuntos) y
"Estado de cuenta" quedaron igual que en Caja: abren un diálogo nativo de
Qt o el selector de archivos del sistema — Documentación es un subsistema
compartido con Vendedores y con los comprobantes de Caja, se migra aparte
más adelante en vez de tres veces por separado.

Seguimiento y Tarjetas pasaron a ser overlays HTML con la lista y el
formulario juntos en la misma pantalla (antes Tarjetas abría un diálogo
chico aparte para cada alta/edición; ahora el formulario está siempre
visible arriba de la lista, con un botón "Cancelar edición" cuando se
está editando una tarjeta existente — un click menos por edición).

- [x] `recursos/web/clientes/` (`index.html`, `clientes.css`, `clientes.js`)
- [x] `PuenteClientes` (`ui/puentes.py`) — envuelve `repo.Clientes`,
      `repo.Seguimientos` y `repo.TarjetasCliente`; `documentacion()` y
      `estado_cuenta()` abren diálogos/archivos nativos; señal
      `cambio_datos` conectada igual que en Caja
- [x] `ui/principal.py`: Clientes pasa a ser `VistaWeb`, mismo fallback a
      Qt si hiciera falta
- [x] Lógica del puente probada en Python puro: filtro de mes de
      cumpleaños, `guardar()`/`eliminar()` (incluido el caso real de
      rechazar borrar un cliente con reservas), altas y bajas de
      seguimientos y tarjetas
- [x] HTML/CSS/JS verificados con un arnés interactivo: selección de fila,
      apertura de los tres modales (Cliente, Seguimiento, Tarjetas) con
      los datos precargados correctos
- [ ] **Pablo confirma en su PC**: cargar/editar un cliente, registrar un
      seguimiento, agregar y editar una tarjeta, y confirmar que
      Documentación y Estado de cuenta siguen andando igual que antes

## Etapa 4 — Vendedores

**Estado: código completo, falta tu confirmación visual**

La más simple de las pantallas de maestros: un ABM sin diálogos anidados.
"Documentación" queda igual que en Clientes/Caja — diálogo nativo de Qt,
el subsistema de adjuntos se migra aparte más adelante (no específicamente
en esta etapa, a diferencia de lo que decía antes este archivo).

- [x] `recursos/web/vendedores/` (`index.html`, `vendedores.css`,
      `vendedores.js`)
- [x] `PuenteVendedores` (`ui/puentes.py`) — envuelve `repo.Vendedores`;
      `documentacion()` abre el diálogo nativo; `exportar()` abre el
      selector de archivo nativo; señal `cambio_datos` (no conectada a
      `refrescar_todo()` — tampoco lo estaba en la versión de Qt)
- [x] `ui/principal.py`: Vendedores pasa a ser `VistaWeb`, mismo
      fallback a Qt si `PySide6-Addons` no está instalado
- [x] Lógica del puente probada en Python puro: `listar()`/`obtener()`,
      `guardar()` válido e inválido (rechaza sin DNI), `eliminar()`
      (rechaza un vendedor con reservas asociadas)
- [x] Verificación indirecta: la prueba de interfaz existente sobre el
      desglose de files por estado por vendedor ahora pasa por el
      puente (antes tocaba `ventana.vendedores.tabla` directo)
- [ ] **Pablo confirma en su PC**: cargar/editar un vendedor y
      confirmar que Documentación sigue andando igual que antes

## Etapa 5 — Operadores

**Estado: código completo, falta tu confirmación visual**

Las variantes por tipo de viaje y moneda (hasta 4 por operador) pasaron a
ser una sección más dentro del mismo modal del operador, visible solo
cuando ya existe (necesitan su `proveedor_id`) — mismo criterio que tenía
el diálogo de Qt con las variantes anidadas, pero sin abrir una ventana
aparte por cada alta/edición: el formulario de variante queda siempre
visible arriba de su propia lista, con "Cancelar edición" cuando se está
editando una (mismo patrón que Tarjetas en Clientes).

- [x] `recursos/web/operadores/` (`index.html`, `operadores.css`,
      `operadores.js`)
- [x] `PuenteProveedores` (`ui/puentes.py`) — envuelve `repo.Proveedores`
      y `repo.ProveedorVariantes`; `exportar()` nativo; señal
      `cambio_datos` (misma salvedad que Vendedores)
- [x] `ui/principal.py`: Operadores pasa a ser `VistaWeb`, mismo
      fallback a Qt
- [x] Lógica del puente probada en Python puro: `listar()`/`obtener()`,
      `guardar()` de operador, alta/rechazo/baja de una variante
      (rechaza un tipo de viaje que no sea Nacional/Internacional),
      `eliminar()` (rechaza un operador con reservas asociadas)
- [x] Verificación indirecta: la prueba de interfaz existente sobre la
      columna Facturación ahora pasa por el puente
- [ ] **Pablo confirma en su PC**: cargar/editar un operador, agregar y
      editar una variante, y confirmar que Exportar sigue andando

## Etapa 6 — Reportes

**Estado: código completo, falta tu confirmación visual**

A diferencia de las pantallas anteriores, acá no hay un formulario por
entidad: es una única tabla genérica que cambia de columnas según el
informe elegido (15 informes distintos, de "Cobros pendientes" a
"Encuestas sin responder"). Para no mantener la lista de informes y sus
columnas en dos lugares, `PuenteReportes.metadatos()` lee directo de
`tablero.VistaReportes.REPORTES` (la misma constante que usaba la
versión de Qt) en vez de duplicarla en JS.

- [x] `recursos/web/reportes/` (`index.html`, `reportes.css`,
      `reportes.js`) — la tabla y sus columnas se arman en vivo a partir
      de `metadatos()`, ninguna columna quedó hardcodeada en el HTML
- [x] `PuenteReportes` (`ui/puentes.py`) — `metadatos()`/`datos()` de
      solo lectura; `exportar()` (Excel/CSV) y `exportar_pdf()` son
      diálogos nativos, mismo criterio que el resto de las pantallas
- [x] `ui/principal.py`: Reportes pasa a ser `VistaWeb`, mismo fallback
      a Qt
- [x] Lógica del puente probada en Python puro: `metadatos()` coincide
      con `VistaReportes.REPORTES`/`CAMPOS_MONEDA`, `datos()` trae el
      file de prueba en "Cobros pendientes", un nombre de informe que
      no existe no rompe nada
- [ ] **Pablo confirma en su PC**: cambiar entre varios informes,
      confirmar que las columnas y los montos se ven bien, y que
      Exportar PDF/Excel siguen funcionando

## Etapa 7 — Cierre

**Estado: código completo, falta tu confirmación visual**

La pantalla con más acciones distintas hasta ahora: período, resumen
consolidado con la cotización del BCRA, un panel por moneda con la grilla
de números del mes, la tabla de comisiones a liquidar, y el diálogo de
objetivo. El cálculo del consolidado (`Ventas consolidadas`/`Margen
consolidado`) se quedó del lado del JS a propósito — depende de un valor
de cotización que el usuario puede estar tipeando sin haber guardado
todavía, igual que en la versión de Qt (`_refrescar_consolidado()` usaba
`self.cotizacion.value()` en memoria, no lo persistido).

- [x] `recursos/web/cierre/` (`index.html`, `cierre.css`, `cierre.js`)
- [x] `PuenteCierre` (`ui/puentes.py`) — envuelve `repo.Cierre`,
      `repo.Objetivos`, `repo.Liquidaciones`, `repo.GastosFijos.
      generar_mes()` y `core/bcra.py`; `pdf_liquidacion()` y
      `exportar_pdf()` son diálogos nativos; señal `cambio_datos` al
      generar gastos fijos o pagar una liquidación (afecta Caja)
- [x] `ui/principal.py`: Cierre pasa a ser `VistaWeb`, mismo fallback a
      Qt
- [x] Lógica del puente probada en Python puro: `comparar()` marca bien
      el mes en curso, `objetivo_guardar()`/`objetivo_obtener()`,
      `cerrar()` rechaza el mes en curso y cierra un mes terminado con
      movimientos, `reabrir()` revierte el cierre
- [ ] **Pablo confirma en su PC**: revisar un par de períodos, cargar un
      objetivo, generar gastos fijos, cerrar y reabrir un mes viejo (no
      el actual), pagar una liquidación e imprimirla, y confirmar que la
      cotización del BCRA sigue trayéndose bien de internet

## Etapa 8 — Caja y gastos

**Estado: código completo, falta tu confirmación visual**

Tres solapas en una sola página (Gastos fijos, Gastos extraordinarios,
Arqueos de caja) — primera vez que se usa un patrón de solapas dentro de
una pantalla web, así que de paso se agregó `.tabs`/`.tab`/`.panel-tab` a
`comun/base.css` (compartido, lo va a volver a necesitar Reservas). Los
gastos extraordinarios siguen siendo, por abajo, un movimiento de Caja
más (egreso sin file): `PuenteCajaGastos.extraordinario_guardar()` fuerza
`tipo=EGRESO` y `reserva_id=None` antes de pasarlo a `repo.Caja.guardar()`,
igual que hacía el diálogo de Qt reutilizado.

- [x] `recursos/web/caja_gastos/` (`index.html`, `caja_gastos.css`,
      `caja_gastos.js`)
- [x] `comun/base.css`: agregado el patrón de solapas (`.tabs`/`.tab`/
      `.panel-tab`)
- [x] `PuenteCajaGastos` (`ui/puentes.py`) — envuelve `repo.GastosFijos`,
      `repo.Caja` (extraordinarios) y `repo.Arqueos`; `extraordinario_
      exportar()` es un diálogo nativo; señal `cambio_datos` al guardar
      o eliminar un extraordinario (afecta Caja)
- [x] `ui/principal.py`: Caja y gastos pasa a ser `VistaWeb`, mismo
      fallback a Qt
- [x] Lógica del puente probada en Python puro: alta/rechazo/baja de un
      gasto fijo (con el texto de vigencia armado), alta/baja de un
      extraordinario (confirmando que fuerza EGRESO sin file), alta/baja
      de un arqueo con el cálculo de diferencia verificado a mano
- [ ] **Pablo confirma en su PC**: cargar un gasto fijo, uno
      extraordinario, y hacer un arqueo — confirmar que el cálculo de
      diferencia se ve bien y que Exportar sigue funcionando

## Etapa 9 — Ajustes y Herramientas

**Estado: código completo, falta tu confirmación visual**

Las dos pantallas más simples de la app, así que se hicieron juntas.
**Ajustes** es alta/baja/orden de valores de la tabla `listas` (no tiene
`repo.py` propio, es la misma consulta cruda que ya usaba `PanelListas`
en Qt). El orden ya no se arrastra: son flechas ↑/↓ por fila — más fácil
de hacer bien sin poder probarlo a mano en un navegador de verdad, y en
línea con la idea original de "todo con botones visibles". Agregar y
renombrar un valor usan el prompt nativo del navegador (`window.prompt`),
mismo rol que tenía `QInputDialog.getText` en Qt.

**Herramientas** no tiene datos propios: es un menú de botones que
disparan acciones que ya existían tal cual en `VentanaPrincipal`
(importar Excel, backup, restaurar, diagnóstico, etc.) — `PuenteHerramientas`
solo reenvía cada click, sin lógica nueva. Es la única pantalla de esta
migración cuyo puente necesita la ventana real (no `None`): sin ella no
hay dónde ejecutar esas acciones.

- [x] `recursos/web/ajustes/` y `recursos/web/herramientas/`
      (`index.html`, `.css`, `.js` de cada una)
- [x] `comun/base.css`: agregado el patrón `.herramienta` (fila
      título + explicación + botón), reutilizable si hace falta en otra
      pantalla de menú de acciones
- [x] `PuenteAjustes` y `PuenteHerramientas` (`ui/puentes.py`)
- [x] `ui/principal.py`: las dos pasan a ser `VistaWeb`, mismo fallback
      a Qt
- [x] Lógica de `PuenteAjustes` probada en Python puro: alta, renombre,
      reordenamiento y baja de un valor de lista, de punta a punta;
      `PuenteHerramientas.info()` responde con datos reales
- [ ] **Pablo confirma en su PC**: agregar/renombrar/reordenar/quitar un
      valor de alguna lista, y probar un par de botones de Herramientas
      (Diagnóstico y Configurar alcanzan para confirmar que el resto
      también dispara bien, ya que todos pasan por el mismo mecanismo)

## Etapa 10 — Reservas

**Estado: pendiente**. La más grande — 7 solapas, ~1.500 líneas y buena
parte de los diálogos de la app (Reserva, Servicios, Cuotas, Cancelar,
Encuesta) — va última a propósito, con el patrón ya probado nueve veces.
