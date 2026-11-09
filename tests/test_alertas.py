"""
Pruebas de Alerta Patitas (páginas, fechas y lectura desde Supabase simulado).
La regla de 15 km y los permisos se prueban en tests/sql/30_pruebas_alertas.sql.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from services import alertas as servicio_alertas  # noqa: E402

UUID_ALERTA = "4a1c2a4e-0000-4000-8000-000000000001"
AHORA = datetime.now(timezone.utc)


def fila_alerta(**cambios):
    fila = {
        "id": UUID_ALERTA, "nombre_mascota": "Chispa BD", "especie": "perro", "raza": None,
        "sexo": "hembra", "tamano": "pequeño", "edad_aproximada": "3 años", "color": "café",
        "senas_particulares": "Oreja doblada", "collar": None, "descripcion": None, "ruta_foto": None,
        "zona_referencia": "Centro", "municipio": "Tijuana",
        "visto_por_ultima_vez": (AHORA - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
        "latitud_aprox": "32.51", "longitud_aprox": "-117.04", "mostrar_telefono": False,
        "estado": "activa", "creada_en": (AHORA - timedelta(hours=2)).isoformat(),
        "expira_en": (AHORA + timedelta(days=30)).isoformat(),
        "emisor": {"nombre_publico": "Dueña BD", "creado_en": "2026-04-02T10:00:00+00:00",
                   "nivel_verificacion": "registrada"},
    }
    fila.update(cambios)
    return fila


class ConsultaFalsa:
    def __init__(self, datos, registro):
        self.datos, self.registro = datos, registro

    def __getattr__(self, nombre):
        def metodo(*args, **kwargs):
            self.registro.append((nombre, args))
            return self
        return metodo

    def execute(self):
        return type("Respuesta", (), {"data": self.datos})()


class ClienteFalso:
    def __init__(self, filas, avisadas=0):
        self.filas, self.avisadas, self.registro = filas, avisadas, []

    def table(self, nombre):
        self.registro.append(("table", (nombre,)))
        return ConsultaFalsa(self.filas, self.registro)

    def rpc(self, nombre, parametros):
        self.registro.append(("rpc", (nombre, parametros)))
        return ConsultaFalsa(self.avisadas, self.registro)


@pytest.fixture
def modo_ejemplo():
    app.config.update(TESTING=True, SUPABASE_URL="", SUPABASE_CLAVE_PUBLICA="")
    with app.test_client() as c:
        yield c


@pytest.fixture
def con_supabase(monkeypatch):
    app.config.update(TESTING=True, SUPABASE_URL="https://ejemplo.supabase.co",
                      SUPABASE_CLAVE_PUBLICA="sb_publishable_prueba")
    falso = ClienteFalso([fila_alerta()], avisadas=12)
    monkeypatch.setattr(servicio_alertas, "obtener_cliente", lambda: falso)
    yield app.test_client(), falso
    app.config.update(SUPABASE_URL="", SUPABASE_CLAVE_PUBLICA="")


# --- Fechas -------------------------------------------------------------------
@pytest.mark.parametrize("delta,texto", [
    (timedelta(seconds=20), "hace un momento"), (timedelta(minutes=1), "hace 1 minuto"),
    (timedelta(minutes=45), "hace 45 minutos"), (timedelta(hours=3), "hace 3 horas"),
    (timedelta(days=1, hours=5), "hace 1 día"), (timedelta(days=12), "hace 12 días"),
])
def test_hace_tiempo(delta, texto):
    assert servicio_alertas.hace_tiempo(AHORA - delta, ahora=AHORA) == texto


def test_fecha_en_hora_de_tijuana():
    # 6 nov 2026 22:30 UTC = 14:30 en Tijuana (UTC-8)
    assert servicio_alertas.fecha_local(datetime(2026, 11, 6, 22, 30, tzinfo=timezone.utc)) == "6 nov 2026, 14:30"


def test_lee_fechas_de_supabase_con_z():
    assert servicio_alertas.a_fecha("2026-11-06T10:00:00Z").tzinfo is not None


# --- Modo de ejemplo ----------------------------------------------------------
@pytest.mark.parametrize("ruta", ["/alertas", "/alertas/emitir", "/alerta/ejemplo-chispa", "/alerta/ejemplo-bruno"])
def test_paginas_de_alertas_cargan(modo_ejemplo, ruta):
    assert modo_ejemplo.get(ruta).status_code == 200


def test_alerta_inexistente_da_404(modo_ejemplo):
    assert modo_ejemplo.get("/alerta/no-existe").status_code == 404


def test_inicio_muestra_banda_de_alertas(modo_ejemplo):
    html = modo_ejemplo.get("/").get_data(as_text=True)
    assert "Se busca a" in html and "Chispa" in html


def test_detalle_muestra_rasgos_y_seguridad(modo_ejemplo):
    html = modo_ejemplo.get("/alerta/ejemplo-chispa").get_data(as_text=True)
    for texto in ["Oreja izquierda doblada", "Collar rosa", "Mariana (ejemplo)", "148", "estafa",
                  "Zona aproximada", 'data-radio-km="15"']:
        assert texto in html


def test_telefono_nunca_aparece_en_la_pagina(modo_ejemplo):
    # Aunque la familia lo autorice, el número solo se pedirá con sesión iniciada (Etapa 3).
    html = modo_ejemplo.get("/alerta/ejemplo-chispa").get_data(as_text=True)
    assert "Inicia sesión para ver el teléfono" in html
    html_bruno = modo_ejemplo.get("/alerta/ejemplo-bruno").get_data(as_text=True)
    assert "Inicia sesión para ver el teléfono" not in html_bruno
    assert "prefiere recibir avisos por Patitas" in html_bruno


def test_vencidas_no_se_listan(modo_ejemplo, monkeypatch):
    vencida = dict(servicio_alertas.datos_ejemplo.ALERTAS[0], id="vencida", nombre="Vencida",
                   expira_en=AHORA - timedelta(days=1))
    monkeypatch.setattr(servicio_alertas.datos_ejemplo, "ALERTAS", [vencida])
    assert "Vencida" not in modo_ejemplo.get("/alertas").get_data(as_text=True)


# --- Con Supabase (simulado) --------------------------------------------------
def test_lista_pide_solo_activas_y_sin_vencer(con_supabase):
    cliente, falso = con_supabase
    html = cliente.get("/alertas").get_data(as_text=True)
    assert "Chispa BD" in html
    assert ("eq", ("estado", "activa")) in falso.registro
    filtro = next(a for m, a in falso.registro if m == "gt")
    assert filtro[0] == "expira_en" and filtro[1].endswith("Z") and "+" not in filtro[1]


def test_detalle_desde_supabase(con_supabase):
    cliente, falso = con_supabase
    html = cliente.get(f"/alerta/{UUID_ALERTA}").get_data(as_text=True)
    assert "Chispa BD" in html and "Dueña BD" in html and "No especificada" in html
    assert "Se avisó a <strong>12</strong>" in html
    assert ("rpc", ("personas_avisadas", {"id_alerta": UUID_ALERTA})) in falso.registro


def test_id_invalido_no_consulta_la_base(con_supabase):
    cliente, falso = con_supabase
    assert cliente.get("/alerta/no-es-uuid").status_code == 404
    assert falso.registro == []


def test_alerta_encontrada_no_pide_avistamientos(con_supabase, monkeypatch):
    cliente, _ = con_supabase
    falso = ClienteFalso([fila_alerta(estado="encontrada")])
    monkeypatch.setattr(servicio_alertas, "obtener_cliente", lambda: falso)
    html = cliente.get(f"/alerta/{UUID_ALERTA}").get_data(as_text=True)
    assert "¡Ya está en casa!" in html
    assert "Lo vi" not in html
