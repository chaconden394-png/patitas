# Guía · Publicar Patitas en Vercel

Vercel ejecuta la app de Flask en sus servidores y le da una dirección pública
(por ejemplo `https://patitas-xxxx.vercel.app`). La base de datos, las cuentas y las
fotos siguen en Supabase: no cambian.

## Antes de empezar: lo que cambió en el código
- `static/` ahora vive en `public/static/`: en Vercel, Flask no entrega los archivos estáticos;
  Vercel los toma de `public/`. En tu Codespace todo sigue funcionando igual.
- `vercel.json`: deja fuera de Vercel las pruebas, el SQL y las guías.
- Las fotos se reducen en el navegador antes de enviarse: Vercel acepta máximo 4.5 MB por envío.
- En producción, `SECRET_KEY` es obligatoria (si falta, la app no arranca y lo dice).
- En Vercel, los límites de intentos usan la IP real del visitante.

---

## Parte A · Actualiza tu código (en el Codespace)
Ejecuta uno por uno:
```bash
mkdir -p public
```
```bash
git mv static public/static
```
Sube `patitas-vercel.zip` a la raíz del Codespace y:
```bash
unzip -o patitas-vercel.zip
```
```bash
rm patitas-vercel.zip
```
```bash
python -m pytest -q
```
Debe decir **148 passed**. Abre la app (`flask --app app run --debug`) y revisa que se vea con sus colores y el logo.

Súbelo a GitHub:
```bash
git add .
```
```bash
git status
```
(revisa que `.env` NO aparezca)
```bash
git commit -m "Preparar Patitas para Vercel"
```
```bash
git push
```

## Parte B · Crea una clave nueva para producción
En la terminal del Codespace:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Copia el resultado (64 letras y números). **Es secreta**: no la compartas ni la guardes en el repositorio.
Es distinta a la de tu `.env`.

## Parte C · Crea el proyecto en Vercel
1. Entra a vercel.com y crea tu cuenta con **GitHub**. Elige el plan gratuito (**Hobby**) solo si estás de
   acuerdo con sus condiciones: Vercel lo ofrece para uso personal, no comercial. Si Patitas recibirá
   donaciones o tendrá fines comerciales, revisa sus planes antes. (Esa decisión es tuya.)
2. En tu panel de Vercel, agrega un proyecto nuevo e **importa** el repositorio `patitas` de GitHub
   (si no aparece, dale a Vercel permiso de ver ese repositorio).
3. En la pantalla de configuración, Vercel debe detectar **Flask**. No cambies los comandos de instalación.
4. En **Environment Variables** agrega estas 4 (nombre exacto → valor):

| Nombre | Valor |
|---|---|
| `SECRET_KEY` | la clave que generaste en la Parte B |
| `PATITAS_ENV` | `production` |
| `SUPABASE_URL` | el mismo valor que tienes en tu `.env` |
| `SUPABASE_CLAVE_PUBLICA` | el mismo valor que tienes en tu `.env` (la **publishable/anon**) |

> ⚠️ Nunca pongas la clave `service_role` / `sb_secret_...` en Vercel ni en ningún otro lado de la app.

5. **Deploy**. Al terminar, Vercel te muestra la dirección de tu sitio. Anótala.

## Parte D · Avisa a Supabase de la nueva dirección
Los enlaces de los correos (confirmar cuenta, recuperar contraseña) usan la "Site URL".
1. Supabase → **Authentication** → **URL Configuration**.
2. **Site URL**: cambia la de Codespaces por tu dirección de Vercel, por ejemplo `https://patitas-xxxx.vercel.app`
   (sin `/` al final). Guarda.
3. En **Redirect URLs** agrega también la dirección de Vercel.

Desde ahora, los correos llevan a la versión de Vercel (también los de cuentas creadas en tu Codespace).

## Parte E · Comprueba
En tu dirección de Vercel:
1. La página de inicio se ve con colores, logo y tipografías.
2. **Adoptar** muestra los animales de Supabase con sus fotos.
3. Estas direcciones deben mostrar la página "No encontramos esa página" de Patitas, **nunca** el contenido de un archivo:
   - `https://TU-DIRECCION.vercel.app/requirements.txt`
   - `https://TU-DIRECCION.vercel.app/app.py`
   - `https://TU-DIRECCION.vercel.app/.env`

   Si alguna muestra texto de un archivo, **detente y avísame**.
4. Crea una cuenta nueva → el enlace del correo debe abrir tu sitio de Vercel → confirma → entra.
5. Inicia sesión con `refugio.prueba@example.com` y sube una foto desde el celular (prueba con una foto grande).
6. Emite y cierra una alerta de prueba.

Si algo falla: en Vercel abre tu proyecto → **Logs** (o el despliegue → registros de la función) y copia las
líneas con `WARNING` o `Error`.

## Cada vez que cambies el código
Solo haz `git push`: Vercel publica la nueva versión sola en uno o dos minutos.

## Límites que debes conocer
- **Límite de intentos** (registro, reenviar correo): se guarda en la memoria de cada servidor. En Vercel puede
  haber varios servidores, así que el límite es menos estricto. Supabase Auth tiene sus propios límites.
  Antes del lanzamiento conviene moverlo a la base de datos (está en pendientes).
- **El sitio es público**: cualquiera con la dirección puede registrarse. Todavía faltan decisiones de
  lanzamiento (moderación, proceso de derechos ARCO, correo con dominio propio). Úsalo como versión de prueba
  y no lo anuncies como servicio abierto hasta completarlas.
