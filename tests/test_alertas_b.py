"""
Pruebas de Alerta Patitas, Parte B: emitir con foto, mi zona, "Lo vi",
cerrar y renovar, mis alertas y notificaciones.
Usa la librería real de Supabase conectada a tests/simulador_alertas.py.
"""
import io
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from services.alertas import ZONA_HORARIA  # noqa: E402
from services.seguridad import reiniciar_limites  # noqa: E402
from simulador_alertas import SimuladorConAlertas  # noqa: E402
from simulador_supabase import CLAVE_PUBLICA, URL  # noqa: E402

CONTRASENA = "perritos2026"
CENTRO = (32.5149, -117.0382)


@pytest.fixture
def sim():
    simulador = SimuladorConAlertas()
    app.config.update(TESTING=True, SUPABASE_URL=URL, SUPABASE_CLAVE_PUBLICA=CLAVE_PUBLICA,
                      SUPABASE_HTTPX_PRUEBAS=simulador.cliente_httpx())
    reiniciar_limites()
    yield simulador
    app.config.update(SUPABASE_URL="", SUPABASE_CLAVE_PUBLICA="", SUPABASE_HTTPX_PRUEBAS=None)


@pytest.fixture
def cliente(sim):
    with app.test_client() as c:
        yield c


def texto(r):
    return r.get_data(as_text=True)


def post(cliente, ruta, datos=None, **kwargs):
    with cliente.session_transaction() as s:
        s.setdefault("_csrf", "token-de-prueba")
        token = s["_csrf"]
    datos = dict(datos or {})
    datos.setdefault("csrf_token", token)
    return cliente.post(ruta, data=datos, **kwargs)


def entrar(cliente, sim, correo, nombre="Persona Prueba"):
    if correo not in sim.usuarios:
        sim.crear_usuario(correo, CONTRASENA, nombre=nombre)
    with cliente.session_transaction() as s:
        s.clear()
    r = post(cliente, "/iniciar-sesion", {"correo": correo, "contrasena": CONTRASENA})
    assert r.status_code == 302
    return sim.usuarios[correo]["id"]


def foto_con_gps():
    """JPEG de 3000x2000 con datos GPS ocultos, como una foto de celular."""
    exif = Image.Exif()
    exif[0x8825] = {2: (32.0, 31.0, 0.0), 1: "N"}
    salida = io.BytesIO()
    Image.new("RGB", (3000, 2000), (180, 120, 60)).save(salida, "JPEG", exif=exif)
    return salida.getvalue()


def hace(horas=1):
    return (datetime.now(timezone.utc) - timedelta(hours=horas)).astimezone(ZONA_HORARIA).strftime("%Y-%m-%dT%H:%M")


def formulario_alerta(**cambios):
    datos = {"nombre_mascota": "Chispa", "especie": "perro", "sexo": "hembra", "tamano": "pequeño",
             "edad_aproximada": "3 años", "raza": "", "color": "Café con blanco",
             "senas_particulares": "Oreja doblada", "collar": "", "descripcion": "Es miedosa",
             "zona_referencia": "Centro, Parque Teniente Guerrero", "visto_por_ultima_vez": hace(2),
             "latitud": str(CENTRO[0]), "longitud": str(CENTRO[1]), "mostrar_telefono": "si",
             "foto": (io.BytesIO(foto_con_gps()), "chispa.jpg")}
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not None}


def emitir(cliente, **cambios):
    return post(cliente, "/alertas/emitir", formulario_alerta(**cambios), content_type="multipart/form-data")


def preparar_vecinos(sim):
    """Zonas de alerta: una a 2 km, una a 20 km y una cercana que no acepta alertas."""
    cerca = sim.crear_usuario("vecina@example.com", CONTRASENA, nombre="Vecina Zona Río")
    lejos = sim.crear_usuario("lejos@example.com", CONTRASENA, nombre="Vecino Rosarito")
    no_quiere = sim.crear_usuario("noquiere@example.com", CONTRASENA, nombre="Sin Alertas")
    sim.zonas[cerca] = {"usuario_id": cerca, "latitud": 32.53, "longitud": -117.02, "acepta_alertas": True}
    sim.zonas[lejos] = {"usuario_id": lejos, "latitud": 32.34, "longitud": -117.06, "acepta_alertas": True}
    sim.zonas[no_quiere] = {"usuario_id": no_quiere, "latitud": 32.52, "longitud": -117.03, "acepta_alertas": False}
    return cerca, lejos, no_quiere


