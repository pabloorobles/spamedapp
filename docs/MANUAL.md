# Manual de uso — Spamed Travel

## La idea general

Cada venta es un **file**. El file guarda cuánto le cobrás al cliente y cuánto
le pagás al proveedor. Toda la plata que entra o sale se carga en la **caja**,
y cada movimiento se ata al file correspondiente. Con eso el programa calcula
solo los saldos, el estado de la venta, la ganancia y la comisión del vendedor.

**No se cargan saldos a mano.** Si un número no cierra, faltan o sobran
movimientos de caja.

---

## Cómo se navega

A la izquierda está la **barra lateral**: *Operación* (Tablero, Reservas,
Caja), *Maestros* (Clientes, Vendedores, Proveedores) y *Análisis* (Reportes,
Cierre contable). Abajo, **Ajustes** y **Herramientas**.

Todo se hace con botones, sin combinaciones de teclas. Cada pantalla tiene su
título arriba, con los botones de acción principales a la derecha.

## Secciones

### Tablero
Lo que hay que mirar a la mañana: cuánto hay a cobrar, cuánto a pagar, la
ganancia de los files en curso, el neto de caja del mes y la lista de alertas
(señas y reservas vencidas, viajes que salen sin estar pagados al proveedor).

### Reservas
La grilla de todos los files. Además del buscador y los filtros por estado y
moneda, hay un **filtro por rango de fechas** que se puede aplicar sobre la
fecha de reserva, la de salida o el vencimiento.

El formulario de cada file tiene siete solapas:

| Solapa | Para qué |
|---|---|
| Datos generales | cliente, vendedor, proveedor, importes y comisiones |
| Detalle del viaje | fechas, transporte, hotel, régimen, excursiones |
| Servicios | varios proveedores en un mismo file |
| Pasajeros | quiénes viajan, con documento y pasaporte |
| Plan de pagos | en cuántas cuotas paga y cuándo vence cada una |
| Movimientos | los cobros y pagos ya registrados |
| Adjuntos | vouchers, comprobantes, escaneos |

En los desplegables de cliente, vendedor y proveedor está el botón **+**: si el
que buscás no existe, lo cargás ahí mismo sin perder lo que ya escribiste. Buscador por file, cliente, destino, proveedor o
vendedor, y filtros por estado y moneda. Abajo, los totales de lo que estás
viendo, separados por moneda.

Botones:

- **Nueva reserva** — el número de file se sugiere solo.
- **Editar** — o doble clic en la fila.
- **Registrar cobro** — abre la caja con el saldo del cliente ya cargado.
- **Registrar pago** — ídem con el saldo del proveedor.
- **Duplicar** — clona el file con sus servicios y pasajeros, sin la caja.
  Sirve para grupos y para cotizar variantes.
- **Cotización** — el PDF que se le manda al cliente antes de que reserve.
- **Voucher** — el PDF del viaje ya confirmado.
- **Cancelar file** — pregunta si devolvés plata y cuánto. Si decís que sí,
  genera el egreso en la caja. El file sale de los totales pero se conserva.
  Se puede reactivar.
- **Eliminar** — solo si el file no tiene movimientos de caja.

Las filas en rojo tienen alertas; las grises están canceladas.

### Caja
Todos los ingresos y egresos. Un movimiento puede estar atado a un file o ser
un gasto general de la agencia (sueldos, alquiler, publicidad, impuestos).

El monto siempre se carga **en positivo**; lo que define el signo es el tipo
(ingreso o egreso). Si el movimiento tiene un file asociado, la moneda tiene
que coincidir con la del file: el programa no deja mezclar.

**Cambio de moneda** (botón en la barra de acciones). Sirve para registrar
compra o venta de divisas: comprás dólares con pesos, o vendés dólares para
hacerte de pesos. Se cargan los dos montos —lo que sale y lo que entra— y el
programa arma dos movimientos ligados: un egreso en la moneda que sale y un
ingreso en la que entra. La cotización se calcula sola y queda guardada.

Las monedas **no se consolidan**: pesos y dólares siguen cada uno su propio
saldo en todos los reportes. La operación de cambio no inventa una ganancia,
solo mueve plata de un saldo al otro. En el reporte *Cambios de moneda* ves el
historial con la cotización de cada operación.

Si borrás una de las dos patas de un cambio, se borra la otra también: no
pueden quedar desbalanceadas.

**Imprimir recibo**: seleccionar un cobro asociado a un file y apretar el
botón. Genera un PDF con los datos del cliente, el importe recibido y el saldo
que queda.

### Clientes / Vendedores / Proveedores
ABM clásico. Un registro no se puede borrar si tiene files asociados — se marca
como inactivo, así deja de aparecer en los combos pero se conserva el historial.

