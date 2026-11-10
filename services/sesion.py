"""
Sesión de la persona en el navegador y permisos por página.

La sesión de Flask es una cookie FIRMADA con SECRET_KEY (nadie puede
modificarla sin esa clave), HttpOnly (JavaScript no puede leerla) y SameSite.
Guarda los tokens de Supabase y algunos datos para mostrar el menú.

Importante: el menú usa los datos guardados, pero los PERMISOS reales los
decide la base de datos (RLS) con el token de la persona, y las páginas de
administración vuelven a preguntar a la base de datos en cada visita.
"""
import time
from functools import wraps

from flask import flash, g, redirect, request, session, url_for

from services import autenticacion
from services.supabase_cliente import supabase_configurado

MARGEN_RENOVACION = 60  # segundos antes de vencer el token, se pide uno nuevo


def _limpiar_conservando_basicos():
    """Vacía la sesión, pero conserva el código CSRF y los mensajes pendientes."""
    conservar = {k: session[k] for k in ("_csrf", "_flashes") if k in session}
    session.clear()
    session.update(conservar)


def guardar_sesion(datos_sesion, perfil):
    """Se llama al iniciar sesión, confirmar el correo o recuperar la contraseña."""
    _limpiar_conservando_basicos()        # empieza una sesión limpia
    session.permanent = True
    session["tokens"] = {
        "access_token": datos_sesion["access_token"],
        "refresh_token": datos_sesion["refresh_token"],
        "expira_en": datos_sesion["expira_en"],
    }
    session["usuario"] = {
        "id": datos_sesion["usuario_id"],
        "correo": datos_sesion["correo"],
        "nombre": perfil["nombre_publico"],
        "tipo_cuenta": perfil["tipo_cuenta"],
        "es_admin": bool(perfil.get("es_admin")),
    }


def borrar_sesion():
    _limpiar_conservando_basicos()


def usuario_actual():
    """Datos de la persona con sesión iniciada, o None. Renueva el token si hace falta."""
    if "usuario_cargado" in g:
        return g.usuario
    g.usuario_cargado = True
    g.usuario = None

    usuario, tokens = session.get("usuario"), session.get("tokens")
    if not usuario or not tokens or not supabase_configurado():
        return None

    if tokens["expira_en"] - MARGEN_RENOVACION <= time.time():
        try:
            nuevos = autenticacion.renovar(tokens["refresh_token"])
        except autenticacion.ErrorCuenta:
            borrar_sesion()
            return None
        session["tokens"] = {k: nuevos[k] for k in ("access_token", "refresh_token", "expira_en")}

    g.usuario = usuario
    return usuario


def token_actual():
    """Token de acceso vigente (llamar después de usuario_actual())."""
    return session["tokens"]["access_token"]


def actualizar_nombre_en_sesion(nombre):
    usuario = dict(session["usuario"])
    usuario["nombre"] = nombre
    session["usuario"] = usuario


# ---------------------------------------------------------------------------
# Decoradores de permisos para las rutas
# ---------------------------------------------------------------------------
def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if usuario_actual() is None:
            flash("Inicia sesión para continuar.", "info")
            return redirect(url_for("iniciar_sesion", siguiente=request.full_path.rstrip("?")))
        return vista(*args, **kwargs)
    return envoltura


def tipo_requerido(*tipos):
    """Solo para ciertos tipos de cuenta (por ejemplo refugios y rescatistas)."""
    def decorador(vista):
        @wraps(vista)
        @login_requerido
        def envoltura(*args, **kwargs):
            if usuario_actual()["tipo_cuenta"] not in tipos:
                flash("Esa sección es para otro tipo de cuenta.", "aviso")
                return redirect(url_for("mi_cuenta"))
            return vista(*args, **kwargs)
        return envoltura
    return decorador


def admin_requerido(vista):
    """Solo administradores. Pregunta a la base de datos en cada visita."""
    @wraps(vista)
    @login_requerido
    def envoltura(*args, **kwargs):
        try:
            permitido = autenticacion.es_admin(token_actual())
        except autenticacion.ErrorCuenta:
            permitido = False
        if not permitido:
            from flask import abort
            abort(404)  # no revelamos que la página existe
        return vista(*args, **kwargs)
    return envoltura
