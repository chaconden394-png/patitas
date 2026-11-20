-- SOLO PARA PRUEBAS LOCALES. Comprueba la migración 005 (Etapa 4: animales y fotos).
-- Se ejecuta después de 10_pruebas_permisos.sql (usa sus funciones y personas de prueba).
\set ON_ERROR_STOP 1

-- Personas ficticias nuevas
insert into auth.users (id, email, raw_user_meta_data) values
 ('60000000-0000-0000-0000-000000000001', 'resc@ejemplo.test', '{"nombre_publico":"Rescatista Nueva","tipo_cuenta":"rescatista"}'),
 ('60000000-0000-0000-0000-000000000002', 'ref@ejemplo.test', '{"nombre_publico":"Refugio Nuevo","tipo_cuenta":"refugio"}'),
 ('60000000-0000-0000-0000-000000000003', 'bloq@ejemplo.test', '{"nombre_publico":"Cuenta Bloqueada","tipo_cuenta":"rescatista"}'),
 ('60000000-0000-0000-0000-000000000004', 'susp@ejemplo.test', '{"nombre_publico":"Refugio Suspendido","tipo_cuenta":"refugio"}'),
 ('60000000-0000-0000-0000-000000000005', 'adop@ejemplo.test', '{"nombre_publico":"Adoptante Nueva","tipo_cuenta":"adoptante"}');
-- Preparación como administrador del sistema
insert into public.bloqueos_publicacion (usuario_id, motivo)
  values ('60000000-0000-0000-0000-000000000003', 'Anuncios falsos (prueba)');
insert into public.refugios (id, responsable_id, nombre, estado_verificacion) values
 ('61000000-0000-0000-0000-000000000001', '60000000-0000-0000-0000-000000000002', 'Refugio Pendiente', 'pendiente'),
 ('61000000-0000-0000-0000-000000000002', '60000000-0000-0000-0000-000000000004', 'Refugio Castigado', 'suspendido'),
 ('61000000-0000-0000-0000-000000000003', '60000000-0000-0000-0000-000000000002', 'Refugio Rechazado 2', 'rechazado');

\echo '== Quién puede publicar'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000001"}';
select pruebas.afirmar(pruebas.filas($$insert into public.animales (responsable_id, nombre, especie, tamano, zona)
  values ('60000000-0000-0000-0000-000000000001','Pinto','perro','mediano','Otay')$$) = 1,
  'una rescatista recién registrada (sin verificar) puede publicar');
commit;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000002"}';
select pruebas.afirmar(pruebas.filas($$insert into public.animales (responsable_id, refugio_id, nombre, especie, tamano, zona)
  values ('60000000-0000-0000-0000-000000000002','61000000-0000-0000-0000-000000000001','Tomasa','gato','pequeño','Centro')$$) = 1,
  'un refugio pendiente de verificación puede publicar a nombre de su refugio');
select pruebas.debe_fallar($$insert into public.animales (responsable_id, refugio_id, nombre, especie, tamano, zona)
  values ('60000000-0000-0000-0000-000000000002','61000000-0000-0000-0000-000000000003','X','gato','pequeño','Centro')$$,
  'no puede publicar a nombre de su refugio rechazado');
rollback;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000003"}';
select pruebas.debe_fallar($$insert into public.animales (responsable_id, nombre, especie, tamano, zona)
  values ('60000000-0000-0000-0000-000000000003','X','perro','grande','Otay')$$, 'una cuenta bloqueada no puede publicar');
select pruebas.debe_fallar('select * from public.bloqueos_publicacion', 'nadie puede leer la lista de bloqueos desde la app');
select pruebas.debe_fallar($$delete from public.bloqueos_publicacion$$, 'nadie puede quitarse un bloqueo desde la app');
rollback;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000004"}';
select pruebas.debe_fallar($$insert into public.animales (responsable_id, nombre, especie, tamano, zona)
  values ('60000000-0000-0000-0000-000000000004','X','perro','grande','Otay')$$, 'un refugio suspendido no puede publicar');
rollback;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000005"}';
select pruebas.debe_fallar($$insert into public.animales (responsable_id, nombre, especie, tamano, zona)
  values ('60000000-0000-0000-0000-000000000005','X','perro','grande','Otay')$$, 'una cuenta de adoptante no puede publicar');
rollback;

\echo '== Límite de 10 animales nuevos en 24 horas'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000001"}';
insert into public.animales (responsable_id, nombre, especie, tamano, zona)
  select '60000000-0000-0000-0000-000000000001', 'Cachorro ' || n, 'perro', 'pequeño', 'Otay' from generate_series(1, 9) n;
select pruebas.debe_fallar($$insert into public.animales (responsable_id, nombre, especie, tamano, zona)
  values ('60000000-0000-0000-0000-000000000001','Once','perro','grande','Otay')$$, 'el animal número 11 del día se rechaza');
rollback;

\echo '== Editar y borrar'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000002"}';
select pruebas.afirmar(pruebas.filas($$delete from public.animales where nombre = 'Pinto'$$) = 0,
  'no puede borrar animales de otra persona');
