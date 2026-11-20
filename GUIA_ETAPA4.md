# Guía · Etapa 4: animales y fotos

Requisitos: Etapa 3 (cuentas) y Alerta Patitas Parte B funcionando.

## Qué agrega esta etapa
- **Mi panel → Mis animales**: publicar, editar, cambiar estado (por ejemplo "Adoptado") y borrar.
- **Fotos**: hasta 3 por animal, con foto principal. Se les quita la ubicación GPS y otros datos ocultos.
- **Mi refugio** (solo cuentas de refugio): datos públicos y dirección **privada**. Queda "Pendiente de verificación".
- **Ficha del animal**: galería, convivencia, salud, requisitos, quién lo cuida e insignia **"Sin verificar"**.
- **Catálogo**: filtros de edad, vacunas, esterilización y convivencia; páginas de 12 en 12.

## Paso 1 · Actualiza los archivos
Sube `patitas-etapa4.zip` a la raíz de tu Codespace y ejecuta, uno por uno:
```bash
unzip -o patitas-etapa4.zip
```
```bash
rm patitas-etapa4.zip
```
```bash
python -m pytest -q
```
Debe decir **147 passed**. Tu `.env` no se toca. No hay librerías nuevas.

## Paso 2 · Migración 005
SQL Editor de Supabase → **New query** → pega todo `supabase/migraciones/005_animales_fotos.sql` → **Run** (una sola vez).

Debe decir "Success. No rows returned". Después abre **Storage** en el menú de Supabase: debe aparecer
`fotos-animales` marcado como **Public**, junto a `fotos-alertas`.

> Si aparece un error, no la ejecutes otra vez: envíame el mensaje exacto.

## Paso 3 · Comprueba
```bash
python comprobar_supabase.py
```
Deben salir **8 pasos con ✓** (el nuevo es "Revisando animales y fotos (migración 005)").

```bash
pkill -f flask
```
```bash
flask --app app run --debug
```
Si el puerto 5000 no aparece en **Puertos**: "Reenviar un puerto" → `5000`.

## Paso 4 · Pruebas manuales
Usa una cuenta de tipo **Refugio** (o crea una nueva en "Crear cuenta" eligiendo Refugio).
Las cuentas de adoptante no ven "Mi panel".

**Mi refugio**
1. Menú con tu nombre → **Mi panel** → **Registrar mi refugio**. Llena nombre, zona y, si quieres, la dirección → **Registrar refugio**.
   Debe decir "Pendiente de verificación".
2. Menú **Refugios**: tu refugio aparece como "Pendiente de verificación" y **sin la dirección**.

**Publicar**
3. Mi panel → **Publicar un animal** → llena los datos (usa un animal ficticio para probar) → **Publicar y agregar fotos**.
4. Elige 1 a 3 fotos → **Subir fotos**. Prueba **Hacer principal** y el botón de borrar 🗑.
5. **Ver su ficha pública**: galería, convivencia, "Lo cuida: (tu refugio)" e insignia **Sin verificar**.
6. Menú **Adoptar**: aparece con su foto. Prueba los filtros nuevos (Edad, "Convive con niñas y niños"…).

**Estados y borrar**
7. Mis animales → cambia el estado a **Adoptado** → **Cambiar**. Ya no sale en Adoptar, pero su ficha dice "¡Este animal ya encontró hogar!".
8. Publica otro animal de prueba y **Borrar** → confirma. Desaparece junto con sus fotos (revisa Storage → `fotos-animales`).

**Privacidad (importante)**
9. Si tu foto tenía ubicación GPS: abre la foto publicada (clic derecho → abrir imagen en otra pestaña → guardar)
   y revisa sus propiedades/detalles: ya no debe tener ubicación.
10. Con **otra cuenta** (o sin sesión) abre la ficha: no debe haber botones de editar ni dirección.

## Aprobar un refugio (lo hace un administrador, a mano)
La aprobación nunca es automática. Cuando revises los documentos de un refugio, en el SQL Editor:
```sql
select id, nombre, estado_verificacion from public.refugios order by creado_en desc;
```
```sql
update public.refugios set estado_verificacion = 'verificado', verificado_en = now()
where id = 'PEGA-AQUI-EL-ID';
```
Sus animales cambian de "Sin verificar" a "Publicado por cuenta verificada".

## Bloquear a una cuenta que publica anuncios falsos
```sql
insert into public.bloqueos_publicacion (usuario_id, motivo)
values ('PEGA-AQUI-EL-ID-DEL-USUARIO', 'Explica brevemente el motivo');
```
Para quitar el bloqueo: `delete from public.bloqueos_publicacion where usuario_id = '...';`
Una cuenta bloqueada no puede publicar ni editar, pero sí marcar sus animales como adoptados.
Para ocultar un anuncio concreto: `update public.animales set oculto = true where id = '...';`

## Errores comunes
| Lo que ves | Qué hacer |
|---|---|
| "Esa sección es para otro tipo de cuenta" | Entraste con una cuenta de adoptante. Usa una de refugio o rescatista |
| "Tu cuenta no puede publicar animales en este momento" | ¿Ejecutaste la migración 005? Si sí, revisa que la cuenta no esté en `bloqueos_publicacion` |
| "No pudimos subir la foto" | Revisa que exista `fotos-animales` en Storage (Paso 2). Copia la línea `WARNING` de la terminal |
| "No pudimos leer la foto" | Usa JPG, PNG o WebP. Las fotos HEIC de iPhone: haz captura de pantalla o conviértelas |
| "Llegaste al límite de 10 animales nuevos en 24 horas" | Es un límite contra spam. Espera 24 horas o borra animales de prueba que publicaste hoy |
| La página de Adoptar muestra "No pudimos cargar la información" | Copia el error de la terminal y envíamelo |
| "Falta la migración 005" | Paso 2 |
