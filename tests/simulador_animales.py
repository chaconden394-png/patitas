"""
Simulador de Supabase para la Etapa 4 (animales y fotos). SOLO PARA PRUEBAS.

Amplía SimuladorConAlertas con: animales, fotos de animales (tabla y Storage),
refugios y su dirección privada. Imita de forma simplificada las reglas de la
migración 005; las reglas reales se prueban en tests/sql/60_pruebas_animales.sql.

Además revisa que cada columna pedida en "select" exista, así un error de
escritura en la app (una columna o relación que no existe) hace fallar la prueba,
igual que fallaría en Supabase.
"""
import uuid
from urllib.parse import parse_qsl, urlparse
from datetime import datetime, timedelta, timezone

import httpx

from simulador_alertas import SimuladorConAlertas
from simulador_supabase import leer_jwt

COLUMNAS = {
    "animales": {"id", "responsable_id", "refugio_id", "nombre", "especie", "raza", "edad_aproximada_meses",
                 "tamano", "sexo", "energia", "personalidad", "convive_ninos", "convive_perros", "convive_gatos",
                 "vacunado", "esterilizado", "enfermedades_conocidas", "necesidades_especiales",
                 "requisitos_adopcion", "zona", "municipio", "latitud_aprox", "longitud_aprox", "estado",
                 "oculto", "publicado_en", "actualizado_en"},
    "animales_fotos": {"id", "animal_id", "ruta_archivo", "orden", "creado_en"},
    "perfiles": {"id", "nombre_publico", "tipo_cuenta", "nivel_verificacion", "biografia", "municipio",
                 "creado_en", "actualizado_en"},
    "refugios": {"id", "responsable_id", "nombre", "descripcion", "zona", "municipio", "telefono_publico",
                 "correo_publico", "redes_sociales", "estado_verificacion", "verificado_en", "creado_en",
                 "actualizado_en"},
    "refugios_ubicacion": {"refugio_id", "direccion", "latitud", "longitud", "actualizado_en"},
}
# Relaciones que se pueden incrustar desde "animales" (como las llaves foráneas reales)
RELACIONES = {
    ("animales", "animales_fotos"): "hijos",
    ("animales", "perfiles"): "responsable_id",
    ("animales", "refugios"): "refugio_id",
}
INSERTABLES = {
    "animales": COLUMNAS["animales"] - {"id", "oculto", "publicado_en", "actualizado_en"},
    "animales_fotos": {"animal_id", "ruta_archivo", "orden"},
    "refugios": {"responsable_id", "nombre", "descripcion", "zona", "municipio", "telefono_publico",
                 "correo_publico", "redes_sociales"},
    "refugios_ubicacion": {"refugio_id", "direccion", "latitud", "longitud"},
}
EDITABLES = {
    "animales": INSERTABLES["animales"] - {"responsable_id"},
    "animales_fotos": {"orden"},
    "refugios": INSERTABLES["refugios"] - {"responsable_id"},
    "refugios_ubicacion": {"direccion", "latitud", "longitud"},
}
VALORES = {
    "especie": {"perro", "gato", "conejo", "ave", "otro"}, "tamano": {"pequeño", "mediano", "grande"},
    "sexo": {"hembra", "macho", "desconocido"}, "energia": {"baja", "media", "alta", None},
    "estado": {"disponible", "en_proceso", "adoptado", "hogar_temporal", "perdido", "encontrado",
               "recuperacion", "urgente"},
}


def _ahora():
    return datetime.now(timezone.utc)


def _partir(texto):
    """Divide 'a,b,c(d,e),f' por comas de primer nivel."""
    partes, nivel, actual = [], 0, ""
    for letra in texto:
        if letra == "," and nivel == 0:
            partes.append(actual)
            actual = ""
            continue
        nivel += letra == "("
        nivel -= letra == ")"
        actual += letra
    if actual:
        partes.append(actual)
    return [p.strip() for p in partes if p.strip()]


class ErrorSelect(Exception):
    pass