rollback;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000001"}';
select pruebas.afirmar(pruebas.filas($$update public.animales set estado = 'adoptado' where nombre = 'Pinto'$$) = 1,
  'puede marcar su animal como adoptado');
select pruebas.afirmar(pruebas.filas($$delete from public.animales where nombre = 'Pinto'$$) = 1,
  'puede borrar su propio animal');
rollback;

-- Si la bloquean después de publicar: puede cerrar adopciones, pero no seguir editando
insert into public.bloqueos_publicacion (usuario_id, motivo)
  values ('60000000-0000-0000-0000-000000000001', 'Revisión (prueba)');
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000001"}';
select pruebas.debe_fallar($$update public.animales set nombre = 'Otro nombre', estado = 'disponible' where nombre = 'Pinto'$$,
  'una cuenta bloqueada no puede seguir editando sus anuncios');
select pruebas.afirmar(pruebas.filas($$update public.animales set estado = 'adoptado' where nombre = 'Pinto'$$) = 1,
  'una cuenta bloqueada sí puede marcar un animal como adoptado');
rollback;
delete from public.bloqueos_publicacion where usuario_id = '60000000-0000-0000-0000-000000000001';

\echo '== Fotos en Storage'
select pruebas.afirmar((select public and file_size_limit = 5242880 and allowed_mime_types = array['image/jpeg']
  from storage.buckets where id = 'fotos-animales'), 'existe fotos-animales: público, 5 MB, solo JPEG');
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000001"}';
select pruebas.afirmar(pruebas.filas($$insert into storage.objects (bucket_id, name)
  values ('fotos-animales', '60000000-0000-0000-0000-000000000001/bbbbbbbb-0000-4000-8000-000000000001.jpg')$$) = 1,
  'puede subir una foto a su propia carpeta');
select pruebas.debe_fallar($$insert into storage.objects (bucket_id, name)
  values ('fotos-animales', '60000000-0000-0000-0000-000000000002/robada.jpg')$$, 'no puede subir fotos a la carpeta de otra persona');
commit;
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000002"}';
select pruebas.afirmar(pruebas.filas($$delete from storage.objects
  where name like '60000000-0000-0000-0000-000000000001/%'$$) = 0, 'no puede borrar fotos de otra persona');
rollback;

\echo '== Fotos de un animal'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000001"}';
select pruebas.afirmar(pruebas.filas($$insert into public.animales_fotos (animal_id, ruta_archivo, orden)
  select id, '60000000-0000-0000-0000-000000000001/bbbbbbbb-0000-4000-8000-00000000000' || n || '.jpg', n - 1
  from public.animales, generate_series(1, 3) n where nombre = 'Pinto'$$) = 3, 'puede agregar 3 fotos a su animal');
select pruebas.debe_fallar($$insert into public.animales_fotos (animal_id, ruta_archivo)
  select id, '60000000-0000-0000-0000-000000000001/bbbbbbbb-0000-4000-8000-000000000004.jpg'
  from public.animales where nombre = 'Pinto'$$, 'la cuarta foto se rechaza');
select pruebas.afirmar(pruebas.filas($$update public.animales_fotos set orden = 5
  where ruta_archivo like '%000000000003.jpg'$$) = 1, 'puede cambiar el orden (foto principal)');
select pruebas.afirmar(pruebas.filas($$delete from public.animales_fotos
  where ruta_archivo like '%000000000003.jpg'$$) = 1, 'puede borrar una foto');
select pruebas.debe_fallar($$insert into public.animales_fotos (animal_id, ruta_archivo)
  select id, '60000000-0000-0000-0000-000000000002/bbbbbbbb-0000-4000-8000-000000000009.jpg'
  from public.animales where nombre = 'Pinto'$$, 'no puede usar una foto de la carpeta de otra persona');
select pruebas.debe_fallar($$insert into public.animales_fotos (animal_id, ruta_archivo)
  select id, '../fotos-alertas/algo.jpg' from public.animales where nombre = 'Pinto'$$,
  'rechaza rutas de foto con formato raro');
select pruebas.debe_fallar($$insert into public.animales_fotos (animal_id, ruta_archivo)
  select id, '60000000-0000-0000-0000-000000000001/bbbbbbbb-0000-4000-8000-000000000001.jpg'
  from public.animales where nombre = 'Pinto'$$, 'la misma foto no se puede registrar dos veces');
rollback;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"60000000-0000-0000-0000-000000000002"}';
select pruebas.debe_fallar($$insert into public.animales_fotos (animal_id, ruta_archivo)
  select id, '60000000-0000-0000-0000-000000000002/bbbbbbbb-0000-4000-8000-000000000008.jpg'
  from public.animales where nombre = 'Pinto'$$, 'no puede agregar fotos al animal de otra persona');
rollback;

begin;
set local role anon;
select pruebas.afirmar((select count(*) >= 1 from public.animales where nombre = 'Pinto'),
  'un visitante ve los animales publicados');
select pruebas.debe_fallar($$delete from public.animales where nombre = 'Pinto'$$, 'un visitante no puede borrar animales');
rollback;

\echo '== TODAS LAS PRUEBAS DE ANIMALES PASARON'