def alerta_emitida(cliente, sim, correo="duena@example.com"):
    duena = entrar(cliente, sim, correo, nombre="Dueña de Chispa")
    r = emitir(cliente)
    assert r.status_code == 302, texto(r)
    alerta_id = r.location.rsplit("/", 1)[-1]
    return duena, alerta_id


# --- Emitir -------------------------------------------------------------------
def test_sin_sesion_se_invita_a_iniciar_sesion(cliente, sim):
    html = texto(cliente.get("/alertas/emitir"))
    assert "Para emitir una alerta necesitas una cuenta" in html and "<fieldset disabled>" in html
    r = emitir(cliente)
    assert r.status_code == 302 and "/iniciar-sesion" in r.location
    assert not sim.alertas and not sim.archivos


def test_emitir_alerta_completa(cliente, sim):
    cerca, lejos, no_quiere = preparar_vecinos(sim)
    duena = entrar(cliente, sim, "duena@example.com", nombre="Dueña de Chispa")
    r = emitir(cliente)
    assert r.status_code == 302 and "/alerta/" in r.location

    # La foto se subió a la carpeta de la dueña, como persona (no como visitante)
    (ruta, datos), = sim.archivos.items()
    assert ruta.startswith(f"{duena}/") and ruta.endswith(".jpg")
    subida = [p for p in sim.peticiones if p["ruta"].startswith("/storage/v1/object/fotos-alertas/")][0]
    assert subida["token"] != CLAVE_PUBLICA

    # La foto guardada NO tiene datos ocultos (GPS) y se redujo
    guardada = Image.open(io.BytesIO(datos))
    assert len(guardada.getexif()) == 0 and max(guardada.size) == 1600

    # Se usó emitir_alerta() con el punto exacto
    llamada = [p for p in sim.peticiones if p["ruta"] == "/rest/v1/rpc/emitir_alerta"][0]
    assert llamada["cuerpo"]["p_latitud"] == CENTRO[0] and llamada["cuerpo"]["p_ruta_foto"] == ruta
    assert llamada["cuerpo"]["p_mostrar_telefono"] is True

    # Regla de 15 km: solo la vecina cercana que acepta alertas
    assert [n["usuario_id"] for n in sim.notificaciones] == [cerca]

    html = texto(cliente.get(r.location))
    assert "Avisamos a 1 persona a 15 km" in html
    assert "1</strong> persona a 15 km" in html  # sin "1 personas"
    assert "Tu alerta" in html and "Cerrar la alerta" in html
    assert f"/storage/v1/object/public/fotos-alertas/{ruta}" in html


@pytest.mark.parametrize("cambio,mensaje", [
    ({"foto": None}, "Sube una foto"),
    ({"foto": (io.BytesIO(b"no es imagen"), "x.jpg")}, "No pudimos leer la foto"),
    ({"latitud": "", "longitud": ""}, "Marca el lugar en el mapa"),
    ({"visto_por_ultima_vez": "2099-01-01T10:00"}, "no puede ser en el futuro"),
    ({"nombre_mascota": ""}, "Escribe el nombre de tu mascota"),
    ({"especie": "dragon"}, "Elige la especie"),
    ({"zona_referencia": "x"}, "entre 3 y 120"),
])
def test_emitir_valida_antes_de_subir_nada(cliente, sim, cambio, mensaje):
    entrar(cliente, sim, "duena@example.com")
    r = emitir(cliente, **cambio)
    assert r.status_code == 200 and mensaje in texto(r)
    assert not sim.archivos and not sim.alertas


def test_limite_de_alertas_borra_la_foto_sobrante(cliente, sim):
    entrar(cliente, sim, "duena@example.com")
    emitir(cliente)
    emitir(cliente, nombre_mascota="Bruno")
    r = emitir(cliente, nombre_mascota="Tercera")
    assert "Ya tienes 2 alertas activas" in texto(r)
    assert len(sim.alertas) == 2 and len(sim.archivos) == 2  # la foto de la tercera se borró


def test_el_formulario_conserva_lo_escrito_si_hay_error(cliente, sim):
    entrar(cliente, sim, "duena@example.com")
    html = texto(emitir(cliente, latitud="", longitud=""))
    assert 'value="Chispa"' in html and "Vuelve a elegir la foto" in html


# --- Detalle según quién lo ve ------------------------------------------------
def test_detalle_para_visitante_otra_persona_y_duena(cliente, sim):
    duena, alerta_id = alerta_emitida(cliente, sim)
    post(cliente, "/cerrar-sesion")
    html = texto(cliente.get(f"/alerta/{alerta_id}"))
    assert "Inicia sesión para avisar" in html and "Cerrar la alerta" not in html

    entrar(cliente, sim, "vecina@example.com")
    html = texto(cliente.get(f"/alerta/{alerta_id}"))
    assert "Enviar aviso a la familia" in html and "Cerrar la alerta" not in html and "Avistamientos (" not in html


