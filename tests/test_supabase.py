"""
Pruebas de la conexión con Supabase SIN usar internet.
Se reemplaza el cliente real por uno falso que devuelve filas como las de la base de datos.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from services import animales as servicio  # noqa: E402
from services.supabase_cliente import es_clave_secreta  # noqa: E402

UUID_CANELA = "3f1c2a4e-0000-4000-8000-000000000001"

FILA_CANELA = {
    "id": UUID_CANELA, "nombre": "Canela", "especie": "perro", "raza": "No especificada",
    "edad_aproximada_meses": 24, "tamano": "mediano", "sexo": "hembra", "energia": "media",
    "personalidad": "Cariñosa.", "vacunado": True, "esterilizado": True,
    "zona": "Otay", "municipio": "Tijuana", "estado": "disponible", "publicado_en": "2026-11-01T00:00:00Z",
}
FILA_REFUGIO = {"id": "r1", "nombre": "Refugio BD", "descripcion": "Desde la base",
                "zona": "Otay", "municipio": "Tijuana", "estado_verificacion": "verificado"}


class ConsultaFalsa:
    """Imita la forma de usar el cliente: .table().select().eq()...execute().data"""

    def __init__(self, tabla, registro, error=None):
        self.tabla, self.registro, self.error = tabla, registro, error

    def __getattr__(self, nombre):  # select, eq, in_, order, limit…
        def metodo(*args, **kwargs):
            self.registro.append((self.tabla, nombre, args))
            return self
        return metodo

    def execute(self):
        if self.error:
            raise self.error
        datos = {"animales": [FILA_CANELA], "refugios": [FILA_REFUGIO]}[self.tabla]
        return type("Respuesta", (), {"data": datos})()


class ClienteFalso:
    def __init__(self, error=None):
        self.registro, self.error = [], error

    def table(self, nombre):
        return ConsultaFalsa(nombre, self.registro, self.error)


@pytest.fixture
def con_supabase(monkeypatch):
    app.config.update(TESTING=True, SUPABASE_URL="https://ejemplo.supabase.co",
                      SUPABASE_CLAVE_PUBLICA="sb_publishable_prueba")
    falso = ClienteFalso()
    monkeypatch.setattr(servicio, "obtener_cliente", lambda: falso)
    with app.test_client() as c:
        yield c, falso
    app.config.update(SUPABASE_URL="", SUPABASE_CLAVE_PUBLICA="")


# --- Claves -------------------------------------------------------------------
def test_detecta_clave_secreta_nueva():
    assert es_clave_secreta("sb_secret_abc123")
    assert not es_clave_secreta("sb_publishable_abc123")


def test_detecta_clave_secreta_antigua():
    # JWT con {"role":"service_role"} y otro con {"role":"anon"} (firmas falsas)
    secreta = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.firma"
    publica = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiJ9.firma"
    assert es_clave_secreta(secreta)
    assert not es_clave_secreta(publica)


# --- Conversión de datos ------------------------------------------------------
@pytest.mark.parametrize("meses,texto", [(None, "Edad desconocida"), (1, "1 mes"), (8, "8 meses"),
                                         (12, "1 año"), (30, "2 años")])
def test_texto_edad(meses, texto):
    assert servicio.texto_edad(meses) == texto


# --- Páginas con datos de Supabase -------------------------------------------
def test_catalogo_usa_supabase_y_filtros(con_supabase):
    cliente, falso = con_supabase
    html = cliente.get("/adoptar?especie=perro").get_data(as_text=True)
    assert "Canela" in html and "2 años" in html
    assert "Modo de ejemplo" not in html
    assert ("animales", "eq", ("especie", "perro")) in falso.registro
    estados = next(a for t, m, a in falso.registro if m == "in_")
    assert "perdido" not in estados[1]  # el catálogo nunca pide perdidos


def test_detalle_con_uuid(con_supabase):
    cliente, _ = con_supabase
    respuesta = cliente.get(f"/animal/{UUID_CANELA}")
    assert respuesta.status_code == 200
    assert "Canela" in respuesta.get_data(as_text=True)


def test_detalle_con_id_invalido_da_404_sin_consultar(con_supabase):
    cliente, falso = con_supabase
    assert cliente.get("/animal/no-es-uuid").status_code == 404
    assert falso.registro == []


def test_refugios_desde_supabase(con_supabase):
    cliente, _ = con_supabase
    html = cliente.get("/refugios").get_data(as_text=True)
    assert "Refugio BD" in html and "Refugio verificado</span>" in html


def test_error_de_conexion_muestra_pagina_amable(monkeypatch):
    app.config.update(TESTING=True, SUPABASE_URL="https://ejemplo.supabase.co",
                      SUPABASE_CLAVE_PUBLICA="sb_publishable_prueba")
    monkeypatch.setattr(servicio, "obtener_cliente", lambda: ClienteFalso(error=ConnectionError("sin red")))
    with app.test_client() as c:
        r = c.get("/adoptar")
    app.config.update(SUPABASE_URL="", SUPABASE_CLAVE_PUBLICA="")
    assert r.status_code == 503
    assert "No pudimos cargar la información" in r.get_data(as_text=True)
    assert "sin red" not in r.get_data(as_text=True)  # el detalle técnico no se muestra
