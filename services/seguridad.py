"""
Protecciones generales de Patitas.

1. CSRF: cada formulario lleva un código secreto de la sesión. Así otra página
   web no puede enviar formularios a Patitas "en tu nombre".
2. Límite de intentos: frena a quien prueba muchas contraseñas o pide muchos
   correos. Se guarda en memoria: se reinicia al reiniciar la app y vale para
   un solo servidor (suficiente para desarrollo; se revisará en la Etapa 9).
3. Redirecciones seguras: después de iniciar sesión solo se vuelve a páginas
   de Patitas, nunca a otro sitio.
"""
import secrets
import threading
import time
from collections import defaultdict, deque

from flask import abort, request, session

# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------
def token_csrf():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def verificar_csrf():
    """Se llama antes de cada petición POST."""
    if request.method != "POST":
        return
    esperado = session.get("_csrf")
    recibido = request.form.get("csrf_token", "")
    if not esperado or not secrets.compare_digest(esperado, recibido):
        abort(400, description="El formulario expiró. Recarga la página e inténtalo de nuevo.")


# ---------------------------------------------------------------------------
# Límite de intentos
# ---------------------------------------------------------------------------
_intentos = defaultdict(deque)
_candado = threading.Lock()


def demasiados_intentos(clave, maximo, ventana_segundos):
    """Registra un intento y dice si ya se pasó del límite."""
    ahora = time.monotonic()
    with _candado:
        cola = _intentos[clave]
        while cola and ahora - cola[0] > ventana_segundos:
            cola.popleft()
        if len(cola) >= maximo:
            return True
        cola.append(ahora)
        return False


def olvidar_intentos(clave):
    with _candado:
        _intentos.pop(clave, None)


def reiniciar_limites():
    """Solo para pruebas."""
    with _candado:
        _intentos.clear()


# ---------------------------------------------------------------------------
# Redirecciones
# ---------------------------------------------------------------------------
def destino_seguro(destino, por_defecto="/"):
    """Acepta solo rutas internas como '/cuenta'; rechaza '//otro.com' o 'https://…'."""
    if (destino and destino.startswith("/") and not destino.startswith("//")
            and "\\" not in destino and "\n" not in destino and "\r" not in destino):
        return destino
    return por_defecto
