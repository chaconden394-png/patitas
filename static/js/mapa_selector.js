// Patitas — mapa para marcar un punto (alerta, "Lo vi", zona de alertas).
//
// Uso en una plantilla:
//   <div data-selector-mapa data-lat-input="latitud" data-lng-input="longitud"
//        data-radio-km="15" data-boton-ubicacion="usar-ubicacion" data-estado="estado-mapa"></div>
// Los campos ocultos #latitud y #longitud reciben el punto elegido.

(function () {
  const TIJUANA = [32.5149, -117.0382];

  function iniciar(contenedor) {
    if (!window.L) return;
    const campoLat = document.getElementById(contenedor.dataset.latInput);
    const campoLng = document.getElementById(contenedor.dataset.lngInput);
    const radioKm = parseFloat(contenedor.dataset.radioKm || "0");
    const estado = document.getElementById(contenedor.dataset.estado || "");
    const botonUbicacion = document.getElementById(contenedor.dataset.botonUbicacion || "");

    const inicial = campoLat.value && campoLng.value
      ? [parseFloat(campoLat.value), parseFloat(campoLng.value)] : null;
    const mapa = L.map(contenedor, { scrollWheelZoom: false }).setView(inicial || TIJUANA, inicial ? 13 : 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(mapa);

    let marcador = null;
    let circulo = null;

    function poner(lat, lng, mover) {
      campoLat.value = lat.toFixed(6);
      campoLng.value = lng.toFixed(6);
      if (marcador) {
        marcador.setLatLng([lat, lng]);
      } else {
        marcador = L.circleMarker([lat, lng], {
          radius: 9, color: "#B5372C", weight: 3, fillColor: "#D9483B", fillOpacity: 0.9,
        }).addTo(mapa);
      }
      if (radioKm) {
        if (circulo) circulo.setLatLng([lat, lng]);
        else circulo = L.circle([lat, lng], {
          radius: radioKm * 1000, color: "#6B8F71", weight: 1.5, dashArray: "6 6",
          fillColor: "#A7B89F", fillOpacity: 0.1,
        }).addTo(mapa);
      }
      if (mover) mapa.setView([lat, lng], radioKm ? 11 : 15);
      if (estado) estado.textContent = "Punto marcado. Puedes tocar otro lugar del mapa para cambiarlo.";
    }

    if (inicial) poner(inicial[0], inicial[1], false);
    mapa.on("click", (e) => poner(e.latlng.lat, e.latlng.lng, false));

    if (botonUbicacion) {
      botonUbicacion.addEventListener("click", () => {
        if (!navigator.geolocation) {
          if (estado) estado.textContent = "Tu navegador no permite usar la ubicación. Marca el punto en el mapa.";
          return;
        }
        if (estado) estado.textContent = "Buscando tu ubicación…";
        navigator.geolocation.getCurrentPosition(
          (pos) => poner(pos.coords.latitude, pos.coords.longitude, true),
          () => { if (estado) estado.textContent = "No pudimos obtener tu ubicación. Marca el punto en el mapa."; },
          { enableHighAccuracy: true, timeout: 10000 }
        );
      });
    }

    // Si el mapa estaba oculto (por ejemplo, dentro de un formulario plegable), recalcula su tamaño al mostrarse.
    new ResizeObserver(() => mapa.invalidateSize()).observe(contenedor);
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-selector-mapa]").forEach(iniciar);

    // Vista previa de la foto elegida
    document.querySelectorAll("[data-vista-previa]").forEach((campo) => {
      const imagen = document.getElementById(campo.dataset.vistaPrevia);
      campo.addEventListener("change", () => {
        const archivo = campo.files && campo.files[0];
        if (!archivo) { imagen.hidden = true; return; }
        imagen.src = URL.createObjectURL(archivo);
        imagen.hidden = false;
      });
    });
  });
})();
