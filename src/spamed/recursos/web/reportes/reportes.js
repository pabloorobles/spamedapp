(function () {
  "use strict";

  var dinero = window.SpamedUtil.dinero;
  var fecha = window.SpamedUtil.fecha;

  var puente = null;
  var reportesPorNombre = {}; // nombre -> [{campo, titulo}, ...]
  var camposMoneda = {};      // set (objeto) de nombres de campo en moneda
  var camposFecha = ["vencimiento", "proximo", "vto_pasaporte", "dni_vencimiento"];

  function $(id) { return document.getElementById(id); }

  function pct(valor) {
    var n = Number(valor) || 0;
    return n.toFixed(2).replace(".", ",") + " %";
  }

  function formatear(fila, campo) {
    if (camposMoneda[campo]) return dinero(fila[campo], fila.moneda || "");
    if (campo.indexOf("fecha_") === 0 || camposFecha.indexOf(campo) !== -1) {
      return fecha(fila[campo]);
    }
    if (campo === "pct_cobrado") return pct(fila[campo]);
    var v = fila[campo];
    return v === null || v === undefined ? "" : v;
  }

  // -------------------------------------------------------------- tabla
  function pintarCabecera(columnas) {
    $("cabTabla").innerHTML = "<tr>" + columnas.map(function (c) {
      var esNum = camposMoneda[c.campo] || c.campo === "pct_cobrado";
      return "<th" + (esNum ? " class='num'" : "") + ">" + c.titulo + "</th>";
    }).join("") + "</tr>";
  }

  function pintarFilas(columnas, filas) {
    var cuerpo = filas.map(function (f) {
      return "<tr>" + columnas.map(function (c) {
        var esNum = camposMoneda[c.campo] || c.campo === "pct_cobrado";
        return "<td" + (esNum ? " class='num'" : "") + ">" + formatear(f, c.campo) + "</td>";
      }).join("") + "</tr>";
    }).join("");
    $("tablaReporte").innerHTML = cuerpo ||
      "<tr><td colspan='" + columnas.length + "' class='vacio'>Sin datos para este reporte.</td></tr>";
  }

  // -------------------------------------------------------------- carga
  function refrescar() {
    if (!puente) return;
    var nombre = $("selReporte").value;
    if (!nombre) return;
    var columnas = reportesPorNombre[nombre] || [];
    pintarCabecera(columnas);
    puente.datos(nombre, function (json) {
      var r = JSON.parse(json);
      if (!r.ok) { $("bajada").textContent = "No se pudo cargar: " + r.error; return; }
      pintarFilas(columnas, r.filas);
      $("bajada").textContent = nombre;
      $("pie").textContent = r.filas.length + " fila(s)";
    });
  }
  window.refrescar = refrescar;

  function cargarMetadatos() {
    puente.metadatos(function (json) {
      var m = JSON.parse(json);
      camposMoneda = {};
      (m.campos_moneda || []).forEach(function (c) { camposMoneda[c] = true; });
      var sel = $("selReporte");
      sel.innerHTML = "";
      (m.reportes || []).forEach(function (r) {
        reportesPorNombre[r.nombre] = r.columnas;
        var op = document.createElement("option");
        op.value = r.nombre;
        op.textContent = r.nombre;
        sel.appendChild(op);
      });
      refrescar();
    });
  }

  // -------------------------------------------------------------- eventos
  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;
    cargarMetadatos();

    $("selReporte").addEventListener("change", refrescar);
    $("btnActualizar").addEventListener("click", refrescar);
    $("btnExcel").addEventListener("click", function () { puente.exportar($("selReporte").value); });
    $("btnPdf").addEventListener("click", function () { puente.exportar_pdf($("selReporte").value); });
  });
})();
