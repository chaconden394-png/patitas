-- SOLO PARA PRUEBAS LOCALES: comprueba el archivo de datos ficticios.
\set ON_ERROR_STOP 1
insert into auth.users (email) values ('refugio.prueba@example.com');
\i supabase/datos_prueba/datos_ficticios.sql
\i supabase/datos_prueba/datos_ficticios.sql
begin;
set local role anon;
select pruebas.afirmar((select count(*) = 7 from public.animales a join public.perfiles p on p.id = a.responsable_id where p.nombre_publico = 'Refugio de prueba'), 'un visitante ve los 7 animales de prueba (sin duplicados)');
select pruebas.afirmar((select count(*) = 5 from public.animales a join public.perfiles p on p.id = a.responsable_id where p.nombre_publico = 'Refugio de prueba' and estado in ('disponible','urgente','en_proceso','hogar_temporal','recuperacion')), '5 animales en el catálogo de adopción');
select pruebas.afirmar((select count(*) = 2 from public.refugios where nombre like '%(prueba)'), 'se ven los 2 refugios de prueba');
rollback;
\echo '== DATOS DE PRUEBA OK'

-- Alerta ficticia (requiere la migración 002)
\i supabase/datos_prueba/alerta_ficticia.sql
\i supabase/datos_prueba/alerta_ficticia.sql
begin;
set local role anon;
select pruebas.afirmar((select count(*) = 1 from public.alertas where nombre_mascota = 'Chispa (prueba)'),
  'la alerta ficticia se crea una sola vez aunque se ejecute dos veces');
select pruebas.afirmar((select latitud_aprox = 32.51 from public.alertas where nombre_mascota = 'Chispa (prueba)'),
  'la alerta ficticia tiene su punto aproximado');
rollback;
\echo '== ALERTA FICTICIA OK'