En **Clientes** hay dos botones extra: *Seguimiento*, para anotar cada llamada
o mensaje y cuándo hay que volver a contactar, y *Estado de cuenta*, que saca
el PDF con todo lo que compró y lo que debe.

En **Proveedores** se carga la **comisión que te paga** ese mayorista y si se le
transfiere el neto.

En vendedores se carga el **% de comisión** por defecto. Ese porcentaje se puede
pisar file por file desde el formulario de la reserva, con dos campos:

- **Comisión % del file** — un porcentaje distinto solo para esa venta.
- **Comisión fija** — un monto cerrado, que ignora cualquier porcentaje.

Si los dos quedan vacíos, se usa el % del vendedor. Si están los dos, gana el
monto fijo. El valor que resulta se ve en vivo en el resumen del formulario.

### Reportes
Doce reportes, exportables a **Excel** o a **PDF** con membrete:

| Reporte | Para qué |
|---|---|
| Cobros pendientes | a quién llamar hoy, con teléfono y días de atraso |
| Pagos pendientes a proveedores | qué hay que pagar antes de que salga el viaje |
| Caja mensual | ingresos, egresos y neto por mes y moneda |
| Comisiones por vendedor | liquidación del mes |
| Ventas por destino | qué se vende |
| Volumen por proveedor | con quién trabajás más y cuánto le debés |
| Cambios de moneda | historial de compra/venta de divisas con cotización |
| Cuotas por vencer | qué cuota vence y de quién |
| Cumpleaños del mes | para saludar y vender |
| Seguimientos pendientes | a quién hay que recontactar |
| Pasaportes por vencer | antes de que sea un problema |
| Origen de clientes | de dónde vienen (redes, referidos, calle) |

---

## Cómo se calcula la plata

Esta es la cadena, y conviene tenerla clara porque es el corazón del sistema:

```
Importe al cliente             $ 1.000.000
× comisión del mayorista 12%  → $   120.000   ← lo que gana la agencia
− comisión del vendedor 20%   → $    24.000   ← lo que le toca a él
                                $    96.000   ← queda para la agencia
```

El **costo del proveedor se calcula solo**: es el importe menos tu comisión
($ 880.000 en el ejemplo). No hace falta cargarlo.

**Dónde se define cada porcentaje:**

- La **comisión del mayorista** se carga en el proveedor, en *Proveedores →
  Comisión que me paga*. Se puede pisar file por file.
- La **comisión del vendedor** se carga en el vendedor. También se puede pisar
  por file, con un porcentaje distinto o con un monto fijo.

**El flag «Se le transfiere el neto»** define cómo se registra el pago:

- **Tildado** (lo habitual): le pagás la venta menos tu comisión. Un solo
  egreso en caja.
- **Sin tildar**: le pagás el total y él te devuelve la comisión. Ahí cargás
  dos movimientos: el egreso completo, y un ingreso con el concepto
  *Comisión de proveedor*.

Si un file tiene **varios proveedores** (aéreo por un lado, hotel por otro),
se cargan en la solapa *Servicios* y el costo total pasa a ser la suma de
ellos, en lugar del cálculo por porcentaje.

---

## Los estados y cómo se calculan

El estado **no se elige a mano**: sale de los cobros, los pagos y las fechas.

| Estado | Cuándo |
|---|---|
| **Cotizado** | recién cargado, sin cobros |
| **Reservado** | el cliente pagó al menos el 20% (configurable) |
| **Confirmado** | el cliente terminó de pagar |
| **Emitido** | está el voucher entregado y el proveedor cobrado |
| **En Viaje** | hoy está entre la salida y el regreso |
| **Finalizado** | ya pasó la fecha de regreso |
| **Vencido** | pasó el vencimiento de reserva y no hay cobros suficientes |
| **Cancelado** | se canceló a mano |

El porcentaje de seña se cambia en **Herramientas → Configuración**.

---

## Flujo típico de una venta

1. **Reservas → Nueva reserva.** Cliente, vendedor, proveedor, destino, importe
   al cliente, costo del proveedor, moneda y los dos vencimientos.
   → queda en *Cotizado*.
2. El cliente seña: seleccionar el file → **Registrar cobro**.
   → pasa a *Reservado*.
3. Se van cargando los pagos parciales del mismo modo.
   Al llegar a cero → *Confirmado*.
4. Se le paga al mayorista: **Registrar pago**.
5. Se entrega el voucher: editar el file y cargar la fecha de entrega.
   → *Emitido*.
6. El viaje ocurre y cierra solo por fecha: *En Viaje* → *Finalizado*.

---

## Cierre contable

La pantalla muestra el **estado del mes en curso** y sirve para cerrar los
meses ya terminados. Por cada moneda, separadas:

