"""
Conexión con Supabase.

Usa SOLO la clave pública (la que Supabase llama "publishable" o "anon").
Con esa clave, la base de datos aplica las reglas RLS: cada consulta solo
puede ver o cambiar lo que esas reglas permiten.

La clave secreta (llamada "secret" o "service_role") NUNCA se usa aquí.
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


def obtener_cliente():
    """Devuelve el cliente de Supabase (se crea una sola vez)."""
    global _cliente
    if _cliente is None:
        from supabase import create_client

        clave = current_app.config["SUPABASE_CLAVE_PUBLICA"]
        if es_clave_secreta(clave):
            raise RuntimeError(
                "SUPABASE_CLAVE_PUBLICA contiene la clave SECRETA. "
                "Usa la clave pública (publishable/anon) y guarda la secreta fuera del proyecto."
            )
        _cliente = create_client(current_app.config["SUPABASE_URL"], clave)
    return _cliente
