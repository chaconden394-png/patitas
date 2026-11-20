"""
Pruebas de la Etapa 4: publicar animales, fotos (máx. 3), estados, borrar,
mi refugio, insignia "Sin verificar", filtros nuevos y páginas del catálogo.
Usa la librería real de Supabase conectada a tests/simulador_animales.py.
"""
import io
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from services.animales_panel import MENSAJE_SIN_PERMISO  # noqa: E402
from services.seguridad import reiniciar_limites  # noqa: E402
from simulador_animales import SimuladorConAnimales  # noqa: E402
from simulador_supabase import CLAVE_PUBLICA, URL  # noqa: E402

CONTRASENA = "perritos2026"


@pytest.fixture
def sim():
    simulador = SimuladorConAnimales()
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


def entrar(cliente, sim, correo, tipo="rescatista", nombre="Rescatista Prueba"):
    if correo not in sim.usuarios:
        sim.crear_usuario(correo, CONTRASENA, nombre=nombre, tipo=tipo)
    with cliente.session_transaction() as s:
        s.clear()
    r = post(cliente, "/iniciar-sesion", {"correo": correo, "contrasena": CONTRASENA})
    assert r.status_code == 302
    return sim.usuarios[correo]["id"]


def foto(color=(180, 120, 60), tamano=(3000, 2000), gps=True):
    """JPEG grande con datos GPS ocultos, como una foto de celular."""
    exif = Image.Exif()
    if gps:
        exif[0x8825] = {2: (32.0, 31.0, 0.0), 1: "N"}
    salida = io.BytesIO()
    Image.new("RGB", tamano, color).save(salida, "JPEG", exif=exif)
    return salida.getvalue()


def formulario(**cambios):
    datos = {"nombre": "Canela", "especie": "perro", "sexo": "hembra", "tamano": "mediano", "energia": "media",
             "raza": "", "edad_anios": "2", "edad_meses": "3", "personalidad": "Cariñosa.\nLe encanta la playa.",
             "convive_ninos": "si", "convive_perros": "si", "convive_gatos": "no", "vacunado": "si",
             "esterilizado": "si", "enfermedades_conocidas": "", "necesidades_especiales": "",
             "requisitos_adopcion": "Visita previa", "zona": "Playas de Tijuana", "estado": "disponible"}
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not None}


def publicar(cliente, **cambios):
    return post(cliente, "/panel/animales/nuevo", formulario(**cambios))


def publicado(cliente, sim, correo="resc@example.com", **cambios):
    yo = entrar(cliente, sim, correo)
    r = publicar(cliente, **cambios)
    assert r.status_code == 302, texto(r)
    animal_id = r.location.split("/panel/animal/")[1].split("/")[0]
    return yo, animal_id


def subir(cliente, animal_id, *fotos_bytes):
    archivos = [(io.BytesIO(b), f"foto{i}.jpg") for i, b in enumerate(fotos_bytes)]
    return post(cliente, f"/panel/animal/{animal_id}/fotos", {"fotos": archivos},
                content_type="multipart/form-data", follow_redirects=True)


# --- Acceso al panel ------------------------------------------------------------
def test_panel_solo_para_refugios_y_rescatistas(cliente, sim):
    assert "/iniciar-sesion" in cliente.get("/panel/animales").location
    entrar(cliente, sim, "adopta@example.com", tipo="adoptante")
    for ruta in ("/panel", "/panel/animales", "/panel/animales/nuevo"):
        r = cliente.get(ruta)
        assert r.status_code == 302 and r.location.endswith("/cuenta")
    r = publicar(cliente)
    assert r.status_code == 302 and not sim.animales


def test_mi_refugio_solo_para_cuentas_de_refugio(cliente, sim):
    entrar(cliente, sim, "resc@example.com")
    assert cliente.get("/panel/mi-refugio").status_code == 302
    assert "Mi refugio" not in texto(cliente.get("/panel"))


# --- Publicar ---------------------------------------------------------------------
def test_publicar_animal_completo(cliente, sim):
    yo, animal_id = publicado(cliente, sim)
    a = sim.animales[animal_id]
    assert a["responsable_id"] == yo and a["nombre"] == "Canela" and a["edad_aproximada_meses"] == 27
    assert a["convive_ninos"] is True and a["convive_gatos"] is False and a["vacunado"] is True
    assert a["raza"] == "No especificada" and a["energia"] == "media"
    assert a["personalidad"] == "Cariñosa.\nLe encanta la playa."   # conserva el salto de línea
    # Se guardó con el token de la persona (RLS), no como visitante
    alta = [p for p in sim.peticiones if p["ruta"] == "/rest/v1/animales" and p["metodo"] == "POST"][0]
    assert alta["token"] != CLAVE_PUBLICA
    html = texto(cliente.get(f"/panel/animal/{animal_id}/fotos"))
    assert "Ya está publicado" in html or "ya está publicado" in html
    assert "puedes subir 3 más" in html


