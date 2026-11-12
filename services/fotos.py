"""
Fotos que suben las personas (por ahora, las de Alerta Patitas).

Antes de guardar una foto, la app:
  1. Comprueba que de verdad sea una imagen (JPEG, PNG o WebP).
  2. La gira según la orientación de la cámara.
  3. Le QUITA los datos ocultos (EXIF), entre ellos la ubicación GPS donde se
     tomó, que muchas veces es la casa del dueño.
  4. La reduce a 1600 px como máximo y la guarda como JPEG.
"""
import io
import uuid
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES_ENTRADA = 8 * 1024 * 1024   # 8 MB (la foto original)
MAX_BYTES_SALIDA = 5 * 1024 * 1024    # 5 MB (límite del contenedor en Supabase)
MAX_LADO = 1600
FORMATOS = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO: JPEG de algunas cámaras
BUCKET = "fotos-alertas"

# Protección contra imágenes "bomba" (enormes al abrirse)
Image.MAX_IMAGE_PIXELS = 40_000_000


class ErrorFoto(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def limpiar_foto(datos):
    """Devuelve la foto como JPEG limpio (sin EXIF/GPS) o lanza ErrorFoto."""
    if not datos:
        raise ErrorFoto("Sube una foto de tu mascota.")
    if len(datos) > MAX_BYTES_ENTRADA:
        raise ErrorFoto("La foto pesa más de 8 MB. Elige una más ligera.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            imagen = Image.open(io.BytesIO(datos))
            if imagen.format not in FORMATOS:
                raise ErrorFoto("Formato no permitido. Usa una foto JPG, PNG o WebP.")
            imagen.load()
    except ErrorFoto:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError):
        raise ErrorFoto("No pudimos leer la foto. Usa una foto JPG, PNG o WebP "
                        "(si es de iPhone en formato HEIC, conviértela o haz una captura de pantalla).")

    imagen = ImageOps.exif_transpose(imagen)          # gira según la cámara
    if imagen.mode in ("RGBA", "LA", "P"):
        fondo = Image.new("RGB", imagen.size, (255, 255, 255))
        imagen = imagen.convert("RGBA")
        fondo.paste(imagen, mask=imagen.split()[-1])
        imagen = fondo
    else:
        imagen = imagen.convert("RGB")
    imagen.thumbnail((MAX_LADO, MAX_LADO))

    salida = io.BytesIO()
    # Al no pasar "exif=", Pillow guarda la foto SIN datos ocultos.
    imagen.save(salida, "JPEG", quality=85, optimize=True)
    resultado = salida.getvalue()
    if len(resultado) > MAX_BYTES_SALIDA:
        raise ErrorFoto("La foto es demasiado grande incluso reducida. Elige otra.")
    return resultado


def nueva_ruta(usuario_id):
    """Ruta dentro del contenedor: <id de la persona>/<id aleatorio>.jpg"""
    return f"{usuario_id}/{uuid.uuid4()}.jpg"


def url_publica(supabase_url, ruta):
    if not ruta:
        return None
    return f"{supabase_url}/storage/v1/object/public/{BUCKET}/{ruta}"
