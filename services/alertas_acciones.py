"""
Alerta Patitas · acciones de personas con sesión iniciada (Parte B).

Todo se hace con el token de la persona (cliente_de_usuario), así que la base
de datos aplica sus reglas: límites de alertas, quién ve qué, radio de 15 km…
Este archivo valida los datos y traduce los errores a mensajes en español.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from services import fotos
from services.alertas import ZONA_HORARIA, a_fecha, fila_a_alerta, CAMPOS_ALERTA
from services.supabase_cliente import cliente_de_usuario

ESPECIES = {"perro": "Perro", "gato": "Gato", "conejo": "Conejo", "ave": "Ave", "otro": "Otro"}
SEXOS = {"hembra": "Hembra", "macho": "Macho", "desconocido": "No sé"}
TAMANOS = {"pequeño": "Pequeño", "mediano": "Mediano", "grande": "Grande"}
MENSAJE_GENERICO = "No pudimos completar la operación. Inténtalo de nuevo en unos minutos."


class ErrorAlerta(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _anotar(texto, *datos):
    current_app.logger.warning(texto, *datos)


def _ejecutar(consulta):
    """Ejecuta una consulta y traduce los errores de la base de datos."""
    from postgrest.exceptions import APIError

    try:
        return consulta.execute()
    except APIError as error:
        _anotar("Error de la base de datos en alertas · código=%s · mensaje=%s", error.code, error.message)
        if error.code == "23514":   # nuestras reglas (límites, fechas…): el mensaje ya está en español
            raise ErrorAlerta(error.message) from error
        if error.code == "42501":
            raise ErrorAlerta("No tienes permiso para hacer eso.") from error
        raise ErrorAlerta(MENSAJE_GENERICO) from error
    except Exception as error:
        _anotar("No se pudo hablar con Supabase (alertas) · %s: %s", type(error).__name__, error)
        raise ErrorAlerta(MENSAJE_GENERICO) from error


def _texto(valor, nombre, minimo, maximo, obligatorio=True):
    valor = " ".join((valor or "").split())
    if not valor and not obligatorio:
        return ""
    if not minimo <= len(valor) <= maximo:
        if obligatorio and not valor:
            raise ErrorAlerta(f"Escribe {nombre}.")
        raise ErrorAlerta(f"{nombre[0].upper() + nombre[1:]} debe tener entre {minimo} y {maximo} caracteres.")
    return valor


def _opcion(valor, permitidas, nombre):
    if valor not in permitidas:
        raise ErrorAlerta(f"Elige {nombre}.")
    return valor


def coordenadas(lat, lng, obligatorio=True):
    """Valida latitud/longitud del formulario (vienen como texto)."""
    if not lat and not lng and not obligatorio:
        return None, None
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise ErrorAlerta("Marca el lugar en el mapa o usa tu ubicación.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ErrorAlerta("La ubicación no es válida. Márcala de nuevo en el mapa.")
    return round(lat, 6), round(lng, 6)


def fecha_del_formulario(valor, nombre="la fecha y hora"):
    """'2026-11-09T21:30' (hora de Tijuana) -> datetime en UTC."""
    try:
        local = datetime.strptime(valor or "", "%Y-%m-%dT%H:%M").replace(tzinfo=ZONA_HORARIA)
    except ValueError:
        raise ErrorAlerta(f"Escribe {nombre}.")
    ahora = datetime.now(timezone.utc)
    if local > ahora + timedelta(hours=1):
        raise ErrorAlerta("La fecha no puede ser en el futuro.")
    if local < ahora - timedelta(days=365):
        raise ErrorAlerta("La fecha es de hace más de un año. Revisa que esté bien escrita.")
    return local.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Emitir una alerta
# ---------------------------------------------------------------------------
def validar_alerta(formulario):
    return {
        "p_nombre": _texto(formulario.get("nombre_mascota"), "el nombre de tu mascota", 1, 60),
        "p_especie": _opcion(formulario.get("especie"), ESPECIES, "la especie"),
        "p_sexo": _opcion(formulario.get("sexo"), SEXOS, "el sexo"),
        "p_tamano": _opcion(formulario.get("tamano"), TAMANOS, "el tamaño"),
        "p_edad": _texto(formulario.get("edad_aproximada"), "la edad", 1, 40, obligatorio=False),
        "p_raza": _texto(formulario.get("raza"), "la raza", 1, 60, obligatorio=False),
        "p_color": _texto(formulario.get("color"), "el color", 2, 80),
        "p_senas": _texto(formulario.get("senas_particulares"), "las señas particulares", 1, 500, obligatorio=False),
        "p_collar": _texto(formulario.get("collar"), "el collar", 1, 200, obligatorio=False),
        "p_descripcion": _texto(formulario.get("descripcion"), "la descripción", 1, 1000, obligatorio=False),
        "p_zona": _texto(formulario.get("zona_referencia"), "la zona o una referencia", 3, 120),
        "p_visto": fecha_del_formulario(formulario.get("visto_por_ultima_vez")).isoformat(),
        "p_mostrar_telefono": formulario.get("mostrar_telefono") == "si",
    }


def emitir(token, usuario_id, formulario, foto_bytes):
    datos = validar_alerta(formulario)
    lat, lng = coordenadas(formulario.get("latitud"), formulario.get("longitud"))
    try:
        foto_limpia = fotos.limpiar_foto(foto_bytes)
    except fotos.ErrorFoto as error:
        raise ErrorAlerta(error.mensaje)

    cliente = cliente_de_usuario(token)
    ruta = fotos.nueva_ruta(usuario_id)
    try:
        cliente.storage.from_(fotos.BUCKET).upload(ruta, foto_limpia, {"content-type": "image/jpeg"})
    except Exception as error:
        _anotar("No se pudo subir la foto de la alerta · %s: %s", type(error).__name__, error)
        raise ErrorAlerta("No pudimos subir la foto. Inténtalo de nuevo.")

    datos.update({"p_ruta_foto": ruta, "p_latitud": lat, "p_longitud": lng})
    try:
        respuesta = _ejecutar(cliente.rpc("emitir_alerta", datos))
    except ErrorAlerta:
        _borrar_foto(cliente, ruta)   # no dejar fotos sueltas si la alerta no se guardó
        raise
    return respuesta.data


def _borrar_foto(cliente, ruta):
    try:
        cliente.storage.from_(fotos.BUCKET).remove([ruta])
    except Exception as error:
        _anotar("No se pudo borrar la foto %s · %s", ruta, error)


# ---------------------------------------------------------------------------
# Mis alertas: cerrar y renovar
# ---------------------------------------------------------------------------
def mis_alertas(token, usuario_id):
    respuesta = _ejecutar(cliente_de_usuario(token).table("alertas").select(CAMPOS_ALERTA)
                          .eq("emisor_id", usuario_id).order("creada_en", desc=True).limit(50))
    return [fila_a_alerta(f) for f in respuesta.data]


def cerrar(token, usuario_id, alerta_id, estado):
    if estado not in ("encontrada", "cancelada"):
        raise ErrorAlerta("Elige si la encontraste o si quieres cancelar la alerta.")
    respuesta = _ejecutar(cliente_de_usuario(token).table("alertas").update({"estado": estado})
                          .eq("id", alerta_id).eq("emisor_id", usuario_id))
    if not respuesta.data:
        raise ErrorAlerta("No encontramos esa alerta entre las tuyas.")


def renovar(token, alerta_id):
    return a_fecha(_ejecutar(cliente_de_usuario(token).rpc("renovar_alerta", {"p_alerta": alerta_id})).data)


# ---------------------------------------------------------------------------
# Avistamientos ("Lo vi")
# ---------------------------------------------------------------------------
def reportar_avistamiento(token, usuario_id, alerta_id, formulario):
    lat, lng = coordenadas(formulario.get("latitud"), formulario.get("longitud"), obligatorio=False)
    datos = {
        "alerta_id": alerta_id,
        "reportado_por": usuario_id,
        "lugar": _texto(formulario.get("lugar"), "dónde lo viste", 3, 200),
        "comentario": _texto(formulario.get("comentario"), "el comentario", 1, 500, obligatorio=False) or None,
        "visto_en": fecha_del_formulario(formulario.get("visto_en"), "cuándo lo viste").isoformat(),
        "latitud": lat,
        "longitud": lng,
    }
    _ejecutar(cliente_de_usuario(token).table("avistamientos").insert(datos))


def avistamientos_de(token, alerta_id):
    """La base de datos solo entrega los avistamientos a la dueña de la alerta (y a quien los reportó)."""
    respuesta = _ejecutar(cliente_de_usuario(token).table("avistamientos")
                          .select("id,lugar,comentario,visto_en,latitud,longitud,creado_en,"
                                  "reportado_por,persona:perfiles(nombre_publico)")
                          .eq("alerta_id", alerta_id).order("visto_en", desc=True).limit(100))
    return [{
        "lugar": f["lugar"], "comentario": f.get("comentario") or "",
        "visto_en": a_fecha(f["visto_en"]),
        "latitud": float(f["latitud"]) if f.get("latitud") is not None else None,
        "longitud": float(f["longitud"]) if f.get("longitud") is not None else None,
        "reportado_por": f.get("reportado_por"),
        "persona": (f.get("persona") or {}).get("nombre_publico") or "Usuario de Patitas",
    } for f in respuesta.data]


def telefono_contacto(token, alerta_id):
    """Solo devuelve el teléfono si la dueña lo autorizó y la alerta sigue activa."""
    return _ejecutar(cliente_de_usuario(token).rpc("telefono_contacto_alerta", {"id_alerta": alerta_id})).data


# ---------------------------------------------------------------------------
# Zona de alertas
# ---------------------------------------------------------------------------
def leer_zona(token, usuario_id):
    respuesta = _ejecutar(cliente_de_usuario(token).table("zonas_alerta")
                          .select("latitud,longitud,acepta_alertas").eq("usuario_id", usuario_id).limit(1))
    if not respuesta.data:
        return None
    z = respuesta.data[0]
    return {"latitud": float(z["latitud"]), "longitud": float(z["longitud"]), "acepta_alertas": z["acepta_alertas"]}


def guardar_zona(token, usuario_id, formulario):
    lat, lng = coordenadas(formulario.get("latitud"), formulario.get("longitud"))
    datos = {
        # La base de datos la redondea a ≈ 1 km; aquí también, para no enviar más precisión de la necesaria.
        "latitud": round(lat, 2), "longitud": round(lng, 2),
        "acepta_alertas": formulario.get("acepta_alertas") == "si",
    }
    cliente = cliente_de_usuario(token)
    # Primero intenta actualizar; si aún no tiene zona, la crea. (Un "upsert" pediría
    # permiso para cambiar usuario_id, que la base de datos no da a propósito.)
    actualizada = _ejecutar(cliente.table("zonas_alerta").update(datos).eq("usuario_id", usuario_id))
    if not actualizada.data:
        _ejecutar(cliente.table("zonas_alerta").insert({"usuario_id": usuario_id, **datos}))


def borrar_zona(token, usuario_id):
    _ejecutar(cliente_de_usuario(token).table("zonas_alerta").delete().eq("usuario_id", usuario_id))


# ---------------------------------------------------------------------------
# Notificaciones
# ---------------------------------------------------------------------------
def contar_no_leidas(token):
    try:
        respuesta = (cliente_de_usuario(token).table("notificaciones")
                     .select("id", count="exact", head=True).eq("leida", False).execute())
        return respuesta.count or 0
    except Exception as error:   # la campana nunca debe romper la página
        _anotar("No se pudieron contar las notificaciones · %s", error)
        return 0


def listar_notificaciones(token):
    respuesta = _ejecutar(cliente_de_usuario(token).table("notificaciones")
                          .select("id,tipo,alerta_id,titulo,cuerpo,leida,creada_en")
                          .order("creada_en", desc=True).limit(50))
    return [dict(f, creada_en=a_fecha(f["creada_en"])) for f in respuesta.data]


def marcar_leidas(token, usuario_id):
    _ejecutar(cliente_de_usuario(token).table("notificaciones").update({"leida": True})
              .eq("usuario_id", usuario_id).eq("leida", False))
