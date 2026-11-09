// Patitas — interacciones básicas del frontend.

document.addEventListener("DOMContentLoaded", () => {
  // Cierra el menú móvil al elegir una opción.
  const menu = document.getElementById("menu");
  if (menu) {
    menu.querySelectorAll(".nav-link").forEach((enlace) => {
      enlace.addEventListener("click", () => {
        const instancia = bootstrap.Collapse.getInstance(menu);
        if (instancia) instancia.hide();
      });
    });
  }

  // En el catálogo, aplica los filtros en cuanto cambias una opción.
  document.querySelectorAll(".filtros select").forEach((select) => {
    select.addEventListener("change", () => select.form.submit());
  });
});
