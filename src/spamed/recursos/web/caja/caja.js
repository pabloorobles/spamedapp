(function () {
  "use strict";

  var dinero = window.SpamedUtil.dinero;
  var fecha = window.SpamedUtil.fecha;
  var llenarSelect = window.SpamedUtil.llenarSelect;

  var puente = null;
  var listas = null;
  var reservas = [];
  var filas = [];
  var seleccionId = null;
  var editandoId = null;

  function $(id) { return document.getElementById(id); }

  // -------------------------------------------------------------- grilla
  function refrescar() {
    if (!puente) return;
    puente.listar(
      $("fBusqueda").value, $("fTipo").value, $("fMoneda").value,
      $("fDesde").value, $("fHasta").value,
      function (json) {
        var r = JSON.parse(json);
        if (!r.ok) {
          $("bajada").textContent = "No se pudo cargar: " + r.error;
          return;
        }
        filas = r.filas;
        seleccionId = null;
        pintarTabla();
        pintarTotales();
        actualizarBotones();
        $("bajada").textContent = filas.length
          ? filas.length + " movimiento(s)"
          : "Sin movimientos para el filtro actual.";
      });
  }
  window.refrescar = refrescar;

  function pintarTabla() {
    var cuerpo = filas.map(function (f) {
      var claseMonto = f.tipo === "INGRESO" ? "monto-ingreso" : "monto-egreso";
      var signo = f.tipo === "INGRESO" ? "" : "−";
      return "<tr data-id='" + f.id + "'>" +
        "<td>" + fecha(f.fecha) + "</td>" +
        "<td>" + f.tipo + "</td>" +
        "<td>" + (f.concepto || "") + "</td>" +
        "<td class='file'>" + (f.file || "") + "</td>" +
        "<td>" + (f.cliente || "") + "</td>" +
        "<td>" + f.moneda + "</td>" +
        "<td class='num " + claseMonto + "'>" + signo + dinero(f.monto, f.moneda) + "</td>" +
        "<td>" + (f.medio_pago || "") + "</td>" +
        "<td>" + (f.detalle || "") + "</td>" +
        "</tr>";
    }).join("");
    $("tablaCaja").innerHTML = cuerpo ||
      "<tr><td colspan='9' class='vacio'>Sin movimientos para el filtro actual.</td></tr>";

    Array.prototype.forEach.call($("tablaCaja").querySelectorAll("tr[data-id]"),
      function (tr) {
        tr.addEventListener("click", function () {
          seleccionar(Number(tr.getAttribute("data-id")));
        });
      });
  }

  function seleccionar(id) {
    seleccionId = id;
    Array.prototype.forEach.call($("tablaCaja").querySelectorAll("tr[data-id]"),
      function (tr) {
        tr.classList.toggle("seleccionada", Number(tr.getAttribute("data-id")) === id);
      });
    actualizarBotones();
  }

  function actualizarBotones() {
    var hay = seleccionId !== null;
    $("btnEditar").disabled = !hay;
    $("btnRecibo").disabled = !hay;
    $("btnEliminar").disabled = !hay;
  }

  function pintarTotales() {
    var acum = {};
    filas.forEach(function (f) {
      var a = acum[f.moneda] || (acum[f.moneda] = {i: 0, e: 0});
      if (f.tipo === "INGRESO") a.i += Number(f.monto) || 0;
      else a.e += Number(f.monto) || 0;
    });
    var partes = [filas.length + " movimiento(s)"];
    Object.keys(acum).forEach(function (mon) {
      var a = acum[mon];
      partes.push(mon + ": ingresos " + dinero(a.i, mon) + " · egresos " +
        dinero(a.e, mon) + " · neto " + dinero(a.i - a.e, mon));
    });
    $("totales").textContent = partes.join("      ");
  }

  // --------------------------------------------------------- filtros UI
  function cargarFiltros() {
    puente.listas(function (json) {
      listas = JSON.parse(json);
      llenarSelect($("fMoneda"), listas.monedas, "Todas");
      llenarSelect($("mMoneda"), listas.monedas, "");
      llenarSelect($("mMedio"), listas.medios_pago, "");
      llenarSelect($("cMonedaOrigen"), listas.monedas, "");
      llenarSelect($("cMonedaDestino"), listas.monedas, "");
      llenarSelect($("cMedio"), listas.medios_pago, "");
      if (listas.monedas.length > 1) $("cMonedaDestino").value = listas.monedas[1];
      refrescar();
    });
    puente.reservas_buscables(function (json) {
      reservas = JSON.parse(json);
      var sel = $("mReserva");
      reservas.forEach(function (r) {
        var op = document.createElement("option");
        op.value = r.id;
        op.textContent = r.file + " · " + r.cliente + " · " + (r.destino || "");
        sel.appendChild(op);
      });
    });
  }

  // ------------------------------------------------------- modal: movim.
  function cambioTipo() {
    var esIngreso = $("mTipo").value === "INGRESO";
    var actual = $("mConcepto").value;
    llenarSelect($("mConcepto"), esIngreso ? listas.conceptos_ingreso : listas.conceptos_egreso, "");
    if (actual) $("mConcepto").value = actual;
  }

  function cambioReserva() {
    var rid = $("mReserva").value;
    if (!rid) {
      $("infoReserva").textContent =
        "Sin file asociado: el movimiento cuenta como gasto o ingreso general de la agencia.";
      return;
    }
    puente.reserva_info(Number(rid), function (json) {
      var r = JSON.parse(json);
      if (!r) return;
      $("mMoneda").value = r.moneda;
      $("infoReserva").textContent = r.file + " — " + r.cliente + " · " + r.moneda +
        "   Saldo cliente: " + dinero(r.saldo_cliente, r.moneda) +
        "   Saldo operador: " + dinero(r.saldo_proveedor, r.moneda);
    });
  }

  function abrirMovimiento(id) {
    editandoId = id || null;
    $("errorMovimiento").hidden = true;
    $("tituloMovimiento").textContent = id ? "Editar movimiento" : "Movimiento de caja";
    $("btnComprobantes").disabled = !id;

    function listo() {
      if (id) {
        puente.obtener(id, function (json) {
          var r = JSON.parse(json);
          if (!r.ok || !r.fila) return;
          var f = r.fila;
          $("mTipo").value = f.tipo;
          cambioTipo();
          $("mFecha").value = f.fecha;
          $("mConcepto").value = f.concepto || "";
          $("mReserva").value = f.reserva_id || "";
          $("mMoneda").value = f.moneda;
          $("mMonto").value = f.monto;
          $("mMedio").value = f.medio_pago || "";
          $("mDetalle").value = f.detalle || "";
          cambioReserva();
          $("modalMovimiento").hidden = false;
        });
      } else {
        $("mTipo").value = "INGRESO";
        cambioTipo();
        $("mFecha").value = new Date().toISOString().slice(0, 10);
        $("mReserva").value = "";
        $("mMoneda").value = listas.monedas[0] || "";
        $("mMonto").value = "";
        $("mMedio").value = "";
        $("mDetalle").value = "";
        cambioReserva();
        $("modalMovimiento").hidden = false;
      }
    }
    if (listas) listo(); else puente.listas(function (j) { listas = JSON.parse(j); listo(); });
  }

  function cerrarMovimiento() {
    $("modalMovimiento").hidden = true;
  }

  function guardarMovimiento(ev) {
    ev.preventDefault();
    var payload = {
      id: editandoId,
      tipo: $("mTipo").value,
      fecha: $("mFecha").value,
      concepto: $("mConcepto").value,
      reserva_id: $("mReserva").value ? Number($("mReserva").value) : null,
      moneda: $("mMoneda").value,
      monto: Number($("mMonto").value),
      medio_pago: $("mMedio").value,
      detalle: $("mDetalle").value.trim(),
    };
    puente.guardar(JSON.stringify(payload), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) {
        $("errorMovimiento").textContent = r.error;
        $("errorMovimiento").hidden = false;
        return;
      }
      cerrarMovimiento();
      refrescar();
    });
  }

  // --------------------------------------------------------- modal: cambio
  function abrirCambio() {
    $("errorCambio").hidden = true;
    $("cFecha").value = new Date().toISOString().slice(0, 10);
    $("cMontoOrigen").value = "";
    $("cMontoDestino").value = "";
    $("cDetalle").value = "";
    actualizarCotizacion();
    $("modalCambio").hidden = false;
  }

  function cerrarCambio() {
    $("modalCambio").hidden = true;
  }

  function actualizarCotizacion() {
    var o = Number($("cMontoOrigen").value) || 0;
    var d = Number($("cMontoDestino").value) || 0;
    if (o <= 0 || d <= 0) {
      $("infoCotizacion").textContent =
        "Las monedas no se consolidan: cada una mantiene su saldo propio en los reportes.";
      return;
    }
    var cot = Math.round((Math.max(o, d) / Math.min(o, d)) * 10000) / 10000;
    $("infoCotizacion").textContent = "Cotización implícita: " + cot + "   ·   salen " +
      dinero(o, $("cMonedaOrigen").value) + " y entran " + dinero(d, $("cMonedaDestino").value);
  }

  function guardarCambio(ev) {
    ev.preventDefault();
    var payload = {
      fecha: $("cFecha").value,
      moneda_origen: $("cMonedaOrigen").value,
      monto_origen: Number($("cMontoOrigen").value),
      moneda_destino: $("cMonedaDestino").value,
      monto_destino: Number($("cMontoDestino").value),
      medio_pago: $("cMedio").value,
      detalle: $("cDetalle").value.trim(),
    };
    puente.cambio_moneda(JSON.stringify(payload), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) {
        $("errorCambio").textContent = r.error;
        $("errorCambio").hidden = false;
        return;
      }
      cerrarCambio();
      refrescar();
    });
  }

  // -------------------------------------------------------------- eventos
  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;
    cargarFiltros();

    $("fBusqueda").addEventListener("input", refrescar);
    $("fTipo").addEventListener("change", refrescar);
    $("fMoneda").addEventListener("change", refrescar);
    $("fDesde").addEventListener("change", refrescar);
    $("fHasta").addEventListener("change", refrescar);

    $("btnNuevo").addEventListener("click", function () { abrirMovimiento(null); });
    $("btnEditar").addEventListener("click", function () {
      if (seleccionId !== null) abrirMovimiento(seleccionId);
    });
    $("btnEliminar").addEventListener("click", function () {
      if (seleccionId === null) return;
      if (!window.confirm("¿Eliminar el movimiento seleccionado?")) return;
      puente.eliminar(seleccionId, function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { window.alert(r.error); return; }
        refrescar();
      });
    });
    $("btnRecibo").addEventListener("click", function () {
      if (seleccionId === null) return;
      puente.recibo(seleccionId, function (json) {
        var r = JSON.parse(json);
        if (!r.ok && !r.cancelado) window.alert(r.error);
      });
    });
    $("btnExportar").addEventListener("click", function () {
      puente.exportar(JSON.stringify(filas));
    });
    $("btnCambio").addEventListener("click", abrirCambio);

    $("mTipo").addEventListener("change", cambioTipo);
    $("mReserva").addEventListener("change", cambioReserva);
    $("btnComprobantes").addEventListener("click", function () {
      if (editandoId) puente.comprobantes(editandoId);
    });
    $("btnCancelarMovimiento").addEventListener("click", cerrarMovimiento);
    $("formMovimiento").addEventListener("submit", guardarMovimiento);

    $("cMontoOrigen").addEventListener("input", actualizarCotizacion);
    $("cMontoDestino").addEventListener("input", actualizarCotizacion);
    $("cMonedaOrigen").addEventListener("change", actualizarCotizacion);
    $("cMonedaDestino").addEventListener("change", actualizarCotizacion);
    $("btnCancelarCambio").addEventListener("click", cerrarCambio);
    $("formCambio").addEventListener("submit", guardarCambio);
  });
})();
