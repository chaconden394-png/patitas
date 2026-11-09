# Patitas 🐾
**Busca amor. Encuentra hogar.**

Plataforma web de rescate, adopción y bienestar animal. Comienza en Tijuana, Baja California.

Tecnología: Python + Flask + Jinja2 + Bootstrap 5 + Supabase (PostgreSQL).

Sin Supabase configurado, la app funciona en **modo de ejemplo** con datos ficticios.

---

## Cómo ejecutar en GitHub Codespaces

Todos los comandos se escriben en la **Terminal** de Codespaces (panel inferior).
Si no la ves, abre el menú de Codespaces y busca la opción para abrir una terminal nueva.

Los archivos del proyecto van en la **raíz** del repositorio (junto a este README).

**1. Instala las dependencias** (solo la primera vez o cuando cambie `requirements.txt`):
```bash
pip install -r requirements.txt
```

**2. Crea tu archivo `.env`** a partir del ejemplo (solo la primera vez):
```bash
cp .env.example .env
```

**3. Genera una clave secreta** y pégala en `.env` en la línea `SECRET_KEY=`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**4. Arranca la aplicación:**
```bash
flask --app app run --debug
```

Codespaces mostrará un aviso para abrir el puerto **5000** en el navegador. Si no aparece,
busca la pestaña de **Puertos** (Ports) junto a la terminal y abre la dirección del puerto 5000.

Para detener la aplicación: `Ctrl + C` en la terminal.

## Cómo ejecutar las pruebas
```bash
python -m pytest -v
```

## Cómo conectar Supabase (resumen)
Guía detallada: `GUIA_SUPABASE.md`.

1. Editor de SQL de Supabase, en este orden y **una sola vez** cada una:
   `supabase/migraciones/001_esquema_inicial.sql` → `supabase/migraciones/002_alertas_patitas.sql`.
2. Autenticación → Usuarios: crea `refugio.prueba@example.com`.
3. Editor de SQL: `supabase/datos_prueba/datos_ficticios.sql` → `supabase/datos_prueba/alerta_ficticia.sql`.
4. Botón **Connect** → copia `SUPABASE_URL` y la clave **publishable** a tu `.env`
   (en `.env` la clave se llama `SUPABASE_CLAVE_PUBLICA`). Nunca copies la clave secret.
5. `python comprobar_supabase.py` → debe terminar en "Todo listo".
6. Reinicia la app. El aviso "Modo de ejemplo" debe desaparecer.

## Cómo agregar fotos de los animales de ejemplo
Coloca las fotos en `static/images/animales/` con el nombre que aparece en el campo `foto`
de `services/datos_ejemplo.py` (por ejemplo `canela.jpg`). Si la foto no existe, la página muestra
un marcador ilustrado. Usa fotos propias o con licencia libre.

## Cómo reemplazar el logotipo
Sustituye `static/images/logo-patitas.svg` por el logo oficial **con el mismo nombre de archivo**.

---

## Estructura del proyecto
| Archivo / carpeta | Para qué sirve |
|---|---|
| `app.py` | Crea la app Flask y define las rutas (páginas). |
| `config.py` | Lee la configuración y las claves desde `.env`. |
| `requirements.txt` | Lista de librerías de Python. |
| `.env.example` | Plantilla de configuración **sin** claves reales. |
| `.gitignore` | Evita subir `.env` y archivos temporales a GitHub. |
| `services/estados.py` | Los 8 estados de un animal (texto, icono, color). |
| `services/datos_ejemplo.py` | Datos ficticios para el modo de ejemplo. |
| `services/supabase_cliente.py` | Conexión con Supabase (solo clave pública). |
| `services/animales.py` | Consultas de animales y refugios (Supabase o ejemplo). |
| `services/alertas.py` | Consultas de Alerta Patitas (Supabase o ejemplo). |
| `static/js/alertas.js` | Mapa de la alerta y botón de compartir. |
| `comprobar_supabase.py` | Script que revisa la conexión paso a paso. |
| `templates/base.html` | Estructura común: menú, pie de página, fuentes, Bootstrap. |
| `templates/componentes.html` | Piezas reutilizables: tarjeta de animal, insignias, avisos. |
| `templates/*.html` | Una plantilla por página. |
| `static/css/patitas.css` | Colores, tipografías y estilos del moodboard. |
| `static/js/patitas.js` | Interacciones sencillas. |
| `static/images/` | Logo y fotos públicas (nunca documentos privados). |
| `tests/` | Pruebas automáticas de Python; `tests/sql/` tiene las pruebas de permisos. |
| `supabase/` | Migraciones SQL y datos de prueba (ver `supabase/README.md`). |
| `AVANCE.md` | Registro de avance, decisiones y pendientes. |
| `GUIA_SUPABASE.md` | Paso a paso para conectar Supabase desde cero. |

## Reglas de seguridad del proyecto
- Nunca subas el archivo `.env` a GitHub.
- La clave secreta de Supabase (`secret` / `service_role`) nunca va en `.env` de la app, en el frontend ni en el repositorio.
- No uses datos personales reales como datos de prueba.
