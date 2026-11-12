"""
Rutas de Alerta Patitas (Partes A y B): lista, detalle, emitir, "Lo vi",
cerrar y renovar, mis alertas, mi zona de alertas y notificaciones.

app.py las activa con: registrar_rutas_alertas(app)
"""
from datetime import datetime, timezone

from flask import abort, flash, redirect, render_template, request, url_for

from services import alertas as servicio_alertas
from services import alertas_acciones as acciones
from services.alertas_acciones import ErrorAlerta
from services.sesion import login_requerido, token_actual, usuario_actual
from services.supabase_cliente import supabase_configurado

RADIO_KM = servicio_alertas.RADIO_KM


def _ahora_local():
    """Valor por defecto de los campos de fecha y hora (hora de Tijuana)."""
    return datetime.now(timezone.utc).astimezone(servicio_alertas.ZONA_HORARIA).strftime("%Y-%m-%dT%H:%M")


def _requiere_supabase():
    if not supabase_configurado():
        flash("Esta función necesita Supabase. Configúralo en .env (ver GUIA_SUPABASE.md).", "aviso")
        return redirect(url_for("alertas"))
    return None


def registrar_rutas_alertas(app):

    @app.context_processor
    def campana():
        usuario = usuario_actual()
        if not usuario:
            return {"notificaciones_no_leidas": 0}
        return {"notificaciones_no_leidas": acciones.contar_no_leidas(token_actual())}

    # -----------------------------------------------------------------------
    # Lista y detalle (públicos)
    # -----------------------------------------------------------------------
    @app.route("/alertas")
    def alertas():
        lista = servicio_alertas.listar_vigentes()
        zona = None
        usuario = usuario_actual()
        if usuario:
            try:
                zona = acciones.leer_zona(token_actual(), usuario["id"])
            except ErrorAlerta:
                zona = None
        if zona:   # muestra a qué distancia de tu zona está cada alerta
            for a in lista:
                if a.get("latitud_aprox") is not None:
                    a["distancia_km"] = servicio_alertas.distancia_km(
                        zona["latitud"], zona["longitud"], a["latitud_aprox"], a["longitud_aprox"])
            lista.sort(key=lambda a: a.get("distancia_km", 10_000))
        return render_template("alertas.html", alertas=lista, zona=zona, radio_km=RADIO_KM)

    @app.route("/alerta/<alerta_id>")
    def detalle_alerta(alerta_id):
        alerta = servicio_alertas.obtener(alerta_id)
        if alerta is None:
            abort(404)
        usuario = usuario_actual()
        es_duena = bool(usuario and alerta.get("emisor_id") == usuario["id"])
        avistamientos, telefono = [], None
        if usuario and supabase_configurado():
            try:
                if es_duena:
                    avistamientos = acciones.avistamientos_de(token_actual(), alerta_id)
                elif alerta["mostrar_telefono"] and servicio_alertas.vigente(alerta):
                    telefono = acciones.telefono_contacto(token_actual(), alerta_id)
            except ErrorAlerta as error:
                flash(error.mensaje, "error")
        # Puntos para el mapa (solo la dueña recibe avistamientos de la base de datos)
        puntos = [{"lat": a["latitud"], "lng": a["longitud"], "lugar": a["lugar"],
                   "cuando": servicio_alertas.fecha_local(a["visto_en"])}
                  for a in avistamientos if a["latitud"] is not None]
        dias_restantes = None
        if es_duena and alerta.get("expira_en"):
            dias_restantes = (alerta["expira_en"] - datetime.now(timezone.utc)).days
        return render_template("alerta_detalle.html", alerta=alerta, vigente=servicio_alertas.vigente(alerta),
                               radio_km=RADIO_KM, es_duena=es_duena, avistamientos=avistamientos,
                               puntos_avistamientos=puntos, dias_restantes=dias_restantes,
                               telefono=telefono, ahora_local=_ahora_local())

    # -----------------------------------------------------------------------
    # Emitir
    # -----------------------------------------------------------------------
    @app.route("/alertas/emitir", methods=["GET", "POST"])
    def emitir_alerta():
        usuario = usuario_actual()
        datos = {"visto_por_ultima_vez": _ahora_local(), "especie": "perro", "sexo": "", "tamano": ""}
        if request.method == "POST":
            if (respuesta := _requiere_supabase()) is not None:
                return respuesta
            if not usuario:
                return redirect(url_for("iniciar_sesion", siguiente=url_for("emitir_alerta")))
            datos = request.form.to_dict()
            foto = request.files.get("foto")
            try:
                alerta_id = acciones.emitir(token_actual(), usuario["id"], request.form,
                                            foto.read() if foto else b"")
            except ErrorAlerta as error:
                flash(error.mensaje, "error")
            else:
                alerta = servicio_alertas.obtener(alerta_id)
                avisadas = (alerta or {}).get("personas_avisadas") or 0
                if avisadas:
                    personas = "1 persona" if avisadas == 1 else f"{avisadas} personas"
                    flash(f"Tu alerta está activa. Avisamos a {personas} a {RADIO_KM} km o menos.", "exito")
                else:
                    flash("Tu alerta está activa. Todavía no hay personas con alertas activadas en esa zona; "
                          "compártela para que más gente la vea.", "exito")
                return redirect(url_for("detalle_alerta", alerta_id=alerta_id))
        ejemplo = servicio_alertas.datos_ejemplo.ALERTAS[0]
        return render_template("alerta_emitir.html", ejemplo=ejemplo, radio_km=RADIO_KM, datos=datos,
                               especies=acciones.ESPECIES, sexos=acciones.SEXOS, tamanos=acciones.TAMANOS)

    # -----------------------------------------------------------------------
    # "Lo vi", cerrar y renovar
    # -----------------------------------------------------------------------
    @app.route("/alerta/<alerta_id>/lo-vi", methods=["POST"])
    @login_requerido
    def reportar_avistamiento(alerta_id):
        try:
            acciones.reportar_avistamiento(token_actual(), usuario_actual()["id"], alerta_id, request.form)
        except ErrorAlerta as error:
            flash(error.mensaje, "error")
        else:
            flash("¡Gracias! Avisamos a la familia de dónde y cuándo lo viste.", "exito")
        return redirect(url_for("detalle_alerta", alerta_id=alerta_id))

    @app.route("/alerta/<alerta_id>/cerrar", methods=["POST"])
    @login_requerido
    def cerrar_alerta(alerta_id):
        estado = request.form.get("estado")
        try:
            acciones.cerrar(token_actual(), usuario_actual()["id"], alerta_id, estado)
        except ErrorAlerta as error:
            flash(error.mensaje, "error")
        else:
            if estado == "encontrada":
                flash("¡Qué alegría! Avisamos a quienes ayudaron a buscarlo.", "exito")
            else:
                flash("La alerta se canceló.", "info")
        return redirect(url_for("detalle_alerta", alerta_id=alerta_id))

    @app.route("/alerta/<alerta_id>/renovar", methods=["POST"])
    @login_requerido
    def renovar_alerta(alerta_id):
        try:
            acciones.renovar(token_actual(), alerta_id)
        except ErrorAlerta as error:
            flash(error.mensaje, "error")
        else:
            flash("Tu alerta estará activa 30 días más.", "exito")
        return redirect(url_for("detalle_alerta", alerta_id=alerta_id))

    @app.route("/mis-alertas")
    @login_requerido
    def mis_alertas():
        try:
            lista = acciones.mis_alertas(token_actual(), usuario_actual()["id"])
        except ErrorAlerta as error:
            flash(error.mensaje, "error")
            lista = []
        return render_template("mis_alertas.html", alertas=lista,
                               vigente=servicio_alertas.vigente, ahora=datetime.now(timezone.utc))

    # -----------------------------------------------------------------------
    # Mi zona de alertas
    # -----------------------------------------------------------------------
    @app.route("/cuenta/zona-alertas", methods=["GET", "POST"])
    @login_requerido
    def zona_alertas():
        usuario = usuario_actual()
        if request.method == "POST":
            try:
                if request.form.get("accion") == "borrar":
                    acciones.borrar_zona(token_actual(), usuario["id"])
                    flash("Borramos tu zona. Ya no recibirás alertas.", "info")
                else:
                    acciones.guardar_zona(token_actual(), usuario["id"], request.form)
                    flash("Tu zona de alertas se guardó.", "exito")
                return redirect(url_for("zona_alertas"))
            except ErrorAlerta as error:
                flash(error.mensaje, "error")
        try:
            zona = acciones.leer_zona(token_actual(), usuario["id"])
        except ErrorAlerta as error:
            flash(error.mensaje, "error")
            zona = None
        return render_template("zona_alertas.html", zona=zona, radio_km=RADIO_KM)

    # -----------------------------------------------------------------------
    # Notificaciones
    # -----------------------------------------------------------------------
    @app.route("/notificaciones")
    @login_requerido
    def notificaciones():
        try:
            lista = acciones.listar_notificaciones(token_actual())
        except ErrorAlerta as error:
            flash(error.mensaje, "error")
            lista = []
        return render_template("notificaciones.html", notificaciones=lista)

    @app.route("/notificaciones/leidas", methods=["POST"])
    @login_requerido
    def marcar_notificaciones_leidas():
        try:
            acciones.marcar_leidas(token_actual(), usuario_actual()["id"])
        except ErrorAlerta as error:
            flash(error.mensaje, "error")
        return redirect(url_for("notificaciones"))
