-- SOLO PARA PRUEBAS LOCALES. Comprueba la migración 004 (Alerta Patitas, Parte B).
-- Se ejecuta después de 10_ y 30_ (usa sus funciones y personas de prueba).
\set ON_ERROR_STOP 1

\echo '== Contenedor de fotos'
select pruebas.afirmar((select public and file_size_limit = 5242880 and allowed_mime_types = array['image/jpeg']
  from storage.buckets where id = 'fotos-alertas'), 'existe fotos-alertas: público, 5 MB, solo JPEG');

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000002"}';
select pruebas.afirmar(pruebas.filas($$insert into storage.objects (bucket_id, name)
  values ('fotos-alertas', '30000000-0000-0000-0000-000000000002/aaaaaaaa-0000-4000-8000-000000000001.jpg')$$) = 1,
  'puede subir una foto a su propia carpeta');
select pruebas.debe_fallar($$insert into storage.objects (bucket_id, name)
  values ('fotos-alertas', '30000000-0000-0000-0000-000000000003/robada.jpg')$$, 'no puede subir fotos a la carpeta de otra persona');
select pruebas.debe_fallar($$insert into storage.objects (bucket_id, name)
  values ('fotos-alertas', 'suelta.jpg')$$, 'no puede subir fotos fuera de una carpeta');
commit;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000003"}';
select pruebas.afirmar(pruebas.filas($$delete from storage.objects
  where name like '30000000-0000-0000-0000-000000000002/%'$$) = 0, 'no puede borrar fotos de otra persona');
rollback;

\echo '== Emitir alerta en una sola operación'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000002"}';
select pruebas.afirmar((select public.emitir_alerta(
    'Firulais', 'perro', '', 'macho', 'mediano', '2 años', 'Negro', 'Mancha en el ojo', '', 'Salió corriendo',
    '30000000-0000-0000-0000-000000000002/aaaaaaaa-0000-4000-8000-000000000001.jpg',
    'Zona Río', now() - interval '1 hour', true, 32.53, -117.02)) is not null, 'emite la alerta y devuelve su id');
select pruebas.afirmar((select raza = 'No especificada' and emisor_id = '30000000-0000-0000-0000-000000000002'
  and collar is null from public.alertas where nombre_mascota = 'Firulais'),
  'guarda a la persona como emisora y limpia campos vacíos');
select pruebas.afirmar((select count(*) = 1 from public.alertas_ubicacion u join public.alertas a on a.id = u.alerta_id
  where a.nombre_mascota = 'Firulais'), 'guarda la ubicación en la misma operación');
commit;
select pruebas.afirmar((select count(*) >= 2 from public.notificaciones n join public.alertas a on a.id = n.alerta_id
  where a.nombre_mascota = 'Firulais' and n.tipo = 'alerta_cercana'), 'avisa a las personas cercanas (regla de 15 km)');

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000003"}';
select pruebas.debe_fallar($$select public.emitir_alerta('X', 'perro', '', 'macho', 'mediano', '', 'Negro', '', '', '',
    '30000000-0000-0000-0000-000000000002/aaaaaaaa-0000-4000-8000-000000000001.jpg', 'Centro', now(), false, 32.5, -117.0)$$,
  'no puede usar la foto de otra persona');
select pruebas.debe_fallar($$select public.emitir_alerta('X', 'perro', '', 'macho', 'mediano', '', 'Negro', '', '', '',
    '../../otra/ruta.jpg', 'Centro', now(), false, 32.5, -117.0)$$, 'rechaza rutas de foto con formato raro');
select pruebas.debe_fallar($$select public.emitir_alerta('X', 'perro', '', 'macho', 'mediano', '', 'Negro', '', '', '',
    null, 'Centro', now(), false, 999, -117.0)$$, 'con una ubicación inválida no se guarda nada');
select pruebas.afirmar(not exists (select 1 from public.alertas where nombre_mascota = 'X'),
  'si falla la ubicación, la alerta tampoco queda guardada');
rollback;

begin;
set local role anon;
select pruebas.debe_fallar($$select public.emitir_alerta('X', 'perro', '', 'macho', 'mediano', '', 'Negro', '', '', '',
    null, 'Centro', now(), false, 32.5, -117.0)$$, 'un visitante no puede emitir alertas');
select pruebas.debe_fallar($$select public.renovar_alerta('40000000-0000-0000-0000-000000000001')$$,
  'un visitante no puede renovar alertas');
rollback;

\echo '== Renovar alertas'
-- Preparación (como administrador del sistema): una alerta que vence en 3 días y otra recién creada.
update public.alertas set expira_en = now() + interval '3 days' where nombre_mascota = 'Firulais';
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000002"}';
select pruebas.afirmar((select public.renovar_alerta(id) > now() + interval '29 days' from public.alertas
  where nombre_mascota = 'Firulais'), 'puede renovar su alerta cuando faltan 7 días o menos');
select pruebas.debe_fallar($$select public.renovar_alerta(id) from public.alertas where nombre_mascota = 'Firulais'$$,
  'no puede renovarla otra vez si aún faltan más de 7 días');
rollback;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000003"}';
select pruebas.debe_fallar($$select public.renovar_alerta(id) from public.alertas where nombre_mascota = 'Firulais'$$,
  'no puede renovar la alerta de otra persona');
rollback;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000001"}';
select pruebas.debe_fallar($$select public.renovar_alerta('40000000-0000-0000-0000-000000000001')$$,
  'no puede renovar una alerta cerrada (encontrada)');
rollback;

\echo '== TODAS LAS PRUEBAS DE LA PARTE B PASARON'
