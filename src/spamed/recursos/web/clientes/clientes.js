(function () {
  "use strict";

  var dinero = window.SpamedUtil.dinero;
  var fecha = window.SpamedUtil.fecha;
  var llenarSelect = window.SpamedUtil.llenarSelect;
  var MESES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago",
               "Sep", "Oct", "Nov", "Dic"];

  var puente = null;
  var filas = [];
  var seleccionId = null;
  var editandoClienteId = null;
  var subCliente = null; // {id, nombre} del cliente abierto en Seguimiento/Tarjetas
  var seguimientoSel = null;
  var tarjetaEditando = null;

  function $(id) { return document.getElementById(id); }

  // -------------------------------------------------------------- grilla
  function refrescar() {
    if (!puente) return;
    puente.listar(
      $("fBusqueda").value, $("fActivos").checked,
      Number($("fMesCumple").value) || 0, $("fSinNovedades").checked,
      function (json) {
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
        "<td>" + (f.canal || "") + "</td>" +
        "<td>" + fecha(f.fecha_nac) + "</td>" +
        "<td class='num'>" + (f.files || 0) + "</td>" +
        "<td class='num'>" + dinero(f.facturado, "PESOS") + "</td>" +
        "<td>" + fecha(f.ultima_interaccion) + "</td>" +
        "<td class='alertas'>" + ((f.alertas || []).join(" · ")) + "</td>" +
        "</tr>";
    }).join("");
    $("tablaClientes").innerHTML = cuerpo ||
      "<tr><td colspan='11' class='vacio'>Sin registros para el filtro actual.</td></tr>";
    Array.prototype.forEach.call($("tablaClientes").querySelectorAll("tr[data-id]"),
      function (tr) {
        tr.addEventListener("click", function () { seleccionar(Number(tr.getAttribute("data-id"))); });
      });
  }

  function seleccionar(id) {
    seleccionId = id;
    Array.prototype.forEach.call($("tablaClientes").querySelectorAll("tr[data-id]"),
      function (tr) {
        tr.classList.toggle("seleccionada", Number(tr.getAttribute("data-id")) === id);
      });
    actualizarBotones();
  }

  function actualizarBotones() {
    var hay = seleccionId !== null;
    ["btnEditar", "btnEliminar", "btnSeguimiento", "btnDocumentacion",
     "btnTarjetas", "btnEstadoCuenta"].forEach(function (id) { $(id).disabled = !hay; });
  }

  function clienteSeleccionado() {
    return filas.filter(function (f) { return f.id === seleccionId; })[0] || null;
  }

  // --------------------------------------------------------------- filtros
  function cargarFiltros() {
    var selMes = $("fMesCumple");
    for (var m = 1; m <= 12; m++) {
      var op = document.createElement("option");
      op.value = m;
      op.textContent = "Cumple en " + MESES[m];
      selMes.appendChild(op);
    }
    puente.listas(function (json) {
      var l = JSON.parse(json);
      llenarSelect($("clCanal"), l.canales, "—");
      llenarSelect($("sgCanal"), l.canales, "—");
      refrescar();
    });
  }

  // -------------------------------------------------------- modal cliente
  function abrirCliente(id) {
    editandoClienteId = id || null;
    $("errorCliente").hidden = true;
    $("tituloCliente").textContent = id ? "Editar cliente" : "Cliente";
    var f = document.getElementById("formCliente");
    f.reset();
    $("clActivo").checked = true;
    if (id) {
      puente.obtener(id, function (json) {
        var r = JSON.parse(json);
        if (!r.ok || !r.fila) return;
        var d = r.fila;
        $("clDni").value = d.dni || "";
        $("clApellido").value = d.apellido || "";
        $("clNombre").value = d.nombre || "";
        $("clTelefono").value = d.telefono || "";
        $("clEmail").value = d.email || "";
        $("clDireccion").value = d.direccion || "";
        $("clFechaNac").value = d.fecha_nac || "";
        $("clDniVto").value = d.dni_vencimiento || "";
        $("clFechaAlta").value = d.fecha_alta || "";
        $("clCanal").value = d.canal || "";
        $("clDetalleCanal").value = d.detalle_canal || "";
        $("clObservaciones").value = d.observaciones || "";
        $("clActivo").checked = !!d.activo;
        $("modalCliente").hidden = false;
      });
    } else {
      $("clFechaAlta").value = new Date().toISOString().slice(0, 10);
      $("modalCliente").hidden = false;
    }
  }

  function guardarCliente(ev) {
    ev.preventDefault();
    var payload = {
      id: editandoClienteId,
      dni: $("clDni").value.trim(),
      apellido: $("clApellido").value.trim(),
      nombre: $("clNombre").value.trim(),
      telefono: $("clTelefono").value.trim(),
      email: $("clEmail").value.trim(),
      direccion: $("clDireccion").value.trim(),
      fecha_nac: $("clFechaNac").value || null,
      dni_vencimiento: $("clDniVto").value || null,
      fecha_alta: $("clFechaAlta").value || null,
      canal: $("clCanal").value,
      detalle_canal: $("clDetalleCanal").value.trim(),
      observaciones: $("clObservaciones").value.trim(),
      activo: $("clActivo").checked ? 1 : 0,
    };
    puente.guardar(JSON.stringify(payload), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("errorCliente").textContent = r.error; $("errorCliente").hidden = false; return; }
      $("modalCliente").hidden = true;
      refrescar();
    });
  }

  // ----------------------------------------------------- modal seguimiento
  function abrirSeguimiento() {
    var c = clienteSeleccionado();
    if (!c) return;
    subCliente = {id: c.id, nombre: c.apellido + ", " + c.nombre};
    $("nombreSeguimiento").textContent = subCliente.nombre;
    $("errorSeguimiento").hidden = true;
    $("sgFecha").value = new Date().toISOString().slice(0, 10);
    $("sgCanal").value = "";
    $("sgNota").value = "";
    $("sgProximo").value = "";
    seguimientoSel = null;
    $("btnBorrarSeguimiento").disabled = true;
    refrescarSeguimiento();
    $("modalSeguimiento").hidden = false;
  }

  function refrescarSeguimiento() {
    puente.seguimientos_listar(subCliente.id, function (json) {
      var filas2 = JSON.parse(json);
      var cuerpo = filas2.map(function (f) {
        return "<tr data-id='" + f.id + "'><td>" + fecha(f.fecha) + "</td><td>" +
          (f.canal || "") + "</td><td>" + (f.nota || "") + "</td><td>" +
          fecha(f.proximo) + "</td><td>" + (f.file || "") + "</td></tr>";
      }).join("");
      $("tablaSeguimiento").innerHTML = cuerpo ||
        "<tr><td colspan='5' class='vacio'>Sin contactos registrados.</td></tr>";
      Array.prototype.forEach.call($("tablaSeguimiento").querySelectorAll("tr[data-id]"),
        function (tr) {
          tr.addEventListener("click", function () {
            seguimientoSel = Number(tr.getAttribute("data-id"));
            Array.prototype.forEach.call($("tablaSeguimiento").querySelectorAll("tr"),
              function (t) { t.classList.remove("seleccionada"); });
            tr.classList.add("seleccionada");
            $("btnBorrarSeguimiento").disabled = false;
          });
        });
    });
  }

  function registrarSeguimiento(ev) {
    ev.preventDefault();
    puente.seguimiento_guardar(JSON.stringify({
      cliente_id: subCliente.id, fecha: $("sgFecha").value, canal: $("sgCanal").value,
      nota: $("sgNota").value.trim(), proximo: $("sgProximo").value || null,
    }), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("errorSeguimiento").textContent = r.error; $("errorSeguimiento").hidden = false; return; }
      $("sgNota").value = "";
      $("sgProximo").value = "";
      refrescarSeguimiento();
    });
  }

  function borrarSeguimiento() {
    if (seguimientoSel === null) return;
    if (!window.confirm("¿Borrar el contacto seleccionado?")) return;
    puente.seguimiento_eliminar(seguimientoSel, function () {
      seguimientoSel = null;
      $("btnBorrarSeguimiento").disabled = true;
      refrescarSeguimiento();
    });
  }

  // --------------------------------------------------------- modal tarjetas
  function abrirTarjetas() {
    var c = clienteSeleccionado();
    if (!c) return;
    subCliente = {id: c.id, nombre: c.apellido + ", " + c.nombre};
    $("nombreTarjetas").textContent = subCliente.nombre;
    limpiarFormTarjeta();
    refrescarTarjetas();
    $("modalTarjetas").hidden = false;
  }

  function limpiarFormTarjeta() {
    tarjetaEditando = null;
    $("errorTarjeta").hidden = true;
    $("tjMarca").value = "";
    $("tjUltimos4").value = "";
    $("tjVencimiento").value = "";
    $("tjNota").value = "";
    $("btnGuardarTarjeta").textContent = "Agregar tarjeta";
    $("btnCancelarTarjeta").hidden = true;
  }

  function refrescarTarjetas() {
    puente.tarjetas_listar(subCliente.id, function (json) {
      var filas2 = JSON.parse(json);
      var cuerpo = filas2.map(function (f) {
        return "<tr><td>" + (f.marca || "") + "</td><td>" + (f.ultimos4 || "") +
          "</td><td>" + (f.vencimiento || "") + "</td><td>" + (f.nota || "") +
          "</td><td><button type='button' class='btn-suave' style='padding:2px 8px' " +
          "data-editar='" + f.id + "'>Editar</button> " +
          "<button type='button' class='icono-quitar' data-quitar='" + f.id + "'>Quitar</button></td></tr>";
      }).join("");
      $("tablaTarjetas").innerHTML = cuerpo ||
        "<tr><td colspan='5' class='vacio'>Sin tarjetas cargadas.</td></tr>";
      Array.prototype.forEach.call($("tablaTarjetas").querySelectorAll("[data-editar]"),
        function (b) {
          b.addEventListener("click", function () {
            var f = filas2.filter(function (x) { return x.id === Number(b.getAttribute("data-editar")); })[0];
            if (!f) return;
            tarjetaEditando = f.id;
            $("tjMarca").value = f.marca || "";
            $("tjUltimos4").value = f.ultimos4 || "";
            $("tjVencimiento").value = f.vencimiento || "";
            $("tjNota").value = f.nota || "";
            $("btnGuardarTarjeta").textContent = "Guardar cambios";
            $("btnCancelarTarjeta").hidden = false;
          });
        });
      Array.prototype.forEach.call($("tablaTarjetas").querySelectorAll("[data-quitar]"),
        function (b) {
          b.addEventListener("click", function () {
            if (!window.confirm("¿Quitar esta tarjeta?")) return;
            puente.tarjeta_eliminar(Number(b.getAttribute("data-quitar")), function () {
              refrescarTarjetas();
            });
          });
        });
    });
  }

  function guardarTarjeta(ev) {
    ev.preventDefault();
    puente.tarjeta_guardar(JSON.stringify({
      id: tarjetaEditando, cliente_id: subCliente.id,
      marca: $("tjMarca").value.trim(), ultimos4: $("tjUltimos4").value.trim(),
      vencimiento: $("tjVencimiento").value.trim(), nota: $("tjNota").value.trim(),
    }), function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("errorTarjeta").textContent = r.error; $("errorTarjeta").hidden = false; return; }
      limpiarFormTarjeta();
      refrescarTarjetas();
    });
  }

  // -------------------------------------------------------------- eventos
  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;
    cargarFiltros();

    $("fBusqueda").addEventListener("input", refrescar);
    $("fActivos").addEventListener("change", refrescar);
    $("fMesCumple").addEventListener("change", refrescar);
    $("fSinNovedades").addEventListener("change", refrescar);

    $("btnNuevo").addEventListener("click", function () { abrirCliente(null); });
    $("btnEditar").addEventListener("click", function () {
      if (seleccionId !== null) abrirCliente(seleccionId);
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
    $("btnCancelarCliente").addEventListener("click", function () { $("modalCliente").hidden = true; });
    $("formCliente").addEventListener("submit", guardarCliente);

    $("btnSeguimiento").addEventListener("click", abrirSeguimiento);
    $("btnCerrarSeguimiento").addEventListener("click", function () {
      $("modalSeguimiento").hidden = true;
    });
    $("formSeguimiento").addEventListener("submit", registrarSeguimiento);
    $("btnBorrarSeguimiento").addEventListener("click", borrarSeguimiento);

    $("btnTarjetas").addEventListener("click", abrirTarjetas);
    $("btnCerrarTarjetas").addEventListener("click", function () { $("modalTarjetas").hidden = true; });
    $("formTarjeta").addEventListener("submit", guardarTarjeta);
    $("btnCancelarTarjeta").addEventListener("click", limpiarFormTarjeta);

    $("btnDocumentacion").addEventListener("click", function () {
      var c = clienteSeleccionado();
      if (c) puente.documentacion(c.id, c.apellido + ", " + c.nombre);
    });
    $("btnEstadoCuenta").addEventListener("click", function () {
      var c = clienteSeleccionado();
      if (c) puente.estado_cuenta(c.id, c.apellido);
    });
  });
})();
