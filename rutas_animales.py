"""
Rutas de la Etapa 4 (Mi panel): mis animales, publicar, editar, cambiar estado,
borrar, fotos (máx. 3) y mi refugio.

Solo cuentas de refugio y rescatista. La base de datos vuelve a comprobar cada
permiso (migración 005), así que estas rutas no son la única protección.

app.py las activa con: registrar_rutas_animales(app)
"""
from flask import abort, flash, redirect, render_template, request, url_for

from services import animales_panel as panel
from services.animales_panel import ErrorAnimal
from services.estados import ESTADOS
from services.sesion import tipo_requerido, token_actual, usuario_actual

TIPOS_PANEL = ("refugio", "rescatista")
DATOS_NUEVO = {"especie": "perro", "sexo": "", "tamano": "", "energia": "", "estado": "disponible",
               "convive_ninos": "", "convive_perros": "", "convive_gatos": "", "refugio_id": ""}


def _yo():
    return token_actual(), usuario_actual()["id"]


def _opciones_formulario(refugios):
    return {"especies": panel.ESPECIES, "tamanos": panel.TAMANOS, "sexos": panel.SEXOS,
            "energias": panel.ENERGIAS, "estados_publicables": panel.ESTADOS_PUBLICABLES,
            "refugios": refugios}


