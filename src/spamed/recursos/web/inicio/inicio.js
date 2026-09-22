(function () {
  "use strict";

  var ESTADOS = ["Cotizado", "Reservado", "Confirmado", "Emitido", "En Viaje", "Finalizado"];
  var RAMAS = ["Vencido", "Cancelado"];
  var slug = window.SpamedUtil.slug;
  var dinero = window.SpamedUtil.dinero;
  var fecha = window.SpamedUtil.fecha;
  var badge = window.SpamedUtil.badge;

  function resumenPorMoneda(porMoneda, clave) {
    var partes = [];
    Object.keys(porMoneda).forEach(function (mon) {
      var v = porMoneda[mon][clave];
      if (v) partes.push(mon + ": " + dinero(v, mon));
    });
    return partes.length ? partes.join("  ·  ") : "-";
  }

  function chipHtml(nombre, n) {
    var s = slug(nombre);
    return '<div class="pipeline__paso">' +
      '<div class="chip" style="' +
        (n ? "border-color: var(--estado-" + s + "); " +
             "background: color-mix(in srgb, var(--estado-" + s + ") 12%, var(--superficie));"
           : "") + '">' +
        '<span class="chip__n" style="color:' +
          (n ? "var(--estado-" + s + ")" : "var(--texto-suave)") + '">' + n + '</span>' +
        '<span>' + nombre + '</span>' +
      '</div></div>';
  }

  // Los 8 estados van en un solo renglón: los primeros 6 son la
  // secuencia real de un file (con línea de conexión entre ellos);
  // Vencido/Cancelado son ramificaciones -- no van "después" de
  // Finalizado en ningún sentido -- así que se separan con un poco de
  // aire en vez de una línea, pero sin bajar de renglón.
  function pipelineHtml(conteo) {
    var html = "";
    ESTADOS.forEach(function (nombre, i) {
      html += chipHtml(nombre, conteo[nombre] || 0);
      if (i < ESTADOS.length - 1) html += '<div class="pipeline__linea"></div>';
    });
    html += '<div class="pipeline__separador"></div>';
    RAMAS.forEach(function (nombre, i) {
      html += chipHtml(nombre, conteo[nombre] || 0);
      if (i < RAMAS.length - 1) html += '<div class="pipeline__separador"></div>';
    });
    document.getElementById("pipeline").innerHTML = html;
  }

  function pintarAlertas(filas) {
    var cuerpo = filas.map(function (f) {
      var aviso = (f.alertas || []).join(" · ");
      return "<tr><td class='file'>" + f.file + "</td><td>" + f.cliente + "</td><td>" +
        badge(f.estado) + "</td><td class='num'>" + dinero(f.saldo_cliente, f.moneda) +
        "</td><td>" + fecha(f.fecha_vto_reserva) + "</td><td class='alerta'>" + aviso +
        "</td></tr>";
    }).join("");
    document.getElementById("tablaAlertas").innerHTML = cuerpo ||
      "<tr><td colspan='6' class='vacio'>Sin alertas por ahora.</td></tr>";
  }

  function pintarPagos(filas) {
    var cuerpo = filas.map(function (f) {
      return "<tr><td class='file'>" + f.file + "</td><td>" + f.proveedor + "</td><td>" +
        f.destino + "</td><td>" + f.moneda + "</td><td class='num'>" +
        dinero(f.saldo_proveedor, f.moneda) + "</td></tr>";
    }).join("");
    document.getElementById("tablaPagos").innerHTML = cuerpo ||
      "<tr><td colspan='5' class='vacio'>Sin pagos pendientes a operadores.</td></tr>";
  }

  var puente = null;

  function refrescar() {
    if (!puente) return;
    var moneda = document.getElementById("selMoneda").value;
    var desde = document.getElementById("fDesde").value;
    var hasta = document.getElementById("fHasta").value;

    puente.dashboard(moneda, desde, hasta, function (respuestaJson) {
      var d = JSON.parse(respuestaJson);
      if (!d.ok) {
        document.getElementById("bajada").textContent =
          "No se pudo cargar: " + d.error;
        return;
      }
      document.getElementById("bajada").textContent =
        "caja del " + fecha(d.desde) + " al " + fecha(d.hasta);

      document.getElementById("kpiCobrar").textContent = resumenPorMoneda(d.por_moneda, "a_cobrar");
      document.getElementById("kpiCobrarSub").textContent = d.cant_pendientes + " file(s) con saldo";
      document.getElementById("kpiPagar").textContent = resumenPorMoneda(d.por_moneda, "a_pagar");
      document.getElementById("kpiPagarSub").textContent = d.cant_a_pagar + " file(s) a pagar";
      document.getElementById("kpiGanancia").textContent = resumenPorMoneda(d.por_moneda, "ganancia");
      document.getElementById("kpiGananciaSub").textContent = d.cant_activas + " file(s) activos";

      var caja = (d.totales_mes || []).map(function (t) {
        return t.moneda + ": " + dinero(t.neto, t.moneda);
      }).join("  ·  ") || "-";
      document.getElementById("kpiCaja").textContent = caja;

      pipelineHtml(d.estados || {});
      pintarAlertas(d.alertas || []);
      pintarPagos(d.pagos_operadores || []);
    });
  }

  function mesActual() {
    puente.fechas_mes_actual(function (json) {
      var f = JSON.parse(json);
      document.getElementById("fDesde").value = f.desde;
      document.getElementById("fHasta").value = f.hasta;
      refrescar();
    });
  }

  // VentanaPrincipal.ir_a()/refrescar_todo() (ui/principal.py) llaman a
  // esto cada vez que se entra a la pantalla o cambia algo en otra --
  // mismo criterio que ya usan las pantallas de Qt con su .refrescar().
  window.refrescar = refrescar;

  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;

    puente.monedas(function (json) {
      var lista = JSON.parse(json);
      var sel = document.getElementById("selMoneda");
      lista.forEach(function (m) {
        var opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        sel.appendChild(opt);
      });
    });

    document.getElementById("selMoneda").addEventListener("change", refrescar);
    document.getElementById("fDesde").addEventListener("change", refrescar);
    document.getElementById("fHasta").addEventListener("change", refrescar);
    document.getElementById("btnMesActual").addEventListener("click", mesActual);

    mesActual();
  });
})();
