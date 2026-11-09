"""
DATOS DE EJEMPLO - TEMPORALES.

Estos animales, refugios y alertas son ficticios. Se usan en el "modo de ejemplo"
(cuando .env no tiene Supabase configurado).
No contienen datos personales reales.

El campo "foto" es el nombre de un archivo dentro de static/images/animales/.
Si el archivo no existe, la página muestra un marcador ilustrado en su lugar.
"""

ANIMALES = [
    {"id": 1, "nombre": "Canela", "especie": "perro", "raza": "No especificada", "edad": "2 años",
     "tamano": "mediano", "sexo": "hembra", "energia": "media", "zona": "Playas de Tijuana",
     "estado": "disponible", "esterilizado": True, "vacunado": True, "foto": "canela.jpg",
     "personalidad": "Cariñosa, tranquila en casa y le encanta pasear por la playa."},
    {"id": 2, "nombre": "Michi", "especie": "gato", "raza": "Doméstico de pelo corto", "edad": "8 meses",
     "tamano": "pequeño", "sexo": "macho", "energia": "alta", "zona": "Zona Río",
     "estado": "disponible", "esterilizado": True, "vacunado": True, "foto": "michi.jpg",
     "personalidad": "Juguetón y curioso. Se lleva bien con otros gatos."},
    {"id": 3, "nombre": "Rocky", "especie": "perro", "raza": "Mestizo", "edad": "6 años",
     "tamano": "grande", "sexo": "macho", "energia": "baja", "zona": "Otay",
     "estado": "urgente", "esterilizado": False, "vacunado": True, "foto": "rocky.jpg",
     "personalidad": "Noble y paciente. Necesita hogar pronto: el refugio está lleno."},
    {"id": 4, "nombre": "Luna", "especie": "gato", "raza": "No especificada", "edad": "3 años",
     "tamano": "pequeño", "sexo": "hembra", "energia": "baja", "zona": "La Mesa",
     "estado": "en_proceso", "esterilizado": True, "vacunado": True, "foto": "luna.jpg",
     "personalidad": "Tímida al principio, muy dulce cuando toma confianza."},
    {"id": 5, "nombre": "Copito", "especie": "conejo", "raza": "Cabeza de león", "edad": "1 año",
     "tamano": "pequeño", "sexo": "macho", "energia": "media", "zona": "Chapultepec",
     "estado": "hogar_temporal", "esterilizado": False, "vacunado": False, "foto": "copito.jpg",
     "personalidad": "Tranquilo, le gusta que lo cepillen."},
    {"id": 6, "nombre": "Toby", "especie": "perro", "raza": "Chihuahua cruza", "edad": "4 años",
     "tamano": "pequeño", "sexo": "macho", "energia": "alta", "zona": "Cacho",
     "estado": "recuperacion", "esterilizado": True, "vacunado": True, "foto": "toby.jpg",
     "personalidad": "Valiente y alegre. Se recupera de una cirugía en la pata."},
    {"id": 7, "nombre": "Kiwi", "especie": "ave", "raza": "Perico australiano", "edad": "2 años",
     "tamano": "pequeño", "sexo": "hembra", "energia": "alta", "zona": "Hipódromo",
     "estado": "disponible", "esterilizado": False, "vacunado": False, "foto": "kiwi.jpg",
     "personalidad": "Muy sociable, canta por las mañanas."},
    {"id": 8, "nombre": "Nala", "especie": "perro", "raza": "No especificada", "edad": "1 año",
     "tamano": "mediano", "sexo": "hembra", "energia": "alta", "zona": "Santa Fe",
     "estado": "disponible", "esterilizado": True, "vacunado": True, "foto": "nala.jpg",
     "personalidad": "Energética, ideal para familias activas."},
    # --- Perdidos y encontrados (NO se muestran en el catálogo de adopción) ---
    {"id": 9, "nombre": "Pelusa", "especie": "gato", "raza": "Persa cruza", "edad": "5 años",
     "tamano": "pequeño", "sexo": "hembra", "energia": "baja", "zona": "Colonia Cacho",
     "estado": "perdido", "esterilizado": True, "vacunado": True, "foto": "pelusa.jpg",
     "personalidad": "Visto por última vez cerca de un parque de la colonia."},
    {"id": 10, "nombre": "Sin nombre", "especie": "perro", "raza": "No especificada", "edad": "Adulto",
     "tamano": "mediano", "sexo": "macho", "energia": "media", "zona": "Playas de Tijuana",
     "estado": "encontrado", "esterilizado": False, "vacunado": False, "foto": "encontrado1.jpg",
     "personalidad": "Encontrado con collar rojo, sin placa. Está resguardado."},
]

