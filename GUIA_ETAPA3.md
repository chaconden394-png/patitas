# Guía · Etapa 3: cuentas

Requisito: haber terminado `GUIA_SUPABASE.md` ("Todo listo").

## Paso 1 · Actualiza los archivos
Sube `patitas-etapa3.zip` a la raíz de tu Codespace y ejecuta:
```bash
unzip -o patitas-etapa3.zip
```
```bash
rm patitas-etapa3.zip
```
```bash
python -m pytest -q
```
Debe decir **87 passed**. Tu `.env` no se toca.

## Paso 2 · Migración 003
SQL Editor de Supabase → nueva consulta → pega todo `supabase/migraciones/003_cuentas.sql` → Run (una sola vez).

## Paso 3 · Dirección de tu app (Site URL)
1. En la terminal de Codespaces:
   ```bash
   echo "https://${CODESPACE_NAME}-5000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
   ```
   Copia la dirección que aparece (termina en `-5000.app.github.dev`).
2. En Supabase: **Authentication** → busca la sección de configuración de URL (URL Configuration).
3. Pega esa dirección en **Site URL** y guarda. Sin `/` al final.

Si un día creas otro Codespace, su dirección cambia: repite este paso.

## Paso 4 · Plantillas de correo
En **Authentication** busca la sección de plantillas de correo (Emails / Templates).

| Plantilla de Supabase | Asunto | Archivo a pegar en el cuerpo |
|---|---|---|
| Confirm signup | Confirma tu cuenta de Patitas | `supabase/plantillas_correo/confirmar_cuenta.html` |
| Reset Password | Recupera tu contraseña de Patitas | `supabase/plantillas_correo/recuperar_contrasena.html` |

Reemplaza todo el contenido del cuerpo y guarda cada una.

## Paso 5 · Revisa la configuración del correo
En **Authentication**, en la configuración del proveedor **Email**:
- Debe estar activado.
- **Confirm email** debe estar activado (así nadie entra sin confirmar su correo).
- Si existe la opción de longitud mínima de contraseña, ponla en **8**.

## Paso 6 · Comprueba
```bash
python comprobar_supabase.py
```
Debe mostrar 6 pasos con ✓.

```bash
pkill -f flask
```
```bash
flask --app app run --debug
```

## Paso 7 · Pruebas manuales
⚠️ Mientras no configures un servicio de correo propio, Supabase **solo envía correos a los miembros de tu equipo**
(el correo con el que entras a Supabase) y **como máximo 2 por hora**. Haz la prueba de registro con ese correo, una sola vez.

1. **Registro:** Crear cuenta → elige un tipo → usa tu correo de Supabase → debe decir "Revisa tu correo".
2. **Confirmación:** abre el correo **en el mismo navegador** → "Continuar" → debes llegar a "Mi cuenta" con tu nombre arriba a la derecha.
3. **Mi cuenta:** cambia tu biografía y teléfono → "Tu perfil se guardó".
4. **Perfil público:** menú de tu nombre → "Ver mi perfil público": no debe aparecer tu correo ni tu teléfono.
5. **Cerrar sesión:** menú → Cerrar sesión → vuelven los botones "Iniciar sesión / Crear cuenta".
6. **Inicio de sesión:** entra con tu correo y contraseña. Prueba también una contraseña incorrecta.
7. **Recuperar contraseña** (espera 1 hora si ya usaste tus 2 correos): "¿Olvidaste tu contraseña?" → abre el correo → elige una nueva → entra con ella.
8. **Panel:** si tu cuenta es "adoptante", entra a `/panel`: debe regresarte a "Mi cuenta".
9. **Administración:** entra a `/admin`: debe decir "página no encontrada".
   Para hacerte administradora, en el SQL Editor (cambia el correo):
   ```sql
   insert into public.administradores (usuario_id)
   select id from auth.users where email = 'tu-correo@ejemplo.com';
   ```
   Recarga `/admin`: ahora sí debe abrir.

### Más cuentas de prueba sin gastar correos
Authentication → Users → agregar usuario → marca la confirmación automática. Para elegir su nombre y tipo,
después ejecuta en el SQL Editor:
```sql
update public.perfiles set nombre_publico = 'Refugio de prueba 2', tipo_cuenta = 'refugio'
where id = (select id from auth.users where email = 'refugio2@example.com');
```

## Errores comunes
| Lo que ves | Qué hacer |
|---|---|
| "Supabase no puede enviar correos a esa dirección todavía" | Usa el correo de tu cuenta de Supabase o configura un SMTP propio |
| "Se enviaron demasiados correos" | Espera una hora (límite de 2 por hora) |
| El enlace del correo abre otra dirección o da error 404 | Revisa la Site URL (paso 3) y las plantillas (paso 4) |
| "El enlace ya expiró o ya se usó" | Pide uno nuevo; ábrelo una sola vez |
| Al abrir el enlace, GitHub pide iniciar sesión | Normal: el puerto de Codespaces es privado. Ábrelo en el navegador donde usas GitHub |
| "El formulario expiró" | Recarga la página e inténtalo de nuevo |
| "Falta la migración 003" | Paso 2 |
