"""
Consultas públicas de animales y refugios.

Si Supabase está configurado en .env, los datos vienen de la base de datos.
Si no, se usan los datos de ejemplo (modo de ejemplo), para que la app
siga funcionando mientras configuras Supabase.

Las plantillas reciben siempre diccionarios con la misma forma, vengan de
donde vengan, así que no tienen que cambiar.
"""
import uuid

from flask import current_app

from services import datos_ejemplo
from services.estados import ESTADOS_CATALOGO, ESTADOS_PERDIDOS
from services.fotos import BUCKET_ANIMALES, url_publica
from services.supabase_cliente import obtener_cliente, supabase_configurado

POR_PAGINA = 12
LIMITE_RESULTADOS = 60   # listas sin paginación (perdidos, refugios)

# Rangos de edad del filtro del catálogo, en meses: (desde, hasta sin incluir)
EDADES = {
    "cachorro": ("Cachorro (menos de 1 año)", 0, 12),
    "joven": ("Joven (1 a 2 años)", 12, 36),
    "adulto": ("Adulto (3 a 7 años)", 36, 96),
    "mayor": ("Mayor (8 años o más)", 96, 401),
}
# Casillas "solo los que…" del catálogo
CASILLAS = {
    "vacunado": "Vacunas al día",
    "esterilizado": "Esterilizado",
    "convive_ninos": "Convive con niñas y niños",
    "convive_perros": "Convive con perros",
    "convive_gatos": "Convive con gatos",
}