def test_lo_vi_avisa_a_la_duena_y_solo_ella_lo_ve(cliente, sim):
    duena, alerta_id = alerta_emitida(cliente, sim)
    entrar(cliente, sim, "vecina@example.com", nombre="Vecina Zona Río")
    r = post(cliente, f"/alerta/{alerta_id}/lo-vi", {"lugar": "Esquina de la tiendita azul", "visto_en": hace(0),
                                                     "comentario": "Iba al parque", "latitud": "32.533", "longitud": "-117.036"})
    assert r.status_code == 302
    assert "Avisamos a la familia" in texto(cliente.get(r.location))
    assert sim.notificaciones[-1]["usuario_id"] == duena and sim.notificaciones[-1]["tipo"] == "avistamiento"

    entrar(cliente, sim, "otra@example.com")  # una tercera persona no ve la lista
    assert "tiendita azul" not in texto(cliente.get(f"/alerta/{alerta_id}"))

    entrar(cliente, sim, "duena@example.com")
    html = texto(cliente.get(f"/alerta/{alerta_id}"))
    assert "Avistamientos (1)" in html and "Esquina de la tiendita azul" in html and "Vecina Zona Río" in html
    assert "32.533" in html  # el punto llega al mapa de la dueña


def test_lo_vi_valida_y_la_duena_no_puede_reportarse(cliente, sim):
    duena, alerta_id = alerta_emitida(cliente, sim)
    r = post(cliente, f"/alerta/{alerta_id}/lo-vi", {"lugar": "Mi casa", "visto_en": hace(0)}, follow_redirects=True)
    assert "No tienes permiso" in texto(r)
    entrar(cliente, sim, "vecina@example.com")
    r = post(cliente, f"/alerta/{alerta_id}/lo-vi", {"lugar": "", "visto_en": hace(0)}, follow_redirects=True)
    assert "Escribe dónde lo viste" in texto(r)
    assert not sim.avistamientos


def test_lo_vi_requiere_sesion_y_csrf(cliente, sim):
    duena, alerta_id = alerta_emitida(cliente, sim)
    post(cliente, "/cerrar-sesion")
    r = post(cliente, f"/alerta/{alerta_id}/lo-vi", {"lugar": "Centro", "visto_en": hace(0)})
    assert r.status_code == 302 and "/iniciar-sesion" in r.location
    entrar(cliente, sim, "vecina@example.com")
    r = cliente.post(f"/alerta/{alerta_id}/lo-vi", data={"lugar": "Centro", "visto_en": hace(0)})
    assert r.status_code == 400
    assert not sim.avistamientos


# --- Teléfono -----------------------------------------------------------------
def test_telefono_solo_con_sesion_y_autorizacion(cliente, sim):
    duena, alerta_id = alerta_emitida(cliente, sim)
    sim.privados[duena]["telefono"] = "6640001122"
    post(cliente, "/cerrar-sesion")
    assert "6640001122" not in texto(cliente.get(f"/alerta/{alerta_id}"))
    entrar(cliente, sim, "vecina@example.com")
    assert "6640001122" in texto(cliente.get(f"/alerta/{alerta_id}"))
    sim.alertas[alerta_id]["mostrar_telefono"] = False
    html = texto(cliente.get(f"/alerta/{alerta_id}"))
    assert "6640001122" not in html and "prefiere recibir avisos por Patitas" in html


# --- Cerrar y renovar ---------------------------------------------------------
def test_marcar_encontrada_avisa_a_quienes_ayudaron(cliente, sim):
    cerca, _, _ = preparar_vecinos(sim)
    duena, alerta_id = alerta_emitida(cliente, sim)
    r = post(cliente, f"/alerta/{alerta_id}/cerrar", {"estado": "encontrada"}, follow_redirects=True)
    assert "Qué alegría" in texto(r) and "¡Ya está en casa!" in texto(r)
    assert [n["usuario_id"] for n in sim.notificaciones if n["tipo"] == "alerta_cerrada"] == [cerca]
    r = post(cliente, f"/alerta/{alerta_id}/cerrar", {"estado": "cancelada"}, follow_redirects=True)
    assert "ya está cerrada" in texto(r)


