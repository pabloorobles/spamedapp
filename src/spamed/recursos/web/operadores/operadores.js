(function () {
  "use strict";

  var dinero = window.SpamedUtil.dinero;
  var llenarSelect = window.SpamedUtil.llenarSelect;

  var puente = null;
  var filas = [];
  var seleccionId = null;
  var editandoId = null;
  var varianteEditando = null;

  function $(id) { return document.getElementById(id); }

  function porMonedaTexto(porMoneda) {
    var partes = [];
    Object.keys(porMoneda || {}).forEach(function (mon) {
      var v = porMoneda[mon];
      if (v) partes.push(dinero(v, mon));
    });
    return partes.length ? partes.join("  ·  ") : "-";
  }

  // -------------------------------------------------------------- grilla
  function refrescar() {
    if (!puente) return;
    puente.listar($("fBusqueda").value, $("fActivos").checked, function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("bajada").textContent = "No se pudo cargar: " + r.error; return; }
      filas = r.filas;
      seleccionId = null;
      pintarTabla();
      actualizarBotones();
      $("bajada").textContent = filas.length
        ? filas.length + " registro(s)"
        : "Sin registros. Cargá uno con Nuevo, o importá el Excel desde Herramientas.";
    });
  }
  window.refrescar = refrescar;

  function pintarTabla() {
    var cuerpo = filas.map(function (f) {
      return "<tr data-id='" + f.id + "'>" +
        "<td>" + (f.nombre || "") + "</td>" +
        "<td>" + (f.tipo || "") + "</td>" +
        "<td>" + (f.moneda || "") + "</td>" +
        "<td class='num'>" + (Number(f.comision_pct) || 0).toFixed(2) + " %</td>" +
        "<td>" + (f.transfiere_neto ? "Sí" : "No") + "</td>" +
        "<td>" + (f.contacto || "") + "</td>" +
        "<td>" + (f.telefono || "") + "</td>" +
        "<td class='num'>" + (f.files || 0) + "</td>" +
        "<td class='num'>" + porMonedaTexto(f.facturado) + "</td>" +
        "<td>" + (f.activo ? "Sí" : "No") + "</td>" +
        "</tr>";
    }).join("");
    $("tablaOperadores").innerHTML = cuerpo ||
      "<tr><td colspan='10' class='vacio'>Sin registros para el filtro actual.</td></tr>";
    Array.prototype.forEach.call($("tablaOperadores").querySelectorAll("tr[data-id]"),
      function (tr) {
        tr.addEventListener("click", function () { seleccionar(Number(tr.getAttribute("data-id"))); });
      });
  }

  function seleccionar(id) {
    seleccionId = id;
    Array.prototype.forEach.call($("tablaOperadores").querySelectorAll("tr[data-id]"),
      function (tr) {
        tr.classList.toggle("seleccionada", Number(tr.getAttribute("data-id")) === id);
      });
    actualizarBotones();
  }

  function actualizarBotones() {
    var hay = seleccionId !== null;
    $("btnEditar").disabled = !hay;
    $("btnEliminar").disabled = !hay;
  }

  // -------------------------------------------------------- modal operador
  function abrirOperador(id) {
    editandoId = id || null;
    $("errorOperador").hidden = true;
    $("tituloOperador").textContent = id ? "Editar operador" : "Operador";
    var f = document.getElementById("formOperador");
    f.reset();
    $("opNeto").checked = true;
    $("opActivo").checked = true;
    $("opComision").value = "0";
    $("bloqueVariantes").hidden = !id;
    if (id) {
      puente.obtener(id, function (json) {
        var r = JSON.parse(json);
        if (!r.ok || !r.fila) return;
        var d = r.fila;
        $("opNombre").value = d.nombre || "";
        $("opTipo").value = d.tipo || "";
        $("opMoneda").value = d.moneda || "";
        $("opComision").value = d.comision_pct != null ? d.comision_pct : 0;
        $("opNeto").checked = !!d.transfiere_neto;
        $("opContacto").value = d.contacto || "";
        $("opTelefono").value = d.telefono || "";
        $("opEmail").value = d.email || "";
        $("opObservaciones").value = d.observaciones || "";
        $("opActivo").checked = !!d.activo;
        $("modalOperador").hidden = false;
        limpiarFormVariante();
        refrescarVariantes();
      });
    } else {
      $("modalOperador").hidden = false;
    }
  }

  function guardarOperador(ev) {
    ev.preventDefault();
    var payload = {
      id: editandoId,
      nombre: $("opNombre").value.trim(),
      tipo: $("opTipo").value,
      moneda: $("opMoneda").value || "PESOS",
      comision_pct: Number($("opComision").value) || 0,
      transfiere_neto: $("opNeto").checked ? 1 : 0,
      contacto: $("opContacto").value.trim(),
      telefono: $("opTelefono").value.trim(),
      email: $("opEmail").value.trim(),
      observaciones: $("opObservaciones").value.trim(),
      activo: $("opActivo").checked ? 1 : 0,
    };
    puente.guardar(JSON.stringify(payload), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("errorOperador").textContent = r.error; $("errorOperador").hidden = false; return; }
      $("modalOperador").hidden = true;
      refrescar();
    });
  }

  // ------------------------------------------------------------ variantes
  function limpiarFormVariante() {
    varianteEditando = null;
    $("errorVariante").hidden = true;
    $("vaTipoViaje").value = "Nacional";
    $("vaMoneda").value = "";
    $("vaComision").value = "0";
    $("vaNeto").checked = true;
    $("btnGuardarVariante").textContent = "Agregar variante";
    $("btnCancelarVariante").hidden = true;
  }

  function refrescarVariantes() {
    if (!editandoId) return;
    puente.variantes_listar(editandoId, function (json) {
      var vs = JSON.parse(json);
      var cuerpo = vs.map(function (v) {
        return "<tr><td>" + (v.tipo_viaje || "") + "</td><td>" + (v.moneda || "") +
          "</td><td class='num'>" + (Number(v.comision_pct) || 0).toFixed(2) + " %</td><td>" +
          (v.transfiere_neto ? "Sí" : "No") +
          "</td><td><button type='button' class='btn-suave' style='padding:2px 8px' " +
          "data-editar='" + v.id + "'>Editar</button> " +
          "<button type='button' class='icono-quitar' data-quitar='" + v.id + "'>Quitar</button></td></tr>";
      }).join("");
      $("tablaVariantes").innerHTML = cuerpo ||
        "<tr><td colspan='5' class='vacio'>Sin variantes cargadas.</td></tr>";
      Array.prototype.forEach.call($("tablaVariantes").querySelectorAll("[data-editar]"),
        function (b) {
          b.addEventListener("click", function () {
            var v = vs.filter(function (x) { return x.id === Number(b.getAttribute("data-editar")); })[0];
            if (!v) return;
            varianteEditando = v.id;
            $("vaTipoViaje").value = v.tipo_viaje || "Nacional";
            $("vaMoneda").value = v.moneda || "";
            $("vaComision").value = v.comision_pct != null ? v.comision_pct : 0;
            $("vaNeto").checked = !!v.transfiere_neto;
            $("btnGuardarVariante").textContent = "Guardar cambios";
            $("btnCancelarVariante").hidden = false;
          });
        });
      Array.prototype.forEach.call($("tablaVariantes").querySelectorAll("[data-quitar]"),
        function (b) {
          b.addEventListener("click", function () {
            if (!window.confirm("¿Quitar esta variante? El operador vuelve a "
              + "usar la comisión general para esa combinación.")) return;
            puente.variante_eliminar(Number(b.getAttribute("data-quitar")), function () {
              refrescarVariantes();
            });
          });
        });
    });
  }

  function guardarVariante(ev) {
    ev.preventDefault();
    puente.variante_guardar(JSON.stringify({
      id: varianteEditando, proveedor_id: editandoId,
      tipo_viaje: $("vaTipoViaje").value, moneda: $("vaMoneda").value || "PESOS",
      comision_pct: Number($("vaComision").value) || 0,
      transfiere_neto: $("vaNeto").checked ? 1 : 0,
    }), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("errorVariante").textContent = r.error; $("errorVariante").hidden = false; return; }
      limpiarFormVariante();
      refrescarVariantes();
    });
  }

  // --------------------------------------------------------------- filtros
  function cargarFiltros() {
    puente.listas(function (json) {
      var l = JSON.parse(json);
      llenarSelect($("opTipo"), l.tipos, "—");
      llenarSelect($("opMoneda"), l.monedas, "");
      llenarSelect($("vaMoneda"), l.monedas, "");
      refrescar();
    });
  }

  // -------------------------------------------------------------- eventos
  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;
    cargarFiltros();

    $("fBusqueda").addEventListener("input", refrescar);
    $("fActivos").addEventListener("change", refrescar);

    $("btnNuevo").addEventListener("click", function () { abrirOperador(null); });
    $("btnEditar").addEventListener("click", function () {
      if (seleccionId !== null) abrirOperador(seleccionId);
    });
    $("btnEliminar").addEventListener("click", function () {
      if (seleccionId === null) return;
      if (!window.confirm("¿Eliminar el registro seleccionado?")) return;
      puente.eliminar(seleccionId, function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { window.alert(r.error); return; }
        refrescar();
      });
    });
    $("btnExportar").addEventListener("click", function () { puente.exportar(JSON.stringify(filas)); });
    $("btnCancelarOperador").addEventListener("click", function () { $("modalOperador").hidden = true; });
    $("formOperador").addEventListener("submit", guardarOperador);

    $("formVariante").addEventListener("submit", guardarVariante);
    $("btnCancelarVariante").addEventListener("click", limpiarFormVariante);
  });
})();
