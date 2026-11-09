"""
Estados de un animal en Patitas.

Cada estado tiene: texto visible, icono (Bootstrap Icons) y clase de color.
Se definen en un solo lugar para que todas las pantallas usen las mismas insignias.
"""

ESTADOS = {
    "disponible": {"texto": "Disponible para adopción", "icono": "bi-house-heart", "clase": "estado-disponible"},
    "en_proceso": {"texto": "En proceso de adopción", "icono": "bi-hourglass-split", "clase": "estado-proceso"},
    "adoptado": {"texto": "Adoptado", "icono": "bi-heart-fill", "clase": "estado-adoptado"},
    "hogar_temporal": {"texto": "En hogar temporal", "icono": "bi-house-door", "clase": "estado-temporal"},
    "perdido": {"texto": "Perdido", "icono": "bi-search", "clase": "estado-perdido"},
    "encontrado": {"texto": "Encontrado", "icono": "bi-geo-alt", "clase": "estado-encontrado"},
    "recuperacion": {"texto": "En recuperación médica", "icono": "bi-bandaid", "clase": "estado-recuperacion"},
    "urgente": {"texto": "Urgente por riesgo", "icono": "bi-exclamation-triangle-fill", "clase": "estado-urgente"},
}

# Estados que aparecen en el catálogo de ADOPCIÓN.
# Perdidos y encontrados tienen su propia sección: no se mezclan con adopciones.
ESTADOS_CATALOGO = ["disponible", "urgente", "en_proceso", "hogar_temporal", "recuperacion"]

# Estados de la sección "Perdidos y encontrados".
ESTADOS_PERDIDOS = ["perdido", "encontrado"]
