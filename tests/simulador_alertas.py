"""
Simulador de Supabase para la Alerta Patitas (Parte B). SOLO PARA PRUEBAS.

Amplía SimuladorSupabase con: Storage (fotos), alertas, emitir_alerta(),
zonas de alerta, avistamientos, notificaciones y teléfono de contacto.
Imita las reglas de las migraciones 002 y 004 de forma simplificada; las
reglas reales se prueban en tests/sql/ con PostgreSQL.
"""
import uuid
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

import httpx

from simulador_supabase import CLAVE_PUBLICA, SimuladorSupabase, leer_jwt


def _distancia(lat1, lng1, lat2, lng2):
    return 2 * 6371 * asin(sqrt(sin(radians(lat2 - lat1) / 2) ** 2
                               + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lng2 - lng1) / 2) ** 2))


def _ahora():
    return datetime.now(timezone.utc)


def _iso(fecha):
    return fecha.isoformat()


class SimuladorConAlertas(SimuladorSupabase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.archivos = {}        # ruta en fotos-alertas -> bytes
        self.alertas = {}         # id -> fila
        self.ubicaciones = {}     # alerta_id -> (lat, lng) EXACTA
        self.zonas = {}           # usuario_id -> fila
        self.avistamientos = []
        self.notificaciones = []

    # -------------------------------------------------------------- errores
    @staticmethod
    def _error_bd(codigo, mensaje, estado=400):
        return httpx.Response(estado, json={"code": codigo, "message": mensaje, "details": None, "hint": None})

    # -------------------------------------------------------------- storage
    def _storage(self, peticion, ruta, cuerpo, token):
        usuario = leer_jwt(token)
        prefijo = "object/fotos-alertas/"
        if peticion.method == "POST" and ruta.startswith(prefijo):
            nombre = ruta[len(prefijo):]
            if not usuario or nombre.split("/")[0] != usuario:
                return httpx.Response(403, json={"statusCode": "403", "error": "Unauthorized",
                                                 "message": "new row violates row-level security policy"})
            self.archivos[nombre] = self._archivo_de(peticion)
            return httpx.Response(200, json={"Key": f"fotos-alertas/{nombre}", "Id": str(uuid.uuid4())})
        if peticion.method == "DELETE" and ruta == "object/fotos-alertas":
            borrados = [p for p in cuerpo.get("prefixes", []) if p.split("/")[0] == usuario and p in self.archivos]
            for p in borrados:
                del self.archivos[p]
            return httpx.Response(200, json=[{"name": p} for p in borrados])
        return httpx.Response(404, json={"message": "storage: ruta no simulada"})

    @staticmethod
    def _archivo_de(peticion):
        """La librería sube la foto como formulario multipart: extrae solo el archivo."""
        tipo = peticion.headers.get("content-type", "")
        if not tipo.startswith("multipart/"):
            return peticion.content
        from email.parser import BytesParser
        from email.policy import HTTP
        mensaje = BytesParser(policy=HTTP).parsebytes(
            f"Content-Type: {tipo}\r\n\r\n".encode() + peticion.content)
        for parte in mensaje.iter_parts():
            if parte.get_filename() is not None or parte.get_content_type().startswith("image/"):
                return parte.get_payload(decode=True)
        return b""

    # ------------------------------------------------------------ utilidades
    @staticmethod
    def _filtrar(filas, consulta):
        """Filtros sencillos de PostgREST: col=eq.valor, col=gt.valor."""
        for clave, valor in consulta.items():
            if clave in ("select", "order", "limit", "offset", "columns", "on_conflict"):
                continue
            operador, _, dato = valor.partition(".")
            if operador == "eq":
                filas = [f for f in filas if str(f.get(clave)).lower() == dato.lower()]
            elif operador == "gt":
                filas = [f for f in filas if str(f.get(clave)) > dato]
        return filas

    def _vigente(self, a):
        return a["estado"] == "activa" and not a["oculta"] and a["expira_en"] > _iso(_ahora())

    def _con_emisor(self, a):
        p = self.perfiles.get(a["emisor_id"], {})
        return {**a, "emisor": {k: p.get(k) for k in ("nombre_publico", "creado_en", "nivel_verificacion")}}

    def _respuesta(self, filas, consulta, metodo="GET"):
        orden = consulta.get("order", "")
        if orden:
            columna, _, sentido = orden.partition(".")
            filas = sorted(filas, key=lambda f: str(f.get(columna)), reverse=sentido.startswith("desc"))
        if "limit" in consulta:
            filas = filas[: int(consulta["limit"])]
        cabeceras = {"Content-Range": f"0-{max(len(filas) - 1, 0)}/{len(filas)}"}
        if metodo == "HEAD":
            return httpx.Response(200, headers=cabeceras)
        return httpx.Response(200, json=filas, headers=cabeceras)

    # ----------------------------------------------------------------- datos
    def _rest(self, metodo, ruta, consulta, cuerpo, token):
        usuario = leer_jwt(token) if token and token != CLAVE_PUBLICA else None
        if token and token != CLAVE_PUBLICA and usuario is None:
            return httpx.Response(401, json={"code": "PGRST301", "message": "JWT expired"})

        manejador = getattr(self, "_t_" + ruta.replace("rpc/", "rpc_"), None)
        if manejador is None:
            return super()._rest(metodo, ruta, consulta, cuerpo, token)
        return manejador(metodo, consulta, cuerpo, usuario)

    # emitir_alerta (como la migración 004: alerta + ubicación en una sola operación)
    def _t_rpc_emitir_alerta(self, metodo, consulta, c, usuario):
        if not usuario:
            return self._error_bd("42501", "Necesitas iniciar sesión.", 401)
        activas = [a for a in self.alertas.values() if a["emisor_id"] == usuario and self._vigente(a)]
        if len(activas) >= 2:
            return self._error_bd("23514", "Ya tienes 2 alertas activas. Cierra una antes de emitir otra.")
        ruta = c.get("p_ruta_foto")
        if ruta and ruta.split("/")[0] != usuario:
            return self._error_bd("23514", "La foto no pertenece a quien emite la alerta.")
        if not (-90 <= c["p_latitud"] <= 90 and -180 <= c["p_longitud"] <= 180):
            return self._error_bd("23514", "new row violates check constraint")
        nuevo = str(uuid.uuid4())
        ahora = _ahora()
        self.alertas[nuevo] = {
            "id": nuevo, "emisor_id": usuario, "nombre_mascota": c["p_nombre"], "especie": c["p_especie"],
            "raza": c["p_raza"] or "No especificada", "sexo": c["p_sexo"], "tamano": c["p_tamano"],
            "edad_aproximada": c["p_edad"] or None, "color": c["p_color"], "senas_particulares": c["p_senas"] or None,
            "collar": c["p_collar"] or None, "descripcion": c["p_descripcion"] or None, "ruta_foto": ruta,
            "zona_referencia": c["p_zona"], "municipio": "Tijuana", "visto_por_ultima_vez": c["p_visto"],
            "latitud_aprox": round(c["p_latitud"], 2), "longitud_aprox": round(c["p_longitud"], 2),
            "mostrar_telefono": c["p_mostrar_telefono"], "estado": "activa", "oculta": False,
            "creada_en": _iso(ahora), "expira_en": _iso(ahora + timedelta(days=30)),
        }
        self.ubicaciones[nuevo] = (c["p_latitud"], c["p_longitud"])
        for z in self.zonas.values():   # regla de 15 km
            if z["acepta_alertas"] and z["usuario_id"] != usuario and \
                    _distancia(z["latitud"], z["longitud"], c["p_latitud"], c["p_longitud"]) <= 15:
                self._notificar(z["usuario_id"], "alerta_cercana", nuevo,
                                f"Alerta Patitas: se busca a {c['p_nombre']}", "Si lo ves, avísale a su familia.")
        return httpx.Response(200, json=nuevo)

    def _notificar(self, usuario_id, tipo, alerta_id, titulo, cuerpo):
        self.notificaciones.append({"id": len(self.notificaciones) + 1, "usuario_id": usuario_id, "tipo": tipo,
                                    "alerta_id": alerta_id, "titulo": titulo, "cuerpo": cuerpo,
                                    "leida": False, "creada_en": _iso(_ahora())})

    def _t_alertas(self, metodo, consulta, cuerpo, usuario):
        visibles = [a for a in self.alertas.values() if not a["oculta"] or a["emisor_id"] == usuario]
        filas = self._filtrar(visibles, consulta)
        if metodo == "GET":
            return self._respuesta([self._con_emisor(a) for a in filas], consulta)
        if metodo == "PATCH":
            if not usuario or set(cuerpo) - {"estado", "mostrar_telefono", "descripcion"}:
                return self._error_bd("42501", "permission denied", 401)
            cambiadas = []
            for a in filas:
                if a["emisor_id"] != usuario:
                    continue
                if "estado" in cuerpo and a["estado"] != "activa":
                    return self._error_bd("23514", "Esta alerta ya está cerrada.")
                a.update(cuerpo)
                if cuerpo.get("estado") == "encontrada":
                    for n in [n for n in self.notificaciones if n["alerta_id"] == a["id"] and n["tipo"] == "alerta_cercana"]:
                        self._notificar(n["usuario_id"], "alerta_cerrada", a["id"],
                                        f"¡{a['nombre_mascota']} ya está en casa!", "Gracias por ayudar.")
                cambiadas.append(a)
            return httpx.Response(200, json=cambiadas)
        return httpx.Response(405)

    def _t_rpc_personas_avisadas(self, metodo, consulta, cuerpo, usuario):
        return httpx.Response(200, json=sum(1 for n in self.notificaciones
                                            if n["alerta_id"] == cuerpo["id_alerta"] and n["tipo"] == "alerta_cercana"))

    def _t_rpc_renovar_alerta(self, metodo, consulta, cuerpo, usuario):
        a = self.alertas.get(cuerpo["p_alerta"])
        if not a or a["emisor_id"] != usuario:
            return self._error_bd("42501", "No encontramos esa alerta.", 401)
        if a["expira_en"] > _iso(_ahora() + timedelta(days=7)):
            return self._error_bd("23514", "Podrás renovarla cuando falten 7 días o menos.")
        a["expira_en"] = _iso(_ahora() + timedelta(days=30))
        return httpx.Response(200, json=a["expira_en"])

    def _t_rpc_telefono_contacto_alerta(self, metodo, consulta, cuerpo, usuario):
        if not usuario:
            return self._error_bd("42501", "permission denied for function", 401)
        a = self.alertas.get(cuerpo["id_alerta"])
        if not a or not a["mostrar_telefono"] or not self._vigente(a):
            return httpx.Response(200, json=None)
        return httpx.Response(200, json=self.privados[a["emisor_id"]]["telefono"])

    def _t_zonas_alerta(self, metodo, consulta, cuerpo, usuario):
        if not usuario:
            return self._error_bd("42501", "permission denied", 401)
        propias = [z for z in self.zonas.values() if z["usuario_id"] == usuario]
        filas = self._filtrar(propias, consulta)
        if metodo == "GET":
            return self._respuesta(filas, consulta)
        if metodo == "PATCH":
            if "usuario_id" in cuerpo:
                return self._error_bd("42501", "permission denied for column usuario_id", 401)
            for z in filas:
                z.update(cuerpo, latitud=round(cuerpo["latitud"], 2), longitud=round(cuerpo["longitud"], 2))
            return httpx.Response(200, json=filas)
        if metodo == "POST":
            if cuerpo.get("usuario_id") != usuario:
                return self._error_bd("42501", "new row violates row-level security policy", 401)
            if usuario in self.zonas:
                return self._error_bd("23505", "duplicate key value violates unique constraint")
            self.zonas[usuario] = dict(cuerpo, latitud=round(cuerpo["latitud"], 2), longitud=round(cuerpo["longitud"], 2))
            return httpx.Response(201, json=[self.zonas[usuario]])
        if metodo == "DELETE":
            for z in filas:
                del self.zonas[z["usuario_id"]]
            return httpx.Response(200, json=filas)
        return httpx.Response(405)

    def _t_avistamientos(self, metodo, consulta, cuerpo, usuario):
        if not usuario:
            return self._error_bd("42501", "permission denied", 401)
        if metodo == "POST":
            a = self.alertas.get(cuerpo.get("alerta_id"))
            if cuerpo.get("reportado_por") != usuario or not a or not self._vigente(a) or a["emisor_id"] == usuario:
                return self._error_bd("42501", "new row violates row-level security policy", 401)
            fila = dict(cuerpo, id=len(self.avistamientos) + 1, creado_en=_iso(_ahora()))
            self.avistamientos.append(fila)
            self._notificar(a["emisor_id"], "avistamiento", a["id"], f"Alguien vio a {a['nombre_mascota']}",
                            f"Visto en {cuerpo['lugar']}.")
            return httpx.Response(201, json=[fila])
        if metodo == "GET":
            visibles = [v for v in self.avistamientos if v["reportado_por"] == usuario
                        or self.alertas[v["alerta_id"]]["emisor_id"] == usuario]
            filas = [dict(v, persona={"nombre_publico": self.perfiles[v["reportado_por"]]["nombre_publico"]})
                     for v in self._filtrar(visibles, consulta)]
            return self._respuesta(filas, consulta)
        return httpx.Response(405)

    def _t_notificaciones(self, metodo, consulta, cuerpo, usuario):
        if not usuario:
            return self._error_bd("42501", "permission denied", 401)
        filas = self._filtrar([n for n in self.notificaciones if n["usuario_id"] == usuario], consulta)
        if metodo in ("GET", "HEAD"):
            return self._respuesta(filas, consulta, metodo)
        if metodo == "PATCH":
            if set(cuerpo) != {"leida"}:
                return self._error_bd("42501", "permission denied", 401)
            for n in filas:
                n.update(cuerpo)
            return httpx.Response(200, json=filas)
        return httpx.Response(405)
