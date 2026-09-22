# Rediseño grande — seguimiento

Roadmap del rediseño pedido el 16/08/2026: Inicio, estados por pestaña,
renombre a Operador, columnas nuevas en varias pantallas, cierre con BCRA,
reorganización de Ajustes. Dividido en etapas porque tocar todo junto era
demasiado riesgo de una sola vez.

**Cómo se usa este archivo**: un casillero se tilda `[x]` solo cuando esa
tarea está *verificada* — compila, pasan `test_negocio.py` y
`test_interfaz.py`, y se probó a mano en la app — no apenas escrita. Se
actualiza en el mismo commit que cierra el trabajo. El detalle de diseño y
las decisiones de cada etapa vivieron primero en el plan de la sesión que la
implementó; acá queda el resumen y el estado.

---

## Etapa 1 — Renombres, columnas nuevas y reorganización de Ajustes

**Estado: completada** (16/08/2026)

Detalle de dos decisiones tomadas durante la implementación, no anticipadas
en el plan original:
- La página nueva se llama **"Caja y gastos"** y quedó ubicada junto a
  Ajustes y Herramientas en la barra lateral (no dentro de Ajustes).
- "Ajustes" pasó a mostrar directamente el panel de listas, sin envolverlo
  en solapas de una sola pestaña — una pestaña única quedaba rara.

Sin cambios al motor de comisiones ni tablas nuevas para funcionalidad que
todavía no está diseñada en detalle (eso es Etapa 2+).

- [x] Archivo `REDISENO.md` creado (este archivo)
- [x] Renombrar "Proveedor" → "Operador" en toda la UI (solo texto visible;
      tablas, columnas y clases internas quedan igual)
- [x] Reservas: "Importe" → "Importe de venta", "Costo" → "Importe neto",
      "Ganancia" → "Ganancia bruta" (+ arreglar que no se formateaba en
      moneda), "Comisión" → "Comisión vendedor", nueva columna "Ganancia
      neta" (margen_neto)
- [x] Clientes: columna Cumpleaños + filtro por mes, columna Última
      interacción (máximo entre último seguimiento y última reserva) +
      aviso de +3 meses sin novedades, columna Alertas
- [x] Vendedores: migración `fecha_nac` (probada sobre copia de la base
      real), columnas Email / Cumpleaños / Última venta / Ganancia generada
      (por moneda, sin consolidar) / Alertas, desglose de "Files" en
      Cotizados / Reservados / Cancelados
- [x] Operadores: columna Facturación (pagado real a ese operador, por
      moneda)
- [x] Inicio (ex Tablero): renombrado, sacado el botón Actualizar
      (el refresco ya es automático)
- [x] Ajustes: Gastos fijos y Arqueos mudados a la página nueva
      "Caja y gastos", sumada una solapa de Gastos extraordinarios
      (movimientos de caja sin file y sin venir de un gasto fijo);
      Ajustes queda solo con Listas desplegables
- [x] Pruebas de interfaz ampliadas para lo de arriba (test_interfaz.py pasó
      de 62 a 78 casos), las dos suites pasando (57 + 78), y probado sobre
      una copia de la base real: 8 clientes, 5 vendedores, 5 operadores,
      20 reservas y 76 movimientos, todo intacto después de migrar

---

## Etapa 2, parte 1 — Pestañas por estado

**Estado: completada** (16/08/2026)

Antes de tocar código se detectaron tres choques entre cómo Pablo describió
los estados y cómo los calculaba la app (motor 100% automático, sin campos
manuales). Se confirmaron con él y quedaron así — el detalle completo, en
criollo, vive en `calculos.estado_reserva()`:

1. **Se sumó un paso nuevo**: "Reservado" ahora es cuando el cliente dijo
   que sí (reutiliza `fecha_reserva`, que antes no afectaba el estado), sin
   haber pagado nada todavía. Lo que antes se llamaba "Reservado" (seña
   cobrada) ahora es "Confirmado".
