"""
Pruebas de la Etapa 3 (cuentas) con la librería real de Supabase conectada
al simulador de tests/simulador_supabase.py (sin internet).
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from services.seguridad import reiniciar_limites  # noqa: E402
from simulador_supabase import CLAVE_PUBLICA, URL, SimuladorSupabase  # noqa: E402

CONTRASENA = "perritos2026"


@pytest.fixture
def sim():
    simulador = SimuladorSupabase()
    app.config.update(TESTING=True, SUPABASE_URL=URL, SUPABASE_CLAVE_PUBLICA=CLAVE_PUBLICA,
                      SUPABASE_HTTPX_PRUEBAS=simulador.cliente_httpx())
    reiniciar_limites()
    yield simulador
    app.config.update(SUPABASE_URL="", SUPABASE_CLAVE_PUBLICA="", SUPABASE_HTTPX_PRUEBAS=None)


@pytest.fixture
def cliente(sim):
    with app.test_client() as c:
        yield c


def csrf(cliente):
    with cliente.session_transaction() as s:
        s.setdefault("_csrf", "token-de-prueba")
        return s["_csrf"]


def post(cliente, ruta, datos=None, **kwargs):
    datos = dict(datos or {})
    datos.setdefault("csrf_token", csrf(cliente))
    return cliente.post(ruta, data=datos, **kwargs)


def entrar(cliente, sim, correo="ana@example.com", tipo="adoptante", nombre="Ana Prueba"):
    if correo not in sim.usuarios:
        sim.crear_usuario(correo, CONTRASENA, nombre=nombre, tipo=tipo)
    r = post(cliente, "/iniciar-sesion", {"correo": correo, "contrasena": CONTRASENA})
    assert r.status_code == 302, r.get_data(as_text=True)
    return sim.usuarios[correo]["id"]


def peticiones(sim, ruta):
    return [p for p in sim.peticiones if p["ruta"] == ruta]


def texto(r):
    return r.get_data(as_text=True)


REGISTRO_OK = {"nombre": "  Lucía   Prueba ", "correo": "Lucia@Example.com", "contrasena": CONTRASENA,
               "confirmar": CONTRASENA, "tipo_cuenta": "voluntario", "acepta_aviso": "si"}


# --- Registro -----------------------------------------------------------------
def test_registro_envia_los_datos_correctos(cliente, sim):
    r = post(cliente, "/registro", REGISTRO_OK)
    assert r.status_code == 302 and r.location.endswith("/registro/revisa-tu-correo")
    envio = peticiones(sim, "/auth/v1/signup")[0]["cuerpo"]
    assert envio["email"] == "lucia@example.com"
    assert envio["data"] == {"nombre_publico": "Lucía Prueba", "tipo_cuenta": "voluntario",
                             "acepto_aviso_privacidad": True}
    assert sim.ultimo_enlace("lucia@example.com", "email")
    assert "lucia@example.com" in texto(cliente.get("/registro/revisa-tu-correo"))


@pytest.mark.parametrize("cambio,mensaje", [
    ({"acepta_aviso": ""}, "aceptar el aviso de privacidad"),
    ({"confirmar": "otra-cosa-123"}, "no coinciden"),
    ({"contrasena": "solotexto", "confirmar": "solotexto"}, "letras y números"),
    ({"contrasena": "abc12", "confirmar": "abc12"}, "al menos 8"),
    ({"tipo_cuenta": "administrador"}, "Elige un tipo de cuenta"),
    ({"correo": "no-es-correo"}, "correo electrónico válido"),
    ({"nombre": "A"}, "entre 2 y 60"),
])
def test_registro_valida_en_el_servidor(cliente, sim, cambio, mensaje):
    r = post(cliente, "/registro", {**REGISTRO_OK, **cambio})
    assert r.status_code == 200 and mensaje in texto(r)
    assert peticiones(sim, "/auth/v1/signup") == []


def test_registro_no_revela_si_el_correo_ya_existe(cliente, sim):
    sim.crear_usuario("lucia@example.com", CONTRASENA)
    r = post(cliente, "/registro", REGISTRO_OK)
    assert r.status_code == 302 and r.location.endswith("/registro/revisa-tu-correo")


# --- Confirmación de correo ---------------------------------------------------
def test_confirmar_correo_inicia_sesion(cliente, sim):
    post(cliente, "/registro", REGISTRO_OK)
    token = sim.ultimo_enlace("lucia@example.com", "email")
    r = cliente.get(f"/auth/confirmar?token_hash={token}&type=email")
    assert r.status_code == 200 and "Continuar" in texto(r)
    assert peticiones(sim, "/auth/v1/verify") == []  # abrir el enlace no lo gasta
    r = post(cliente, "/auth/confirmar", {"token_hash": token, "type": "email"})
    assert r.status_code == 302 and r.location.endswith("/cuenta")
    html = texto(cliente.get("/cuenta"))
    assert "Lucía Prueba" in html and "Voluntariado" in html and "Cuenta registrada" in html
    assert "Tu correo está confirmado" in html  # el mensaje sobrevive al iniciar sesión


def test_enlace_usado_o_falso_no_sirve(cliente, sim):
    post(cliente, "/registro", REGISTRO_OK)
    token = sim.ultimo_enlace("lucia@example.com", "email")
    post(cliente, "/auth/confirmar", {"token_hash": token, "type": "email"})
    post(cliente, "/cerrar-sesion")
    r = post(cliente, "/auth/confirmar", {"token_hash": token, "type": "email"}, follow_redirects=True)
    assert "expiró o ya se usó" in texto(r)
    r = post(cliente, "/auth/confirmar", {"token_hash": "x", "type": "magiclink"})
    assert r.status_code == 302 and "/iniciar-sesion" in r.location


def test_login_sin_confirmar_ofrece_reenviar(cliente, sim):
    post(cliente, "/registro", REGISTRO_OK)
    r = post(cliente, "/iniciar-sesion", {"correo": "lucia@example.com", "contrasena": CONTRASENA})
    assert "Primero confirma tu correo" in texto(r) and "Reenviar correo" in texto(r)
    antes = len(sim.correos)
    post(cliente, "/registro/reenviar", {"correo": "lucia@example.com"})
    assert len(sim.correos) == antes + 1


# --- Inicio de sesión ---------------------------------------------------------
def test_login_correcto_muestra_menu_de_usuario(cliente, sim):
    entrar(cliente, sim)
    html = texto(cliente.get("/cuenta"))
    assert "¡Hola de nuevo!" in html
    assert "Ana Prueba" in html and "Cerrar sesión" in html and "Crear cuenta" not in html
    with cliente.session_transaction() as s:
        assert s["usuario"]["tipo_cuenta"] == "adoptante" and s["tokens"]["access_token"]


def test_cookie_de_sesion_es_httponly(cliente, sim):
    sim.crear_usuario("ana@example.com", CONTRASENA)
    r = post(cliente, "/iniciar-sesion", {"correo": "ana@example.com", "contrasena": CONTRASENA})
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_contrasena_incorrecta_y_bloqueo_por_intentos(cliente, sim):
    sim.crear_usuario("ana@example.com", CONTRASENA)
    for _ in range(5):
        r = post(cliente, "/iniciar-sesion", {"correo": "ana@example.com", "contrasena": "incorrecta1"})
        assert "Correo o contraseña incorrectos" in texto(r)
    llamadas = len(peticiones(sim, "/auth/v1/token"))
    r = post(cliente, "/iniciar-sesion", {"correo": "ana@example.com", "contrasena": CONTRASENA})
    assert "Demasiados intentos" in texto(r)
    assert len(peticiones(sim, "/auth/v1/token")) == llamadas  # ni siquiera se consultó a Supabase


def test_paginas_privadas_piden_sesion_y_regresan(cliente, sim):
    r = cliente.get("/cuenta")
    assert r.status_code == 302 and "/iniciar-sesion?siguiente=/cuenta" in r.location
    sim.crear_usuario("ana@example.com", CONTRASENA)
    r = post(cliente, "/iniciar-sesion", {"correo": "ana@example.com", "contrasena": CONTRASENA,
                                          "siguiente": "/cuenta"})
    assert r.location.endswith("/cuenta")


@pytest.mark.parametrize("destino", ["//sitio-malo.com", "https://sitio-malo.com", "/\\sitio-malo.com"])
def test_no_redirige_a_otros_sitios(cliente, sim, destino):
    sim.crear_usuario("ana@example.com", CONTRASENA)
    r = post(cliente, "/iniciar-sesion", {"correo": "ana@example.com", "contrasena": CONTRASENA,
                                          "siguiente": destino})
    assert "sitio-malo" not in r.location


# --- Mi cuenta ----------------------------------------------------------------
def test_editar_perfil_usa_el_token_de_la_persona(cliente, sim):
    usuario_id = entrar(cliente, sim)
    r = post(cliente, "/cuenta", {"nombre_publico": "Ana  Nueva", "biografia": "Amo a los gatos",
                                  "municipio": "Tijuana", "telefono": "664 123-4567"})
    assert r.status_code == 302
    cambios = [p for p in sim.peticiones if p["metodo"] == "PATCH"]
    assert {p["ruta"] for p in cambios} == {"/rest/v1/perfiles", "/rest/v1/perfiles_privados"}
    assert all(p["token"] != CLAVE_PUBLICA for p in cambios)  # nunca como visitante
    assert set(cambios[0]["cuerpo"]) == {"nombre_publico", "biografia", "municipio"}
    assert sim.perfiles[usuario_id]["nombre_publico"] == "Ana Nueva"
    assert sim.privados[usuario_id]["telefono"] == "6641234567"
    assert "Ana Nueva" in texto(cliente.get("/cuenta"))


def test_editar_perfil_valida_telefono(cliente, sim):
    entrar(cliente, sim)
    r = post(cliente, "/cuenta", {"nombre_publico": "Ana", "telefono": "12345"})
    assert "10 a 15 dígitos" in texto(r)
    assert not [p for p in sim.peticiones if p["metodo"] == "PATCH"]


def test_cuenta_no_muestra_datos_de_otra_persona(cliente, sim):
    entrar(cliente, sim)
    sim.crear_usuario("beto@example.com", CONTRASENA, nombre="Beto Secreto")
    assert "Beto Secreto" not in texto(cliente.get("/cuenta"))


# --- CSRF y cierre de sesión --------------------------------------------------
def test_formularios_sin_codigo_csrf_se_rechazan(cliente, sim):
    sim.crear_usuario("ana@example.com", CONTRASENA)
    r = cliente.post("/iniciar-sesion", data={"correo": "ana@example.com", "contrasena": CONTRASENA})
    assert r.status_code == 400 and "El formulario expiró" in texto(r)
    r = cliente.post("/iniciar-sesion", data={"correo": "ana@example.com", "contrasena": CONTRASENA,
                                              "csrf_token": "inventado"})
    assert r.status_code == 400
    assert peticiones(sim, "/auth/v1/token") == []


def test_cerrar_sesion_revoca_en_supabase(cliente, sim):
    entrar(cliente, sim)
    assert cliente.get("/cerrar-sesion").status_code == 405  # solo con formulario (POST)
    r = post(cliente, "/cerrar-sesion")
    assert r.status_code == 302
    assert peticiones(sim, "/auth/v1/logout")
    with cliente.session_transaction() as s:
        assert "usuario" not in s and "tokens" not in s
    assert cliente.get("/cuenta").status_code == 302


# --- Renovación de tokens -----------------------------------------------------
def test_token_vencido_se_renueva_solo(cliente, sim):
    sim.dura_token = 30  # menos que el margen de 60 s: se renovará en la siguiente visita
    entrar(cliente, sim)
    with cliente.session_transaction() as s:
        anterior = s["tokens"]["refresh_token"]
    assert cliente.get("/cuenta").status_code == 200
    assert [p for p in peticiones(sim, "/auth/v1/token") if p["consulta"].get("grant_type") == "refresh_token"]
    with cliente.session_transaction() as s:
        assert s["tokens"]["refresh_token"] != anterior


def test_si_la_renovacion_falla_se_cierra_la_sesion(cliente, sim):
    sim.dura_token = 30
    entrar(cliente, sim)
    sim.refresh_tokens.clear()  # por ejemplo, la sesión se cerró en otro dispositivo
    r = cliente.get("/cuenta")
    assert r.status_code == 302 and "/iniciar-sesion" in r.location
    with cliente.session_transaction() as s:
        assert "usuario" not in s


# --- Recuperar contraseña -----------------------------------------------------
def test_recuperar_no_revela_si_la_cuenta_existe(cliente, sim):
    r = post(cliente, "/recuperar-contrasena", {"correo": "nadie@example.com"})
    assert "Si ese correo tiene una cuenta" in texto(r)
    assert sim.correos == []


def test_recuperar_contrasena_completo(cliente, sim):
    sim.crear_usuario("ana@example.com", CONTRASENA, nombre="Ana Prueba")
    post(cliente, "/recuperar-contrasena", {"correo": "ana@example.com"})
    token = sim.ultimo_enlace("ana@example.com", "recovery")
    r = post(cliente, "/auth/confirmar", {"token_hash": token, "type": "recovery"})
    assert r.location.endswith("/cuenta/nueva-contrasena")
    assert "Elige tu nueva contraseña" in texto(cliente.get("/cuenta/nueva-contrasena"))
    r = post(cliente, "/cuenta/nueva-contrasena", {"contrasena": "gatitos2027", "confirmar": "gatitos2027"})
    assert r.location.endswith("/cuenta")
    assert [p for p in peticiones(sim, "/auth/v1/user") if p["metodo"] == "PUT"][0]["cuerpo"]["password"] == "gatitos2027"
    post(cliente, "/cerrar-sesion")
    r = post(cliente, "/iniciar-sesion", {"correo": "ana@example.com", "contrasena": "gatitos2027"})
    assert r.status_code == 302


def test_nueva_contrasena_igual_a_la_anterior(cliente, sim):
    entrar(cliente, sim)
    r = post(cliente, "/cuenta/nueva-contrasena", {"contrasena": CONTRASENA, "confirmar": CONTRASENA})
    assert "distinta de la anterior" in texto(r)


# --- Permisos por rol ---------------------------------------------------------
def test_panel_solo_para_refugios_y_rescatistas(cliente, sim):
    entrar(cliente, sim, tipo="adoptante")
    r = cliente.get("/panel")
    assert r.status_code == 302 and r.location.endswith("/cuenta")
    post(cliente, "/cerrar-sesion")
    entrar(cliente, sim, correo="refugio@example.com", tipo="refugio", nombre="Refugio Prueba")
    assert cliente.get("/panel").status_code == 200
    assert "Mi panel" in texto(cliente.get("/cuenta"))


def test_admin_se_comprueba_en_la_base_de_datos_cada_vez(cliente, sim):
    usuario_id = entrar(cliente, sim)
    assert cliente.get("/admin").status_code == 404  # no revela que existe
    sim.administradores.add(usuario_id)
    assert cliente.get("/admin").status_code == 200
    sim.administradores.discard(usuario_id)  # se le quitó el permiso
    assert cliente.get("/admin").status_code == 404
    assert cliente.get("/admin").status_code == 404


def test_admin_sin_sesion_pide_iniciar_sesion(cliente, sim):
    r = cliente.get("/admin")
    assert r.status_code == 302 and "/iniciar-sesion" in r.location


# --- Perfil público -----------------------------------------------------------
def test_perfil_publico_no_muestra_datos_privados(cliente, sim):
    usuario_id = sim.crear_usuario("ana@example.com", CONTRASENA, nombre="Ana Prueba")
    sim.privados[usuario_id]["telefono"] = "6640001122"
    html = texto(cliente.get(f"/perfil/{usuario_id}"))
    assert "Ana Prueba" in html and "identidad no verificada" in html
    assert "6640001122" not in html and "ana@example.com" not in html
    assert cliente.get("/perfil/no-es-uuid").status_code == 404


def test_paginas_con_sesion_no_se_guardan_en_cache(cliente, sim):
    entrar(cliente, sim)
    assert cliente.get("/cuenta").headers.get("Cache-Control") == "no-store"


# --- Sin Supabase (modo de ejemplo) -------------------------------------------
def test_sin_supabase_las_cuentas_avisan_y_no_fallan():
    app.config.update(TESTING=True, SUPABASE_URL="", SUPABASE_CLAVE_PUBLICA="", SUPABASE_HTTPX_PRUEBAS=None)
    with app.test_client() as c:
        html = texto(c.get("/registro"))
        assert "Las cuentas necesitan Supabase" in html and "disabled" in html
        with c.session_transaction() as s:
            s["_csrf"] = "t"
        r = c.post("/registro", data={**REGISTRO_OK, "csrf_token": "t"})
        assert r.status_code == 302
        assert c.get("/cuenta").status_code == 302
        assert c.get("/perfil/3f1c2a4e-0000-4000-8000-000000000001").status_code == 404


def test_si_no_se_puede_leer_el_perfil_no_queda_sesion_a_medias(cliente, sim):
    post(cliente, "/registro", REGISTRO_OK)
    token = sim.ultimo_enlace("lucia@example.com", "email")
    sim.perfiles.clear()  # por ejemplo, la migración no se ejecutó bien
    r = post(cliente, "/auth/confirmar", {"token_hash": token, "type": "email"})
    assert r.status_code == 302 and "/iniciar-sesion" in r.location
    with cliente.session_transaction() as s:
        assert "usuario" not in s and "tokens" not in s
    assert peticiones(sim, "/auth/v1/logout")
