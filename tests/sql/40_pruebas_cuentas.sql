-- SOLO PARA PRUEBAS LOCALES. Comprueba la migración 003 (cuentas).
-- Se ejecuta después de 10_pruebas_permisos.sql (usa sus funciones de prueba).
\set ON_ERROR_STOP 1

insert into auth.users (id, email, raw_user_meta_data) values
 ('50000000-0000-0000-0000-000000000001', 'acepta@ejemplo.test',
   '{"nombre_publico":"  Lucía Prueba  ","tipo_cuenta":"voluntario","acepto_aviso_privacidad":true}'),
 ('50000000-0000-0000-0000-000000000002', 'noacepta@ejemplo.test',
   '{"nombre_publico":"Sin Consentimiento","tipo_cuenta":"refugio"}'),
 ('50000000-0000-0000-0000-000000000003', 'admin2@ejemplo.test',
   '{"nombre_publico":"Quiere Ser Admin","tipo_cuenta":"administrador","acepto_aviso_privacidad":"true"}');

\echo '== Registro con consentimiento'
select pruebas.afirmar((select acepto_aviso_privacidad_en is not null from public.perfiles_privados
  where id = '50000000-0000-0000-0000-000000000001'), 'si aceptó el aviso, se guarda la fecha');
select pruebas.afirmar((select acepto_aviso_privacidad_en is null from public.perfiles_privados
  where id = '50000000-0000-0000-0000-000000000002'), 'si no lo aceptó, la fecha queda vacía');
select pruebas.afirmar((select nombre_publico = 'Lucía Prueba' and tipo_cuenta = 'voluntario' from public.perfiles
  where id = '50000000-0000-0000-0000-000000000001'), 'guarda nombre sin espacios extra y el tipo elegido');
select pruebas.afirmar((select tipo_cuenta = 'refugio' from public.perfiles
  where id = '50000000-0000-0000-0000-000000000002'), 'se puede registrar como refugio');
select pruebas.afirmar((select tipo_cuenta = 'adoptante' from public.perfiles
  where id = '50000000-0000-0000-0000-000000000003'), 'pedir "administrador" al registrarse da una cuenta de adoptante');
select pruebas.afirmar(not exists (select 1 from public.administradores
  where usuario_id = '50000000-0000-0000-0000-000000000003'), 'registrarse nunca crea administradores');
select pruebas.afirmar((select nivel_verificacion = 'registrada' from public.perfiles
  where id = '50000000-0000-0000-0000-000000000001'), 'toda cuenta nueva empieza como "registrada"');

\echo '== El consentimiento no se puede falsificar'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"50000000-0000-0000-0000-000000000002"}';
select pruebas.debe_fallar($$update public.perfiles_privados set acepto_aviso_privacidad_en = '2020-01-01'
  where id = '50000000-0000-0000-0000-000000000002'$$, 'no puede escribir una fecha de aceptación inventada');
select pruebas.afirmar(public.aceptar_aviso_privacidad() is not null, 'puede aceptar el aviso con la función');
select pruebas.afirmar((select acepto_aviso_privacidad_en = now() from public.perfiles_privados),
  'la función guarda la hora actual');
select pruebas.afirmar(pruebas.filas($$update public.perfiles_privados set telefono = '6640009999'
  where id = '50000000-0000-0000-0000-000000000002'$$) = 1, 'sigue pudiendo cambiar su teléfono');
rollback;

begin;
set local role anon;
select pruebas.debe_fallar('select public.aceptar_aviso_privacidad()', 'un visitante no puede usar la función de aceptación');
rollback;

\echo '== TODAS LAS PRUEBAS DE CUENTAS PASARON'
