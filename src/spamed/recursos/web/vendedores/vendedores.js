(function () {
  "use strict";

  var dinero = window.SpamedUtil.dinero;
  var fecha = window.SpamedUtil.fecha;

  var puente = null;
  var filas = [];
  var seleccionId = null;
  var editandoId = null;

  function $(id) { return document.getElementById(id); }

  function gananciaTexto(porMoneda) {
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
        "<td>" + (f.apellido || "") + "</td>" +
        "<td>" + (f.nombre || "") + "</td>" +
        "<td>" + (f.dni || "") + "</td>" +
        "<td>" + (f.telefono || "") + "</td>" +
        "<td>" + (f.email || "") + "</td>" +
        "<td>" + fecha(f.fecha_nac) + "</td>" +
        "<td class='num'>" + (Number(f.comision_pct) || 0).toFixed(2) + " %</td>" +
        "<td class='num'>" + (f.files || 0) + "</td>" +
        "<td>" + fecha(f.ultima_venta) + "</td>" +
        "<td class='num'>" + gananciaTexto(f.ganancia_generada) + "</td>" +
        "<td class='alertas'>" + ((f.alertas || []).join(" · ")) + "</td>" +
        "<td>" + (f.activo ? "Sí" : "No") + "</td>" +
        "</tr>";
    }).join("");
    $("tablaVendedores").innerHTML = cuerpo ||
      "<tr><td colspan='12' class='vacio'>Sin registros para el filtro actual.</td></tr>";
    Array.prototype.forEach.call($("tablaVendedores").querySelectorAll("tr[data-id]"),
      function (tr) {
        tr.addEventListener("click", function () { seleccionar(Number(tr.getAttribute("data-id"))); });
      });
  }

  function seleccionar(id) {
    seleccionId = id;
    Array.prototype.forEach.call($("tablaVendedores").querySelectorAll("tr[data-id]"),
      function (tr) {
        tr.classList.toggle("seleccionada", Number(tr.getAttribute("data-id")) === id);
      });
    actualizarBotones();
  }

  function actualizarBotones() {
    var hay = seleccionId !== null;
    ["btnEditar", "btnEliminar", "btnDocumentacion"].forEach(function (id) {
      $(id).disabled = !hay;
    });
  }

  function vendedorSeleccionado() {
    return filas.filter(function (f) { return f.id === seleccionId; })[0] || null;
  }

  // -------------------------------------------------------- modal vendedor
  function abrirVendedor(id) {
    editandoId = id || null;
    $("errorVendedor").hidden = true;
    $("tituloVendedor").textContent = id ? "Editar vendedor" : "Vendedor";
    var f = document.getElementById("formVendedor");
    f.reset();
    $("vActivo").checked = true;
    $("vComision").value = "0";
    if (id) {
      puente.obtener(id, function (json) {
        var r = JSON.parse(json);
        if (!r.ok || !r.fila) return;
        var d = r.fila;
        $("vDni").value = d.dni || "";
        $("vApellido").value = d.apellido || "";
        $("vNombre").value = d.nombre || "";
        $("vTelefono").value = d.telefono || "";
        $("vEmail").value = d.email || "";
        $("vFechaNac").value = d.fecha_nac || "";
        $("vComision").value = d.comision_pct != null ? d.comision_pct : 0;
        $("vActivo").checked = !!d.activo;
        $("modalVendedor").hidden = false;
      });
    } else {
      $("modalVendedor").hidden = false;
    }
  }

  function guardarVendedor(ev) {
    ev.preventDefault();
    var payload = {
      id: editandoId,
      dni: $("vDni").value.trim(),
      apellido: $("vApellido").value.trim(),
      nombre: $("vNombre").value.trim(),
      telefono: $("vTelefono").value.trim(),
      email: $("vEmail").value.trim(),
      fecha_nac: $("vFechaNac").value || null,
      comision_pct: Number($("vComision").value) || 0,
      activo: $("vActivo").checked ? 1 : 0,
    };
    puente.guardar(JSON.stringify(payload), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("errorVendedor").textContent = r.error; $("errorVendedor").hidden = false; return; }
      $("modalVendedor").hidden = true;
      refrescar();
    });
  }

  // -------------------------------------------------------------- eventos
  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;
    refrescar();

    $("fBusqueda").addEventListener("input", refrescar);
    $("fActivos").addEventListener("change", refrescar);

    $("btnNuevo").addEventListener("click", function () { abrirVendedor(null); });
    $("btnEditar").addEventListener("click", function () {
      if (seleccionId !== null) abrirVendedor(seleccionId);
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
    $("btnCancelarVendedor").addEventListener("click", function () { $("modalVendedor").hidden = true; });
    $("formVendedor").addEventListener("submit", guardarVendedor);

    $("btnDocumentacion").addEventListener("click", function () {
      var v = vendedorSeleccionado();
      if (v) puente.documentacion(v.id, v.apellido + ", " + v.nombre);
    });
  });
})();
