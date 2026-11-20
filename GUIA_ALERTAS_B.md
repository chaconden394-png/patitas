# Guía · Alerta Patitas, Parte B

Requisito: Etapa 3 funcionando (cuentas y correo).

## Paso 1 · Actualiza los archivos
Sube `patitas-alertas-b.zip` a la raíz de tu Codespace y ejecuta, uno por uno:
```bash
unzip -o patitas-alertas-b.zip
```
```bash
rm patitas-alertas-b.zip
```
```bash
pip install -r requirements.txt
```
(instala **Pillow**, la librería que limpia las fotos)
```bash
python -m pytest -q
```
Debe decir **113 passed**. Tu `.env` no se toca.

## Paso 2 · Migración 004
SQL Editor de Supabase → nueva consulta → pega todo `supabase/migraciones/004_alertas_parte_b.sql` → Run (una sola vez).

Crea el contenedor de fotos **fotos-alertas** y sus reglas. Para comprobarlo, en el menú de Supabase abre
**Storage**: debe aparecer `fotos-alertas` marcado como público.

> Si al ejecutarla aparece un error que menciona `storage.buckets` o `storage.objects`, envíame el mensaje exacto.

## Paso 3 · Comprueba
```bash
python comprobar_supabase.py
```
Deben salir **7 pasos con ✓**.

```bash
pkill -f flask
```
```bash
flask --app app run --debug
```
Si el puerto 5000 no aparece en **Puertos**: "Reenviar un puerto" → `5000`.

## Paso 4 · Pruebas manuales
Necesitas **dos cuentas**: la tuya (dueña) y otra (vecina). Para la segunda usa otro correo tuyo o crea un usuario
en Authentication → Users con confirmación automática.

**Como la vecina**
1. Menú con tu nombre → **Mi zona de alertas** → toca el mapa cerca del Centro (o "Usar mi ubicación") → **Guardar mi zona**.

**Como la dueña** (cierra sesión y entra con tu cuenta)
2. **Alertas** → **Emitir una alerta** → elige una foto, llena los datos y toca el mapa en el Centro → **Emitir alerta**.
   Debe decir "Tu alerta está activa. Avisamos a 1 persona…".
3. Comprueba que se ve la foto.

**Como la vecina**
4. La **campana** 🔔 debe mostrar **1**. Ábrela → toca la alerta.
5. **Lo vi** → escribe dónde → (opcional) marca el punto → **Enviar aviso a la familia**.

**Como la dueña**
6. La campana muestra el aviso. En la alerta, sección **Avistamientos (1)**, y un punto azul en el mapa.
7. **Cerrar la alerta** → **¡Ya apareció!** → la vecina recibe "¡… ya está en casa!".
8. Menú → **Mis alertas**: aparece como "Encontrada".

**Privacidad (importante)**
9. Si tu foto tenía ubicación GPS: descarga la foto publicada (clic derecho → guardar) y revisa sus
   propiedades/detalles: ya no debe tener ubicación.
10. Como la vecina, en la alerta NO debe aparecer la lista de avistamientos.

## Errores comunes
| Lo que ves | Qué hacer |
|---|---|
| "No pudimos subir la foto" | Revisa que la migración 004 creó `fotos-alertas` (Storage). Copia la línea `WARNING` de la terminal |
| "No pudimos leer la foto" | Usa JPG o PNG. Las fotos HEIC de iPhone: haz captura de pantalla o conviértelas |
| "Avisamos…" no aparece; dice que nadie tiene alertas en esa zona | La vecina no guardó su zona, o está a más de 15 km |
| "Ya tienes 2 alertas activas" | Cierra una desde la alerta (Cerrar la alerta) |
| "Usar mi ubicación" no hace nada | El navegador pide permiso: acéptalo. O toca el mapa |
| El mapa sale gris | Revisa tu conexión; recarga la página |
| "Falta la migración 004" | Paso 2 |
