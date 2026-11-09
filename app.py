"""
Patitas - "Busca amor. Encuentra hogar."
Aplicación principal de Flask: crea la app y define las rutas.

Para ejecutar en Codespaces:
    flask --app app run --debug
"""
import os

from flask import Flask, abort, render_template, request

from config import Config
from services import alertas as servicio_alertas
from services import animales as servicio
from services.datos_ejemplo import PUBLICACIONES
from services.estados import ESTADOS

app = Flask(__name__)
app.config.from_object(Config)

# Valores permitidos para los filtros (validación del lado del servidor).
FILTROS_PERMITIDOS = {
    "especie": ["perro", "gato", "conejo", "ave"],
    "tamano": ["pequeño", "mediano", "grande"],
    "sexo": ["hembra", "macho"],
    "energia": ["baja", "media", "alta"],
}

CARPETA_FOTOS = os.path.join(app.static_folder, "images", "animales")


# ---------------------------------------------------------------------------
# Utilidades disponibles en todas las plantillas
# ---------------------------------------------------------------------------
def foto_existe(nombre_archivo):
    """True si la foto está en static/images/animales/."""
    return bool(nombre_archivo) and os.path.isfile(os.path.join(CARPETA_FOTOS, nombre_archivo))


# Disponibles en todas las plantillas, incluidas las macros de componentes.html.
app.jinja_env.globals.update(ESTADOS=ESTADOS, foto_existe=foto_existe)
app.jinja_env.filters["hace_tiempo"] = servicio_alertas.hace_tiempo
app.jinja_env.filters["fecha_local"] = servicio_alertas.fecha_local
app.jinja_env.filters["mes_anio"] = servicio_alertas.mes_anio


@app.context_processor
def variables_de_pagina():
    # Para mostrar el aviso "modo de ejemplo" mientras Supabase no esté configurado.
    return {"modo_ejemplo": servicio.modo_ejemplo()}


@app.after_request
def cabeceras_seguridad(respuesta):
    """Cabeceras básicas que protegen contra ataques comunes."""
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "SAMEORIGIN"
    respuesta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return respuesta


def leer_filtros():
    """Lee los filtros de la URL y descarta cualquier valor no permitido."""
    filtros = {}
    for campo, permitidos in FILTROS_PERMITIDOS.items():
        valor = request.args.get(campo, "").strip().lower()
        if valor in permitidos:
            filtros[campo] = valor
    return filtros


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.route("/")
def inicio():
    return render_template("index.html", destacados=servicio.listar_destacados(),
                           refugios=servicio.listar_refugios()[:3],
                           alertas=servicio_alertas.listar_vigentes()[:3])


@app.route("/adoptar")
def catalogo():
    filtros = leer_filtros()
    return render_template("catalogo.html", animales=servicio.listar_catalogo(filtros),
                           filtros=filtros, opciones=FILTROS_PERMITIDOS)


@app.route("/animal/<animal_id>")
def detalle_animal(animal_id):
    animal = servicio.obtener_animal(animal_id)
    if animal is None:
        abort(404)
    return render_template("detalle_animal.html", animal=animal)


@app.route("/perdidos-y-encontrados")
def perdidos():
    return render_template("perdidos.html", animales=servicio.listar_perdidos_encontrados())


# ---------------------------------------------------------------------------
# Alerta Patitas (mascotas perdidas)
# ---------------------------------------------------------------------------
@app.route("/alertas")
def alertas():
    return render_template("alertas.html", alertas=servicio_alertas.listar_vigentes(),
                           radio_km=servicio_alertas.RADIO_KM)


@app.route("/alertas/emitir")
def emitir_alerta():
    # Visual por ahora: emitir requiere cuentas (Etapa 3).
    ejemplo = servicio_alertas.datos_ejemplo.ALERTAS[0]
    return render_template("alerta_emitir.html", ejemplo=ejemplo, radio_km=servicio_alertas.RADIO_KM)


@app.route("/alerta/<alerta_id>")
def detalle_alerta(alerta_id):
    alerta = servicio_alertas.obtener(alerta_id)
    if alerta is None:
        abort(404)
    return render_template("alerta_detalle.html", alerta=alerta,
                           vigente=servicio_alertas.vigente(alerta), radio_km=servicio_alertas.RADIO_KM)


@app.route("/refugios")
def refugios():
    return render_template("refugios.html", refugios=servicio.listar_refugios())


@app.route("/comunidad")
def comunidad():
    # La comunidad se conecta a la base de datos en la Etapa 6.
    return render_template("comunidad.html", publicaciones=PUBLICACIONES)


@app.route("/acerca")
def acerca():
    return render_template("acerca.html")


@app.route("/iniciar-sesion")
def iniciar_sesion():
    return render_template("login.html")


@app.route("/registro")
def registro():
    return render_template("registro.html")


@app.route("/privacidad")
def privacidad():
    return render_template("privacidad.html")


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def pagina_no_encontrada(error):
    return render_template("404.html"), 404


@app.errorhandler(servicio.ErrorBaseDeDatos)
def error_base_de_datos(error):
    # El detalle técnico va a la terminal; la persona ve un mensaje amable.
    app.logger.error("Error al consultar Supabase: %s", error)
    return render_template("error_conexion.html"), 503


if __name__ == "__main__":
    app.run(debug=Config.PATITAS_ENV == "development")
