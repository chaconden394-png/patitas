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
  document.querySelectorAll(".filtros select, .filtros input[type=checkbox]").forEach((campo) => {
    campo.addEventListener("change", () => campo.form.submit());
  });

  // Ficha del animal: al tocar una miniatura, se muestra en grande.
  document.querySelectorAll("[data-galeria]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const principal = document.getElementById(boton.dataset.galeria);
      principal.src = boton.dataset.src;
      document.querySelectorAll(`[data-galeria="${boton.dataset.galeria}"]`)
        .forEach((b) => b.setAttribute("aria-pressed", b === boton ? "true" : "false"));
    });
  });

  // Subir fotos: vista previa de varias fotos y aviso si se eligen demasiadas.
  document.querySelectorAll("[data-previas]").forEach((campo) => {
    const contenedor = document.getElementById(campo.dataset.previas);
    const aviso = document.getElementById(campo.dataset.aviso);
    const maximo = Number(campo.dataset.maximo || 3);
    campo.addEventListener("change", () => {
      contenedor.replaceChildren();
      const archivos = [...(campo.files || [])];
      archivos.slice(0, maximo).forEach((archivo) => {
        const img = document.createElement("img");
        img.src = URL.createObjectURL(archivo);
        img.alt = "Vista previa";
        img.className = "foto-previa-mini";
        contenedor.appendChild(img);
      });
      if (aviso) aviso.hidden = archivos.length <= maximo;
      if (campo.form) campo.form.querySelector("[type=submit]").disabled = archivos.length === 0 || archivos.length > maximo;
    });
  });

  // "No sé su edad" desactiva los campos de años y meses.
  document.querySelectorAll("[data-desactiva]").forEach((casilla) => {
    const campos = casilla.dataset.desactiva.split(",").map((id) => document.getElementById(id));
    const aplicar = () => campos.forEach((c) => { c.disabled = casilla.checked; });
    casilla.addEventListener("change", aplicar);
    aplicar();
  });
});

// Botones que piden confirmación antes de enviar (por ejemplo "Borrar")
document.addEventListener("submit", (evento) => {
  const mensaje = evento.target.dataset.confirmar;
  if (mensaje && !window.confirm(mensaje)) evento.preventDefault();
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

// ---------------------------------------------------------------------------
// Fotos más ligeras antes de enviarlas.
// En Vercel cada envío puede pesar máximo 4.5 MB, y una foto de celular puede
// pesar más. Aquí se reduce a 1600 px (el mismo tamaño que guarda el servidor)
// y se convierte a JPEG; el servidor la vuelve a revisar y limpiar de todos modos.
// ---------------------------------------------------------------------------
const LADO_MAXIMO = 1600;

async function reducirFoto(archivo) {
  if (!archivo.type.startsWith("image/")) return archivo;
  try {
    const imagen = await createImageBitmap(archivo, { imageOrientation: "from-image" });
    const escala = Math.min(1, LADO_MAXIMO / Math.max(imagen.width, imagen.height));
    const lienzo = document.createElement("canvas");
    lienzo.width = Math.round(imagen.width * escala);
    lienzo.height = Math.round(imagen.height * escala);
    const contexto = lienzo.getContext("2d");
    contexto.fillStyle = "#ffffff";                 // fondo blanco para PNG transparentes
    contexto.fillRect(0, 0, lienzo.width, lienzo.height);
    contexto.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
    const reducida = await new Promise((listo) => lienzo.toBlob(listo, "image/jpeg", 0.88));
    if (!reducida || (reducida.size >= archivo.size && escala === 1 && archivo.type === "image/jpeg")) return archivo;
    return new File([reducida], archivo.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch (error) {
    return archivo;   // si este navegador no puede reducirla, se envía tal cual
  }
}

document.addEventListener("submit", async (evento) => {
  const formulario = evento.target;
  const campos = [...formulario.querySelectorAll("input[type=file][data-reducir]")].filter((c) => c.files.length);
  if (!campos.length || evento.defaultPrevented || formulario.dataset.fotosListas) return;
  evento.preventDefault();
  const boton = formulario.querySelector("[type=submit]");
  const textoOriginal = boton ? boton.innerHTML : "";
  if (boton) { boton.disabled = true; boton.textContent = "Preparando fotos…"; }
  try {
    for (const campo of campos) {
      const lista = new DataTransfer();
      for (const archivo of campo.files) lista.items.add(await reducirFoto(archivo));
      campo.files = lista.files;
    }
  } catch (error) {
    // Navegador sin DataTransfer: se envían las fotos originales.
  }
  formulario.dataset.fotosListas = "1";
  if (boton) boton.innerHTML = textoOriginal;
  formulario.submit();
});
