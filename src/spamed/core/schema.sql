-- Esquema Spamed Travel v1
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clientes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dni             TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    apellido        TEXT    NOT NULL,
    telefono        TEXT,
    email           TEXT,
    direccion       TEXT,
    fecha_nac       TEXT,
    dni_vencimiento TEXT,
    fecha_alta      TEXT    NOT NULL DEFAULT (date('now','localtime')),
    canal           TEXT,
    detalle_canal   TEXT,
    observaciones   TEXT,
    activo          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS vendedores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dni             TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    apellido        TEXT    NOT NULL,
    telefono        TEXT,
    email           TEXT,
    fecha_nac       TEXT,
    comision_pct    REAL    NOT NULL DEFAULT 0,
    fecha_alta      TEXT    NOT NULL DEFAULT (date('now','localtime')),
    activo          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS proveedores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL UNIQUE,
    tipo            TEXT,
    moneda          TEXT    NOT NULL DEFAULT 'PESOS',
    contacto        TEXT,
    telefono        TEXT,
    email           TEXT,
    observaciones   TEXT,
    -- % sobre la venta que el mayorista reconoce como comision de la agencia
    comision_pct    REAL    NOT NULL DEFAULT 0,
    -- 1 = se le transfiere el neto (venta - comision) en un solo egreso
    -- 0 = se le paga el total y devuelve la comision como ingreso aparte
    transfiere_neto INTEGER NOT NULL DEFAULT 1,
    activo          INTEGER NOT NULL DEFAULT 1
);

-- Hasta 4 comisiones distintas por operador, segun si el viaje es
-- Nacional/Internacional y en que moneda. Si un file no elige tipo_viaje, o
-- no hay variante cargada para esa combinacion, se usa la comision general
-- de arriba (ver v_reservas_saldos).
CREATE TABLE IF NOT EXISTS proveedor_variantes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proveedor_id    INTEGER NOT NULL REFERENCES proveedores(id) ON DELETE CASCADE,
    tipo_viaje      TEXT    NOT NULL CHECK (tipo_viaje IN ('Nacional','Internacional')),
    moneda          TEXT    NOT NULL DEFAULT 'PESOS',
    comision_pct    REAL    NOT NULL DEFAULT 0,
    transfiere_neto INTEGER NOT NULL DEFAULT 1,
    UNIQUE (proveedor_id, tipo_viaje, moneda)
);
CREATE INDEX IF NOT EXISTS ix_provvar_proveedor ON proveedor_variantes(proveedor_id);

