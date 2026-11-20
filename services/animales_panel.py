"""
Etapa 4 · Mi panel: publicar y administrar animales, sus fotos y mi refugio.

Todo se hace con el token de la persona (cliente_de_usuario), así que la base
de datos aplica sus reglas (migración 005): quién puede publicar, máximo 10
animales nuevos al día, máximo 3 fotos, fotos solo en la carpeta propia…
Este archivo valida los formularios y traduce los errores a mensajes en español.
"""
import re

from flask import current_app

from services import fotos
from services.animales import CAMPOS_DETALLE, es_uuid, fila_a_animal
from services.supabase_cliente import cliente_de_usuario

MAX_FOTOS = 3
ESPECIES = {"perro": "Perro", "gato": "Gato", "conejo": "Conejo", "ave": "Ave", "otro": "Otro"}
TAMANOS = {"pequeño": "Pequeño", "mediano": "Mediano", "grande": "Grande"}
SEXOS = {"hembra": "Hembra", "macho": "Macho", "desconocido": "No se sabe"}
ENERGIAS = {"baja": "Baja", "media": "Media", "alta": "Alta"}
# Perdidos y encontrados NO se publican aquí: tienen Alerta Patitas.
ESTADOS_PUBLICABLES = ["disponible", "urgente", "en_proceso", "hogar_temporal", "recuperacion", "adoptado"]
CONVIVENCIA = {"si": True, "no": False, "": None}

MENSAJE_GENERICO = "No pudimos completar la operación. Inténtalo de nuevo en unos minutos."
MENSAJE_SIN_PERMISO = ("Tu cuenta no puede publicar animales en este momento. "
                       "Si crees que es un error, escríbenos desde la página de contacto.")