2. **"Emitido" cambió de significado**: antes era "ya le di el voucher al
   cliente"; ahora es "está todo pagado — cliente y operador — y estoy
   esperando que el operador me mande el voucher" (campo nuevo,
   `voucher_recibido`, sin relación con el que ya existía para el cliente).
3. **La encuesta no se manda sola**: se genera en PDF, Pablo la manda a
   mano (WhatsApp, mail) y la respuesta se carga a mano en la app. Sin
   credenciales de correo guardadas.

Orden final de prioridad: `Cancelado > Finalizado > En Viaje > Emitido >
Confirmado > Vencido > Reservado > Cotizado`. "Vencido" pasa por encima de
"Reservado" a propósito: haber dicho que sí no protege del vencimiento si
no hay plata en juego.

- [x] Migración `reservas.voucher_recibido` + motor de estados reescrito
      (probado sobre copia de la base real: 21 files reales recalculados
      sin excepciones, sin perder ni cambiar ningún registro)
- [x] `test_negocio.py` reescrito para la cadena nueva + casos para lo que
      no existía (Reservado sin pago, Vencido gana sobre Reservado)
- [x] Reservas: pestaña "Todos" + una por cada uno de los 8 estados,
      reutilizando el mismo panel de filtros/grilla/acciones parametrizado
- [x] Reservado: botón "Marcar OK del cliente" (carga `fecha_reserva`)
- [x] Emitido: columna "Voucher operador" + botón "Marcar voucher recibido"
- [x] Confirmado: adjuntar comprobante a un movimiento de caja puntual
      (migración `adjuntos.movimiento_id`, reutiliza el diálogo de
      documentación ya existente); exportar recibo ya existía
- [x] Finalizado: encuesta de satisfacción — tabla `encuestas` nueva,
      PDF con 3 preguntas de 1 a 5 + comentario, diálogo para cargar la
      respuesta a mano, reporte "Encuestas sin responder" en Reportes
- [x] Vencido: botón "Exportar resumen por cliente" (reutiliza
      `documentos.informe()`, sin backend nuevo)
- [x] Cancelado: lista `motivo_cancelacion` nueva (editable desde Ajustes),
      el motivo libre pasó a ser un combo + detalle opcional
- [x] `test_interfaz.py` ampliado (78 → 100+ casos) para cada pieza de
      arriba; las dos suites pasando y verificado sobre copia de la base
      real — 21 files, 9 clientes, 6 vendedores, 5 operadores, 78
      movimientos, todo intacto después de migrar

---

## Etapa 2, parte 2 — variantes, filtros de Inicio, DNI/tarjetas, BCRA y periodicidad

**Estado: completada** (17/08/2026)

Dos decisiones tomadas antes de tocar código (confirmadas con Pablo):
- La cotización del dólar sale de **dolarapi.com** (espejo confiable de la
  oficial/BCRA) en vez de la API oficial de bcra.gob.ar, que tiene problemas
  de certificado SSL conocidos. Se guarda la última cotización obtenida (con
  fecha) en `parametros`, así el cierre sigue funcionando offline mostrando
  "última conocida" en vez de romperse.
- Los datos de tarjeta son **solo de referencia**: marca, últimos 4 dígitos
  y vencimiento (texto MM/AA). Nunca el número completo ni el CVV — no hay
  cifrado en la app como para guardar eso con responsabilidad.

- [x] Modelo de variantes del operador: tabla `proveedor_variantes`
      (operador × Nacional/Internacional × moneda, hasta 4 por operador),
      columna `reservas.tipo_viaje` (opcional). Sin tipo de viaje cargado en
      el file, nada cambia — la comisión general del operador sigue
      mandando exactamente igual que antes. `DialogoProveedor` suma la
      sección de variantes (solo al editar), `DialogoReserva` suma el combo
      y la vista previa en vivo usa la variante que corresponda