@pytest.mark.parametrize("cambio,mensaje", [
    ({"nombre": ""}, "Escribe el nombre"),
    ({"especie": "dragon"}, "Elige la especie"),
    ({"sexo": ""}, "Elige el sexo"),
    ({"edad_anios": "", "edad_meses": ""}, "No sé su edad"),
    ({"edad_meses": "14"}, "entre 0 y 11"),
    ({"zona": "x"}, "entre 3 y 80"),
    ({"estado": "perdido"}, "Elige el estado"),           # los perdidos van en Alerta Patitas
    ({"convive_ninos": "tal vez"}, "convivencia"),
    ({"personalidad": "a" * 1001}, "máximo 1000"),
    ({"refugio_id": "00000000-0000-4000-8000-000000000000"}, "Elige uno de tus refugios"),
])
def test_publicar_valida_los_datos(cliente, sim, cambio, mensaje):
    entrar(cliente, sim, "resc@example.com")
    r = publicar(cliente, **cambio)
    assert r.status_code == 200 and mensaje in texto(r)
    assert not sim.animales
    # Lo que ya escribió no se pierde
    if "nombre" not in cambio:
        assert 'value="Canela"' in texto(r)


def test_edad_desconocida(cliente, sim):
    _, animal_id = publicado(cliente, sim, edad_desconocida="si", edad_anios="", edad_meses="")
    assert sim.animales[animal_id]["edad_aproximada_meses"] is None
    assert "Edad desconocida" in texto(cliente.get(f"/animal/{animal_id}"))


def test_cuenta_bloqueada_no_publica(cliente, sim):
    yo = entrar(cliente, sim, "bloq@example.com")
    sim.bloqueados.add(yo)
    r = publicar(cliente)
    assert r.status_code == 200 and MENSAJE_SIN_PERMISO in texto(r)
    assert not sim.animales


def test_limite_de_10_animales_al_dia(cliente, sim):
    entrar(cliente, sim, "muchos@example.com")
    for i in range(10):
        assert publicar(cliente, nombre=f"Cachorro {i}").status_code == 302
    r = publicar(cliente, nombre="Once")
    assert "límite de 10 animales" in texto(r)
    assert len(sim.animales) == 10


# --- Fotos ----------------------------------------------------------------------
def test_fotos_se_limpian_y_suben_a_mi_carpeta(cliente, sim):
    yo, animal_id = publicado(cliente, sim)
    r = subir(cliente, animal_id, foto(), foto((20, 120, 60)))
    assert "2 fotos guardadas" in texto(r)
    assert len(sim.archivos_animales) == 2
    for ruta, datos in sim.archivos_animales.items():
        assert ruta.startswith(f"{yo}/") and ruta.endswith(".jpg")
        guardada = Image.open(io.BytesIO(datos))
        assert len(guardada.getexif()) == 0 and max(guardada.size) == 1600   # sin GPS y reducida
    ordenes = sorted(f["orden"] for f in sim.fotos_animales.values())
    assert ordenes == [0, 1]
    assert "puedes subir 1 más" in texto(r)


def test_maximo_3_fotos(cliente, sim):
    _, animal_id = publicado(cliente, sim)
    subir(cliente, animal_id, foto(), foto())
    r = subir(cliente, animal_id, foto(), foto())
    assert "máximo 3 fotos" in texto(r) and "Puedes subir 1 más" in texto(r)
    assert len(sim.archivos_animales) == 2    # no se subió ninguna de las dos
    r = subir(cliente, animal_id, foto())
    assert "Foto guardada" in texto(r) and "Ya tiene 3 fotos" in texto(r)
    assert len(sim.fotos_animales) == 3


def test_foto_invalida_no_sube_nada(cliente, sim):
    _, animal_id = publicado(cliente, sim)
    archivos = [(io.BytesIO(foto()), "buena.jpg"), (io.BytesIO(b"no es imagen"), "mala.jpg")]
    r = post(cliente, f"/panel/animal/{animal_id}/fotos", {"fotos": archivos},
             content_type="multipart/form-data", follow_redirects=True)
    assert "No pudimos leer la foto" in texto(r)
    assert not sim.archivos_animales and not sim.fotos_animales


