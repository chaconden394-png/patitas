"""
Cuentas de Patitas con Supabase Auth.

Este archivo solo habla con Supabase. Lo que se guarda en la sesión del
navegador y los permisos por página están en services/sesion.py.

Los enlaces de los correos (confirmar cuenta, recuperar contraseña) llevan un
token_hash que la app verifica en /auth/confirmar. Para eso hay que cambiar
las plantillas de correo en Supabase (ver GUIA_ETAPA3.md).
"""
import re

from services.supabase_cliente import cliente_auth, cliente_de_usuario

TIPOS_CUENTA = {
    "adoptante": ("bi-house-heart", "Quiero adoptar"),
    "rescatista": ("bi-person-heart", "Soy rescatista independiente"),
    "refugio": ("bi-buildings", "Represento un refugio o asociación"),
    "reportante": ("bi-megaphone", "Quiero reportar un animal"),
    "voluntario": ("bi-people", "Voluntariado u hogar temporal"),
    "negocio": ("bi-shop", "Veterinaria o negocio pet friendly"),
}
NOMBRES_TIPO = {
    "adoptante": "Adoptante", "rescatista": "Rescatista independiente", "refugio": "Refugio o asociación",
    "reportante": "Reportes de animales", "voluntario": "Voluntariado y hogar temporal",
    "negocio": "Veterinaria o negocio",
}
NIVELES = {
    "registrada": "Cuenta registrada",
    "identidad_verificada": "Identidad verificada",
    "habilitada": "Habilitada para adoptar o publicar",
}

PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATRON_TELEFONO = re.compile(r"^\+?[0-9]{10,15}$")