class ErrorAnimal(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _anotar(texto, *datos):
    current_app.logger.warning(texto, *datos)


def _ejecutar(consulta, sin_permiso=MENSAJE_SIN_PERMISO):
    """Ejecuta una consulta y traduce los errores de la base de datos."""
    from postgrest.exceptions import APIError

    try:
        return consulta.execute()
    except APIError as error:
        _anotar("Error de la base de datos en animales · código=%s · mensaje=%s", error.code, error.message)
        if error.code == "23514":   # nuestras reglas (límites, fotos…): el mensaje ya está en español
            raise ErrorAnimal(error.message) from error
        if error.code == "42501":   # permisos / RLS
            raise ErrorAnimal(sin_permiso) from error
        raise ErrorAnimal(MENSAJE_GENERICO) from error
    except Exception as error:
        _anotar("No se pudo hablar con Supabase (animales) · %s: %s", type(error).__name__, error)
        raise ErrorAnimal(MENSAJE_GENERICO) from error


def _texto(valor, nombre, minimo, maximo, obligatorio=True):
    valor = " ".join((valor or "").split())
    if not valor and not obligatorio:
        return None
    if not minimo <= len(valor) <= maximo:
        if obligatorio and not valor:
            raise ErrorAnimal(f"Escribe {nombre}.")
        raise ErrorAnimal(f"{nombre[0].upper() + nombre[1:]} debe tener entre {minimo} y {maximo} caracteres.")
    return valor


def _parrafo(valor, nombre, maximo):
    """Texto largo opcional: conserva los saltos de línea, quita espacios sobrantes."""
    valor = "\n".join(" ".join(linea.split()) for linea in (valor or "").strip().splitlines()).strip()
    if len(valor) > maximo:
        raise ErrorAnimal(f"{nombre[0].upper() + nombre[1:]} puede tener máximo {maximo} caracteres.")
    return valor or None


def _opcion(valor, permitidas, nombre, obligatorio=True):
    if not valor and not obligatorio:
        return None
    if valor not in permitidas:
        raise ErrorAnimal(f"Elige {nombre}.")
    return valor


def _entero(valor, nombre, minimo, maximo):
    valor = (valor or "").strip()
    if not valor:
        return 0
    if not valor.isdigit() or not minimo <= int(valor) <= maximo:
        raise ErrorAnimal(f"{nombre[0].upper() + nombre[1:]} debe ser un número entre {minimo} y {maximo}.")
    return int(valor)


# ---------------------------------------------------------------------------
# Formulario del animal
# ---------------------------------------------------------------------------
def validar_animal(formulario, refugios_propios):
    """Convierte el formulario en columnas de la tabla `animales`. Lanza ErrorAnimal si algo falta."""
    if formulario.get("edad_desconocida") == "si":
        edad = None
    else:
        anios = _entero(formulario.get("edad_anios"), "los años", 0, 33)
        meses = _entero(formulario.get("edad_meses"), "los meses", 0, 11)
        edad = anios * 12 + meses
        if not (formulario.get("edad_anios") or "").strip() and not (formulario.get("edad_meses") or "").strip():
            raise ErrorAnimal("Escribe la edad aproximada o marca «No sé su edad».")

    refugio_id = formulario.get("refugio_id") or None
    if refugio_id and refugio_id not in {r["id"] for r in refugios_propios}:
        raise ErrorAnimal("Elige uno de tus refugios.")

    convivencia = {}
    for campo in ("convive_ninos", "convive_perros", "convive_gatos"):
        valor = formulario.get(campo, "")
        if valor not in CONVIVENCIA:
            raise ErrorAnimal("Revisa las respuestas de convivencia.")
        convivencia[campo] = CONVIVENCIA[valor]

    return {
        "nombre": _texto(formulario.get("nombre"), "el nombre", 1, 60),
        "especie": _opcion(formulario.get("especie"), ESPECIES, "la especie"),
        "raza": _texto(formulario.get("raza"), "la raza", 1, 60, obligatorio=False) or "No especificada",
        "edad_aproximada_meses": edad,
        "tamano": _opcion(formulario.get("tamano"), TAMANOS, "el tamaño"),
        "sexo": _opcion(formulario.get("sexo"), SEXOS, "el sexo"),
        "energia": _opcion(formulario.get("energia"), ENERGIAS, "el nivel de energía", obligatorio=False),
        "personalidad": _parrafo(formulario.get("personalidad"), "la personalidad", 1000),
        **convivencia,
        "vacunado": formulario.get("vacunado") == "si",
        "esterilizado": formulario.get("esterilizado") == "si",
        "enfermedades_conocidas": _parrafo(formulario.get("enfermedades_conocidas"), "las enfermedades", 1000),
        "necesidades_especiales": _parrafo(formulario.get("necesidades_especiales"), "las necesidades especiales", 1000),
        "requisitos_adopcion": _parrafo(formulario.get("requisitos_adopcion"), "los requisitos", 1000),
        "zona": _texto(formulario.get("zona"), "la colonia o zona", 3, 80),
        "estado": _opcion(formulario.get("estado"), ESTADOS_PUBLICABLES, "el estado"),
        "refugio_id": refugio_id,
    }


def animal_a_formulario(animal):
    """Valores del formulario de edición a partir de un animal guardado."""
    meses = animal.get("edad_meses")
    tri = {True: "si", False: "no", None: ""}
    return {
        "nombre": animal["nombre"], "especie": animal["especie"],
        "raza": "" if animal["raza"] == "No especificada" else animal["raza"],
        "edad_desconocida": "si" if meses is None else "",
        "edad_anios": "" if meses is None else str(meses // 12),
        "edad_meses": "" if meses is None else str(meses % 12),
        "tamano": animal["tamano"], "sexo": animal["sexo"], "energia": animal["energia"],
        "personalidad": animal["personalidad"],
        "convive_ninos": tri[animal["convive_ninos"]], "convive_perros": tri[animal["convive_perros"]],
        "convive_gatos": tri[animal["convive_gatos"]],
        "vacunado": "si" if animal["vacunado"] else "", "esterilizado": "si" if animal["esterilizado"] else "",
        "enfermedades_conocidas": animal["enfermedades"], "necesidades_especiales": animal["necesidades"],
        "requisitos_adopcion": animal["requisitos"], "zona": animal["zona"], "estado": animal["estado"],
        "refugio_id": (animal.get("refugio") or {}).get("id") or "",
    }


# ---------------------------------------------------------------------------
# Mis animales
# ---------------------------------------------------------------------------
def mis_animales(token, usuario_id):
    respuesta = _ejecutar(cliente_de_usuario(token).table("animales").select(CAMPOS_DETALLE + ",oculto")
                          .eq("responsable_id", usuario_id).order("publicado_en", desc=True).limit(200))
    animales = []
    for fila in respuesta.data:
        animal = fila_a_animal(fila)
        animal["oculto"] = bool(fila.get("oculto"))
        animales.append(animal)
    return animales


def obtener_mio(token, usuario_id, animal_id):
    """Un animal de la persona, o None si no existe o es de alguien más."""
    if not es_uuid(animal_id):
        return None
    respuesta = _ejecutar(cliente_de_usuario(token).table("animales").select(CAMPOS_DETALLE + ",oculto")
                          .eq("id", animal_id).eq("responsable_id", usuario_id).limit(1))
    if not respuesta.data:
        return None
    animal = fila_a_animal(respuesta.data[0])
    animal["oculto"] = bool(respuesta.data[0].get("oculto"))
    return animal


def crear(token, usuario_id, formulario, refugios_propios):
    datos = validar_animal(formulario, refugios_propios)
    respuesta = _ejecutar(cliente_de_usuario(token).table("animales")
                          .insert({"responsable_id": usuario_id, **datos}))
    return respuesta.data[0]["id"]


def actualizar(token, usuario_id, animal_id, formulario, refugios_propios):
    datos = validar_animal(formulario, refugios_propios)
    respuesta = _ejecutar(cliente_de_usuario(token).table("animales").update(datos)
                          .eq("id", animal_id).eq("responsable_id", usuario_id))
    if not respuesta.data:
        raise ErrorAnimal("No encontramos ese animal entre los tuyos.")


def cambiar_estado(token, usuario_id, animal_id, estado):
    if estado not in ESTADOS_PUBLICABLES:
        raise ErrorAnimal("Elige un estado válido.")
    respuesta = _ejecutar(cliente_de_usuario(token).table("animales").update({"estado": estado})
                          .eq("id", animal_id).eq("responsable_id", usuario_id))
    if not respuesta.data:
        raise ErrorAnimal("No encontramos ese animal entre los tuyos.")


def borrar(token, usuario_id, animal_id):
    """Borra el animal y después sus archivos de fotos."""
    animal = obtener_mio(token, usuario_id, animal_id)
    if animal is None:
        raise ErrorAnimal("No encontramos ese animal entre los tuyos.")
    cliente = cliente_de_usuario(token)
    respuesta = _ejecutar(cliente.table("animales").delete().eq("id", animal_id).eq("responsable_id", usuario_id))
    if not respuesta.data:
        raise ErrorAnimal("No encontramos ese animal entre los tuyos.")
    _borrar_archivos(cliente, [f["ruta"] for f in animal["fotos"]])
    return animal["nombre"]


# ---------------------------------------------------------------------------
# Fotos (máximo 3 por animal)
# ---------------------------------------------------------------------------
def _borrar_archivos(cliente, rutas):
    if not rutas:
        return
    try:
        cliente.storage.from_(fotos.BUCKET_ANIMALES).remove(rutas)
    except Exception as error:   # el registro ya no existe; el archivo queda huérfano pero no visible en Patitas
        _anotar("No se pudieron borrar fotos de animales %s · %s", rutas, error)


def subir_fotos(token, usuario_id, animal_id, archivos):
    """Sube varias fotos. Devuelve cuántas se guardaron; lanza ErrorAnimal con el primer problema."""
    animal = obtener_mio(token, usuario_id, animal_id)
    if animal is None:
        raise ErrorAnimal("No encontramos ese animal entre los tuyos.")
    archivos = [a for a in archivos if a]
    if not archivos:
        raise ErrorAnimal("Elige al menos una foto.")
    lugar = MAX_FOTOS - len(animal["fotos"])
    if len(archivos) > lugar:
        raise ErrorAnimal(f"Cada animal puede tener máximo {MAX_FOTOS} fotos. "
                          + (f"Puedes subir {lugar} más." if lugar > 0 else "Borra una para subir otra."))
    # Primero se limpian TODAS: si una no sirve, no se sube ninguna.
    try:
        limpias = [fotos.limpiar_foto(datos) for datos in archivos]
    except fotos.ErrorFoto as error:
        raise ErrorAnimal(error.mensaje)

    cliente = cliente_de_usuario(token)
    siguiente = max([f["orden"] for f in animal["fotos"]], default=-1) + 1
    guardadas = 0
    for i, foto in enumerate(limpias):
        ruta = fotos.nueva_ruta(usuario_id)
        try:
            cliente.storage.from_(fotos.BUCKET_ANIMALES).upload(ruta, foto, {"content-type": "image/jpeg"})
        except Exception as error:
            _anotar("No se pudo subir la foto del animal · %s: %s", type(error).__name__, error)
            raise ErrorAnimal("No pudimos subir la foto. Inténtalo de nuevo." if not guardadas else
                              f"Guardamos {guardadas} foto(s), pero no pudimos subir las demás.")
        try:
            _ejecutar(cliente.table("animales_fotos").insert(
                {"animal_id": animal_id, "ruta_archivo": ruta, "orden": min(siguiente + i, 20)}))
        except ErrorAnimal:
            _borrar_archivos(cliente, [ruta])   # no dejar archivos sueltos
            raise
        guardadas += 1
    return guardadas


def borrar_foto(token, usuario_id, animal_id, foto_id):
    animal = obtener_mio(token, usuario_id, animal_id)
    foto = next((f for f in (animal or {}).get("fotos", []) if f["id"] == foto_id), None)
    if foto is None:
        raise ErrorAnimal("No encontramos esa foto.")
    cliente = cliente_de_usuario(token)
    _ejecutar(cliente.table("animales_fotos").delete().eq("id", foto_id).eq("animal_id", animal_id))
    _borrar_archivos(cliente, [foto["ruta"]])


def foto_principal(token, usuario_id, animal_id, foto_id):
    """La foto elegida pasa al primer lugar; las demás conservan su orden."""
    animal = obtener_mio(token, usuario_id, animal_id)
    lista = (animal or {}).get("fotos", [])
    if not any(f["id"] == foto_id for f in lista):
        raise ErrorAnimal("No encontramos esa foto.")
    nuevas = [f for f in lista if f["id"] == foto_id] + [f for f in lista if f["id"] != foto_id]
    cliente = cliente_de_usuario(token)
    for orden, f in enumerate(nuevas):
        if f["orden"] != orden:
            _ejecutar(cliente.table("animales_fotos").update({"orden": orden}).eq("id", f["id"]))


# ---------------------------------------------------------------------------
# Mi refugio (cuentas de refugio)
# ---------------------------------------------------------------------------
ESTADOS_REFUGIO = {
    "pendiente": "Pendiente de verificación",
    "verificado": "Refugio verificado",
    "rechazado": "No aprobado",
    "suspendido": "Suspendido",
}


def mis_refugios(token, usuario_id):
    respuesta = _ejecutar(cliente_de_usuario(token).table("refugios")
                          .select("id,nombre,descripcion,zona,municipio,telefono_publico,correo_publico,"
                                  "estado_verificacion,creado_en")
                          .eq("responsable_id", usuario_id).order("creado_en").limit(10))
    return respuesta.data


def refugios_para_publicar(token, usuario_id):
    """Refugios propios a cuyo nombre se puede publicar (pendientes o verificados)."""
    return [r for r in mis_refugios(token, usuario_id) if r["estado_verificacion"] in ("pendiente", "verificado")]


def leer_mi_refugio(token, usuario_id):
    """El refugio de la persona (el primero) con su dirección privada, o None."""
    refugios = mis_refugios(token, usuario_id)
    if not refugios:
        return None
    refugio = dict(refugios[0])
    ubicacion = _ejecutar(cliente_de_usuario(token).table("refugios_ubicacion").select("direccion")
                          .eq("refugio_id", refugio["id"]).limit(1)).data
    refugio["direccion"] = ubicacion[0]["direccion"] if ubicacion else ""
    return refugio


def _telefono(valor):
    valor = re.sub(r"[\s\-().]", "", valor or "")
    if not valor:
        return None
    if not re.fullmatch(r"\+?[0-9]{10,15}", valor):
        raise ErrorAnimal("El teléfono debe tener de 10 a 15 dígitos (puede empezar con +).")
    return valor


def _correo(valor):
    valor = (valor or "").strip()
    if not valor:
        return None
    if len(valor) > 120 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", valor):
        raise ErrorAnimal("Escribe un correo público válido.")
    return valor


def validar_refugio(formulario):
    return {
        "nombre": _texto(formulario.get("nombre"), "el nombre del refugio", 3, 100),
        "descripcion": _parrafo(formulario.get("descripcion"), "la descripción", 1000),
        "zona": _texto(formulario.get("zona"), "la colonia o zona", 3, 80),
        "telefono_publico": _telefono(formulario.get("telefono_publico")),
        "correo_publico": _correo(formulario.get("correo_publico")),
    }


def guardar_mi_refugio(token, usuario_id, formulario):
    """Crea o actualiza el refugio de la persona. La dirección exacta va a una tabla privada."""
    datos = validar_refugio(formulario)
    direccion = _texto(formulario.get("direccion"), "la dirección", 5, 200, obligatorio=False)
    cliente = cliente_de_usuario(token)
    actual = mis_refugios(token, usuario_id)
    if actual:
        refugio_id = actual[0]["id"]
        _ejecutar(cliente.table("refugios").update(datos).eq("id", refugio_id).eq("responsable_id", usuario_id),
                  sin_permiso="No tienes permiso para cambiar ese refugio.")
        nuevo = False
    else:
        respuesta = _ejecutar(cliente.table("refugios").insert({"responsable_id": usuario_id, **datos}),
                              sin_permiso="No pudimos registrar el refugio con tu cuenta.")
        refugio_id = respuesta.data[0]["id"]
        nuevo = True
    if direccion:
        # Igual que la zona de alertas: primero actualizar; si no existe, crearla (sin "upsert").
        hecha = _ejecutar(cliente.table("refugios_ubicacion").update({"direccion": direccion})
                          .eq("refugio_id", refugio_id))
        if not hecha.data:
            _ejecutar(cliente.table("refugios_ubicacion").insert({"refugio_id": refugio_id, "direccion": direccion}))
    return nuevo