CAMPOS_ANIMAL = (
    "id,nombre,especie,raza,edad_aproximada_meses,tamano,sexo,energia,personalidad,"
    "vacunado,esterilizado,zona,municipio,estado,publicado_en,"
    "fotos:animales_fotos(id,ruta_archivo,orden),"
    # El "!" indica qué relación usar: animales.responsable_id -> perfiles (no la de favoritos)
    "responsable:perfiles!responsable_id(nivel_verificacion),"
    "refugio:refugios!refugio_id(estado_verificacion)"
)
CAMPOS_DETALLE = (
    "id,nombre,especie,raza,edad_aproximada_meses,tamano,sexo,energia,personalidad,"
    "convive_ninos,convive_perros,convive_gatos,vacunado,esterilizado,enfermedades_conocidas,"
    "necesidades_especiales,requisitos_adopcion,zona,municipio,estado,publicado_en,responsable_id,refugio_id,"
    "fotos:animales_fotos(id,ruta_archivo,orden),"
    "responsable:perfiles!responsable_id(id,nombre_publico,tipo_cuenta,nivel_verificacion),"
    "refugio:refugios!refugio_id(id,nombre,estado_verificacion)"
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


def fotos_ordenadas(fila):
    """Fotos del animal, la principal (orden más bajo) primero."""
    fotos = sorted(fila.get("fotos") or [], key=lambda f: (f.get("orden") or 0, f.get("ruta_archivo")))
    base = current_app.config["SUPABASE_URL"]
    return [{"id": f.get("id"), "ruta": f["ruta_archivo"], "orden": f.get("orden") or 0,
             "url": url_publica(base, f["ruta_archivo"], BUCKET_ANIMALES)} for f in fotos]


def esta_verificado(fila):
    """Verificado = su refugio fue aprobado o su cuenta fue verificada por el equipo de Patitas."""
    refugio = fila.get("refugio") or {}
    responsable = fila.get("responsable") or {}
    return (refugio.get("estado_verificacion") == "verificado"
            or responsable.get("nivel_verificacion") in ("identidad_verificada", "habilitada"))


def fila_a_animal(fila):
    fotos = fotos_ordenadas(fila)
    responsable = fila.get("responsable") or {}
    refugio = fila.get("refugio") or {}
    return {
        "id": fila["id"],
        "nombre": fila["nombre"],
        "especie": fila["especie"],
        "raza": fila.get("raza") or "No especificada",
        "edad": texto_edad(fila.get("edad_aproximada_meses")),
        "edad_meses": fila.get("edad_aproximada_meses"),
        "tamano": fila["tamano"],
        "sexo": fila.get("sexo") or "desconocido",
        "energia": fila.get("energia") or "",
        "personalidad": fila.get("personalidad") or "",
        "vacunado": bool(fila.get("vacunado")),
        "esterilizado": bool(fila.get("esterilizado")),
        "convive_ninos": fila.get("convive_ninos"),
        "convive_perros": fila.get("convive_perros"),
        "convive_gatos": fila.get("convive_gatos"),
        "enfermedades": fila.get("enfermedades_conocidas") or "",
        "necesidades": fila.get("necesidades_especiales") or "",
        "requisitos": fila.get("requisitos_adopcion") or "",
        "zona": fila["zona"],
        "estado": fila["estado"],
        "foto": None,                               # foto local (solo modo de ejemplo)
        "fotos": fotos,
        "foto_url": fotos[0]["url"] if fotos else None,
        "verificado": esta_verificado(fila),
        "publicador": ({"id": responsable["id"], "nombre": responsable.get("nombre_publico") or "Usuario de Patitas",
                        "tipo": responsable.get("tipo_cuenta")} if responsable.get("id") else None),
        "refugio": ({"id": refugio["id"], "nombre": refugio["nombre"],
                     "verificado": refugio.get("estado_verificacion") == "verificado"} if refugio.get("id") else None),
    }


def fila_a_refugio(fila):
    return {
        "id": fila["id"],
        "nombre": fila["nombre"],
        "descripcion": fila.get("descripcion") or "",
        "zona": fila.get("zona") or fila.get("municipio") or "",
        "verificado": fila["estado_verificacion"] == "verificado",
        "animales": None,
    }


def _respuesta(consulta):
    try:
        return consulta.execute()
    except Exception as error:  # red, clave inválida, tabla inexistente…
        raise ErrorBaseDeDatos(str(error)) from error


def _ejecutar(consulta):
    return _respuesta(consulta).data


# ---------------------------------------------------------------------------
# Catálogo de adopción (con filtros y páginas)
# ---------------------------------------------------------------------------
def consulta_catalogo(filtros, pagina=1):
    """Construye (sin ejecutar) la consulta del catálogo. Separada para poder probarla."""
    consulta = (obtener_cliente().table("animales").select(CAMPOS_ANIMAL, count="exact")
                .in_("estado", ESTADOS_CATALOGO))
    for campo, valor in filtros.items():
        if campo == "edad":
            _, desde, hasta = EDADES[valor]
            consulta = consulta.gte("edad_aproximada_meses", desde).lt("edad_aproximada_meses", hasta)
        elif campo in CASILLAS:
            consulta = consulta.eq(campo, True)
        else:
            consulta = consulta.eq(campo, valor)
    inicio = (pagina - 1) * POR_PAGINA
    return consulta.order("publicado_en", desc=True).range(inicio, inicio + POR_PAGINA - 1)


def _cumple(animal, filtros):
    for campo, valor in filtros.items():
        if campo == "edad":
            _, desde, hasta = EDADES[valor]
            if animal.get("edad_meses") is None or not desde <= animal["edad_meses"] < hasta:
                return False
        elif campo in CASILLAS:
            if animal.get(campo) is not True:
                return False
        elif animal.get(campo) != valor:
            return False
    return True


def listar_catalogo(filtros, pagina=1):
    """Animales para adopción: (lista de la página, total). `filtros` ya viene validado por app.py."""
    if modo_ejemplo():
        todos = [a for a in datos_ejemplo.ANIMALES if a["estado"] in ESTADOS_CATALOGO and _cumple(a, filtros)]
        inicio = (pagina - 1) * POR_PAGINA
        return todos[inicio:inicio + POR_PAGINA], len(todos)
    respuesta = _respuesta(consulta_catalogo(filtros, pagina))
    return [fila_a_animal(f) for f in respuesta.data], respuesta.count or 0


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


def es_uuid(valor):
    try:
        uuid.UUID(str(valor))
        return True
    except ValueError:
        return False


def obtener_animal(animal_id):
    """Un animal por su id, o None si no existe o no es visible."""
    if modo_ejemplo():
        return next((a for a in datos_ejemplo.ANIMALES if str(a["id"]) == str(animal_id)), None)
    if not es_uuid(animal_id):   # en la base de datos los id son UUID
        return None
    consulta = (obtener_cliente().table("animales").select(CAMPOS_DETALLE)
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