def test_otra_persona_no_puede_cerrar_ni_renovar(cliente, sim):
    duena, alerta_id = alerta_emitida(cliente, sim)
    entrar(cliente, sim, "vecina@example.com")
    r = post(cliente, f"/alerta/{alerta_id}/cerrar", {"estado": "encontrada"}, follow_redirects=True)
    assert "No encontramos esa alerta entre las tuyas" in texto(r)
    r = post(cliente, f"/alerta/{alerta_id}/renovar", follow_redirects=True)
    assert "No tienes permiso" in texto(r)
    assert sim.alertas[alerta_id]["estado"] == "activa"


def test_renovar_solo_cuando_faltan_7_dias(cliente, sim):
    duena, alerta_id = alerta_emitida(cliente, sim)
    assert "Renovar 30 días más" not in texto(cliente.get(f"/alerta/{alerta_id}"))
    r = post(cliente, f"/alerta/{alerta_id}/renovar", follow_redirects=True)
    assert "cuando falten 7 días o menos" in texto(r)
    sim.alertas[alerta_id]["expira_en"] = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    assert "Renovar 30 días más" in texto(cliente.get(f"/alerta/{alerta_id}"))
    r = post(cliente, f"/alerta/{alerta_id}/renovar", follow_redirects=True)
    assert "30 días más" in texto(r)


def test_mis_alertas_muestra_estados(cliente, sim):
    duena, alerta_id = alerta_emitida(cliente, sim)
    emitir(cliente, nombre_mascota="Bruno")
    post(cliente, f"/alerta/{alerta_id}/cerrar", {"estado": "encontrada"})
    html = texto(cliente.get("/mis-alertas"))
    assert "Chispa" in html and "Encontrada" in html and "Bruno" in html and "Activa" in html


# --- Mi zona de alertas -------------------------------------------------------
def test_guardar_cambiar_y_borrar_zona(cliente, sim):
    usuario = entrar(cliente, sim, "vecina@example.com")
    assert "Toca el mapa para marcar tu zona" in texto(cliente.get("/cuenta/zona-alertas"))
    r = post(cliente, "/cuenta/zona-alertas", {"latitud": "32.53412", "longitud": "-117.02189", "acepta_alertas": "si"})
    assert r.status_code == 302
    assert sim.zonas[usuario]["latitud"] == 32.53 and sim.zonas[usuario]["acepta_alertas"] is True
    post(cliente, "/cuenta/zona-alertas", {"latitud": "32.50", "longitud": "-117.00"})  # sin marcar la casilla
    assert sim.zonas[usuario]["acepta_alertas"] is False and sim.zonas[usuario]["longitud"] == -117.0
    cambios = [p for p in sim.peticiones if p["ruta"] == "/rest/v1/zonas_alerta" and p["metodo"] == "PATCH"]
    assert all("usuario_id" not in p["cuerpo"] for p in cambios)  # nunca intenta cambiar usuario_id
    post(cliente, "/cuenta/zona-alertas", {"accion": "borrar"})
    assert usuario not in sim.zonas


def test_zona_invalida_no_se_guarda(cliente, sim):
    usuario = entrar(cliente, sim, "vecina@example.com")
    r = post(cliente, "/cuenta/zona-alertas", {"latitud": "999", "longitud": "-117"})
    assert "no es válida" in texto(r) and usuario not in sim.zonas


def test_la_lista_muestra_la_distancia_a_mi_zona(cliente, sim):
    alerta_emitida(cliente, sim)
    usuario = entrar(cliente, sim, "vecina@example.com")
    sim.zonas[usuario] = {"usuario_id": usuario, "latitud": 32.53, "longitud": -117.02, "acepta_alertas": True}
    html = texto(cliente.get("/alertas"))
    assert "km de tu zona" in html and "Cambiar mi zona" in html


# --- Notificaciones -----------------------------------------------------------
def test_campana_y_notificaciones(cliente, sim):
    cerca, _, _ = preparar_vecinos(sim)
    alerta_emitida(cliente, sim)
    entrar(cliente, sim, "vecina@example.com")
    html = texto(cliente.get("/cuenta"))
    assert 'class="contador-campana">1<' in html
    html = texto(cliente.get("/notificaciones"))
    assert "Alerta Patitas: se busca a Chispa" in html and "Marcar todas como leídas" in html
    post(cliente, "/notificaciones/leidas")
    assert all(n["leida"] for n in sim.notificaciones if n["usuario_id"] == cerca)
    assert "contador-campana" not in texto(cliente.get("/cuenta"))


def test_paginas_privadas_de_alertas_piden_sesion(cliente, sim):
    for ruta in ["/mis-alertas", "/cuenta/zona-alertas", "/notificaciones"]:
        r = cliente.get(ruta)
        assert r.status_code == 302 and "/iniciar-sesion" in r.location
