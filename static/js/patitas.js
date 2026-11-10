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

// Botón "mostrar contraseña"
document.addEventListener("click", (evento) => {
  const boton = evento.target.closest("[data-mostrar]");
  if (!boton) return;
  const campo = document.getElementById(boton.dataset.mostrar);
  const visible = campo.type === "text";
  campo.type = visible ? "password" : "text";
  boton.setAttribute("aria-label", visible ? "Mostrar contraseña" : "Ocultar contraseña");
  boton.querySelector("i").className = visible ? "bi bi-eye" : "bi bi-eye-slash";
});
