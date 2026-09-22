(function () {
  "use strict";

  var puente = null;

  function $(id) { return document.getElementById(id); }

  function cargarInfo() {
    if (!puente) return;
    puente.info(function (json) {
      var r = JSON.parse(json);
      $("btnTema").textContent = "Cambiar a " + (r.tema === "oscuro" ? "claro" : "oscuro");
      $("nombreVersion").textContent = r.app_nombre + " " + r.app_version;
      $("detalleCarpeta").textContent = "Ahí viven la base y las copias: " + r.carpeta_datos;
    });
  }
  window.refrescar = cargarInfo;

  new QWebChannel(qt.webChannelTransport, function (canal) {
    puente = canal.objects.puente;
    cargarInfo();

    $("btnPlantilla").addEventListener("click", function () { puente.descargar_plantilla(); });
    $("btnImportar").addEventListener("click", function () { puente.importar_excel(); });
    $("btnBackup").addEventListener("click", function () { puente.backup(); });
    $("btnRestaurar").addEventListener("click", function () { puente.restaurar(); });
    $("btnCarpeta").addEventListener("click", function () { puente.abrir_carpeta(); });
    $("btnTema").addEventListener("click", function () { puente.alternar_tema(); });
    $("btnConfigurar").addEventListener("click", function () { puente.configurar(); });
    $("btnDiagnostico").addEventListener("click", function () { puente.diagnostico(); });
    $("btnAcerca").addEventListener("click", function () { puente.acerca_de(); });
  });
})();