- Ventas, comisión de la agencia, comisión de vendedores y **margen**.
- Cobros, pagos a proveedores, gastos generales y **resultado de caja**.
- Objetivo del mes, cumplimiento y variación contra el mes anterior.

Abajo, las **comisiones a liquidar**: cuánto le corresponde a cada vendedor
por los files del período. El botón *Marcar como pagada* genera el egreso en
la caja automáticamente, y *Imprimir liquidación* saca el PDF con el detalle
file por file para que lo firme.

**Generar gastos fijos** crea de una vez los movimientos del mes (alquiler,
sueldos, internet). No duplica los que ya existan.

**Cerrar el mes** guarda una foto de los números. Solo se pueden cerrar meses
terminados. Si después hay que corregir algo, se reabre.

---

## Ajustes

Tres solapas:

- **Listas desplegables** — los valores de todos los menús de la aplicación:
  monedas, medios de pago, conceptos, regímenes, tipos de servicio. Se agregan,
  se renombran, se quitan y se ordenan arrastrando. Así no hay que escribir a
  mano y no se cuelan errores de tipeo.
- **Gastos fijos** — lo que pagás todos los meses, cargado una sola vez.
- **Arqueos de caja** — contás el efectivo y lo comparás con el sistema.

---

## Documentos en PDF

Todos en A4 y con el logo de SpaMed Travel en el membrete:

| Documento | Dónde | Para qué |
|---|---|---|
| **Cotización** | Reservas | el presupuesto que se manda antes de reservar |
| **Voucher** | Reservas | el comprobante del viaje confirmado, con pasajeros y servicios |
| **Recibo** | Caja | constancia de un cobro puntual |
| **Estado de cuenta** | Clientes | todo lo que compró y lo que debe |
| **Liquidación** | Cierre contable | comisiones de un vendedor, para que firme |
| **Cierre del mes** | Cierre contable | el resumen contable completo |
| **Informes** | Reportes | cualquiera de los doce, tal como se ve en pantalla |

El membrete sale de **Herramientas → Configuración → Datos para documentos**.
Ahí se carga dirección, teléfono, legajo EVT y CUIT en una línea.

---

## Backups

Se hace uno automático cada vez que cerrás el programa, en
`%LOCALAPPDATA%\SpamedTravel\backups`.

- **Archivo → Hacer backup ahora** para uno manual.
- **Archivo → Restaurar backup…** para volver atrás (antes de restaurar guarda
  una copia del estado actual, así que no se pierde nada).
- **Archivo → Abrir carpeta de datos** para copiar el `.db` a un pendrive o a
  la nube.

Recomendación: una vez por semana, copiar `spamed.db` a Drive o a un pendrive.

---

## Aspecto

La app viene con la identidad de SpaMed Travel: índigo del logo para la
estructura, turquesa para los acentos y ámbar para las alertas.

Hay **dos temas**, en el menú **Ver**:

- **Claro** — fondo crema pastel, el de las placas de redes. Es el de arranque.
- **Oscuro** — para trabajar de noche o con poca luz.

Se cambia desde **Herramientas → Aspecto de la aplicación**. La elección queda
guardada: la próxima vez arranca con el que dejaste.

Los colores de estado están pensados como señal, no como decoración: celeste y
turquesa para lo que avanza bien, verde para lo cobrado, ámbar para lo vencido
y rojo para lo cancelado. Se leen de un vistazo en la grilla sin tener que
frenar a interpretar.

---

## Atajos

| Tecla | Acción |
|---|---|
| `Ctrl+N` | nueva reserva |
| `Ctrl+M` | nuevo movimiento de caja |
| `Ctrl+K` | nuevo cliente |
| `Ctrl+D` | cambio de moneda |
| `Ctrl+P` | voucher del file seleccionado |
| `Ctrl+T` | alternar tema claro / oscuro |
| `F5` | actualizar todo |
| `Ctrl+Q` | salir |

---

## Diferencias con el Excel

El Excel tenía tres cálculos mal que la aplicación corrige:

1. **Saldo del proveedor.** El Excel sumaba los pagos en vez de restarlos, así
   que la deuda con el mayorista crecía con cada pago y el estado *Emitida*
   nunca daba verdadero.
2. **Signo de los montos de caja.** Convivían positivos y negativos en la misma
   columna; ahora el tipo (ingreso/egreso) está separado del monto.
3. **Carga por macro corrida.** El VBA escribía los datos dos columnas más a la
   derecha de lo que correspondía, por eso transporte, hotel, régimen y
   excursiones quedaban siempre vacíos.

Además: la comisión del vendedor ahora se calcula de verdad con su porcentaje
(en el Excel el campo existía pero no se usaba), los estados se derivan solos en
lugar de tener columnas `VERDADERO`/`FALSO` fijas, y no hay riesgo de romper
fórmulas por insertar una fila o una columna.
