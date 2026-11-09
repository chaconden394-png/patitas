"""
Pruebas de las páginas en MODO DE EJEMPLO (sin Supabase).
Ejecutar desde la carpeta del proyecto con:  python -m pytest -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402


@pytest.fixture
def cliente():
    # Forzamos el modo de ejemplo aunque tu .env tenga Supabase configurado,
    # para que estas pruebas no dependan de internet.
    app.config.update(TESTING=True, SUPABASE_URL="", SUPABASE_CLAVE_PUBLICA="")
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("ruta", [
    "/", "/adoptar", "/perdidos-y-encontrados", "/refugios", "/comunidad",
    "/acerca", "/iniciar-sesion", "/registro", "/privacidad", "/animal/1",
])
def test_paginas_cargan(cliente, ruta):
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 200
    assert "Patitas" in respuesta.get_data(as_text=True)


def test_aviso_modo_ejemplo(cliente):
    assert "Modo de ejemplo" in cliente.get("/").get_data(as_text=True)


def test_pagina_inexistente_da_404(cliente):
    assert cliente.get("/no-existe").status_code == 404
    assert cliente.get("/animal/9999").status_code == 404


def test_catalogo_no_mezcla_perdidos(cliente):
    html = cliente.get("/adoptar").get_data(as_text=True)
    assert "Pelusa" not in html  # está perdida, no en adopción
    assert "Canela" in html


def test_perdidos_solo_muestra_perdidos_y_encontrados(cliente):
    html = cliente.get("/perdidos-y-encontrados").get_data(as_text=True)
    assert "Pelusa" in html
    assert "Canela" not in html


def test_filtro_especie(cliente):
    html = cliente.get("/adoptar?especie=gato").get_data(as_text=True)
    assert "Michi" in html
    assert "Canela" not in html


def test_filtro_invalido_se_ignora(cliente):
    html = cliente.get("/adoptar?especie=<script>alert(1)</script>").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "Canela" in html  # muestra todo, como si no hubiera filtro


def test_refugio_no_verificado_no_muestra_insignia(cliente):
    html = cliente.get("/refugios").get_data(as_text=True)
    assert "Pendiente de verificación" in html
    assert html.count("Refugio verificado</span>") == 1  # solo el refugio de ejemplo aprobado


def test_cabeceras_de_seguridad(cliente):
    r = cliente.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "SAMEORIGIN"