def test_si_falla_el_registro_se_borra_el_archivo(cliente, sim):
    _, animal_id = publicado(cliente, sim)
    sim.rechazar_fotos = True                      # la base de datos rechaza el registro de la foto
    r = subir(cliente, animal_id, foto())
    assert "máximo 3 fotos" in texto(r)
    subidas = [p for p in sim.peticiones if p["ruta"].startswith("/storage/v1/object/fotos-animales/")]
    assert len(subidas) == 1                       # el archivo sí llegó a subirse…
    assert not sim.archivos_animales               # …pero se borró para no dejarlo suelto


def test_foto_principal_galeria_y_borrar(cliente, sim):
    _, animal_id = publicado(cliente, sim)
    subir(cliente, animal_id, foto((200, 0, 0), (800, 600)), foto((0, 200, 0), (800, 600)))
    primera, segunda = sorted(sim.fotos_animales.values(), key=lambda f: f["orden"])

    # La ficha pública muestra la principal en grande y las miniaturas
    html = texto(cliente.get(f"/animal/{animal_id}"))
    assert f'id="foto-grande" src="{URL}/storage/v1/object/public/fotos-animales/{primera["ruta_archivo"]}"' in html
    assert html.count('data-galeria="foto-grande"') == 2

    r = post(cliente, f"/panel/animal/{animal_id}/foto/{segunda['id']}/principal", follow_redirects=True)
    assert "foto principal" in texto(r)
    assert sim.fotos_animales[segunda["id"]]["orden"] == 0 and sim.fotos_animales[primera["id"]]["orden"] == 1
    html = texto(cliente.get("/adoptar"))
    assert f'fotos-animales/{segunda["ruta_archivo"]}' in html          # la tarjeta usa la principal

    r = post(cliente, f"/panel/animal/{animal_id}/foto/{segunda['id']}/borrar", follow_redirects=True)
    assert "Foto borrada" in texto(r)
    assert segunda["id"] not in sim.fotos_animales and segunda["ruta_archivo"] not in sim.archivos_animales
    assert primera["ruta_archivo"] in sim.archivos_animales


# --- Editar, estado, borrar ---------------------------------------------------------
def test_editar_muestra_los_datos_y_guarda(cliente, sim):
    _, animal_id = publicado(cliente, sim)
    html = texto(cliente.get(f"/panel/animal/{animal_id}/editar"))
    assert 'value="Canela"' in html and 'name="edad_anios" class="form-control" inputmode="numeric" maxlength="2" placeholder="2"\n                 value="2"' in html
    r = post(cliente, f"/panel/animal/{animal_id}/editar", formulario(nombre="Canelita", estado="urgente"))
    assert r.status_code == 302
    assert sim.animales[animal_id]["nombre"] == "Canelita" and sim.animales[animal_id]["estado"] == "urgente"


def test_cambiar_estado_a_adoptado(cliente, sim):
    _, animal_id = publicado(cliente, sim)
    assert "Canela" in texto(cliente.get("/adoptar"))
    r = post(cliente, f"/panel/animal/{animal_id}/estado", {"estado": "adoptado"}, follow_redirects=True)
    assert "adoptado" in texto(r)
    assert sim.animales[animal_id]["estado"] == "adoptado"
    assert "Canela" not in texto(cliente.get("/adoptar"))           # ya no aparece en el catálogo
    assert "ya encontró hogar" in texto(cliente.get(f"/animal/{animal_id}"))
    r = post(cliente, f"/panel/animal/{animal_id}/estado", {"estado": "perdido"}, follow_redirects=True)
    assert "Elige un estado válido" in texto(r)


def test_nadie_toca_animales_ajenos(cliente, sim):
    _, animal_id = publicado(cliente, sim, correo="duena@example.com")
    entrar(cliente, sim, "otra@example.com")
    assert cliente.get(f"/panel/animal/{animal_id}/editar").status_code == 404
    assert cliente.get(f"/panel/animal/{animal_id}/fotos").status_code == 404
    for ruta, datos in [("editar", formulario(nombre="Robado")), ("estado", {"estado": "adoptado"}), ("borrar", {})]:
        post(cliente, f"/panel/animal/{animal_id}/{ruta}", datos)
    subir(cliente, animal_id, foto())
    a = sim.animales[animal_id]
    assert a["nombre"] == "Canela" and a["estado"] == "disponible"
    assert not sim.archivos_animales and not sim.fotos_animales


