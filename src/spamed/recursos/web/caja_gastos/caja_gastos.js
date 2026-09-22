(function () {
  "use strict";

  var dinero = window.SpamedUtil.dinero;
  var fecha = window.SpamedUtil.fecha;
  var llenarSelect = window.SpamedUtil.llenarSelect;

  var puente = null;

  function $(id) { return document.getElementById(id); }

  // -------------------------------------------------------------- tabs
  var PANEL_POR_TAB = {fijos: "tabFijos", extra: "tabExtra", arqueos: "tabArqueos"};

  function activarTab(nombre) {
    Array.prototype.forEach.call($("tabs").querySelectorAll(".tab"), function (t) {
      t.classList.toggle("activo", t.dataset.tab === nombre);
    });
    Object.keys(PANEL_POR_TAB).forEach(function (n) {
      $(PANEL_POR_TAB[n]).classList.toggle("activo", n === nombre);
    });
  }

  function refrescar() {
    if (!puente) return;
    refrescarFijos();
    refrescarExtra();
    refrescarArqueos();
  }
  window.refrescar = refrescar;

  // =============================================================== fijos
  var filasFijos = [];
  var fijoSel = null;
  var editandoFijoId = null;

  function refrescarFijos() {
    puente.gastos_listar(function (json) {
      var r = JSON.parse(json);
      if (!r.ok) return;
      filasFijos = r.filas;
      fijoSel = null;
      $("btnEditarFijo").disabled = true;
      $("btnEliminarFijo").disabled = true;
      var cuerpo = filasFijos.map(function (f) {
        return "<tr data-id='" + f.id + "'>" +
          "<td>" + (f.concepto || "") + "</td><td>" + (f.moneda || "") + "</td>" +
          "<td class='num'>" + dinero(f.importe, f.moneda) + "</td>" +
          "<td>" + (f.dia_mes || "") + "</td><td>" + (f.periodicidad || "") + "</td>" +
          "<td>" + (f.vigencia || "") + "</td><td>" + (f.medio_pago || "") + "</td>" +
          "<td>" + (f.activo ? "Sí" : "No") + "</td>" +
          "<td>" + fecha(f.ultimo_generado) + "</td></tr>";
      }).join("");
      $("tablaFijos").innerHTML = cuerpo ||
        "<tr><td colspan='9' class='vacio'>Sin gastos fijos cargados.</td></tr>";
      Array.prototype.forEach.call($("tablaFijos").querySelectorAll("tr[data-id]"), function (tr) {
        tr.addEventListener("click", function () {
          fijoSel = filasFijos.filter(function (f) { return f.id === Number(tr.getAttribute("data-id")); })[0];
          Array.prototype.forEach.call($("tablaFijos").querySelectorAll("tr"),
            function (t) { t.classList.remove("seleccionada"); });
          tr.classList.add("seleccionada");
          $("btnEditarFijo").disabled = false;
          $("btnEliminarFijo").disabled = false;
        });
      });
    });
  }

  function abrirFijo(id) {
    editandoFijoId = id || null;
    $("errorFijo").hidden = true;
    $("tituloFijo").textContent = id ? "Editar gasto fijo" : "Gasto fijo";
    $("formFijo").reset();
    $("gfDia").value = "1";
    $("gfImporte").value = "0";
    $("gfCuotas").value = "0";
    $("gfActivo").checked = true;
    if (id) {
      var f = fijoSel;
      $("gfConcepto").value = f.concepto || "";
      $("gfMoneda").value = f.moneda || "";
      $("gfImporte").value = f.importe != null ? f.importe : 0;
      $("gfDia").value = f.dia_mes || 1;
      $("gfMedio").value = f.medio_pago || "";
      $("gfPeriodicidad").value = f.periodicidad || "Mensual";
      $("gfFechaInicio").value = f.fecha_inicio || "";
      $("gfFechaFin").value = f.fecha_fin || "";
      $("gfCuotas").value = f.cantidad_cuotas || 0;
      $("gfActivo").checked = !!f.activo;
    }
    $("modalFijo").hidden = false;
  }

  function guardarFijo(ev) {
    ev.preventDefault();
    puente.gasto_guardar(JSON.stringify({
      id: editandoFijoId, concepto: $("gfConcepto").value,
      moneda: $("gfMoneda").value || "PESOS",
      importe: Number($("gfImporte").value) || 0,
      dia_mes: Number($("gfDia").value) || 1,
      medio_pago: $("gfMedio").value,
      periodicidad: $("gfPeriodicidad").value || "Mensual",
      fecha_inicio: $("gfFechaInicio").value || null,
      fecha_fin: $("gfFechaFin").value || null,
      cantidad_cuotas: Number($("gfCuotas").value) || null,
      activo: $("gfActivo").checked ? 1 : 0,
    }), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("errorFijo").textContent = r.error; $("errorFijo").hidden = false; return; }
      $("modalFijo").hidden = true;
      refrescarFijos();
    });
  }

  // =============================================================== extra
  var filasExtra = [];
  var extraSel = null;
  var editandoExtraId = null;

  function refrescarExtra() {
    puente.extraordinarios_listar(function (json) {
      var r = JSON.parse(json);
      if (!r.ok) return;
      filasExtra = r.filas;
      extraSel = null;
      $("btnEditarExtra").disabled = true;
      var cuerpo = filasExtra.map(function (f) {
        return "<tr data-id='" + f.id + "'>" +
          "<td>" + fecha(f.fecha) + "</td><td>" + (f.concepto || "") + "</td>" +
          "<td>" + (f.moneda || "") + "</td><td class='num'>" + dinero(f.monto, f.moneda) +
          "</td><td>" + (f.medio_pago || "") + "</td><td>" + (f.detalle || "") + "</td></tr>";
      }).join("");
      $("tablaExtra").innerHTML = cuerpo ||
        "<tr><td colspan='6' class='vacio'>Sin gastos extraordinarios cargados.</td></tr>";
      var acum = {};
      filasExtra.forEach(function (f) { acum[f.moneda] = (acum[f.moneda] || 0) + Number(f.monto || 0); });
      var partes = Object.keys(acum).map(function (m) { return m + ": " + dinero(acum[m], m); });
      $("totalesExtra").textContent = partes.join("  ·  ") || "Sin gastos extraordinarios cargados.";
      Array.prototype.forEach.call($("tablaExtra").querySelectorAll("tr[data-id]"), function (tr) {
        tr.addEventListener("click", function () {
          extraSel = filasExtra.filter(function (f) { return f.id === Number(tr.getAttribute("data-id")); })[0];
          Array.prototype.forEach.call($("tablaExtra").querySelectorAll("tr"),
            function (t) { t.classList.remove("seleccionada"); });
          tr.classList.add("seleccionada");
          $("btnEditarExtra").disabled = false;
        });
      });
    });
  }

  function abrirExtra(id) {
    editandoExtraId = id || null;
    $("errorExtra").hidden = true;
    $("tituloExtra").textContent = id ? "Editar gasto" : "Gasto extraordinario";
    $("formExtra").reset();
    $("exMonto").value = "0";
    if (id) {
      puente.extraordinario_obtener(id, function (json) {
        var r = JSON.parse(json);
        if (!r.ok || !r.fila) return;
        var d = r.fila;
        $("exFecha").value = d.fecha || "";
        $("exConcepto").value = d.concepto || "";
        $("exMoneda").value = d.moneda || "";
        $("exMonto").value = d.monto != null ? d.monto : 0;
        $("exMedio").value = d.medio_pago || "";
        $("exDetalle").value = d.detalle || "";
        $("modalExtra").hidden = false;
      });
    } else {
      $("exFecha").value = new Date().toISOString().slice(0, 10);
      $("modalExtra").hidden = false;
    }
  }

  function guardarExtra(ev) {
    ev.preventDefault();
    puente.extraordinario_guardar(JSON.stringify({
      id: editandoExtraId, fecha: $("exFecha").value,
      concepto: $("exConcepto").value, moneda: $("exMoneda").value || "PESOS",
      monto: Number($("exMonto").value) || 0, medio_pago: $("exMedio").value,
      detalle: $("exDetalle").value.trim(),
    }), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("errorExtra").textContent = r.error; $("errorExtra").hidden = false; return; }
      $("modalExtra").hidden = true;
      refrescarExtra();
    });
  }

  // ============================================================= arqueos
  var filasArqueos = [];
  var arqueoSel = null;

  function refrescarArqueos() {
    puente.arqueos_listar(function (json) {
      var r = JSON.parse(json);
      if (!r.ok) return;
      filasArqueos = r.filas;
      arqueoSel = null;
      $("btnEliminarArqueo").disabled = true;
      var cuerpo = filasArqueos.map(function (f) {
        return "<tr data-id='" + f.id + "'>" +
          "<td>" + fecha(f.fecha) + "</td><td>" + (f.moneda || "") + "</td>" +
          "<td class='num'>" + dinero(f.saldo_sistema, f.moneda) + "</td>" +
          "<td class='num'>" + dinero(f.saldo_contado, f.moneda) + "</td>" +
          "<td class='num'>" + dinero(f.diferencia, f.moneda) + "</td>" +
          "<td>" + (f.nota || "") + "</td></tr>";
      }).join("");
      $("tablaArqueos").innerHTML = cuerpo ||
        "<tr><td colspan='6' class='vacio'>Sin arqueos cargados.</td></tr>";
      Array.prototype.forEach.call($("tablaArqueos").querySelectorAll("tr[data-id]"), function (tr) {
        tr.addEventListener("click", function () {
          arqueoSel = filasArqueos.filter(function (f) { return f.id === Number(tr.getAttribute("data-id")); })[0];
          Array.prototype.forEach.call($("tablaArqueos").querySelectorAll("tr"),
            function (t) { t.classList.remove("seleccionada"); });
          tr.classList.add("seleccionada");
          $("btnEliminarArqueo").disabled = false;
        });
      });
    });
  }

  function calcularArqueo() {
    var mon = $("arMoneda").value || "PESOS";
    puente.arqueo_saldo_sistema(mon, $("arFecha").value, function (json) {
      var r = JSON.parse(json);
      $("arSistema").textContent = dinero(r.saldo, mon);
      var dif = (Number($("arContado").value) || 0) - r.saldo;
      $("arDif").textContent = dinero(dif, mon);
      $("arDif").style.color = Math.abs(dif) < 0.01 ? "" : "var(--alerta)";
    });
  }

  function abrirArqueo() {
    $("formArqueo").reset();
    $("arFecha").value = new Date().toISOString().slice(0, 10);
    $("arContado").value = "0";
    $("modalArqueo").hidden = false;
    calcularArqueo();
  }

  function guardarArqueo(ev) {
    ev.preventDefault();
    puente.arqueo_guardar(JSON.stringify({
      fecha: $("arFecha").value, moneda: $("arMoneda").value || "PESOS",
      saldo_contado: Number($("arContado").value) || 0,
      nota: $("arNota").value.trim(),
    }), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { window.alert(r.error); return; }
      $("modalArqueo").hidden = true;
      refrescarArqueos();
    });
  }

  // -------------------------------------------------------------- eventos
  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;
    puente.listas(function (json) {
      var l = JSON.parse(json);
      llenarSelect($("gfConcepto"), l.conceptos_egreso);
      llenarSelect($("gfMoneda"), l.monedas);
      llenarSelect($("gfMedio"), l.medios_pago, "—");
      llenarSelect($("gfPeriodicidad"), l.periodicidades);
      llenarSelect($("exConcepto"), l.conceptos_egreso, "—");
      llenarSelect($("exMoneda"), l.monedas);
      llenarSelect($("exMedio"), l.medios_pago, "—");
      llenarSelect($("arMoneda"), l.monedas);
      refrescar();
    });

    Array.prototype.forEach.call($("tabs").querySelectorAll(".tab"), function (t) {
      t.addEventListener("click", function () { activarTab(t.dataset.tab); });
    });

    $("btnNuevoFijo").addEventListener("click", function () { abrirFijo(null); });
    $("btnEditarFijo").addEventListener("click", function () {
      if (fijoSel) abrirFijo(fijoSel.id);
    });
    $("btnEliminarFijo").addEventListener("click", function () {
      if (!fijoSel) return;
      if (!window.confirm("¿Eliminar el gasto fijo?")) return;
      puente.gasto_eliminar(fijoSel.id, function () { refrescarFijos(); });
    });
    $("btnCancelarFijo").addEventListener("click", function () { $("modalFijo").hidden = true; });
    $("formFijo").addEventListener("submit", guardarFijo);

    $("btnNuevoExtra").addEventListener("click", function () { abrirExtra(null); });
    $("btnEditarExtra").addEventListener("click", function () {
      if (extraSel) abrirExtra(extraSel.id);
    });
    $("btnExportarExtra").addEventListener("click", function () {
      puente.extraordinario_exportar(JSON.stringify(filasExtra));
    });
    $("btnCancelarExtra").addEventListener("click", function () { $("modalExtra").hidden = true; });
    $("formExtra").addEventListener("submit", guardarExtra);

    $("btnNuevoArqueo").addEventListener("click", abrirArqueo);
    $("btnEliminarArqueo").addEventListener("click", function () {
      if (!arqueoSel) return;
      if (!window.confirm("¿Eliminar el arqueo?")) return;
      puente.arqueo_eliminar(arqueoSel.id, function () { refrescarArqueos(); });
    });
    $("btnCancelarArqueo").addEventListener("click", function () { $("modalArqueo").hidden = true; });
    $("formArqueo").addEventListener("submit", guardarArqueo);
    $("arContado").addEventListener("input", calcularArqueo);
    $("arMoneda").addEventListener("change", calcularArqueo);
    $("arFecha").addEventListener("change", calcularArqueo);
  });
})();
