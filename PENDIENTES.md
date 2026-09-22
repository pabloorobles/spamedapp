# Pendientes

Cosas que decidimos **no** hacer todavía, con el motivo y lo que implicaría
retomarlas. No es una lista de deseos: cada punto está acá porque se evaluó y
se pospuso a propósito.

---

## 1. Facturación electrónica (ARCA / ex AFIP)

**Estado:** pospuesto mientras la app esté en demo.
**Decidido el:** 15/08/2026.

### Por qué no está

Hoy los PDFs de la app son documentos internos: el voucher, el recibo y la
cotización sirven para operar con el pasajero, pero **no son comprobantes
fiscales**. El recibo lo aclara en el pie (`core/documentos.py`, función
`html_recibo`). Mientras la agencia siga facturando por fuera, esto no
bloquea nada.

### Qué haría falta para hacerlo

No es un cambio de una tarde. Los pasos reales:

1. **Certificado digital.** Generar el CSR, subirlo a ARCA y asociarlo al
   servicio de facturación electrónica (WSFE). El certificado vence y hay que
   renovarlo — eso es mantenimiento recurrente, no algo que se hace una vez.
2. **Homologación primero.** ARCA tiene dos entornos: homologación (pruebas)
   y producción. Todo se prueba contra homologación antes de emitir un
   comprobante real, porque un comprobante mal emitido en producción no se
   borra: se anula con una nota de crédito.
3. **Punto de venta** habilitado para "web services" en el portal de ARCA.
   Los puntos de venta de talonario o de controlador fiscal no sirven.
4. **Tipo de comprobante.** Definir si la agencia emite factura A, B o C
   según su condición frente al IVA y la del cliente. Para una agencia de
   viajes hay además un régimen especial de IVA sobre la comisión (no sobre
   el total del paquete) que hay que confirmar con el contador antes de
   escribir una línea de código.
5. **Solicitud del CAE** por cada comprobante, guardarlo en la base junto con
   su vencimiento, y contemplar qué pasa si el servicio de ARCA está caído
   (que pasa seguido): la venta no puede quedar bloqueada.
6. **Numeración correlativa** por punto de venta y tipo, sin huecos. Hoy la
   app numera files (`R2601`), que es otra cosa distinta.

### Impacto en el modelo

Tabla nueva `comprobantes` (tipo, punto de venta, número, CAE, vencimiento
del CAE, importe neto, IVA, total, `reserva_id`), y un campo de condición
frente al IVA en `clientes`. La cadena de comisiones actual no se toca.

### Antes de arrancar

Hablarlo con el contador de la agencia. La parte técnica es la mitad del
problema; la otra mitad es fiscal y no la define el programa.

---

## 2. Purga automática de backups viejos

**Estado:** pospuesto mientras la app esté en demo.
**Decidido el:** 15/08/2026.

### Por qué no está

`core/db.py::backup()` genera una copia cada vez que se cierra la app, más
las que se piden a mano desde Herramientas, y **nunca borra ninguna**. Los
archivos van a `%LOCALAPPDATA%\SpamedTravel\backups\`.

En demo esto es una ventaja, no un problema: si algo sale mal hay historial
completo para volver atrás. Y son archivos SQLite chicos — con la base actual,
meses de uso diario ocupan poco.

### Por qué no se toca ahora

Es la única funcionalidad de la lista que **borra archivos**. Un error de
signo o de comparación de fechas en la regla de purga se lleva puestos los
resguardos justo cuando más falta hacen. No es el momento de correr ese
riesgo.

### Qué haría falta

Una política de retención en `db.backup()`, del estilo: conservar todos los
de los últimos 7 días, uno por día del último mes, uno por mes más atrás.
Antes de activarla:

- que sea **configurable y desactivable** desde Ajustes;
- que la primera versión sólo **informe** qué borraría, sin borrar nada, para
  poder revisarlo;
- prueba dedicada en la suite, con archivos de fecha simulada;
- nunca borrar el más reciente, pase lo que pase con la regla.

### Cuándo revisarlo

Cuando la carpeta de backups moleste de verdad. Revisar el tamaño con:

```powershell
Get-ChildItem "$env:LOCALAPPDATA\SpamedTravel\backups" | Measure-Object -Property Length -Sum
```