- [x] Inicio: filtro de moneda + rango de fechas ("Mes actual" como atajo),
      "Caja del mes" pasó a "Caja del período", tabla nueva "Pagos
      pendientes a operadores" (reutiliza `Reportes.pagos_pendientes()`,
      que ya existía para Reportes)
- [x] Clientes: `dni_vencimiento` + botón "Tarjetas…" (mismo patrón que
      "Documentación") para cargar/ver/borrar tarjetas de referencia;
      reportes nuevos "DNI por vencer" y "Tarjetas por vencer"
- [x] Cierre: panel "Resumen consolidado (informativo)" — convierte lo que
      no es pesos a su equivalente en pesos con la cotización del BCRA y
      muestra el total sumado, aclarado como informativo. Los totales por
      moneda de arriba **no se tocan**, siguen exactamente iguales.
      `core/bcra.py` nuevo (primera vez que la app sale a internet):
      `urllib.request` sin dependencias nuevas, timeout de 6 segundos, si
      falla (sin conexión, sitio caído) avisa y no pisa la última
      cotización guardada
- [x] Gastos fijos: `periodicidad` (Mensual/Bimestral/Trimestral/Semestral/
      Anual), `fecha_inicio`/`fecha_fin`, `cantidad_cuotas` +
      `cuotas_generadas` como contador interno. Sin `fecha_inicio` cargada
      se comporta igual que antes (mensual sin límite)
- [x] Las dos suites ampliadas y pasando — `test_negocio.py` (78 casos) y
      `test_interfaz.py` (140 casos) — y probado sobre una copia de la base
      real: 9 clientes, 6 vendedores, 5 operadores, 21 reservas y 78
      movimientos, todo intacto después de migrar; tablas y columnas nuevas
      presentes y vacías (nadie cargó variantes/tarjetas/gastos todavía en
      la base real)

**Limitación conocida**: el fetch online de `bcra.py` no se pudo probar de
punta a punta en el entorno de desarrollo (sin salida a internet ahí). Se
verificó por separado: el camino de éxito con datos simulados, el camino de
error (sin red y con una URL inválida) cayendo prolijo a la última
cotización guardada, y que una cotización guardada nunca se pisa por un
fetch fallido. **Falta que Pablo haga un clic de "Actualizar cotización"
en su PC** para confirmar el camino feliz contra el sitio real.

---

## Identidad de marca — paleta, tipografía, íconos y PDFs

**Estado: completada** (17/08/2026)

No es parte del rediseño original: Pablo mandó el Manual de Marca oficial
de SpaMed Travel (v1.0, 2026) más los templates que usa hoy en papel
(voucher, liquidación, recibos, libro de reservas, presupuesto) y pidió
alinear el diseño de la app a eso. Antes de tocar código se resolvieron
tres decisiones de alcance con Pablo (`AskUserQuestion`):

- **Tipografía**: se integran Outfit e Instrument Sans de verdad (Pablo
  baja los `.ttf`), no la alternativa de sistema — aunque esa alternativa
  queda igual como *fallback automático* si los archivos no están.
- **PDFs**: solo se les aplica la paleta y tipografía de marca. No se
  replica el formato fiscal real de los templates en papel (numeración,
  ORIGINAL/DUPLICADO, CUIT/IVA, textos legales de cancelación) — eso es un
  cambio de contenido, no de diseño, y habría que revisarlo dato por dato.
  Queda como posible tarea aparte si se quiere más adelante.
- **Íconos**: se suma una familia de íconos lineales (2px, sin relleno) a
  la barra lateral. La barra **no tenía ningún ícono antes** — es 100%
  agregado, no reemplazo.

