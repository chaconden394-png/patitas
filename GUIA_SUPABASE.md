# Guía: Patitas desde cero con Supabase

Tiempo aproximado: 30 minutos. No necesitas instalar nada en tu computadora.

## Parte 1 · Repositorio y Codespace

1. En GitHub, crea un repositorio nuevo (por ejemplo `patitas`). Puede ser privado.
   Marca la opción de agregar un README para que no quede vacío.
2. En el repositorio, abre el botón **Code** → pestaña **Codespaces** → crea un Codespace.
3. Arrastra `patitas-completo.zip` al panel de archivos de la izquierda (a la raíz, no dentro de una carpeta).
4. En la terminal:
   ```bash
   unzip -o patitas-completo.zip
   ```
   ```bash
   rm patitas-completo.zip
   ```
5. Instala las librerías:
   ```bash
   pip install -r requirements.txt
   ```
6. Comprueba que todo está bien (debe decir `51 passed`):
   ```bash
   python -m pytest -q
   ```

## Parte 2 · Proyecto de Supabase

Recomendado: un **proyecto nuevo**. Si reutilizas el anterior, las migraciones ya ejecutadas
darán errores como `already exists`; en ese caso salta las que ya corriste.

1. En supabase.com, crea un proyecto nuevo:
   - Nombre: `patitas`.
   - Contraseña de la base de datos: genérala y guárdala en un gestor de contraseñas (la app no la usa).
   - Región: la más cercana a Tijuana (costa oeste de Estados Unidos).
2. Espera a que termine de prepararse.

## Parte 3 · Tablas y reglas de seguridad

En el menú lateral de Supabase abre el **SQL Editor**. Para cada archivo: nueva consulta →
pega **todo** el contenido → ejecutar (**Run**). Debe decir "Success".

| Orden | Archivo | Veces |
|---|---|---|
| 1 | `supabase/migraciones/001_esquema_inicial.sql` | Una sola vez |
| 2 | `supabase/migraciones/002_alertas_patitas.sql` | Una sola vez |

Comprobación (nueva consulta):
```sql
select tablename, rowsecurity from pg_tables where schemaname = 'public' order by 1;
```
Deben aparecer **14 tablas**, todas con `true`.

## Parte 4 · Datos de prueba

1. Menú **Authentication** → **Users** → opción para agregar/crear usuario (no invitar):
   - Correo: `refugio.prueba@example.com`
   - Contraseña: la que quieras (anótala).
   - Si aparece la casilla para confirmar el correo automáticamente, márcala.
2. En el **SQL Editor**, ejecuta en este orden (se pueden repetir sin duplicar):
   1. `supabase/datos_prueba/datos_ficticios.sql`
   2. `supabase/datos_prueba/alerta_ficticia.sql`

## Parte 5 · Conectar la app

1. En Supabase, botón **Connect** (arriba). Si te pregunta cómo lo usarás, cualquier opción muestra
   los mismos valores. Ignora los comandos `npm` y `npx`: son para JavaScript.
2. **No uses "Copy all"**: copiaría la clave secreta. Copia solo:
   - `SUPABASE_URL`
   - `SUPABASE_PUBLISHABLE_KEY` (empieza con `sb_publishable_`)
3. En la terminal de Codespaces:
   ```bash
   cp .env.example .env
   ```
4. Abre `.env` y llena (sin comillas ni espacios):
   ```
   SUPABASE_URL=https://xxxxxxxx.supabase.co
   SUPABASE_CLAVE_PUBLICA=sb_publishable_xxxxxxxx
   ```
5. Genera la clave de Flask y pégala en `SECRET_KEY=`:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
6. Guarda con `Ctrl + S`.

## Parte 6 · Comprobar

```bash
python comprobar_supabase.py
```
Debe mostrar 5 pasos con ✓ y terminar en **"Todo listo"**.

```bash
flask --app app run --debug
```
Abre el puerto 5000 y revisa:
- No aparece la banda "Modo de ejemplo".
- Inicio: banda roja "Se busca a Chispa (prueba)".
- Adoptar: Canela, Michi, Rocky, Luna y Toby.
- Perdidos y encontrados: Pelusa y "Sin nombre".
- Refugios: uno verificado y uno pendiente.
- Detalle de la alerta: mapa con círculo naranja en el Centro.

Si dice "Address already in use": `pkill -f flask` y vuelve a arrancar.

## Parte 7 · Guardar en GitHub

```bash
git status
```
**`.env` no debe aparecer.** Si aparece, detente. Si no:
```bash
git add .
```
```bash
git commit -m "Patitas: etapas 1 y 2 y Alerta Patitas (parte A)"
```
```bash
git push
```

## Errores comunes

| Mensaje | Qué hacer |
|---|---|
| Falta SUPABASE_URL o SUPABASE_CLAVE_PUBLICA | Revisa `.env` y guárdalo |
| ¡Pusiste la clave SECRETA! | Cámbiala por la `sb_publishable_` |
| No se pudo consultar… | Revisa la clave y que corriste la migración 001 |
| No se pudieron leer las alertas | Ejecuta la migración 002 |
| Animales visibles: 0 | Ejecuta `datos_ficticios.sql` |
| Primero crea en Supabase el usuario… | Revisa el correo del usuario de prueba |
| type "…" already exists | Esa migración ya se había ejecutado: no la repitas |
| ModuleNotFoundError | `pip install -r requirements.txt` |
