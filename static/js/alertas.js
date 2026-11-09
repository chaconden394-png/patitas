// Patitas — página de detalle de una Alerta Patitas.

document.addEventListener("DOMContentLoaded", () => {
  // ---------- Mapa con la zona aproximada ----------
  const contenedor = document.getElementById("mapa-alerta");
  if (contenedor && window.L) {
    const lat = parseFloat(contenedor.dataset.lat);
    const lng = parseFloat(contenedor.dataset.lng);
    const radioKm = parseFloat(contenedor.dataset.radioKm);

    const mapa = L.map(contenedor, { scrollWheelZoom: false }).setView([lat, lng], 11);
    // Mapa base gratuito de OpenStreetMap (requiere mostrar la atribución).
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(mapa);

    // Radio de aviso (15 km)
    L.circle([lat, lng], {
      radius: radioKm * 1000, color: "#6B8F71", weight: 1.5, dashArray: "6 6",
      fillColor: "#A7B89F", fillOpacity: 0.08,
    }).addTo(mapa);
    // Zona aproximada (~1 km): nunca el punto exacto
    L.circle([lat, lng], {
      radius: 800, color: "#E8763F", weight: 2, fillColor: "#FF8F5A", fillOpacity: 0.35,
    }).addTo(mapa);
  }

  // ---------- Compartir (botón en la tarjeta y en la barra del celular) ----------
  const estado = document.querySelector(".estado-compartir");
  document.querySelectorAll(".boton-compartir").forEach((boton) => {
    boton.addEventListener("click", async () => {
      const datos = { title: boton.dataset.titulo, text: boton.dataset.texto, url: window.location.href };
      try {
        if (navigator.share) {
          await navigator.share(datos);
        } else {
          await navigator.clipboard.writeText(datos.url);
          if (estado) estado.textContent = "Enlace copiado. Pégalo en WhatsApp o tus redes.";
        }
      } catch (error) {
        if (error.name !== "AbortError" && estado) {
          estado.textContent = "Copia el enlace desde la barra de direcciones para compartirlo.";
        }
      }
    });
  });
});