class SimuladorConAnimales(SimuladorConAlertas):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.animales = {}
        self.fotos_animales = {}
        self.refugios = {}
        self.ubicaciones_refugio = {}
        self.bloqueados = set()
        self.archivos_animales = {}
        self.rechazar_fotos = False   # simula que la base de datos rechaza el registro de una foto

    # ------------------------------------------------------------- ayudantes
    def crear_refugio(self, responsable_id, nombre, estado="pendiente"):
        nuevo = str(uuid.uuid4())
        self.refugios[nuevo] = {
            "id": nuevo, "responsable_id": responsable_id, "nombre": nombre, "descripcion": None,
            "zona": "Otay", "municipio": "Tijuana", "telefono_publico": None, "correo_publico": None,
            "redes_sociales": {}, "estado_verificacion": estado, "verificado_en": None,
            "creado_en": _ahora().isoformat(), "actualizado_en": _ahora().isoformat()}
        return nuevo

    def _puede_publicar(self, usuario):
        perfil = self.perfiles.get(usuario) or {}
        if not usuario or usuario in self.bloqueados:
            return False
        if any(r["responsable_id"] == usuario and r["estado_verificacion"] == "suspendido"
               for r in self.refugios.values()):
            return False
        return (perfil.get("nivel_verificacion") == "habilitada" or perfil.get("tipo_cuenta") in ("refugio", "rescatista")
                or any(r["responsable_id"] == usuario and r["estado_verificacion"] == "verificado"
                       for r in self.refugios.values()))

    # -------------------------------------------------------------- storage
    def _storage(self, peticion, ruta, cuerpo, token):
        prefijo = "object/fotos-animales/"
        usuario = leer_jwt(token)
        if peticion.method == "POST" and ruta.startswith(prefijo):
            nombre = ruta[len(prefijo):]
            if not usuario or nombre.split("/")[0] != usuario:
                return httpx.Response(403, json={"statusCode": "403", "error": "Unauthorized",
                                                 "message": "new row violates row-level security policy"})
            self.archivos_animales[nombre] = self._archivo_de(peticion)
            return httpx.Response(200, json={"Key": f"fotos-animales/{nombre}", "Id": str(uuid.uuid4())})
        if peticion.method == "DELETE" and ruta == "object/fotos-animales":
            borrados = [p for p in cuerpo.get("prefixes", []) if p.split("/")[0] == usuario and p in self.archivos_animales]
            for p in borrados:
                del self.archivos_animales[p]
            return httpx.Response(200, json=[{"name": p} for p in borrados])
        return super()._storage(peticion, ruta, cuerpo, token)

    # ---------------------------------------------------------------- lectura
    def _visible(self, tabla, fila, usuario):
        if tabla == "animales":
            return not fila["oculto"] or fila["responsable_id"] == usuario
        if tabla == "animales_fotos":
            animal = self.animales.get(fila["animal_id"])
            return bool(animal) and self._visible("animales", animal, usuario)
        if tabla == "refugios":
            return fila["estado_verificacion"] in ("pendiente", "verificado") or fila["responsable_id"] == usuario
        if tabla == "refugios_ubicacion":
            r = self.refugios.get(fila["refugio_id"])
            return bool(r) and r["responsable_id"] == usuario
        if tabla == "perfiles":
            return True
        return False

    def _tabla(self, nombre):
        return {"animales": self.animales, "animales_fotos": self.fotos_animales, "refugios": self.refugios,
                "refugios_ubicacion": self.ubicaciones_refugio, "perfiles": self.perfiles}[nombre]

    def _proyectar(self, tabla, fila, seleccion, usuario):
        """Aplica un "select" de PostgREST (con relaciones incrustadas) a una fila."""
        if seleccion in ("", "*"):
            return dict(fila)
        salida = {}
        for parte in _partir(seleccion):
            if "(" in parte:
                cabeza, interior = parte.split("(", 1)
                interior = interior[:-1]
                alias, _, destino = cabeza.partition(":") if ":" in cabeza else (cabeza, "", cabeza)
                destino, _, pista = destino.partition("!")
                relacion = RELACIONES.get((tabla, destino))
                if relacion is None:
                    raise ErrorSelect(f"Could not find a relationship between '{tabla}' and '{destino}'")
                if pista and pista != relacion:
                    raise ErrorSelect(f"Pista de relación inválida: {pista}")
                if destino == "perfiles" and not pista:
                    # En Supabase real es ambigua (también existe la relación por "favoritos")
                    raise ErrorSelect("PGRST201: more than one relationship was found for 'animales' and 'perfiles'")
                if relacion == "hijos":
                    hijos = [f for f in self.fotos_animales.values()
                             if f["animal_id"] == fila["id"] and self._visible(destino, f, usuario)]
                    salida[alias] = [self._proyectar(destino, h, interior, usuario) for h in hijos]
                else:
                    relacionada = self._tabla(destino).get(fila.get(relacion))
                    if relacionada and self._visible(destino, relacionada, usuario):
                        salida[alias] = self._proyectar(destino, relacionada, interior, usuario)
                    else:
                        salida[alias] = None
            else:
                if parte not in COLUMNAS[tabla]:
                    raise ErrorSelect(f"column {tabla}.{parte} does not exist")
                salida[parte] = fila.get(parte)
        return salida

    @staticmethod
    def _cumple_filtros(fila, pares):
        for clave, valor in pares:
            if clave in ("select", "order", "limit", "offset", "columns", "on_conflict"):
                continue
            operador, _, dato = valor.partition(".")
            actual = fila.get(clave)
            texto = "" if actual is None else (str(actual).lower() if isinstance(actual, bool) else str(actual))
            if operador == "eq" and texto != dato:
                return False
            if operador == "in" and texto not in [d.strip('"') for d in dato.strip("()").split(",")]:
                return False
            if operador in ("gte", "lt", "gt", "lte"):
                if actual is None:
                    return False
                a, b = float(actual), float(dato)
                if not {"gte": a >= b, "lt": a < b, "gt": a > b, "lte": a <= b}[operador]:
                    return False
        return True

    def _filas(self, tabla, consulta, usuario):
        # Se usan los pares crudos de la URL: una columna puede tener dos filtros (gte y lt).
        pares = parse_qsl(urlparse(self._url).query)
        return [f for f in self._tabla(tabla).values()
                if self._visible(tabla, f, usuario) and self._cumple_filtros(f, pares)]

    def _leer(self, tabla, metodo, consulta, usuario, cabeceras):
        filas = self._filas(tabla, consulta, usuario)
        orden = consulta.get("order", "")
        if orden:
            columna, _, sentido = orden.partition(".")
            filas = sorted(filas, key=lambda f: str(f.get(columna)), reverse=sentido.startswith("desc"))
        total = len(filas)
        inicio = int(consulta.get("offset", 0))
        if "limit" in consulta:
            filas = filas[inicio:inicio + int(consulta["limit"])]
        else:
            filas = filas[inicio:]
        try:
            datos = [self._proyectar(tabla, f, consulta.get("select", "*"), usuario) for f in filas]
        except ErrorSelect as error:
            return self._error_bd("PGRST200", str(error))
        rango = f"{inicio}-{inicio + len(datos) - 1}" if datos else "*"
        conteo = str(total) if "count=exact" in cabeceras.get("prefer", "") else "*"
        return httpx.Response(200, json=datos, headers={"Content-Range": f"{rango}/{conteo}"})

    # ------------------------------------------------------------ escritura
    def _validar_animal(self, datos, usuario):
        for campo, permitidos in VALORES.items():
            if campo in datos and datos[campo] not in permitidos:
                return self._error_bd("22P02", f"invalid input value for enum: {datos[campo]}")
        if "nombre" in datos and not 1 <= len(datos["nombre"] or "") <= 60:
            return self._error_bd("23514", "new row violates check constraint")
        refugio_id = datos.get("refugio_id")
        if refugio_id:
            r = self.refugios.get(refugio_id)
            if not r or r["responsable_id"] != usuario:
                return self._error_bd("42501", "new row violates row-level security policy", 403)
            if r["estado_verificacion"] not in ("pendiente", "verificado"):
                return self._error_bd("23514", "Ese refugio no está activo en Patitas.")
        return None

    def _escribir(self, tabla, metodo, consulta, cuerpo, usuario):
        if not usuario:
            return self._error_bd("42501", "permission denied", 401)
        datos_tabla = self._tabla(tabla)
        if metodo == "POST":
            filas_nuevas = cuerpo if isinstance(cuerpo, list) else [cuerpo]
            creadas = []
            for datos in filas_nuevas:
                if set(datos) - INSERTABLES[tabla]:
                    return self._error_bd("42501", f"permission denied for table {tabla}", 401)
                if tabla == "animales":
                    if datos.get("responsable_id") != usuario or not self._puede_publicar(usuario):
                        return self._error_bd("42501", "new row violates row-level security policy for table \"animales\"", 403)
                    if (error := self._validar_animal(datos, usuario)) is not None:
                        return error
                    hoy = [a for a in self.animales.values() if a["responsable_id"] == usuario
                           and a["publicado_en"] > (_ahora() - timedelta(hours=24)).isoformat()]
                    if len(hoy) >= 10:
                        return self._error_bd("23514", "Llegaste al límite de 10 animales nuevos en 24 horas. Inténtalo mañana.")
                    fila = {c: None for c in COLUMNAS["animales"]}
                    fila.update({"raza": "No especificada", "sexo": "desconocido", "vacunado": False,
                                 "esterilizado": False, "municipio": "Tijuana", "estado": "disponible",
                                 "oculto": False, "publicado_en": _ahora().isoformat()}, **datos)
                    fila["id"] = str(uuid.uuid4())
                elif tabla == "animales_fotos":
                    if self.rechazar_fotos:
                        return self._error_bd("23514", "Cada animal puede tener máximo 3 fotos. Borra una para subir otra.")
                    animal = self.animales.get(datos.get("animal_id"))
                    if not animal or animal["responsable_id"] != usuario:
                        return self._error_bd("42501", "new row violates row-level security policy", 403)
                    if datos["ruta_archivo"].split("/")[0] != animal["responsable_id"]:
                        return self._error_bd("23514", "La foto no pertenece a quien publicó el animal.")
                    if sum(1 for f in self.fotos_animales.values() if f["animal_id"] == animal["id"]) >= 3:
                        return self._error_bd("23514", "Cada animal puede tener máximo 3 fotos. Borra una para subir otra.")
                    fila = {"id": str(uuid.uuid4()), "orden": 0, "creado_en": _ahora().isoformat(), **datos}
                elif tabla == "refugios":
                    if datos.get("responsable_id") != usuario:
                        return self._error_bd("42501", "new row violates row-level security policy", 403)
                    fila = {c: None for c in COLUMNAS["refugios"]}
                    fila.update({"municipio": "Tijuana", "redes_sociales": {}, "estado_verificacion": "pendiente",
                                 "creado_en": _ahora().isoformat()}, **datos)
                    fila["id"] = str(uuid.uuid4())
                else:   # refugios_ubicacion
                    r = self.refugios.get(datos.get("refugio_id"))
                    if not r or r["responsable_id"] != usuario:
                        return self._error_bd("42501", "new row violates row-level security policy", 403)
                    if datos["refugio_id"] in self.ubicaciones_refugio:
                        return self._error_bd("23505", "duplicate key value violates unique constraint")
                    fila = dict(datos)
                    datos_tabla[fila["refugio_id"]] = fila
                    creadas.append(fila)
                    continue
                datos_tabla[fila["id"]] = fila
                creadas.append(fila)
            return httpx.Response(201, json=creadas)

        def propia(f):
            if tabla == "animales":
                return f["responsable_id"] == usuario
            if tabla == "animales_fotos":
                return self.animales.get(f["animal_id"], {}).get("responsable_id") == usuario
            if tabla == "refugios":
                return f["responsable_id"] == usuario
            return self.refugios.get(f["refugio_id"], {}).get("responsable_id") == usuario

        filas = [f for f in self._filas(tabla, consulta, usuario) if propia(f)]
        if metodo == "PATCH":
            if set(cuerpo) - EDITABLES[tabla]:
                return self._error_bd("42501", f"permission denied for table {tabla}", 401)
            if tabla == "animales":
                if (error := self._validar_animal(cuerpo, usuario)) is not None:
                    return error
                for f in filas:
                    estado = cuerpo.get("estado", f["estado"])
                    if not self._puede_publicar(usuario) and estado not in ("adoptado", "en_proceso"):
                        return self._error_bd("42501", "new row violates row-level security policy", 403)
            for f in filas:
                f.update(cuerpo)
            return httpx.Response(200, json=filas)
        if metodo == "DELETE":
            if tabla not in ("animales", "animales_fotos"):
                return self._error_bd("42501", f"permission denied for table {tabla}", 401)
            for f in filas:
                del datos_tabla[f["id"]]
                if tabla == "animales":   # en cascada
                    for foto_id in [i for i, x in self.fotos_animales.items() if x["animal_id"] == f["id"]]:
                        del self.fotos_animales[foto_id]
            return httpx.Response(200, json=filas)
        return httpx.Response(405)

    # ------------------------------------------------------------ entrada
    def manejar(self, peticion):
        self._prefer = peticion.headers.get("prefer", "")
        self._url = str(peticion.url)
        return super().manejar(peticion)

    def _rest(self, metodo, ruta, consulta, cuerpo, token):
        if ruta not in ("animales", "animales_fotos", "refugios", "refugios_ubicacion") and \
                not (ruta == "perfiles" and metodo == "GET" and "(" in consulta.get("select", "")):
            return super()._rest(metodo, ruta, consulta, cuerpo, token)
        usuario = leer_jwt(token) if token and token != self._clave() else None
        if metodo in ("GET", "HEAD"):
            if ruta == "refugios_ubicacion" and not usuario:
                return self._error_bd("42501", "permission denied for table refugios_ubicacion", 401)
            return self._leer(ruta, metodo, consulta, usuario, {"prefer": self._prefer})
        return self._escribir(ruta, metodo, consulta, cuerpo, usuario)

    @staticmethod
    def _clave():
        from simulador_supabase import CLAVE_PUBLICA
        return CLAVE_PUBLICA
