"""
Configuración de Patitas.

Todas las claves y datos sensibles se leen de variables de entorno
(archivo .env en desarrollo). Nunca escribas claves reales en este archivo.
"""
import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv

# Carga las variables del archivo .env (si existe) en el entorno.
load_dotenv()


class Config:
    # Clave para firmar las sesiones de Flask.
    # Si no existe en .env, se genera una temporal (las sesiones se pierden al reiniciar).
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

    # Modo de la aplicación: "development" o "production".
    PATITAS_ENV = os.getenv("PATITAS_ENV", "development")

    # Cookies de sesión más seguras.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = PATITAS_ENV == "production"
    # La sesión dura 7 días; los tokens de Supabase se renuevan solos mientras tanto.
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Límite de tamaño de las peticiones (protege contra archivos enormes): 10 MB.
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    # Supabase. Solo la URL y la clave PÚBLICA (Supabase la llama "publishable" o "anon").
    # La clave secreta ("secret" o "service_role") NUNCA va aquí ni en el repositorio.
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    SUPABASE_CLAVE_PUBLICA = os.getenv("SUPABASE_CLAVE_PUBLICA", "").strip()