REFUGIOS = [
    {"id": 1, "nombre": "Refugio Huellitas TJ (ejemplo)", "zona": "Otay", "verificado": True,
     "animales": 34, "descripcion": "Rescate y rehabilitación de perros y gatos en situación de calle."},
    {"id": 2, "nombre": "Gatitos de la Mesa (ejemplo)", "zona": "La Mesa", "verificado": False,
     "animales": 12, "descripcion": "Colectivo dedicado a gatos rescatados y campañas de esterilización."},
    {"id": 3, "nombre": "Asociación Corazón Peludo (ejemplo)", "zona": "Playas de Tijuana", "verificado": False,
     "animales": 21, "descripcion": "Hogares temporales y adopciones responsables."},
]

PUBLICACIONES = [
    {"autor": "Refugio Huellitas TJ (ejemplo)", "tipo": "Historia de éxito", "icono": "bi-stars",
     "texto": "¡Max encontró familia! Después de 8 meses en el refugio ya duerme en su nueva cama.",
     "tiempo": "hace 2 horas", "me_gusta": 128, "comentarios": 14},
    {"autor": "Gatitos de la Mesa (ejemplo)", "tipo": "Campaña de esterilización", "icono": "bi-calendar-heart",
     "texto": "Este sábado tendremos jornada de esterilización a bajo costo. Cupo limitado.",
     "tiempo": "hace 5 horas", "me_gusta": 76, "comentarios": 9},
    {"autor": "Voluntaria (ejemplo)", "tipo": "Voluntariado", "icono": "bi-people",
     "texto": "Buscamos voluntarios para paseos los domingos por la mañana.",
     "tiempo": "ayer", "me_gusta": 41, "comentarios": 6},
]

# --- Alertas Patitas de ejemplo (ficticias) ---------------------------------
# Las fechas se calculan al arrancar la app para que siempre parezcan recientes.
from datetime import datetime, timedelta, timezone  # noqa: E402

_ahora = datetime.now(timezone.utc)

ALERTAS = [
    {"id": "ejemplo-chispa", "nombre": "Chispa", "especie": "perro", "raza": "Mestiza", "sexo": "hembra",
     "tamano": "pequeño", "edad_aproximada": "3 años", "color": "Café con blanco",
     "senas_particulares": "Oreja izquierda doblada y una mancha blanca en el pecho.",
     "collar": "Collar rosa con cascabel, sin placa.",
     "descripcion": "Se asustó con los cohetes y salió corriendo. Es miedosa: si la ves, háblale despacio y no la persigas.",
     "zona_referencia": "Centro, cerca del Parque Teniente Guerrero", "municipio": "Tijuana",
     "visto_por_ultima_vez": _ahora - timedelta(hours=3), "creada_en": _ahora - timedelta(hours=2, minutes=40),
     "expira_en": _ahora + timedelta(days=30), "latitud_aprox": 32.51, "longitud_aprox": -117.04,
     "mostrar_telefono": True, "estado": "activa", "foto": "chispa.jpg", "personas_avisadas": 148,
     "emisor": {"nombre_publico": "Mariana (ejemplo)", "creado_en": _ahora - timedelta(days=210),
                "nivel_verificacion": "registrada"}},
    {"id": "ejemplo-bruno", "nombre": "Bruno", "especie": "perro", "raza": "Labrador cruza", "sexo": "macho",
     "tamano": "grande", "edad_aproximada": "6 años", "color": "Negro",
     "senas_particulares": "Canas en el hocico. Cojea un poco de la pata trasera derecha.",
     "collar": "Sin collar.",
     "descripcion": "Salió por la puerta del patio. Es amigable con todos, pero necesita su medicina diaria.",
     "zona_referencia": "Playas de Tijuana, por el Malecón", "municipio": "Tijuana",
     "visto_por_ultima_vez": _ahora - timedelta(days=1, hours=5), "creada_en": _ahora - timedelta(days=1, hours=4),
     "expira_en": _ahora + timedelta(days=29), "latitud_aprox": 32.53, "longitud_aprox": -117.12,
     "mostrar_telefono": False, "estado": "activa", "foto": "bruno.jpg", "personas_avisadas": 96,
     "emisor": {"nombre_publico": "Familia Ortega (ejemplo)", "creado_en": _ahora - timedelta(days=45),
                "nivel_verificacion": "identidad_verificada"}},
]
