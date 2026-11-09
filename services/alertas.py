"""
Alerta Patitas: consultas de alertas de mascotas perdidas.

Igual que services/animales.py: si Supabase está configurado se usan datos
reales; si no, los de ejemplo. Las plantillas reciben siempre la misma forma.

Quién recibe cada alerta (radio de 15 km) lo decide la base de datos
(migración 002), no este archivo.
"""
import uuid
from datetime import datetime, timezone

from services import datos_ejemplo
from services.animales import ErrorBaseDeDatos, modo_ejemplo
from services.supabase_cliente import obtener_cliente

try:
    from zoneinfo import ZoneInfo
    ZONA_HORARIA = ZoneInfo("America/Tijuana")
except Exception:  # sin datos de zonas horarias: usamos UTC
    ZONA_HORARIA = timezone.utc

RADIO_KM = 15
LIMITE_ALERTAS = 30

CAMPOS_ALERTA = (
    "id,nombre_mascota,especie,raza,sexo,tamano,edad_aproximada,color,senas_particulares,collar,"
    "descripcion,ruta_foto,zona_referencia,municipio,visto_por_ultima_vez,latitud_aprox,longitud_aprox,"
    "mostrar_telefono,estado,creada_en,expira_en,"
    "emisor:perfiles(nombre_publico,creado_en,nivel_verificacion)"
)

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------
def a_fecha(valor):
    """Convierte el texto de fecha de Supabase en datetime (con zona horaria)."""
    if isinstance(valor, datetime) or valor is None:
        return valor
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))


def hace_tiempo(fecha, ahora=None):
    """'hace 5 minutos', 'hace 3 horas', 'hace 2 días'."""
    if fecha is None:
        return ""
    ahora = ahora or datetime.now(timezone.utc)
    segundos = max(0, int((ahora - fecha).total_seconds()))
    if segundos < 60:
        return "hace un momento"
    for tamano, singular, plural in [(86400, "día", "días"), (3600, "hora", "horas"), (60, "minuto", "minutos")]:
        if segundos >= tamano:
            n = segundos // tamano
            return f"hace {n} {singular if n == 1 else plural}"


def fecha_local(fecha):
    """'6 nov 2026, 14:30' en hora de Tijuana."""
    if fecha is None:
        return ""
    f = fecha.astimezone(ZONA_HORARIA)
    return f"{f.day} {MESES[f.month - 1]} {f.year}, {f:%H:%M}"


def mes_anio(fecha):
    """'abr 2026'."""
    if fecha is None:
        return ""
    f = fecha.astimezone(ZONA_HORARIA)
    return f"{MESES[f.month - 1]} {f.year}"


# ---------------------------------------------------------------------------
# Conversión de filas al formato de las plantillas
# ---------------------------------------------------------------------------
def fila_a_alerta(fila):
    emisor = fila.get("emisor") or {}
    return {
        "id": fila["id"],
        "nombre": fila["nombre_mascota"],
        "especie": fila["especie"],
        "raza": fila.get("raza") or "No especificada",
        "sexo": fila.get("sexo") or "desconocido",
        "tamano": fila["tamano"],
        "edad_aproximada": fila.get("edad_aproximada") or "",
        "color": fila["color"],
        "senas_particulares": fila.get("senas_particulares") or "",
        "collar": fila.get("collar") or "",
        "descripcion": fila.get("descripcion") or "",
        "zona_referencia": fila["zona_referencia"],
        "municipio": fila.get("municipio") or "Tijuana",
        "visto_por_ultima_vez": a_fecha(fila["visto_por_ultima_vez"]),
        "creada_en": a_fecha(fila["creada_en"]),
        "expira_en": a_fecha(fila["expira_en"]),
        "latitud_aprox": float(fila["latitud_aprox"]) if fila.get("latitud_aprox") is not None else None,
        "longitud_aprox": float(fila["longitud_aprox"]) if fila.get("longitud_aprox") is not None else None,
        "mostrar_telefono": bool(fila.get("mostrar_telefono")),
        "estado": fila["estado"],
        "foto": None,  # las fotos llegan con Supabase Storage (Etapa 4)
        "personas_avisadas": None,
        "emisor": {
            "nombre_publico": emisor.get("nombre_publico") or "Usuario de Patitas",
            "creado_en": a_fecha(emisor.get("creado_en")),
            "nivel_verificacion": emisor.get("nivel_verificacion") or "registrada",
        },
    }


def vigente(alerta, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    return alerta["estado"] == "activa" and alerta["expira_en"] > ahora


def _ejecutar(consulta):
    try:
        return consulta.execute().data
    except Exception as error:
        raise ErrorBaseDeDatos(str(error)) from error


# ---------------------------------------------------------------------------
# Consultas públicas
# ---------------------------------------------------------------------------
def listar_vigentes():
    """Alertas activas y sin vencer, de la más reciente a la más antigua."""
    if modo_ejemplo():
        return sorted((a for a in datos_ejemplo.ALERTAS if vigente(a)),
                      key=lambda a: a["creada_en"], reverse=True)
    # Formato con "Z": el signo "+" de "+00:00" podría leerse como espacio en la URL.
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    consulta = (obtener_cliente().table("alertas").select(CAMPOS_ALERTA)
                .eq("estado", "activa").gt("expira_en", ahora)
                .order("creada_en", desc=True).limit(LIMITE_ALERTAS))
    return [fila_a_alerta(f) for f in _ejecutar(consulta)]


def obtener(alerta_id):
    """Una alerta (vigente o cerrada) por su id, o None."""
    if modo_ejemplo():
        return next((a for a in datos_ejemplo.ALERTAS if a["id"] == str(alerta_id)), None)
    try:
        uuid.UUID(str(alerta_id))
    except ValueError:
        return None
    filas = _ejecutar(obtener_cliente().table("alertas").select(CAMPOS_ALERTA).eq("id", alerta_id).limit(1))
    if not filas:
        return None
    alerta = fila_a_alerta(filas[0])
    alerta["personas_avisadas"] = _ejecutar(
        obtener_cliente().rpc("personas_avisadas", {"id_alerta": str(alerta_id)}))
    return alerta