CREATE TABLE IF NOT EXISTS reservas (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    file                  TEXT    NOT NULL UNIQUE,
    cliente_id            INTEGER NOT NULL REFERENCES clientes(id),
    vendedor_id           INTEGER NOT NULL REFERENCES vendedores(id),
    proveedor_id          INTEGER NOT NULL REFERENCES proveedores(id),
    destino               TEXT,
    moneda                TEXT    NOT NULL DEFAULT 'PESOS',
    tipo_viaje            TEXT,   -- Nacional/Internacional, opcional; ver proveedor_variantes
    importe_cliente       REAL    NOT NULL DEFAULT 0,
    costo_proveedor       REAL    NOT NULL DEFAULT 0,
    cant_pasajeros        INTEGER NOT NULL DEFAULT 1,
    fecha_cotizacion      TEXT,
    fecha_reserva         TEXT,
    fecha_vto_sena        TEXT,
    fecha_vto_reserva     TEXT,
    fecha_entrega_voucher TEXT,
    voucher_recibido      TEXT,   -- del operador a la agencia; ver calculos.estado_reserva
    fecha_salida          TEXT,
    fecha_regreso         TEXT,
    transporte            TEXT,
    hotel                 TEXT,
    regimen               TEXT,
    excursiones           TEXT,
    comision_pct          REAL,          -- % del vendedor, pisa el del maestro
    comision_monto        REAL,          -- monto fijo del vendedor
    comision_prov_pct     REAL,          -- % del mayorista, pisa el del maestro
    transfiere_neto       INTEGER,       -- pisa el flag del proveedor
    devolucion            REAL NOT NULL DEFAULT 0,
    cancelada             INTEGER NOT NULL DEFAULT 0,
    motivo_cancelacion    TEXT,
    notas                 TEXT,
    creado_en             TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    actualizado_en        TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS ix_reservas_cliente   ON reservas(cliente_id);
CREATE INDEX IF NOT EXISTS ix_reservas_vendedor  ON reservas(vendedor_id);
CREATE INDEX IF NOT EXISTS ix_reservas_proveedor ON reservas(proveedor_id);

-- Los montos SIEMPRE se guardan positivos; el signo lo define 'tipo'.
CREATE TABLE IF NOT EXISTS movimientos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT    NOT NULL,
    tipo        TEXT    NOT NULL CHECK (tipo IN ('INGRESO','EGRESO')),
    concepto    TEXT    NOT NULL,
    reserva_id  INTEGER REFERENCES reservas(id) ON DELETE SET NULL,
    moneda      TEXT    NOT NULL DEFAULT 'PESOS',
    monto       REAL    NOT NULL CHECK (monto >= 0),
    medio_pago  TEXT,
    detalle     TEXT,
    operacion   TEXT,
    cotizacion  REAL,
    creado_en   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS ix_mov_operacion ON movimientos(operacion);

CREATE INDEX IF NOT EXISTS ix_mov_reserva ON movimientos(reserva_id);
CREATE INDEX IF NOT EXISTS ix_mov_fecha   ON movimientos(fecha);

CREATE TABLE IF NOT EXISTS parametros (
    clave TEXT PRIMARY KEY,
    valor TEXT
);

-- Listas desplegables editables (equivalente a la hoja Helper del Excel).
CREATE TABLE IF NOT EXISTS listas (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo   TEXT    NOT NULL,
    valor  TEXT    NOT NULL,
    orden  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (tipo, valor)
);

-- ===========================================================  TABLAS NUEVAS

-- Servicios del file: permite varios proveedores por reserva (aereo, hotel,
-- excursiones). Si un file no tiene servicios, se usa costo_proveedor.
CREATE TABLE IF NOT EXISTS reserva_servicios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    reserva_id    INTEGER NOT NULL REFERENCES reservas(id) ON DELETE CASCADE,
    proveedor_id  INTEGER NOT NULL REFERENCES proveedores(id),
    concepto      TEXT    NOT NULL,
    detalle       TEXT,
    importe_venta REAL    NOT NULL DEFAULT 0,
    costo         REAL    NOT NULL DEFAULT 0,
    orden         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_serv_reserva ON reserva_servicios(reserva_id);

-- Pasajeros del file, con los datos que van al voucher.
CREATE TABLE IF NOT EXISTS pasajeros (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    reserva_id   INTEGER NOT NULL REFERENCES reservas(id) ON DELETE CASCADE,
    nombre       TEXT    NOT NULL,
    documento    TEXT,
    fecha_nac    TEXT,
    pasaporte    TEXT,
    vto_pasaporte TEXT,
    observaciones TEXT,
    orden        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_pax_reserva ON pasajeros(reserva_id);

-- Tarjetas del cliente, SOLO a modo de referencia: jamas el numero completo
-- ni el CVV, unicamente los ultimos 4 digitos. No sirve para cobrar, es
-- para saber con que tarjeta suele pagar.
CREATE TABLE IF NOT EXISTS tarjetas_cliente (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    marca       TEXT,
    ultimos4    TEXT,
    vencimiento TEXT,   -- MM/AA tal cual figura en la tarjeta, texto libre
    nota        TEXT,
    creado_en   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_tarj_cliente ON tarjetas_cliente(cliente_id);

-- Plan de pagos: cuotas previstas del cliente.
CREATE TABLE IF NOT EXISTS cuotas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reserva_id  INTEGER NOT NULL REFERENCES reservas(id) ON DELETE CASCADE,
    numero      INTEGER NOT NULL DEFAULT 1,
    vencimiento TEXT    NOT NULL,
    importe     REAL    NOT NULL DEFAULT 0,
    nota        TEXT
);
CREATE INDEX IF NOT EXISTS ix_cuota_reserva ON cuotas(reserva_id);

-- Archivos enlazados al file, al cliente, al vendedor o a un pago puntual
-- (comprobante de una transferencia). Se guarda la ruta, no el contenido.
CREATE TABLE IF NOT EXISTS adjuntos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    reserva_id   INTEGER REFERENCES reservas(id) ON DELETE CASCADE,
    cliente_id   INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
    vendedor_id  INTEGER REFERENCES vendedores(id) ON DELETE CASCADE,
    movimiento_id INTEGER REFERENCES movimientos(id) ON DELETE CASCADE,
    titulo       TEXT    NOT NULL,
    ruta         TEXT    NOT NULL,
    agregado_en  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
-- Ojo: los indices sobre vendedor_id y movimiento_id NO van aca. Este script
-- corre entero antes que las migraciones, asi que en una base vieja esas
-- columnas todavia no existen y el CREATE INDEX tumbaria el executescript
-- completo. Se crean en db.py::_migrar(), despues del ALTER TABLE.
CREATE INDEX IF NOT EXISTS ix_adj_reserva ON adjuntos(reserva_id);
CREATE INDEX IF NOT EXISTS ix_adj_cliente ON adjuntos(cliente_id);

-- Seguimiento comercial: llamadas, mails, visitas.
CREATE TABLE IF NOT EXISTS seguimientos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    reserva_id  INTEGER REFERENCES reservas(id) ON DELETE SET NULL,
    fecha       TEXT    NOT NULL,
    canal       TEXT,
    nota        TEXT    NOT NULL,
    proximo     TEXT,
    creado_en   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_seg_cliente ON seguimientos(cliente_id);

-- Encuesta de satisfaccion al Finalizar el viaje. Se genera en PDF (no hay
-- envio automatico) y la respuesta se carga a mano cuando el cliente
-- contesta. Puntajes de 1 a 5.
CREATE TABLE IF NOT EXISTS encuestas (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    reserva_id           INTEGER NOT NULL REFERENCES reservas(id) ON DELETE CASCADE,
    fecha_generada       TEXT    NOT NULL DEFAULT (date('now','localtime')),
    fecha_respuesta      TEXT,
    puntaje_atencion     INTEGER,
    puntaje_expectativas INTEGER,
    puntaje_recomendaria INTEGER,
    comentario           TEXT
);
CREATE INDEX IF NOT EXISTS ix_enc_reserva ON encuestas(reserva_id);

-- Cierres contables mensuales: congelan la foto del mes.
CREATE TABLE IF NOT EXISTS cierres (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    anio       INTEGER NOT NULL,
    mes        INTEGER NOT NULL,
    moneda     TEXT    NOT NULL,
    resumen    TEXT    NOT NULL,
    cerrado_en TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    nota       TEXT,
    UNIQUE (anio, mes, moneda)
);

-- Gastos que se repiten cada tanto (Mensual por defecto).
CREATE TABLE IF NOT EXISTS gastos_fijos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto        TEXT    NOT NULL,
    moneda          TEXT    NOT NULL DEFAULT 'PESOS',
    importe         REAL    NOT NULL DEFAULT 0,
    dia_mes         INTEGER NOT NULL DEFAULT 1,
    medio_pago      TEXT,
    activo          INTEGER NOT NULL DEFAULT 1,
    ultimo_generado TEXT,
    -- Mensual/Bimestral/Trimestral/Semestral/Anual. Sin fecha_inicio
    -- cargada, se comporta como siempre (mensual sin limite).
    periodicidad    TEXT    NOT NULL DEFAULT 'Mensual',
    fecha_inicio    TEXT,
    fecha_fin       TEXT,
    cantidad_cuotas INTEGER,
    cuotas_generadas INTEGER NOT NULL DEFAULT 0
);

-- Liquidaciones de comision al vendedor.
CREATE TABLE IF NOT EXISTS liquidaciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vendedor_id  INTEGER NOT NULL REFERENCES vendedores(id),
    anio         INTEGER NOT NULL,
    mes          INTEGER NOT NULL,
    moneda       TEXT    NOT NULL,
    importe      REAL    NOT NULL DEFAULT 0,
    detalle      TEXT,
    pagada       INTEGER NOT NULL DEFAULT 0,
    movimiento_id INTEGER REFERENCES movimientos(id) ON DELETE SET NULL,
    creada_en    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (vendedor_id, anio, mes, moneda)
);

