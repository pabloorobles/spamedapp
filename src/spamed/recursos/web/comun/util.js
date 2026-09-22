/* Spamed Travel — utilidades compartidas por todas las pantallas web.
   Sin dependencias de ninguna pantalla en particular. */
window.SpamedUtil = (function () {
  "use strict";

  function slug(nombre) {
    return String(nombre).toLowerCase().replace(/ /g, "-");
  }

  function dinero(valor, moneda) {
    var n = Number(valor) || 0;
    var texto = new Intl.NumberFormat("es-AR",
      {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(n);
    var simbolo = moneda === "PESOS" ? "$" : moneda === "DOLAR" ? "US$" : "";
    return (simbolo + " " + texto).trim();
  }

  function fecha(iso) {
    if (!iso) return "";
    var p = String(iso).slice(0, 10).split("-");
    return p.length === 3 ? p[2] + "/" + p[1] + "/" + p[0] : "";
  }

  function badge(estado) {
    return '<span class="badge" style="background:var(--estado-' + slug(estado) + ')">' +
      estado + '</span>';
  }

  function llenarSelect(sel, valores, primeraOpcion) {
    sel.innerHTML = "";
    if (primeraOpcion) {
      var op0 = document.createElement("option");
      op0.value = "";
      op0.textContent = primeraOpcion;
      sel.appendChild(op0);
    }
    valores.forEach(function (v) {
      var op = document.createElement("option");
      op.value = v;
      op.textContent = v;
      sel.appendChild(op);
    });
  }

  return {slug: slug, dinero: dinero, fecha: fecha, badge: badge,
          llenarSelect: llenarSelect};
})();
