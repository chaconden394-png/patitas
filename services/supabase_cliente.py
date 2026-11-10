"""
Conexión con Supabase.

Usa SOLO la clave pública (la que Supabase llama "publishable" o "anon").
Con esa clave, la base de datos aplica las reglas RLS: cada consulta solo
puede ver o cambiar lo que esas reglas permiten.

La clave secreta (llamada "secret" o "service_role") NUNCA se usa aquí.

Hay tres tipos de conexión:
  * obtener_cliente()          -> visitante sin sesión (datos públicos).
  * cliente_de_usuario(token)  -> actúa COMO la persona que inició sesión;
                                  RLS aplica sus permisos.
  * cliente_auth()             -> para registrar, iniciar sesión, etc.
                                  Se crea nuevo en cada uso para que las
                                  sesiones de dos personas nunca se mezclen.
"""
import base64
import json

from flask import current_app

_cliente = None


def es_clave_secreta(clave):
    """True si la clave parece ser la secreta (que salta todas las reglas RLS)."""
    if not clave:
        return False
    if clave.startswith("sb_secret_"):
        return True
    partes = clave.split(".")
    if len(partes) == 3:  # formato antiguo (JWT): leer el rol que contiene
        try:
            relleno = "=" * (-len(partes[1]) % 4)
            datos = json.loads(base64.urlsafe_b64decode(partes[1] + relleno))
            return datos.get("role") == "service_role"
        except (ValueError, json.JSONDecodeError):
            return False
    return False


def supabase_configurado():
    """True si .env tiene la URL y la clave pública de Supabase."""
    cfg = current_app.config
    return bool(cfg.get("SUPABASE_URL") and cfg.get("SUPABASE_CLAVE_PUBLICA"))


def _clave_publica():
    clave = current_app.config["SUPABASE_CLAVE_PUBLICA"]
    if es_clave_secreta(clave):
        raise RuntimeError(
            "SUPABASE_CLAVE_PUBLICA contiene la clave SECRETA. "
            "Usa la clave pública (publishable/anon) y guarda la secreta fuera del proyecto."
        )
    return clave


def _crear(headers=None):
    from supabase import ClientOptions, create_client

    opciones = ClientOptions(
        headers=headers or {},
        persist_session=False,      # nunca guardar sesiones dentro del cliente
        auto_refresh_token=False,   # la app renueva los tokens (services/sesion.py)
        flow_type="implicit",       # los enlaces de correo usan token_hash (ver GUIA_ETAPA3.md)
        # Solo en pruebas automáticas: permite conectar un simulador de Supabase.
        httpx_client=current_app.config.get("SUPABASE_HTTPX_PRUEBAS"),
    )
    return create_client(current_app.config["SUPABASE_URL"], _clave_publica(), opciones)


def obtener_cliente():
    """Cliente de visitante (sin sesión). Se crea una sola vez."""
    global _cliente
    if _cliente is None or current_app.config.get("SUPABASE_HTTPX_PRUEBAS"):
        _cliente = _crear()
    return _cliente


def cliente_de_usuario(access_token):
    """Cliente que actúa como la persona dueña del token. Uno nuevo por petición."""
    return _crear(headers={"Authorization": f"Bearer {access_token}"})


def cliente_auth():
    """Cliente nuevo para operaciones de cuenta (registro, inicio de sesión…)."""
    return _crear()
