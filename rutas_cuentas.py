"""
Rutas de cuentas (Etapa 3): registro, inicio y cierre de sesión, confirmación
de correo, recuperación de contraseña, mi cuenta, perfil público y paneles.

app.py las activa con: registrar_rutas_cuentas(app)
"""
import uuid

from flask import abort, flash, redirect, render_template, request, session, url_for

from services import autenticacion as auth
from services.autenticacion import ErrorCuenta
from services.seguridad import demasiados_intentos, destino_seguro, olvidar_intentos
from services.sesion import (admin_requerido, actualizar_nombre_en_sesion, borrar_sesion,
                             guardar_sesion, login_requerido, tipo_requerido, token_actual,
                             usuario_actual)
from services.supabase_cliente import supabase_configurado

MINUTO, HORA = 60, 3600


def _ip():
    return request.remote_addr or "desconocida"


def _sin_supabase():
    """En modo de ejemplo no hay cuentas: avisa y regresa."""
    flash("Las cuentas necesitan Supabase. Configúralo en .env (ver GUIA_SUPABASE.md).", "aviso")
    return redirect(request.path)


def _entrar(datos_sesion, siguiente="/"):
    """Guarda la sesión y redirige. Si no se puede leer el perfil, no deja la sesión a medias."""
    try:
        perfil = auth.leer_mi_perfil(datos_sesion["access_token"], datos_sesion["usuario_id"])
    except ErrorCuenta as error:
        auth.cerrar_sesion(datos_sesion["access_token"])
        borrar_sesion()
        flash(error.mensaje, "error")
        return redirect(url_for("iniciar_sesion"))
    guardar_sesion(datos_sesion, perfil)
    return redirect(destino_seguro(siguiente, url_for("mi_cuenta")))