class ErrorCuenta(Exception):
    """Error que se puede mostrar tal cual a la persona."""

    def __init__(self, mensaje, codigo=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


# Mensajes en español para los códigos de error de Supabase Auth.
MENSAJES_ERROR = {
    "invalid_credentials": "Correo o contraseña incorrectos.",
    "email_not_confirmed": "Primero confirma tu correo. Revisa tu bandeja de entrada (y la de spam).",
    "user_already_exists": "Ya existe una cuenta con ese correo. Inicia sesión o recupera tu contraseña.",
    "email_exists": "Ya existe una cuenta con ese correo. Inicia sesión o recupera tu contraseña.",
    "weak_password": "La contraseña es demasiado débil. Usa al menos 8 caracteres con letras y números.",
    "same_password": "La nueva contraseña debe ser distinta de la anterior.",
    "otp_expired": "El enlace ya expiró o ya se usó. Pide uno nuevo.",
    "email_address_invalid": "Ese correo no es válido.",
    "email_address_not_authorized": (
        "Supabase no puede enviar correos a esa dirección todavía. "
        "Mientras no configures un servicio de correo propio, solo llegan a los miembros de tu equipo de Supabase."
    ),
    "over_email_send_rate_limit": "Se enviaron demasiados correos. Espera un rato e inténtalo de nuevo.",
    "over_request_rate_limit": "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
    "signup_disabled": "El registro de cuentas está desactivado en este momento.",
    "user_banned": "Esta cuenta está suspendida. Escríbenos si crees que es un error.",
    "session_not_found": "Tu sesión terminó. Inicia sesión de nuevo.",
    "bad_jwt": "Tu sesión terminó. Inicia sesión de nuevo.",
    "refresh_token_not_found": "Tu sesión terminó. Inicia sesión de nuevo.",
    "refresh_token_already_used": "Tu sesión terminó. Inicia sesión de nuevo.",
}
MENSAJE_GENERICO = "No pudimos completar la operación. Inténtalo de nuevo en unos minutos."


MENSAJE_ERROR_CORREO = (
    "Tu cuenta no se pudo crear porque falló el envío del correo. "
    "Inténtalo de nuevo más tarde."
)


def _anotar(texto, *datos):
    """Escribe el detalle técnico en la TERMINAL (nunca se muestra en la página).
    Sirve para diagnosticar errores. No incluye contraseñas."""
    try:
        from flask import current_app
        current_app.logger.warning(texto, *datos)
    except RuntimeError:  # fuera de una petición de Flask
        pass


def _traducir(error):
    """Convierte un error de Supabase en ErrorCuenta con mensaje en español."""
    codigo = getattr(error, "code", None)
    _anotar("Supabase Auth respondió con error · código=%s · estado=%s · mensaje=%s",
            codigo, getattr(error, "status", None), getattr(error, "message", str(error)))
    if codigo in MENSAJES_ERROR:
        return ErrorCuenta(MENSAJES_ERROR[codigo], codigo)
    # Supabase responde "Error sending ... email" cuando falla el SMTP.
    if "sending" in str(getattr(error, "message", "")).lower():
        return ErrorCuenta(MENSAJE_ERROR_CORREO, "envio_correo")
    return ErrorCuenta(MENSAJE_GENERICO, codigo)


def _llamar(funcion, *args, **kwargs):
    from supabase_auth.errors import AuthError

    try:
        return funcion(*args, **kwargs)
    except AuthError as error:
        raise _traducir(error) from error
    except Exception as error:  # red caída, Supabase sin responder…
        _anotar("No se pudo hablar con Supabase Auth · %s: %s", type(error).__name__, error)
        raise ErrorCuenta(MENSAJE_GENERICO) from error


def _sesion_a_dict(sesion):
    return {
        "access_token": sesion.access_token,
        "refresh_token": sesion.refresh_token,
        "expira_en": int(sesion.expires_at or 0),
        "usuario_id": sesion.user.id,
        "correo": sesion.user.email,
    }


# ---------------------------------------------------------------------------
# Validación (también en el servidor, aunque el formulario ya valide)
# ---------------------------------------------------------------------------
def validar_correo(correo):
    correo = (correo or "").strip().lower()
    if not correo or len(correo) > 254 or not PATRON_CORREO.match(correo):
        raise ErrorCuenta("Escribe un correo electrónico válido.")
    return correo


def validar_contrasena(contrasena):
    contrasena = contrasena or ""
    if len(contrasena) < 8:
        raise ErrorCuenta("La contraseña debe tener al menos 8 caracteres.")
    if len(contrasena.encode("utf-8")) > 72:
        raise ErrorCuenta("La contraseña es demasiado larga (máximo 72 caracteres).")
    if not (re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", contrasena) and re.search(r"[0-9]", contrasena)):
        raise ErrorCuenta("La contraseña debe incluir letras y números.")
    return contrasena


def validar_nombre(nombre):
    nombre = " ".join((nombre or "").split())
    if not 2 <= len(nombre) <= 60:
        raise ErrorCuenta("El nombre debe tener entre 2 y 60 caracteres.")
    return nombre


def validar_telefono(telefono):
    """Acepta espacios y guiones; guarda solo números (y + inicial)."""
    limpio = re.sub(r"[\s\-().]", "", telefono or "")
    if not limpio:
        return None
    if not PATRON_TELEFONO.match(limpio):
        raise ErrorCuenta("Escribe un teléfono de 10 a 15 dígitos (por ejemplo 664 123 4567).")
    return limpio


# ---------------------------------------------------------------------------
# Operaciones de cuenta
# ---------------------------------------------------------------------------
def registrar(correo, contrasena, nombre, tipo_cuenta, acepta_aviso):
    """Crea la cuenta. Supabase envía el correo de confirmación.

    Devuelve la sesión solo si el proyecto NO pide confirmar el correo
    (no recomendado); normalmente devuelve None.
    """
    correo = validar_correo(correo)
    contrasena = validar_contrasena(contrasena)
    nombre = validar_nombre(nombre)
    if tipo_cuenta not in TIPOS_CUENTA:
        raise ErrorCuenta("Elige un tipo de cuenta.")
    if not acepta_aviso:
        raise ErrorCuenta("Para crear tu cuenta necesitas aceptar el aviso de privacidad.")

    respuesta = _llamar(cliente_auth().auth.sign_up, {
        "email": correo,
        "password": contrasena,
        "options": {"data": {
            "nombre_publico": nombre,
            "tipo_cuenta": tipo_cuenta,
            "acepto_aviso_privacidad": True,
        }},
    })
    return _sesion_a_dict(respuesta.session) if respuesta.session else None


def iniciar_sesion(correo, contrasena):
    correo = validar_correo(correo)
    if not contrasena:
        raise ErrorCuenta("Escribe tu contraseña.")
    respuesta = _llamar(cliente_auth().auth.sign_in_with_password,
                        {"email": correo, "password": contrasena})
    if not respuesta.session:
        raise ErrorCuenta(MENSAJE_GENERICO)
    return _sesion_a_dict(respuesta.session)


def verificar_enlace(token_hash, tipo):
    """Valida el enlace de un correo (confirmación o recuperación) e inicia sesión."""
    if tipo not in ("email", "signup", "recovery") or not token_hash or len(token_hash) > 200:
        raise ErrorCuenta("El enlace no es válido. Pide uno nuevo.")
    respuesta = _llamar(cliente_auth().auth.verify_otp, {"token_hash": token_hash, "type": tipo})
    if not respuesta.session:
        raise ErrorCuenta("El enlace no es válido. Pide uno nuevo.")
    return _sesion_a_dict(respuesta.session)


def enviar_recuperacion(correo):
    """Envía el correo para elegir una contraseña nueva.

    Por seguridad, la app responde igual exista o no la cuenta.
    """
    correo = validar_correo(correo)
    _llamar(cliente_auth().auth.reset_password_for_email, correo)


def reenviar_confirmacion(correo):
    correo = validar_correo(correo)
    _llamar(cliente_auth().auth.resend, {"type": "signup", "email": correo})


def renovar(refresh_token):
    """Pide tokens nuevos cuando el actual está por vencer."""
    respuesta = _llamar(cliente_auth().auth.refresh_session, refresh_token)
    if not respuesta.session:
        raise ErrorCuenta("Tu sesión terminó. Inicia sesión de nuevo.")
    return _sesion_a_dict(respuesta.session)


def cambiar_contrasena(sesion, nueva):
    nueva = validar_contrasena(nueva)
    cliente = cliente_auth()
    _llamar(cliente.auth.set_session, sesion["access_token"], sesion["refresh_token"])
    _llamar(cliente.auth.update_user, {"password": nueva})


def cerrar_sesion(access_token):
    """Revoca la sesión en Supabase. Si falla, la app borra la sesión igual."""
    try:
        cliente_auth().auth.admin.sign_out(access_token, "local")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Perfil (siempre con el token de la persona: RLS decide qué puede hacer)
# ---------------------------------------------------------------------------
def leer_mi_perfil(access_token, usuario_id):
    cliente = cliente_de_usuario(access_token)
    perfil = _llamar_bd(cliente.table("perfiles")
                        .select("id,nombre_publico,tipo_cuenta,nivel_verificacion,biografia,municipio,creado_en")
                        .eq("id", usuario_id).limit(1))
    privados = _llamar_bd(cliente.table("perfiles_privados")
                          .select("telefono,telefono_verificado,acepto_aviso_privacidad_en")
                          .eq("id", usuario_id).limit(1))
    if not perfil:
        raise ErrorCuenta("No encontramos tu perfil. Cierra sesión y vuelve a entrar.")
    datos = dict(perfil[0])
    datos.update(privados[0] if privados else {})
    datos["es_admin"] = bool(_llamar_bd(cliente.rpc("es_admin", {})))
    return datos


def actualizar_mi_perfil(access_token, usuario_id, nombre, biografia, municipio, telefono):
    nombre = validar_nombre(nombre)
    biografia = (biografia or "").strip()
    if len(biografia) > 500:
        raise ErrorCuenta("La biografía puede tener hasta 500 caracteres.")
    municipio = " ".join((municipio or "").split()) or "Tijuana"
    if len(municipio) > 60:
        raise ErrorCuenta("El municipio puede tener hasta 60 caracteres.")
    telefono = validar_telefono(telefono)

    cliente = cliente_de_usuario(access_token)
    # Solo se envían las columnas que la persona puede cambiar (la base de datos
    # rechazaría cualquier otra, como el nivel de verificación).
    filas = _llamar_bd(cliente.table("perfiles")
                       .update({"nombre_publico": nombre, "biografia": biografia or None, "municipio": municipio})
                       .eq("id", usuario_id))
    if not filas:
        raise ErrorCuenta("No se pudo guardar tu perfil. Cierra sesión y vuelve a entrar.")
    _llamar_bd(cliente.table("perfiles_privados").update({"telefono": telefono}).eq("id", usuario_id))
    return nombre


def es_admin(access_token):
    """Pregunta a la base de datos (no a la sesión) si la persona es administradora."""
    return bool(_llamar_bd(cliente_de_usuario(access_token).rpc("es_admin", {})))


def perfil_publico(usuario_id):
    from services.supabase_cliente import obtener_cliente

    filas = _llamar_bd(obtener_cliente().table("perfiles")
                       .select("id,nombre_publico,tipo_cuenta,nivel_verificacion,biografia,municipio,creado_en")
                       .eq("id", usuario_id).limit(1))
    return filas[0] if filas else None


def _llamar_bd(consulta):
    try:
        return consulta.execute().data
    except Exception as error:
        _anotar("Error al consultar la base de datos · %s: %s", type(error).__name__, error)
        raise ErrorCuenta(MENSAJE_GENERICO) from error