def test_borrar_animal_borra_sus_fotos(cliente, sim):
    _, animal_id = publicado(cliente, sim)
    subir(cliente, animal_id, foto(), foto())
    r = post(cliente, f"/panel/animal/{animal_id}/borrar", follow_redirects=True)
    assert "Borramos la publicación de Canela" in texto(r)
    assert not sim.animales and not sim.fotos_animales and not sim.archivos_animales


def test_mis_animales_lista_y_avisa_sin_fotos(cliente, sim):
    _, animal_id = publicado(cliente, sim)
    html = texto(cliente.get("/panel/animales"))
    assert "Canela" in html and "0 de 3 fotos" in html and "agrega al menos una" in html
    assert 'data-confirmar="¿Borrar la publicación de Canela' in html
    html = texto(cliente.get("/panel"))
    assert "Buscan hogar" in html and "Canela" in html


# --- Ficha pública: verificación ---------------------------------------------------
def test_animal_de_rescatista_sin_verificar(cliente, sim):
    yo, animal_id = publicado(cliente, sim)
    html = texto(cliente.get(f"/animal/{animal_id}"))
    assert "Sin verificar" in html and "nunca pages por adelantado" in html
    assert f"/perfil/{yo}" in html and "Rescatista Prueba" in html
    assert "Niñas y niños: sí" in html and "Gatos: no" in html
    assert "Le encanta la playa" in html and "Visita previa" in html
    assert "Sin verificar" in texto(cliente.get("/adoptar"))
    # Cuando el equipo de Patitas la habilita, cambia la insignia
    sim.perfiles[yo]["nivel_verificacion"] = "habilitada"
    html = texto(cliente.get(f"/animal/{animal_id}"))
    assert "Publicado por cuenta verificada" in html and "Sin verificar" not in html


def test_animal_oculto_no_se_ve(cliente, sim):
    _, animal_id = publicado(cliente, sim)
    sim.animales[animal_id]["oculto"] = True
    assert "Oculto por moderación" in texto(cliente.get("/panel/animales"))    # su dueña sí lo ve
    with cliente.session_transaction() as s:
        s.clear()
    assert cliente.get(f"/animal/{animal_id}").status_code == 404
    assert "Canela" not in texto(cliente.get("/adoptar"))


# --- Mi refugio -----------------------------------------------------------------------
def test_registrar_refugio_y_publicar_a_su_nombre(cliente, sim):
    yo = entrar(cliente, sim, "huellitas@example.com", tipo="refugio", nombre="Huellitas TJ")
    assert "Registra los datos de tu refugio" in texto(cliente.get("/panel"))
    r = post(cliente, "/panel/mi-refugio", {"nombre": "Refugio Huellitas", "descripcion": "Rescatamos perros.",
                                            "zona": "Otay", "telefono_publico": "664 000 0000",
                                            "correo_publico": "", "direccion": "Calle Ficticia 123, Otay"},
             follow_redirects=True)
    assert "Pendiente de verificación" in texto(r)
    (refugio,) = sim.refugios.values()
    assert refugio["responsable_id"] == yo and refugio["estado_verificacion"] == "pendiente"
    assert refugio["telefono_publico"] == "6640000000"
    assert sim.ubicaciones_refugio[refugio["id"]]["direccion"] == "Calle Ficticia 123, Otay"

    # La dirección nunca aparece en páginas públicas
    html = texto(cliente.get("/refugios"))
    assert "Refugio Huellitas" in html and "Calle Ficticia" not in html

    # Publicar a nombre del refugio (está preseleccionado por ser el único)
    form = texto(cliente.get("/panel/animales/nuevo"))
    assert "Refugio Huellitas (pendiente de verificación)" in form and f'value="{refugio["id"]}" selected' in form
    r = publicar(cliente, refugio_id=refugio["id"])
    animal_id = r.location.split("/panel/animal/")[1].split("/")[0]
    html = texto(cliente.get(f"/animal/{animal_id}"))
    assert "Refugio Huellitas" in html and "Sin verificar" in html and "Calle Ficticia" not in html

    # El equipo aprueba el refugio (a mano, en el editor SQL)
    refugio["estado_verificacion"] = "verificado"
    assert "Publicado por cuenta verificada" in texto(cliente.get(f"/animal/{animal_id}"))