def registrar_rutas_animales(app):

    @app.route("/panel", endpoint="panel")
    @tipo_requerido(*TIPOS_PANEL)
    def panel_inicio():
        token, yo = _yo()
        try:
            animales = panel.mis_animales(token, yo)
            refugio = panel.leer_mi_refugio(token, yo) if usuario_actual()["tipo_cuenta"] == "refugio" else None
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
            animales, refugio = [], None
        conteo = {
            "publicados": sum(1 for a in animales if a["estado"] not in ("adoptado",)),
            "en_proceso": sum(1 for a in animales if a["estado"] == "en_proceso"),
            "adoptados": sum(1 for a in animales if a["estado"] == "adoptado"),
        }
        return render_template("panel.html", conteo=conteo, refugio=refugio,
                               estados_refugio=panel.ESTADOS_REFUGIO, recientes=animales[:3])

    # -----------------------------------------------------------------------
    # Mis animales
    # -----------------------------------------------------------------------
    @app.route("/panel/animales")
    @tipo_requerido(*TIPOS_PANEL)
    def mis_animales():
        token, yo = _yo()
        try:
            animales = panel.mis_animales(token, yo)
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
            animales = []
        return render_template("panel_animales.html", animales=animales,
                               estados_publicables=panel.ESTADOS_PUBLICABLES, max_fotos=panel.MAX_FOTOS)

    @app.route("/panel/animales/nuevo", methods=["GET", "POST"])
    @tipo_requerido(*TIPOS_PANEL)
    def publicar_animal():
        token, yo = _yo()
        try:
            refugios = panel.refugios_para_publicar(token, yo)
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
            refugios = []
        datos = dict(DATOS_NUEVO, refugio_id=refugios[0]["id"] if len(refugios) == 1 else "")
        if request.method == "POST":
            datos = request.form.to_dict()
            try:
                animal_id = panel.crear(token, yo, request.form, refugios)
            except ErrorAnimal as error:
                flash(error.mensaje, "error")
            else:
                flash(f"¡{datos.get('nombre', 'Tu animal').strip()} ya está publicado! Ahora agrega sus fotos.", "exito")
                return redirect(url_for("fotos_animal", animal_id=animal_id))
        return render_template("animal_formulario.html", datos=datos, animal=None, **_opciones_formulario(refugios))

    @app.route("/panel/animal/<animal_id>/editar", methods=["GET", "POST"])
    @tipo_requerido(*TIPOS_PANEL)
    def editar_animal(animal_id):
        token, yo = _yo()
        try:
            animal = panel.obtener_mio(token, yo, animal_id)
            refugios = panel.refugios_para_publicar(token, yo)
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
            return redirect(url_for("mis_animales"))
        if animal is None:
            abort(404)
        datos = panel.animal_a_formulario(animal)
        if request.method == "POST":
            datos = request.form.to_dict()
            try:
                panel.actualizar(token, yo, animal_id, request.form, refugios)
            except ErrorAnimal as error:
                flash(error.mensaje, "error")
            else:
                flash("Guardamos los cambios.", "exito")
                return redirect(url_for("mis_animales"))
        return render_template("animal_formulario.html", datos=datos, animal=animal, **_opciones_formulario(refugios))

    @app.route("/panel/animal/<animal_id>/estado", methods=["POST"])
    @tipo_requerido(*TIPOS_PANEL)
    def estado_animal(animal_id):
        token, yo = _yo()
        estado = request.form.get("estado", "")
        try:
            panel.cambiar_estado(token, yo, animal_id, estado)
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
        else:
            if estado == "adoptado":
                flash("¡Qué alegría! Lo marcamos como adoptado.", "exito")
            else:
                flash(f"Estado actualizado: {ESTADOS[estado]['texto']}.", "exito")
        return redirect(url_for("mis_animales"))

    @app.route("/panel/animal/<animal_id>/borrar", methods=["POST"])
    @tipo_requerido(*TIPOS_PANEL)
    def borrar_animal(animal_id):
        token, yo = _yo()
        try:
            nombre = panel.borrar(token, yo, animal_id)
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
        else:
            flash(f"Borramos la publicación de {nombre} y sus fotos.", "info")
        return redirect(url_for("mis_animales"))

    # -----------------------------------------------------------------------
    # Fotos
    # -----------------------------------------------------------------------
    @app.route("/panel/animal/<animal_id>/fotos", methods=["GET", "POST"])
    @tipo_requerido(*TIPOS_PANEL)
    def fotos_animal(animal_id):
        token, yo = _yo()
        if request.method == "POST":
            archivos = [f.read() for f in request.files.getlist("fotos") if f and f.filename]
            try:
                guardadas = panel.subir_fotos(token, yo, animal_id, archivos)
            except ErrorAnimal as error:
                flash(error.mensaje, "error")
            else:
                flash("Foto guardada." if guardadas == 1 else f"{guardadas} fotos guardadas.", "exito")
            return redirect(url_for("fotos_animal", animal_id=animal_id))
        try:
            animal = panel.obtener_mio(token, yo, animal_id)
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
            return redirect(url_for("mis_animales"))
        if animal is None:
            abort(404)
        return render_template("animal_fotos.html", animal=animal, max_fotos=panel.MAX_FOTOS)

    @app.route("/panel/animal/<animal_id>/foto/<foto_id>/borrar", methods=["POST"])
    @tipo_requerido(*TIPOS_PANEL)
    def borrar_foto_animal(animal_id, foto_id):
        token, yo = _yo()
        try:
            panel.borrar_foto(token, yo, animal_id, foto_id)
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
        else:
            flash("Foto borrada.", "info")
        return redirect(url_for("fotos_animal", animal_id=animal_id))

    @app.route("/panel/animal/<animal_id>/foto/<foto_id>/principal", methods=["POST"])
    @tipo_requerido(*TIPOS_PANEL)
    def foto_principal_animal(animal_id, foto_id):
        token, yo = _yo()
        try:
            panel.foto_principal(token, yo, animal_id, foto_id)
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
        else:
            flash("Listo: esa es ahora la foto principal.", "exito")
        return redirect(url_for("fotos_animal", animal_id=animal_id))

    # -----------------------------------------------------------------------
    # Mi refugio (solo cuentas de refugio)
    # -----------------------------------------------------------------------
    @app.route("/panel/mi-refugio", methods=["GET", "POST"])
    @tipo_requerido("refugio")
    def mi_refugio():
        token, yo = _yo()
        try:
            refugio = panel.leer_mi_refugio(token, yo)
        except ErrorAnimal as error:
            flash(error.mensaje, "error")
            return redirect(url_for("panel"))
        datos = refugio or {"nombre": usuario_actual()["nombre"]}
        if request.method == "POST":
            datos = dict(refugio or {}, **request.form.to_dict())
            try:
                nuevo = panel.guardar_mi_refugio(token, yo, request.form)
            except ErrorAnimal as error:
                flash(error.mensaje, "error")
            else:
                flash("Registramos tu refugio. Queda «Pendiente de verificación» hasta que el equipo de Patitas "
                      "lo revise; mientras tanto ya puedes publicar animales." if nuevo
                      else "Guardamos los datos de tu refugio.", "exito")
                return redirect(url_for("mi_refugio"))
        return render_template("mi_refugio.html", datos=datos, refugio=refugio,
                               estados_refugio=panel.ESTADOS_REFUGIO)