-- Arqueos de caja: efectivo contado contra efectivo del sistema.
CREATE TABLE IF NOT EXISTS arqueos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT    NOT NULL,
    moneda      TEXT    NOT NULL DEFAULT 'PESOS',
    saldo_sistema REAL  NOT NULL DEFAULT 0,
    saldo_contado REAL  NOT NULL DEFAULT 0,
    diferencia  REAL    NOT NULL DEFAULT 0,
    nota        TEXT,
    creado_en   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Objetivo de ventas por mes y moneda.
CREATE TABLE IF NOT EXISTS objetivos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    anio    INTEGER NOT NULL,
    mes     INTEGER NOT NULL,
    moneda  TEXT    NOT NULL DEFAULT 'PESOS',
    importe REAL    NOT NULL DEFAULT 0,
    UNIQUE (anio, mes, moneda)
);

-- Vista de saldos y comisiones.
--
-- Cadena economica:
--   importe_cliente                      lo que paga el pasajero
--   x comision_prov_pct                  lo que el mayorista reconoce a la agencia
--   = comision_agencia
--   - comision_vendedor                  la parte del vendedor
--   = margen_neto                        lo que le queda a la agencia
--
-- El costo del proveedor sale de los servicios cargados; si el file no tiene
-- servicios, se usa importe - comision_agencia (o costo_proveedor si se
-- cargo a mano y no hay comision definida).
CREATE VIEW IF NOT EXISTS v_reservas_saldos AS
WITH serv AS (
    SELECT reserva_id, SUM(costo) costo, SUM(importe_venta) venta,
           COUNT(*) cantidad
    FROM reserva_servicios GROUP BY reserva_id
),
ing AS (
    SELECT reserva_id, SUM(monto) total FROM movimientos
    WHERE tipo = 'INGRESO' AND reserva_id IS NOT NULL
      AND COALESCE(concepto,'') <> 'Comision de proveedor'
    GROUP BY reserva_id
),
com_dev AS (
    SELECT reserva_id, SUM(monto) total FROM movimientos
    WHERE tipo = 'INGRESO' AND reserva_id IS NOT NULL
      AND concepto = 'Comision de proveedor'
    GROUP BY reserva_id
),
egr AS (
    SELECT reserva_id, SUM(monto) total FROM movimientos
    WHERE tipo = 'EGRESO' AND reserva_id IS NOT NULL
      AND COALESCE(concepto,'') <> 'Devolucion a cliente'
    GROUP BY reserva_id
),
dev AS (
    SELECT reserva_id, SUM(monto) total FROM movimientos
    WHERE tipo = 'EGRESO' AND reserva_id IS NOT NULL
      AND concepto = 'Devolucion a cliente'
    GROUP BY reserva_id
),
pax AS (
    SELECT reserva_id, COUNT(*) cantidad FROM pasajeros GROUP BY reserva_id
),
base AS (
    SELECT
        r.*,
        c.apellido || ', ' || c.nombre AS cliente,
        c.dni       AS cliente_dni,
        c.telefono  AS cliente_telefono,
        c.email     AS cliente_email,
        v.apellido || ', ' || v.nombre AS vendedor,
        p.nombre    AS proveedor,
        COALESCE(r.comision_pct, v.comision_pct)                    AS pct_vendedor,
        -- La variante (nacional/internacional x moneda) pisa la comision
        -- general del operador; el file puede seguir pisando todo a mano.
        COALESCE(r.comision_prov_pct, pv.comision_pct, p.comision_pct)     AS pct_proveedor,
        COALESCE(r.transfiere_neto, pv.transfiere_neto, p.transfiere_neto, 1) AS neto,
        COALESCE(s.costo, 0)       AS costo_servicios,
        COALESCE(s.cantidad, 0)    AS cant_servicios,
        COALESCE(ing.total, 0)     AS cobrado_cliente,
        COALESCE(egr.total, 0)     AS pagado_proveedor,
        COALESCE(com_dev.total, 0) AS comision_recibida,
        COALESCE(dev.total, 0)     AS devuelto,
        COALESCE(pax.cantidad, 0)  AS cant_pasajeros_cargados
    FROM reservas r
    JOIN clientes    c ON c.id = r.cliente_id
    JOIN vendedores  v ON v.id = r.vendedor_id
    JOIN proveedores p ON p.id = r.proveedor_id
    LEFT JOIN proveedor_variantes pv ON pv.proveedor_id = r.proveedor_id
                                     AND pv.tipo_viaje = r.tipo_viaje
                                     AND pv.moneda = r.moneda
    LEFT JOIN serv s      ON s.reserva_id = r.id
    LEFT JOIN ing         ON ing.reserva_id = r.id
    LEFT JOIN egr         ON egr.reserva_id = r.id
    LEFT JOIN com_dev     ON com_dev.reserva_id = r.id
    LEFT JOIN dev         ON dev.reserva_id = r.id
    LEFT JOIN pax         ON pax.reserva_id = r.id
),
calc AS (
    SELECT base.*,
        CASE WHEN pct_proveedor > 0
             THEN importe_cliente * pct_proveedor / 100.0
             ELSE importe_cliente - costo_efectivo_previo
        END AS comision_agencia
    FROM (SELECT base.*,
                 CASE WHEN cant_servicios > 0 THEN costo_servicios
                      ELSE costo_proveedor END AS costo_efectivo_previo
          FROM base) base
)
SELECT
    id, file, cliente_id, vendedor_id, proveedor_id, destino, moneda,
    tipo_viaje, importe_cliente, cant_pasajeros, cancelada, motivo_cancelacion,
    fecha_cotizacion, fecha_reserva, fecha_vto_sena, fecha_vto_reserva,
    fecha_entrega_voucher, voucher_recibido, fecha_salida, fecha_regreso,
    transporte, hotel, regimen, excursiones, notas,
    comision_monto, comision_prov_pct, devolucion,
    cliente, cliente_dni, cliente_telefono, cliente_email,
    vendedor, proveedor,
    pct_vendedor AS comision_pct,
    pct_proveedor,
    neto AS transfiere_neto,
    cant_servicios, cant_pasajeros_cargados,
    cobrado_cliente, pagado_proveedor, comision_recibida, devuelto,

    comision_agencia,

    -- Costo real del proveedor: los servicios mandan; si no hay, se deriva
    -- de la comision; y si tampoco hay comision, se usa lo cargado a mano.
    CASE WHEN cant_servicios > 0 THEN costo_servicios
         WHEN pct_proveedor > 0  THEN importe_cliente - comision_agencia
         ELSE costo_proveedor END AS costo_proveedor,

    importe_cliente - cobrado_cliente AS saldo_cliente,

    CASE WHEN cant_servicios > 0 THEN costo_servicios
         WHEN pct_proveedor > 0  THEN importe_cliente - comision_agencia
         ELSE costo_proveedor END - pagado_proveedor AS saldo_proveedor,

    comision_agencia AS ganancia_bruta,

    COALESCE(comision_monto,
             comision_agencia * pct_vendedor / 100.0) AS comision_vendedor,

    comision_agencia - COALESCE(comision_monto,
             comision_agencia * pct_vendedor / 100.0) AS margen_neto
FROM calc;