def test_editar_refugio_y_validaciones(cliente, sim):
    yo = entrar(cliente, sim, "ref@example.com", tipo="refugio", nombre="Refugio Prueba")
    r = post(cliente, "/panel/mi-refugio", {"nombre": "R", "zona": "Otay"})
    assert "entre 3 y 100" in texto(r) and not sim.refugios
    r = post(cliente, "/panel/mi-refugio", {"nombre": "Refugio Gatitos", "zona": "Otay", "telefono_publico": "123"})
    assert "10 a 15 dígitos" in texto(r)
    post(cliente, "/panel/mi-refugio", {"nombre": "Refugio Gatitos", "zona": "Otay", "direccion": "Calle Uno 1"})
    post(cliente, "/panel/mi-refugio", {"nombre": "Refugio Gatitos de la Mesa", "zona": "La Mesa", "direccion": "Calle Dos 2"})
    (refugio,) = sim.refugios.values()          # se actualizó, no se creó otro
    assert refugio["nombre"] == "Refugio Gatitos de la Mesa"
    assert sim.ubicaciones_refugio[refugio["id"]]["direccion"] == "Calle Dos 2"
    html = texto(cliente.get("/panel/mi-refugio"))
    assert 'value="Calle Dos 2"' in html and refugio["responsable_id"] == yo


def test_refugio_rechazado_no_se_puede_usar(cliente, sim):
    yo = entrar(cliente, sim, "ref@example.com", tipo="refugio")
    rechazado = sim.crear_refugio(yo, "Refugio Rechazado", "rechazado")
    form = texto(cliente.get("/panel/animales/nuevo"))
    assert "Refugio Rechazado" not in form
    r = publicar(cliente, refugio_id=rechazado)
    assert "Elige uno de tus refugios" in texto(r)
    assert "No aprobado" in texto(cliente.get("/panel/mi-refugio"))


# --- Catálogo: filtros y páginas ---------------------------------------------------------
def test_catalogo_filtros_nuevos_con_supabase(cliente, sim):
    entrar(cliente, sim, "resc@example.com")
    publicar(cliente, nombre="Bebé", edad_anios="0", edad_meses="5", vacunado=None, convive_ninos="")
    publicar(cliente, nombre="Abuelo", edad_anios="10", edad_meses="0", convive_ninos="si")
    publicar(cliente, nombre="Joven", edad_anios="1", edad_meses="6", convive_ninos="no")
    def nombres(url):
        html = texto(cliente.get(url))
        return {n for n in ("Bebé", "Abuelo", "Joven") if f">{n}</h3>" in html}
    assert nombres("/adoptar?edad=cachorro") == {"Bebé"}
    assert nombres("/adoptar?edad=mayor") == {"Abuelo"}
    assert nombres("/adoptar?edad=joven") == {"Joven"}
    assert nombres("/adoptar?vacunado=si") == {"Abuelo", "Joven"}
    assert nombres("/adoptar?convive_ninos=si") == {"Abuelo"}      # "no se sabe" no cuenta como sí
    assert nombres("/adoptar?edad=inventada&vacunado=quizas") == {"Bebé", "Abuelo", "Joven"}


def test_catalogo_por_paginas(cliente, sim):
    for correo in ("uno@example.com", "dos@example.com"):
        entrar(cliente, sim, correo)
        for i in range(7):
            publicar(cliente, nombre=f"{correo[:3]}{i}")
    assert len(sim.animales) == 14
    html = texto(cliente.get("/adoptar"))
    assert "14 resultados · página 1 de 2" in html and html.count('class="tarjeta tarjeta-animal') == 12
    html = texto(cliente.get("/adoptar?pagina=2"))
    assert html.count('class="tarjeta tarjeta-animal') == 2
    r = cliente.get("/adoptar?pagina=9&especie=perro")
    assert r.status_code == 302 and "pagina=2" in r.location and "especie=perro" in r.location
    assert cliente.get("/adoptar?pagina=abc").status_code == 200


def test_catalogo_en_modo_de_ejemplo():
    app.config.update(TESTING=True, SUPABASE_URL="", SUPABASE_CLAVE_PUBLICA="")
    with app.test_client() as c:
        html = texto(c.get("/adoptar?edad=cachorro"))
        assert "Michi" in html and "Canela" not in html
        html = texto(c.get("/adoptar?convive_gatos=si"))
        assert "Michi" in html and "Canela" not in html
        assert "Sin verificar" not in texto(c.get("/adoptar"))   # los ejemplos no llevan sello
        assert c.get("/animal/1").status_code == 200
