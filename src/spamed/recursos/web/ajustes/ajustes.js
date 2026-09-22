(function () {
  "use strict";

  var puente = null;
  var valores = [];
  var seleccion = null;

  function $(id) { return document.getElementById(id); }
  function tipoActual() { return $("selLista").value; }

  function refrescar() {
    if (!puente) return;
    puente.valores(tipoActual(), function (json) {
      valores = JSON.parse(json);
      seleccion = null;
      pintar();
      actualizarBotones();
    });
  }
  window.refrescar = refrescar;

  function pintar() {
    var cuerpo = valores.map(function (v, i) {
      return "<tr data-i='" + i + "'><td>" + v + "</td><td style='text-align:right'>" +
        "<button type='button' class='btn-flecha' data-subir='" + i + "'" +
        (i === 0 ? " disabled" : "") + " title='Subir'>&uarr;</button>" +
        "<button type='button' class='btn-flecha' data-bajar='" + i + "'" +
        (i === valores.length - 1 ? " disabled" : "") + " title='Bajar'>&darr;</button>" +
        "</td></tr>";
    }).join("");
    $("tablaListas").innerHTML = cuerpo ||
      "<tr><td colspan='2' class='vacio'>Sin valores cargados.</td></tr>";

    Array.prototype.forEach.call($("tablaListas").querySelectorAll("tr[data-i]"), function (tr) {
      tr.addEventListener("click", function (ev) {
        if (ev.target.closest("button")) return;
        seleccion = valores[Number(tr.getAttribute("data-i"))];
        Array.prototype.forEach.call($("tablaListas").querySelectorAll("tr"),
          function (t) { t.classList.remove("seleccionada"); });
        tr.classList.add("seleccionada");
        actualizarBotones();
      });
    });
    Array.prototype.forEach.call($("tablaListas").querySelectorAll("[data-subir]"), function (b) {
      b.addEventListener("click", function () { mover(Number(b.getAttribute("data-subir")), -1); });
    });
    Array.prototype.forEach.call($("tablaListas").querySelectorAll("[data-bajar]"), function (b) {
      b.addEventListener("click", function () { mover(Number(b.getAttribute("data-bajar")), 1); });
    });
  }

  function actualizarBotones() {
    $("btnRenombrar").disabled = seleccion === null;
    $("btnQuitar").disabled = seleccion === null;
  }

  function mover(i, delta) {
    var j = i + delta;
    if (j < 0 || j >= valores.length) return;
    var tmp = valores[i];
    valores[i] = valores[j];
    valores[j] = tmp;
    puente.guardar_orden(tipoActual(), JSON.stringify(valores), function () { refrescar(); });
  }

  // -------------------------------------------------------------- eventos
  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;
    puente.tipos(function (json) {
      var tipos = JSON.parse(json);
      var sel = $("selLista");
      tipos.forEach(function (t) {
        var op = document.createElement("option");
        op.value = t.clave; op.textContent = t.etiqueta;
        sel.appendChild(op);
      });
      refrescar();
    });

    $("selLista").addEventListener("change", refrescar);

    $("btnAgregar").addEventListener("click", function () {
      var texto = window.prompt("Nuevo valor para «" + $("selLista").selectedOptions[0].textContent + "»:");
      if (texto === null) return;
      texto = texto.trim();
      if (!texto) return;
      puente.agregar(tipoActual(), texto, function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { window.alert(r.error); return; }
        refrescar();
      });
    });

    $("btnRenombrar").addEventListener("click", function () {
      if (seleccion === null) return;
      var texto = window.prompt("Nuevo nombre:", seleccion);
      if (texto === null) return;
      texto = texto.trim();
      if (!texto || texto === seleccion) return;
      var viejo = seleccion;
      puente.renombrar(tipoActual(), viejo, texto, function (json) {
        var r = JSON.parse(json);
        if (!r.ok) { window.alert(r.error); return; }
        refrescar();
        window.alert("Valor renombrado.\n\nOjo: los registros que ya tenían el valor "
          + "anterior siguen diciendo «" + viejo + "».");
      });
    });

    $("btnQuitar").addEventListener("click", function () {
      if (seleccion === null) return;
      if (!window.confirm("¿Quitar «" + seleccion + "» de la lista?\n\n"
        + "Los registros que ya lo usan no se modifican.")) return;
      puente.quitar(tipoActual(), seleccion, function () { refrescar(); });
    });
  });
})();