def registrar_rutas_cuentas(app):

    # -----------------------------------------------------------------------
    # Registro
    # -----------------------------------------------------------------------
    @app.route("/registro", methods=["GET", "POST"])
    def registro():
        if usuario_actual():
            return redirect(url_for("mi_cuenta"))
        datos = {"nombre": "", "correo": "", "tipo_cuenta": request.args.get("tipo", "")}
        if request.method == "POST":
            if not supabase_configurado():
                return _sin_supabase()
            datos = {"nombre": request.form.get("nombre", ""), "correo": request.form.get("correo", ""),
                     "tipo_cuenta": request.form.get("tipo_cuenta", "")}
            try:
                if demasiados_intentos(f"registro:{_ip()}", 5, HORA):
                    raise ErrorCuenta("Demasiados registros desde esta conexión. Inténtalo más tarde.")
                if request.form.get("contrasena") != request.form.get("confirmar"):
                    raise ErrorCuenta("Las contraseñas no coinciden.")
                sesion_nueva = auth.registrar(datos["correo"], request.form.get("contrasena"), datos["nombre"],
                                              datos["tipo_cuenta"], request.form.get("acepta_aviso") == "si")
            except ErrorCuenta as error:
                flash(error.mensaje, "error")
            else:
                if sesion_nueva:  # el proyecto no pide confirmar correo
                    return _entrar(sesion_nueva)
                session["correo_pendiente"] = auth.validar_correo(datos["correo"])
                return redirect(url_for("revisa_tu_correo"))
        return render_template("registro.html", datos=datos, tipos=auth.TIPOS_CUENTA)

    @app.route("/registro/revisa-tu-correo")
    def revisa_tu_correo():
        correo = session.get("correo_pendiente")
        if not correo:
            return redirect(url_for("registro"))
        return render_template("revisa_correo.html", correo=correo)

    @app.route("/registro/reenviar", methods=["POST"])
    def reenviar_confirmacion():
        correo = session.get("correo_pendiente") or request.form.get("correo", "")
        try:
            if demasiados_intentos(f"reenviar:{correo.lower()}", 3, HORA):
                raise ErrorCuenta("Ya reenviamos el correo varias veces. Espera una hora.")
            auth.reenviar_confirmacion(correo)
            session["correo_pendiente"] = auth.validar_correo(correo)
            flash("Te enviamos el correo de nuevo.", "exito")
        except ErrorCuenta as error:
            flash(error.mensaje, "error")
        return redirect(url_for("revisa_tu_correo") if session.get("correo_pendiente") else url_for("iniciar_sesion"))

    # -----------------------------------------------------------------------
    # Enlaces de los correos (confirmar cuenta / recuperar contraseña)
    # Se pide un clic en "Continuar" (POST) porque algunos correos abren los
    # enlaces automáticamente para revisarlos y eso gastaría el enlace.
    # -----------------------------------------------------------------------
    @app.route("/auth/confirmar", methods=["GET", "POST"])
    def confirmar_enlace():
        fuente = request.form if request.method == "POST" else request.args
        token_hash, tipo = fuente.get("token_hash", ""), fuente.get("type", "")
        if tipo not in ("email", "signup", "recovery") or not token_hash:
            flash("El enlace no es válido. Pide uno nuevo.", "error")
            return redirect(url_for("iniciar_sesion"))
        if request.method == "GET":
            return render_template("confirmar_enlace.html", token_hash=token_hash, tipo=tipo)
        try:
            datos_sesion = auth.verificar_enlace(token_hash, tipo)
        except ErrorCuenta as error:
            flash(error.mensaje, "error")
            return redirect(url_for("recuperar_contrasena" if tipo == "recovery" else "iniciar_sesion"))
        session.pop("correo_pendiente", None)
        if tipo == "recovery":
            respuesta = _entrar(datos_sesion, url_for("nueva_contrasena"))
            session["recuperando"] = True
            flash("Elige tu nueva contraseña.", "info")
            return respuesta
        flash("¡Tu correo está confirmado! Bienvenida o bienvenido a Patitas.", "exito")
        return _entrar(datos_sesion, url_for("mi_cuenta"))

    # -----------------------------------------------------------------------
    # Inicio y cierre de sesión
    # -----------------------------------------------------------------------
    @app.route("/iniciar-sesion", methods=["GET", "POST"])
    def iniciar_sesion():
        siguiente = destino_seguro(request.values.get("siguiente", ""), "")
        if usuario_actual():
            return redirect(siguiente or url_for("mi_cuenta"))
        correo = ""
        mostrar_reenviar = False
        if request.method == "POST":
            if not supabase_configurado():
                return _sin_supabase()
            correo = request.form.get("correo", "").strip().lower()
            try:
                if (demasiados_intentos(f"login:{correo}", 5, 15 * MINUTO)
                        or demasiados_intentos(f"login-ip:{_ip()}", 20, 15 * MINUTO)):
                    raise ErrorCuenta("Demasiados intentos. Espera 15 minutos o recupera tu contraseña.")
                datos_sesion = auth.iniciar_sesion(correo, request.form.get("contrasena", ""))
                olvidar_intentos(f"login:{correo}")
                flash("¡Hola de nuevo!", "exito")
                return _entrar(datos_sesion, siguiente or url_for("mi_cuenta"))
            except ErrorCuenta as error:
                flash(error.mensaje, "error")
                if error.codigo == "email_not_confirmed":
                    session["correo_pendiente"] = correo
                    mostrar_reenviar = True
        return render_template("login.html", correo=correo, siguiente=siguiente,
                               mostrar_reenviar=mostrar_reenviar)

    @app.route("/cerrar-sesion", methods=["POST"])
    def cerrar_sesion():
        if session.get("tokens"):
            auth.cerrar_sesion(session["tokens"]["access_token"])
        borrar_sesion()
        flash("Cerraste sesión. ¡Vuelve pronto!", "info")
        return redirect(url_for("inicio"))

    # -----------------------------------------------------------------------
    # Recuperar y cambiar contraseña
    # -----------------------------------------------------------------------
    @app.route("/recuperar-contrasena", methods=["GET", "POST"])
    def recuperar_contrasena():
        enviado = False
        if request.method == "POST":
            if not supabase_configurado():
                return _sin_supabase()
            correo = request.form.get("correo", "").strip().lower()
            try:
                if (demasiados_intentos(f"recuperar:{correo}", 3, HORA)
                        or demasiados_intentos(f"recuperar-ip:{_ip()}", 10, HORA)):
                    raise ErrorCuenta("Ya enviamos varios correos. Espera una hora e inténtalo de nuevo.")
                auth.enviar_recuperacion(correo)
                enviado = True
            except ErrorCuenta as error:
                # Si el error es "esa cuenta no existe", Supabase no lo dice:
                # así nadie puede averiguar qué correos están registrados.
                flash(error.mensaje, "error")
        return render_template("recuperar.html", enviado=enviado)

    @app.route("/cuenta/nueva-contrasena", methods=["GET", "POST"])
    @login_requerido
    def nueva_contrasena():
        if request.method == "POST":
            try:
                if request.form.get("contrasena") != request.form.get("confirmar"):
                    raise ErrorCuenta("Las contraseñas no coinciden.")
                auth.cambiar_contrasena(session["tokens"], request.form.get("contrasena"))
            except ErrorCuenta as error:
                flash(error.mensaje, "error")
            else:
                session.pop("recuperando", None)
                flash("Tu contraseña se cambió correctamente.", "exito")
                return redirect(url_for("mi_cuenta"))
        return render_template("nueva_contrasena.html", recuperando=session.get("recuperando"))

    # -----------------------------------------------------------------------
    # Mi cuenta y perfil público
    # -----------------------------------------------------------------------
    @app.route("/cuenta", methods=["GET", "POST"])
    @login_requerido
    def mi_cuenta():
        usuario = usuario_actual()
        if request.method == "POST":
            try:
                nombre = auth.actualizar_mi_perfil(
                    token_actual(), usuario["id"], request.form.get("nombre_publico"),
                    request.form.get("biografia"), request.form.get("municipio"), request.form.get("telefono"))
            except ErrorCuenta as error:
                flash(error.mensaje, "error")
            else:
                actualizar_nombre_en_sesion(nombre)
                flash("Tu perfil se guardó.", "exito")
                return redirect(url_for("mi_cuenta"))
        try:
            perfil = auth.leer_mi_perfil(token_actual(), usuario["id"])
        except ErrorCuenta as error:
            flash(error.mensaje, "error")
            borrar_sesion()
            return redirect(url_for("iniciar_sesion"))
        return render_template("cuenta.html", perfil=perfil, usuario=usuario,
                               nombres_tipo=auth.NOMBRES_TIPO, niveles=auth.NIVELES)

    @app.route("/perfil/<usuario_id>")
    def perfil_publico(usuario_id):
        if not supabase_configurado():
            abort(404)
        try:
            uuid.UUID(usuario_id)
        except ValueError:
            abort(404)
        try:
            perfil = auth.perfil_publico(usuario_id)
        except ErrorCuenta:
            perfil = None
        if perfil is None:
            abort(404)
        return render_template("perfil_publico.html", perfil=perfil,
                               nombres_tipo=auth.NOMBRES_TIPO, niveles=auth.NIVELES)

    # -----------------------------------------------------------------------
    # Paneles con permisos por rol
    # -----------------------------------------------------------------------
    @app.route("/panel")
    @tipo_requerido("refugio", "rescatista")
    def panel():
        return render_template("panel.html")

    @app.route("/admin")
    @admin_requerido
    def panel_admin():
        return render_template("admin.html")