- [x] `core/tema.py`: paleta reemplazada por los HEX exactos del manual
      (Azul Profundo `#2E2E8C`, Verde Petróleo `#1E7A8C`, Naranja Sol
      `#F0A848`, Arena `#F6F2EC`, Grafito `#16161F`, + 3 colores de apoyo).
      La barra lateral pasa de índigo a Verde Petróleo ("secundario:
      barras, bloques de interfaz" según el manual). El botón de acento
      (naranja) usa texto azul profundo, no blanco — el manual prohíbe
      expresamente "blanco sobre naranja"; ese mismo ajuste corrigió un
      hover que ya incurría en esa combinación sin que se notara.
      Estados de reserva remapeados a los colores de apoyo (Reservado →
      Celeste Cielo, Confirmado → Verde Palma, Emitido → Verde Petróleo).
- [x] Tipografía: `app.py` carga `recursos/fuentes/Outfit.ttf` y
      `InstrumentSans.ttf` si existen (`QFontDatabase`); si no están,
      no rompe nada — el QSS y el CSS de los PDFs ya tienen Verdana/Arial
      como alternativa de sistema, la misma que habilita el propio manual
      para cuando no se pueden instalar las fuentes.
- [x] 11 íconos lineales nuevos en `recursos/iconos/` (uno por sección de
      la barra lateral), dibujados a mano siguiendo la spec del manual
      (24×24, trazo 2px, esquinas redondeadas, sin relleno).
      `BarraLateral.item()`/`accion()` los muestra con `QIcon`.
- [x] `core/documentos.py`: la hoja de estilos compartida por los 8 tipos
      de PDF (voucher, recibo, encuesta, cotización, estado de cuenta,
      liquidación, informe, cierre) usa los mismos colores y tipografía —
      un solo cambio, sin tocar contenido ni estructura de ningún
      documento.
- [x] Limpieza: un `#C27C24` hardcodeado en `ajustes.py` (color de alerta
      del arqueo) pasó a `color("alerta")`, siguiendo la convención del
      propio `CLAUDE.md`.
- [x] `build/spamed.spec`: entradas nuevas para los 11 SVG y (si existen)
      los 2 `.ttf`. Se agregó también `from PySide6 import QtSvg` en
      `navegacion.py` — sin esa importación explícita, PyInstaller no
      detecta que hace falta el plugin de SVG y los íconos quedarían
      vacíos en el `.exe` aunque anden perfecto en modo desarrollo.
- [x] Las dos suites pasando sin casos nuevos (es diseño visual, no
      comportamiento) y captura de pantalla de la app renderizada
      offscreen para revisar paleta e íconos antes de cerrar.

**Fuentes**: Pablo bajó `Outfit.ttf` e `InstrumentSans.ttf` (fuentes
variables) de Google Fonts y quedaron en `src/spamed/recursos/fuentes/`.
Se confirmó que registran exactamente como `"Outfit"` e `"Instrument
Sans"` (los mismos nombres que usan `tema.py` y `documentos.py`), y una
captura con las fuentes ya cargadas mostró la tipografía de marca
correctamente tanto en la interfaz como en un voucher de muestra
renderizado. `build/spamed.spec` ya las empaqueta si están presentes.

**Limitaciones conocidas del entorno de desarrollo** (no de la app):
- El modo offscreen de Qt en este entorno no tiene ninguna fuente de
  sistema registrada (se confirmó con `QFontInfo`): antes de sumar los
  `.ttf` de marca, cualquier captura mostraba el texto como recuadros
  vacíos sin importar la fuente pedida. Con los archivos bundleados el
  problema desapareció — en la PC de Pablo, con fuentes de sistema reales,
  nunca hubiera pasado.
- No se puede previsualizar un PDF completo con paginado real
  (`pdftoppm` no está instalado en este entorno); se verificó
  renderizando el `QTextDocument` de un voucher de muestra a una imagen
  (mismo motor que usa `guardar_pdf()`, sin el paginado a A4) y
  confirmando que los colores y tipografías de marca se aplican bien.

---

## Pospuesto indefinidamente

Ver [PENDIENTES.md](PENDIENTES.md): facturación electrónica ARCA/AFIP y
purga automática de backups. No forman parte de este rediseño.
