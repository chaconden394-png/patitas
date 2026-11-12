"""
Simulador de Supabase SOLO PARA PRUEBAS.

Imita las respuestas de Supabase Auth y de la API de datos (PostgREST) para
las operaciones de la Etapa 3. La librería real `supabase` hace sus peticiones
HTTP normales, pero en lugar de salir a internet llegan aquí.

Así comprobamos que la app manda exactamente lo que Supabase espera, sin
necesitar internet ni un proyecto real. Las reglas RLS reales se prueban
aparte en tests/sql/.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from urllib.parse import parse_qs, urlparse

import httpx

SECRETO_JWT = b"secreto-solo-para-pruebas"
URL = "https://simulado.supabase.co"
CLAVE_PUBLICA = "sb_publishable_simulada"
COLUMNAS_EDITABLES = {"perfiles": {"nombre_publico", "biografia", "municipio"},
                      "perfiles_privados": {"telefono"}}


def _b64(datos):
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def crear_jwt(usuario_id, dura_segundos=3600):
    cabecera = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    ahora = int(time.time())
    carga = _b64(json.dumps({"sub": usuario_id, "role": "authenticated", "aud": "authenticated",
                             "iat": ahora, "exp": ahora + dura_segundos}).encode())
    firma = _b64(hmac.new(SECRETO_JWT, f"{cabecera}.{carga}".encode(), hashlib.sha256).digest())
    return f"{cabecera}.{carga}.{firma}"


def leer_jwt(token):
    """Devuelve el id de usuario si el token es válido y vigente; si no, None."""
    try:
        cabecera, carga, firma = token.split(".")
        esperada = _b64(hmac.new(SECRETO_JWT, f"{cabecera}.{carga}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(firma, esperada):
            return None
        datos = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
        return datos["sub"] if datos["exp"] > time.time() else None
    except Exception:
        return None


class SimuladorSupabase:
    def __init__(self, confirmar_correo=True):
        self.confirmar_correo = confirmar_correo
        self.usuarios = {}          # correo -> datos
        self.perfiles = {}          # id -> fila
        self.privados = {}          # id -> fila
        self.administradores = set()
        self.refresh_tokens = {}    # token -> usuario_id (se gastan al usarlos)
        self.enlaces = {}           # token_hash -> (usuario_id, tipo)
        self.correos = []           # correos "enviados"
        self.peticiones = []        # registro de todo lo que llegó
        self.dura_token = 3600
        self.falla_correo = False   # simula un SMTP mal configurado

    # ------------------------------------------------------------------ util
    def cliente_httpx(self):
        return httpx.Client(transport=httpx.MockTransport(self.manejar))

    def crear_usuario(self, correo, contrasena, nombre="Persona Prueba", tipo="adoptante", confirmado=True):
        """Atajo para pruebas: como crear un usuario desde el panel de Supabase."""
        return self._alta(correo, contrasena, {"nombre_publico": nombre, "tipo_cuenta": tipo,
                                               "acepto_aviso_privacidad": True}, confirmado)

    def ultimo_enlace(self, correo, tipo):
        for c in reversed(self.correos):
            if c["para"] == correo and c["tipo"] == tipo:
                return c["token_hash"]
        return None

    def _alta(self, correo, contrasena, datos, confirmado):
        usuario_id = str(uuid.uuid4())
        self.usuarios[correo] = {"id": usuario_id, "email": correo, "password": contrasena,
                                 "confirmado": confirmado, "data": datos}
        # Igual que el trigger de la migración 003
        tipo = datos.get("tipo_cuenta")
        if tipo not in ("adoptante", "rescatista", "refugio", "reportante", "voluntario", "negocio"):
            tipo = "adoptante"
        nombre = (datos.get("nombre_publico") or "").strip()[:60]
        self.perfiles[usuario_id] = {
            "id": usuario_id, "nombre_publico": nombre if len(nombre) >= 2 else "Usuario de Patitas",
            "tipo_cuenta": tipo, "nivel_verificacion": "registrada", "biografia": None,
            "municipio": "Tijuana", "creado_en": "2026-11-06T10:00:00+00:00"}
        self.privados[usuario_id] = {
            "id": usuario_id, "telefono": None, "telefono_verificado": False,
            "acepto_aviso_privacidad_en": "2026-11-06T10:00:00+00:00" if datos.get("acepto_aviso_privacidad") is True else None}
        return usuario_id

    def _usuario_por_id(self, usuario_id):
        return next((u for u in self.usuarios.values() if u["id"] == usuario_id), None)

    def _json_usuario(self, u):
        return {"id": u["id"], "aud": "authenticated", "role": "authenticated", "email": u["email"],
                "email_confirmed_at": "2026-11-06T10:00:00Z" if u["confirmado"] else None,
                "app_metadata": {"provider": "email"}, "user_metadata": u["data"],
                "created_at": "2026-11-06T10:00:00Z", "updated_at": "2026-11-06T10:00:00Z", "identities": []}

    def _sesion(self, u):
        refresh = secrets.token_urlsafe(12)
        self.refresh_tokens[refresh] = u["id"]
        return {"access_token": crear_jwt(u["id"], self.dura_token), "token_type": "bearer",
                "expires_in": self.dura_token, "expires_at": int(time.time()) + self.dura_token,
                "refresh_token": refresh, "user": self._json_usuario(u)}

    def _enviar(self, correo, tipo, usuario_id):
        token_hash = secrets.token_hex(16)
        self.enlaces[token_hash] = (usuario_id, tipo)
        self.correos.append({"para": correo, "tipo": tipo, "token_hash": token_hash})

    @staticmethod
    def _error(estado, codigo, mensaje):
        return httpx.Response(estado, json={"code": codigo, "message": mensaje},
                              headers={"X-Supabase-Api-Version": "2024-01-01"})

    @staticmethod
    def _ok(datos, estado=200):
        return httpx.Response(estado, json=datos, headers={"X-Supabase-Api-Version": "2024-01-01"})

    # ------------------------------------------------------------- entrada
    def manejar(self, peticion):
        url = urlparse(str(peticion.url))
        es_json = "json" in peticion.headers.get("content-type", "") or not url.path.startswith("/storage/")
        try:
            cuerpo = json.loads(peticion.content) if (peticion.content and es_json) else {}
        except ValueError:
            cuerpo = {}
        consulta = {k: v[0] for k, v in parse_qs(url.query).items()}
        autorizacion = peticion.headers.get("authorization", "").removeprefix("Bearer ").strip()
        self.peticiones.append({"metodo": peticion.method, "ruta": url.path, "consulta": consulta,
                                "cuerpo": cuerpo, "token": autorizacion,
                                "apikey": peticion.headers.get("apikey") or peticion.headers.get("apiKey")})
        if self.peticiones[-1]["apikey"] != CLAVE_PUBLICA:
            return self._error(401, "no_authorization", "Invalid API key")
        if url.path.startswith("/storage/v1/"):
            return self._storage(peticion, url.path[len("/storage/v1/"):], cuerpo, autorizacion)
        if url.path.startswith("/auth/v1/"):
            return self._auth(peticion.method, url.path[len("/auth/v1/"):], consulta, cuerpo, autorizacion)
        if url.path.startswith("/rest/v1/"):
            return self._rest(peticion.method, url.path[len("/rest/v1/"):], consulta, cuerpo, autorizacion)
        return self._error(404, "not_found", "Ruta desconocida")

    def _storage(self, peticion, ruta, cuerpo, token):
        return self._error(404, "not_found", "Storage no simulado")

    # ---------------------------------------------------------------- auth
    def _auth(self, metodo, ruta, consulta, cuerpo, token):
        if metodo == "POST" and ruta == "signup":
            correo = cuerpo["email"]
            if self.falla_correo:
                return self._error(500, "unexpected_failure", "Error sending confirmation email")
            if correo in self.usuarios:
                # Supabase no revela que el correo existe: devuelve un usuario falso.
                falso = {"id": str(uuid.uuid4()), "email": correo, "confirmado": False, "data": {}}
                return self._ok(self._json_usuario(falso))
            u_id = self._alta(correo, cuerpo["password"], cuerpo.get("data") or {}, not self.confirmar_correo)
            u = self.usuarios[correo]
            if self.confirmar_correo:
                self._enviar(correo, "email", u_id)
                return self._ok(self._json_usuario(u))
            return self._ok(self._sesion(u))

        if metodo == "POST" and ruta == "token":
            if consulta.get("grant_type") == "password":
                u = self.usuarios.get(cuerpo.get("email"))
                if not u or u["password"] != cuerpo.get("password"):
                    return self._error(400, "invalid_credentials", "Invalid login credentials")
                if not u["confirmado"]:
                    return self._error(400, "email_not_confirmed", "Email not confirmed")
                return self._ok(self._sesion(u))
            if consulta.get("grant_type") == "refresh_token":
                u_id = self.refresh_tokens.pop(cuerpo.get("refresh_token"), None)
                if not u_id:
                    return self._error(400, "refresh_token_already_used", "Invalid Refresh Token")
                return self._ok(self._sesion(self._usuario_por_id(u_id)))

        if metodo == "POST" and ruta == "verify":
            enlace = self.enlaces.pop(cuerpo.get("token_hash"), None)
            tipo_pedido = cuerpo.get("type")
            if not enlace or (enlace[1] != tipo_pedido and {enlace[1], tipo_pedido} != {"email", "signup"}):
                return self._error(403, "otp_expired", "Email link is invalid or has expired")
            u = self._usuario_por_id(enlace[0])
            u["confirmado"] = True
            return self._ok(self._sesion(u))

        if metodo == "POST" and ruta == "recover":
            u = self.usuarios.get(cuerpo.get("email"))
            if u:
                self._enviar(u["email"], "recovery", u["id"])
            return self._ok({})

        if metodo == "POST" and ruta == "resend":
            u = self.usuarios.get(cuerpo.get("email"))
            if u and not u["confirmado"]:
                self._enviar(u["email"], "email", u["id"])
            return self._ok({"message_id": None})

        if ruta == "user":
            u_id = leer_jwt(token)
            u = self._usuario_por_id(u_id) if u_id else None
            if not u:
                return self._error(403, "bad_jwt", "invalid JWT")
            if metodo == "GET":
                return self._ok(self._json_usuario(u))
            if metodo == "PUT":
                if "password" in cuerpo:
                    if cuerpo["password"] == u["password"]:
                        return self._error(422, "same_password", "New password should be different")
                    u["password"] = cuerpo["password"]
                return self._ok(self._json_usuario(u))

        if metodo == "POST" and ruta == "logout":
            u_id = leer_jwt(token)
            if not u_id:
                return self._error(403, "bad_jwt", "invalid JWT")
            for r in [r for r, i in self.refresh_tokens.items() if i == u_id]:
                del self.refresh_tokens[r]
            return httpx.Response(204)

        return self._error(404, "not_found", f"Auth: {metodo} {ruta}")

    # ---------------------------------------------------- datos (PostgREST)
    def _rest(self, metodo, ruta, consulta, cuerpo, token):
        usuario_id = leer_jwt(token) if token != CLAVE_PUBLICA else None
        if token and token != CLAVE_PUBLICA and usuario_id is None:
            return httpx.Response(401, json={"code": "PGRST301", "message": "JWT expired"})

        if ruta == "rpc/es_admin":
            return httpx.Response(200, json=usuario_id in self.administradores)

        tablas = {"perfiles": self.perfiles, "perfiles_privados": self.privados}
        if ruta not in tablas:
            return httpx.Response(404, json={"message": "tabla desconocida en el simulador"})
        tabla = tablas[ruta]
        filtro_id = consulta.get("id", "").removeprefix("eq.")

        # RLS simplificado: perfiles es público; perfiles_privados solo el dueño.
        def visible(fila):
            return ruta == "perfiles" or fila["id"] == usuario_id

        if metodo == "GET":
            filas = [f for f in tabla.values() if visible(f) and (not filtro_id or f["id"] == filtro_id)]
            if ruta == "perfiles_privados" and usuario_id is None:
                return httpx.Response(401, json={"code": "42501", "message": "permission denied"})
            columnas = consulta.get("select", "*").split(",")
            if columnas != ["*"]:
                filas = [{c: f.get(c) for c in columnas} for f in filas]
            return httpx.Response(200, json=filas)

        if metodo == "PATCH":
            if usuario_id is None or not set(cuerpo) <= COLUMNAS_EDITABLES[ruta]:
                return httpx.Response(401, json={"code": "42501", "message": "permission denied"})
            filas = [f for f in tabla.values() if f["id"] == filtro_id and f["id"] == usuario_id]
            for f in filas:
                f.update(cuerpo)
            return httpx.Response(200, json=filas)

        return httpx.Response(405, json={"message": "no soportado"})
