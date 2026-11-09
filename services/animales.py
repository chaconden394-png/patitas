"""
Consultas de animales y refugios.

Si Supabase está configurado en .env, los datos vienen de la base de datos.
Si no, se usan los datos de ejemplo (modo de ejemplo), para que la app
siga funcionando mientras configuras Supabase.

Las plantillas reciben siempre diccionarios con la misma forma, vengan de
donde vengan, así que no tienen que cambiar.
"""
import uuid

from services import datos_ejemplo
from services.estados import ESTADOS_CATALOGO, ESTADOS_PERDIDOS
from services.supabase_cliente import obtener_cliente, supabase_configurado

LIMITE_RESULTADOS = 60  # se reemplazará por paginación en la Etapa 4

CAMPOS_ANIMAL = (
    "id,nombre,especie,raza,edad_aproximada_meses,tamano,sexo,energia,personalidad,"
    "vacunado,esterilizado,zona,municipio,estado,publicado_en"
)
CAMPOS_REFUGIO = "id,nombre,descripcion,zona,municipio,estado_verificacion"


class ErrorBaseDeDatos(Exception):
    """No se pudo consultar Supabase."""


def modo_ejemplo():
    return not supabase_configurado()


# ---------------------------------------------------------------------------
# Conversión de filas de la base de datos al formato de las plantillas
# ---------------------------------------------------------------------------
def texto_edad(meses):
    if meses is None:
        return "Edad desconocida"
    if meses < 12:
        return f"{meses} mes" if meses == 1 else f"{meses} meses"
    anios = meses // 12
    return "1 año" if anios == 1 else f"{anios} años"


def fila_a_animal(fila):
    return {
        "id": fila["id"],
        "nombre": fila["nombre"],
        "especie": fila["especie"],
        "raza": fila.get("raza") or "No especificada",
        "edad": texto_edad(fila.get("edad_aproximada_meses")),
        "tamano": fila["tamano"],
        "sexo": fila.get("sexo") or "desconocido",
        "energia": fila.get("energia") or "",
        "personalidad": fila.get("personalidad") or "",
        "vacunado": bool(fila.get("vacunado")),
        "esterilizado": bool(fila.get("esterilizado")),
        "zona": fila["zona"],
        "estado": fila["estado"],
        "foto": None,  # las fotos llegan en la Etapa 4
    }


def fila_a_refugio(fila):
    return {
        "id": fila["id"],
        "nombre": fila["nombre"],
        "descripcion": fila.get("descripcion") or "",
        "zona": fila.get("zona") or fila.get("municipio") or "",
        "verificado": fila["estado_verificacion"] == "verificado",
        "animales": None,  # el conteo se agregará con el panel de refugio
    }


def _ejecutar(consulta):
    try:
        return consulta.execute().data
    except Exception as error:  # red, clave inválida, tabla inexistente…
        raise ErrorBaseDeDatos(str(error)) from error


# ---------------------------------------------------------------------------
# Consultas públicas
# ---------------------------------------------------------------------------
def consulta_catalogo(filtros):
    """Construye (sin ejecutar) la consulta del catálogo. Separada para poder probarla."""
    consulta = (obtener_cliente().table("animales").select(CAMPOS_ANIMAL)
                .in_("estado", ESTADOS_CATALOGO))
    for campo, valor in filtros.items():
        consulta = consulta.eq(campo, valor)
    return consulta.order("publicado_en", desc=True).limit(LIMITE_RESULTADOS)


def listar_catalogo(filtros):
    """Animales para adopción. `filtros` ya viene validado por app.py."""
    if modo_ejemplo():
        en_catalogo = [a for a in datos_ejemplo.ANIMALES if a["estado"] in ESTADOS_CATALOGO]
        return [a for a in en_catalogo if all(a.get(c) == v for c, v in filtros.items())]
    return [fila_a_animal(f) for f in _ejecutar(consulta_catalogo(filtros))]


def listar_destacados(cantidad=4):
    if modo_ejemplo():
        return [a for a in datos_ejemplo.ANIMALES if a["estado"] in ("disponible", "urgente")][:cantidad]
    consulta = (obtener_cliente().table("animales").select(CAMPOS_ANIMAL)
                .in_("estado", ["urgente", "disponible"])
                .order("publicado_en", desc=True).limit(cantidad))
    return [fila_a_animal(f) for f in _ejecutar(consulta)]


def listar_perdidos_encontrados():
    if modo_ejemplo():
        return [a for a in datos_ejemplo.ANIMALES if a["estado"] in ESTADOS_PERDIDOS]
    consulta = (obtener_cliente().table("animales").select(CAMPOS_ANIMAL)
                .in_("estado", ESTADOS_PERDIDOS)
                .order("publicado_en", desc=True).limit(LIMITE_RESULTADOS))
    return [fila_a_animal(f) for f in _ejecutar(consulta)]


def obtener_animal(animal_id):
    """Un animal por su id, o None si no existe o no es visible."""
    if modo_ejemplo():
        return next((a for a in datos_ejemplo.ANIMALES if str(a["id"]) == str(animal_id)), None)
    try:
        uuid.UUID(str(animal_id))  # en la base de datos los id son UUID
    except ValueError:
        return None
    consulta = (obtener_cliente().table("animales").select(CAMPOS_ANIMAL)
                .eq("id", animal_id).limit(1))
    filas = _ejecutar(consulta)
    return fila_a_animal(filas[0]) if filas else None


def listar_refugios():
    if modo_ejemplo():
        return datos_ejemplo.REFUGIOS
    consulta = (obtener_cliente().table("refugios").select(CAMPOS_REFUGIO)
                .in_("estado_verificacion", ["verificado", "pendiente"])
                .order("nombre").limit(LIMITE_RESULTADOS))
    return [fila_a_refugio(f) for f in _ejecutar(consulta)]
