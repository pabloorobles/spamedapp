(function () {
  "use strict";

  var dinero = window.SpamedUtil.dinero;
  var llenarSelect = window.SpamedUtil.llenarSelect;
  var MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

  var puente = null;
  var datosActuales = {};   // por moneda, la ultima respuesta de comparar()
  var estadoCerrado = false;
  var filasLiq = [];
  var liqSel = null;

  function $(id) { return document.getElementById(id); }

  function periodo() {
    return {anio: Number($("inAnio").value), mes: Number($("selMes").value)};
  }

  // ---------------------------------------------------------------- carga
  function refrescar() {
    if (!puente) return;
    var p = periodo();
    puente.comparar(p.anio, p.mes, function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("bajada").textContent = "No se pudo cargar: " + r.error; return; }
      datosActuales = r.datos;
      estadoCerrado = r.cerrado;
      $("bajada").textContent = MESES[p.mes] + " " + p.anio + " — " + r.estado;
      $("btnCerrar").textContent = estadoCerrado ? "Reabrir el mes" : "Cerrar el mes";
      pintarPaneles();
      refrescarConsolidado();
    });
    puente.liquidaciones(p.anio, p.mes, function (json) {
      var r = JSON.parse(json);
      if (!r.ok) return;
      filasLiq = r.filas;
      liqSel = null;
      pintarLiquidaciones();
      actualizarBotonesLiq();
    });
  }
  window.refrescar = refrescar;

  // ------------------------------------------------------------- paneles
  function grid(fila, etiqueta, valor, tono, destacado) {
    var claseVal = "cierre-grid__valor" + (destacado ? " cierre-grid__valor--destacado" : "") +
      (tono ? " tono-" + tono : "");
    return "<div class='cierre-grid__item'><div class='cierre-grid__etiqueta'>" + etiqueta +
      "</div><div class='" + claseVal + "'>" + valor + "</div></div>";
  }

  function pintarPaneles() {
    var cont = $("panelesMoneda");
    var monedas = Object.keys(datosActuales);
    if (!monedas.length) {
      cont.innerHTML = "<div class='panel vacio'>No hay movimientos ni ventas en este período.</div>";
      return;
    }
    cont.innerHTML = monedas.map(function (mon) {
      var d = datosActuales[mon];
      var m = function (v) { return dinero(v, mon); };
      var signo = d.var_ventas > 0 ? "+" : "";
      var celdas = [
        grid(0, "Ventas (" + d.files + " files)", m(d.ventas), "", true),
        grid(0, "Comisión de la agencia", m(d.comision_agencia), "", true),
        grid(0, "Comisión de vendedores", m(d.comision_vendedores)),
        grid(0, "Margen de la agencia", m(d.margen), d.margen >= 0 ? "ok" : "error", true),
        grid(1, "Cobros a clientes", m(d.cobros_clientes)),
        grid(1, "Pagos a operadores", m(d.pagos_proveedores)),
        grid(1, "Gastos generales", m(d.gastos_generales)),
        grid(1, "Resultado de caja", m(d.resultado_caja), d.resultado_caja >= 0 ? "ok" : "error", true),
        grid(2, "Objetivo del mes", d.objetivo ? m(d.objetivo) : "sin definir"),
        grid(2, "Cumplimiento", d.objetivo ? d.cumplimiento + "%" : "—",
             d.cumplimiento >= 100 ? "ok" : "alerta", true),
        grid(2, "Vs. mes anterior", signo + d.var_ventas + "%"),
        grid(2, "Devoluciones", m(d.devoluciones)),
      ].join("");
      return "<div class='panel moneda-panel'><h2>" + mon +
        (d.cerrado ? "<span class='moneda-panel__badge'>Cerrado</span>" : "") +
        "</h2><div class='cierre-grid'>" + celdas + "</div></div>";
    }).join("");
  }

  function refrescarConsolidado() {
    var cot = Number($("inCotizacion").value) || 0;
    if (!cot) { $("consolidado").textContent = "Cargá una cotización para ver el consolidado."; return; }
    var monedas = Object.keys(datosActuales);
    if (!monedas.length) { $("consolidado").textContent = "Sin datos en este período para consolidar."; return; }
    var ventasCons = 0, margenCons = 0;
    monedas.forEach(function (mon) {
      var d = datosActuales[mon];
      var factor = mon === "PESOS" ? 1 : cot;
      ventasCons += d.ventas * factor;
      margenCons += d.margen * factor;
    });
    $("consolidado").textContent =
      "Ventas consolidadas: " + dinero(ventasCons, "PESOS") +
      "   ·   Margen consolidado: " + dinero(margenCons, "PESOS") +
      "   (a " + dinero(cot, "PESOS") + " el dólar)";
  }

  function cargarCotizacion() {
    puente.cotizacion_info(function (json) {
      var r = JSON.parse(json);
      if (r.valor) {
        if (!$("inCotizacion").value) $("inCotizacion").value = r.valor;
        $("cotizacionFecha").textContent =
          "Última cotización guardada: " + dinero(r.valor, "PESOS") + " por US$ — " + r.fecha;
      } else {
        $("cotizacionFecha").textContent =
          "Todavía no hay ninguna cotización guardada. Cargala a mano o traela de internet.";
      }
      refrescarConsolidado();
    });
  }

  // -------------------------------------------------------- liquidaciones
  function pintarLiquidaciones() {
    var cuerpo = filasLiq.map(function (f) {
      return "<tr data-id='" + f.vendedor_id + "' data-moneda='" + f.moneda + "'>" +
        "<td>" + (f.vendedor || "") + "</td><td>" + f.moneda + "</td>" +
        "<td class='num'>" + f.files + "</td>" +
        "<td class='num'>" + dinero(f.ventas, f.moneda) + "</td>" +
        "<td class='num'>" + dinero(f.comision_agencia, f.moneda) + "</td>" +
        "<td class='num'>" + dinero(f.importe, f.moneda) + "</td>" +
        "<td>" + f.estado + "</td></tr>";
    }).join("");
    $("tablaLiq").innerHTML = cuerpo ||
      "<tr><td colspan='7' class='vacio'>Sin comisiones para liquidar en este período.</td></tr>";
    Array.prototype.forEach.call($("tablaLiq").querySelectorAll("tr[data-id]"), function (tr) {
      tr.addEventListener("click", function () {
        var idx = Array.prototype.indexOf.call(tr.parentNode.children, tr);
        liqSel = filasLiq[idx];
        Array.prototype.forEach.call($("tablaLiq").querySelectorAll("tr"),
          function (t) { t.classList.remove("seleccionada"); });
        tr.classList.add("seleccionada");
        actualizarBotonesLiq();
      });
    });
  }

  function actualizarBotonesLiq() {
    $("btnPagarLiq").disabled = !liqSel;
    $("btnPdfLiq").disabled = !liqSel;
  }

  // -------------------------------------------------------------- eventos
  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;

    for (var m = 1; m <= 12; m++) {
      var op = document.createElement("option");
      op.value = m; op.textContent = MESES[m];
      $("selMes").appendChild(op);
    }
    var hoy = new Date();
    $("selMes").value = hoy.getMonth() + 1;
    $("inAnio").value = hoy.getFullYear();
    llenarSelect($("obMoneda"), []);
    puente.comparar(hoy.getFullYear(), hoy.getMonth() + 1, function () {}); // precalienta

    function monedasDesdeInicio() {
      // Las opciones de moneda del objetivo salen de los paneles ya
      // cargados si hay, si no de PESOS/DOLAR por defecto -- evita
      // pedirle al puente una lista aparte solo para esto.
      var monedas = Object.keys(datosActuales);
      llenarSelect($("obMoneda"), monedas.length ? monedas : ["PESOS", "DOLAR"]);
    }

    refrescar();

    $("selMes").addEventListener("change", refrescar);
    $("inAnio").addEventListener("change", refrescar);
    $("btnMesActual").addEventListener("click", function () {
      var h = new Date();
      $("selMes").value = h.getMonth() + 1;
      $("inAnio").value = h.getFullYear();
      refrescar();
    });
    $("btnGenerarGastos").addEventListener("click", function () {
      var p = periodo();
      if (!window.confirm("Se van a generar los gastos fijos de " + MESES[p.mes] + " " + p.anio +
        ".\nLos que ya existan no se duplican. ¿Sigo?")) return;
      puente.generar_gastos(p.anio, p.mes, function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { window.alert(r.error); return; }
        window.alert(r.n ? r.n + " movimiento(s) generado(s)." : "No había gastos pendientes de generar.");
        refrescar();
      });
    });

    $("inCotizacion").addEventListener("input", refrescarConsolidado);
    $("btnCotizacionNet").addEventListener("click", function () {
      puente.cotizacion_actualizar(function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { window.alert(r.error); return; }
        $("inCotizacion").value = r.valor;
        cargarCotizacion();
        window.alert("Cotización actualizada: " + dinero(r.valor, "PESOS") + " por US$.");
      });
    });
    $("btnCotizacionUsar").addEventListener("click", function () {
      var v = Number($("inCotizacion").value) || 0;
      if (v <= 0) { window.alert("Cargá un valor mayor a cero."); return; }
      puente.cotizacion_guardar_manual(v, function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { window.alert(r.error); return; }
        cargarCotizacion();
        window.alert("Cotización guardada.");
      });
    });
    cargarCotizacion();

    $("btnCerrar").addEventListener("click", function () {
      var p = periodo();
      if (estadoCerrado) {
        if (!window.confirm(MESES[p.mes] + " " + p.anio + " ya está cerrado.\n¿Querés reabrirlo para corregir algo?")) return;
        puente.reabrir(p.anio, p.mes, function (json) {
          var r = JSON.parse(json);
          if (!r.ok) { window.alert(r.error); return; }
          window.alert("Período reabierto.");
          refrescar();
        });
        return;
      }
      if (!window.confirm("Se va a cerrar " + MESES[p.mes] + " " + p.anio +
        ".\n\nQueda guardada una foto de los números del mes. Podés reabrirlo después si hace falta. ¿Sigo?")) return;
      puente.cerrar(p.anio, p.mes, function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { window.alert(r.error); return; }
        window.alert("Mes cerrado. Se guardó el resumen de " + r.n + " moneda(s).");
        refrescar();
      });
    });

    $("btnPdf").addEventListener("click", function () {
      var p = periodo();
      puente.exportar_pdf(p.anio, p.mes);
    });

    $("btnObjetivo").addEventListener("click", function () {
      var p = periodo();
      $("objetivoPeriodo").textContent = MESES[p.mes] + " " + p.anio;
      $("errorObjetivo").hidden = true;
      monedasDesdeInicio();
      cargarObjetivo();
      $("modalObjetivo").hidden = false;
    });
    function cargarObjetivo() {
      var p = periodo();
      puente.objetivo_obtener(p.anio, p.mes, $("obMoneda").value, function (json) {
        var r = JSON.parse(json);
        $("obImporte").value = r.importe || 0;
      });
    }
    $("obMoneda").addEventListener("change", cargarObjetivo);
    $("btnCancelarObjetivo").addEventListener("click", function () { $("modalObjetivo").hidden = true; });
    $("formObjetivo").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var p = periodo();
      puente.objetivo_guardar(JSON.stringify({
        anio: p.anio, mes: p.mes, moneda: $("obMoneda").value,
        importe: Number($("obImporte").value) || 0,
      }), function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { $("errorObjetivo").textContent = r.error; $("errorObjetivo").hidden = false; return; }
        $("modalObjetivo").hidden = true;
        refrescar();
      });
    });

    $("btnPagarLiq").addEventListener("click", function () {
      if (!liqSel) return;
      if (liqSel.pagada) { window.alert("Esa liquidación ya está pagada."); return; }
      var p = periodo();
      var importeTxt = dinero(liqSel.importe, liqSel.moneda);
      if (!window.confirm("Se registra el pago de " + importeTxt + " a " + liqSel.vendedor +
        " por " + MESES[p.mes] + " " + p.anio + ".\n\nSe genera el egreso en la caja. ¿Sigo?")) return;
      puente.pagar_liquidacion(JSON.stringify({
        vendedor_id: liqSel.vendedor_id, anio: p.anio, mes: p.mes,
        moneda: liqSel.moneda, importe: liqSel.importe,
      }), function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { window.alert(r.error); return; }
        window.alert("Liquidación registrada y egreso generado.");
        refrescar();
      });
    });
    $("btnPdfLiq").addEventListener("click", function () {
      if (!liqSel) return;
      var p = periodo();
      puente.pdf_liquidacion(JSON.stringify({
        vendedor_id: liqSel.vendedor_id, vendedor: liqSel.vendedor,
        anio: p.anio, mes: p.mes, moneda: liqSel.moneda, importe: liqSel.importe,
      }));
    });
  });
})();
