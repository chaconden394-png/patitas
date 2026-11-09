-- SOLO PARA PRUEBAS LOCALES. Comprueba la migración 002 (Alerta Patitas).
-- Se ejecuta después de 10_pruebas_permisos.sql (usa sus funciones de prueba).
\set ON_ERROR_STOP 1

-- Personas ficticias y sus zonas de alerta (distancia al centro de Tijuana)
insert into auth.users (id, email, raw_user_meta_data) values
 ('30000000-0000-0000-0000-000000000001', 'emisora@ejemplo.test', '{"nombre_publico":"Dueña Prueba"}'),
 ('30000000-0000-0000-0000-000000000002', 'zonario@ejemplo.test', '{"nombre_publico":"Vecino Zona Río"}'),
 ('30000000-0000-0000-0000-000000000003', 'playas@ejemplo.test', '{"nombre_publico":"Vecina Playas"}'),
 ('30000000-0000-0000-0000-000000000004', 'rosarito@ejemplo.test', '{"nombre_publico":"Vecino Rosarito"}'),
 ('30000000-0000-0000-0000-000000000005', 'norte1@ejemplo.test', '{"nombre_publico":"Límite Dentro"}'),
 ('30000000-0000-0000-0000-000000000006', 'norte2@ejemplo.test', '{"nombre_publico":"Límite Fuera"}'),
 ('30000000-0000-0000-0000-000000000007', 'otay@ejemplo.test', '{"nombre_publico":"Otay Sin Alertas"}'),
 ('30000000-0000-0000-0000-000000000008', 'sandiego@ejemplo.test', '{"nombre_publico":"Vecina San Diego"}'),
 ('30000000-0000-0000-0000-000000000009', 'sinzona@ejemplo.test', '{"nombre_publico":"Sin Zona"}');

insert into public.zonas_alerta (usuario_id, latitud, longitud, acepta_alertas) values
 ('30000000-0000-0000-0000-000000000001', 32.5149, -117.0382, true),  -- la emisora (no se avisa a sí misma)
 ('30000000-0000-0000-0000-000000000002', 32.53, -117.02, true),      -- Zona Río      2.4 km
 ('30000000-0000-0000-0000-000000000003', 32.53, -117.12, true),      -- Playas        7.9 km
 ('30000000-0000-0000-0000-000000000004', 32.36, -117.06, true),      -- Rosarito     17.4 km
 ('30000000-0000-0000-0000-000000000005', 32.64, -117.04, true),      -- límite       13.9 km
 ('30000000-0000-0000-0000-000000000006', 32.65, -117.04, true),      -- límite       15.02 km
 ('30000000-0000-0000-0000-000000000007', 32.53, -116.97, false),     -- Otay 6.6 km, NO acepta
 ('30000000-0000-0000-0000-000000000008', 32.72, -117.16, true);      -- San Diego    25.5 km
update public.perfiles_privados set telefono = '6640001122' where id = '30000000-0000-0000-0000-000000000001';

\echo '== Distancias y zonas'
select pruebas.afirmar(round(public.distancia_km(32.5149, -117.0382, 32.53, -117.12), 1) = 7.9, 'la fórmula calcula 7.9 km del centro a Playas');
select pruebas.afirmar((select latitud = 32.51 and longitud = -117.04 from public.zonas_alerta
  where usuario_id = '30000000-0000-0000-0000-000000000001'), 'la zona se guarda redondeada (≈ 1 km)');

\echo '== La dueña emite una alerta'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000001"}';
insert into public.alertas (emisor_id, nombre_mascota, especie, tamano, sexo, color, senas_particulares,
                            zona_referencia, visto_por_ultima_vez, mostrar_telefono)
values ('30000000-0000-0000-0000-000000000001', 'Chispa', 'perro',
        'pequeño', 'hembra', 'café con blanco', 'Oreja izquierda doblada', 'Centro, cerca del Parque Teniente Guerrero',
        now() - interval '2 hours', false);
select pruebas.debe_fallar($$insert into public.alertas (emisor_id, nombre_mascota, especie, tamano, color, zona_referencia, visto_por_ultima_vez)
  values ('30000000-0000-0000-0000-000000000002','X','perro','grande','negro','Centro', now())$$,
  'no puede emitir una alerta a nombre de otra persona');
commit;
-- Solo para que las pruebas usen un id fijo (la app nunca puede elegirlo).
update public.alertas set id = '40000000-0000-0000-0000-000000000001' where nombre_mascota = 'Chispa';

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000001"}';
insert into public.alertas_ubicacion (alerta_id, latitud, longitud)
values ('40000000-0000-0000-0000-000000000001', 32.5149, -117.0382);
select pruebas.debe_fallar($$update public.alertas set latitud_aprox = 32.0
  where id = '40000000-0000-0000-0000-000000000001'$$, 'no puede cambiar el punto público aproximado');
select pruebas.debe_fallar($$update public.alertas set oculta = false
  where id = '40000000-0000-0000-0000-000000000001'$$, 'no puede cambiar la ocultación de moderación');
select pruebas.debe_fallar($$update public.alertas set radio_km = 50
  where id = '40000000-0000-0000-0000-000000000001'$$, 'no puede ampliar el radio de 15 km');
select pruebas.debe_fallar($$insert into public.alertas_ubicacion (alerta_id, latitud, longitud)
  values ('40000000-0000-0000-0000-000000000001', 32.0, -117.0)$$, 'no puede registrar un segundo punto para la misma alerta');
commit;

\echo '== Regla de 15 km'
select pruebas.afirmar((select count(*) = 3 from public.notificaciones
  where alerta_id = '40000000-0000-0000-0000-000000000001' and tipo = 'alerta_cercana'), 'se avisó exactamente a 3 personas');
select pruebas.afirmar((select array_agg(usuario_id order by usuario_id) = array[
    '30000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000003',
    '30000000-0000-0000-0000-000000000005']::uuid[]
  from public.notificaciones where alerta_id = '40000000-0000-0000-0000-000000000001'),
  'recibieron aviso: Zona Río (2.4 km), Playas (7.9 km) y el límite de 13.9 km');
select pruebas.afirmar(not exists (select 1 from public.notificaciones
  where usuario_id = '30000000-0000-0000-0000-000000000006'), 'NO recibe aviso quien está a 15.02 km');
select pruebas.afirmar(not exists (select 1 from public.notificaciones
  where usuario_id in ('30000000-0000-0000-0000-000000000004', '30000000-0000-0000-0000-000000000008')),
  'NO reciben aviso Rosarito (17 km) ni San Diego (25 km)');
select pruebas.afirmar(not exists (select 1 from public.notificaciones
  where usuario_id = '30000000-0000-0000-0000-000000000007'), 'NO recibe aviso quien desactivó las alertas');
select pruebas.afirmar(not exists (select 1 from public.notificaciones
  where usuario_id = '30000000-0000-0000-0000-000000000001' and tipo = 'alerta_cercana'), 'la emisora no se avisa a sí misma');
select pruebas.afirmar((select titulo = 'Alerta Patitas: se busca a Chispa' from public.notificaciones
  where usuario_id = '30000000-0000-0000-0000-000000000002'), 'la notificación tiene el nombre de la mascota');

\echo '== Visitante sin sesión'
begin;
set local role anon;
select pruebas.afirmar((select count(*) = 1 from public.alertas where id = '40000000-0000-0000-0000-000000000001'), 've la alerta');
select pruebas.afirmar((select latitud_aprox = 32.51 and longitud_aprox = -117.04 from public.alertas
  where id = '40000000-0000-0000-0000-000000000001'), 'solo ve el punto aproximado');
select pruebas.afirmar(public.personas_avisadas('40000000-0000-0000-0000-000000000001') = 3, 've cuántas personas fueron avisadas');
select pruebas.debe_fallar('select * from public.alertas_ubicacion', 'no puede ver el punto exacto');
select pruebas.debe_fallar('select * from public.zonas_alerta', 'no puede ver zonas de alerta');
select pruebas.debe_fallar('select * from public.notificaciones', 'no puede ver notificaciones');
select pruebas.debe_fallar($$select public.telefono_contacto_alerta('40000000-0000-0000-0000-000000000001')$$,
  'no puede pedir el teléfono del dueño');
rollback;

\echo '== Vecino de Zona Río (recibió la alerta)'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000002"}';
select pruebas.afirmar((select count(*) = 1 from public.notificaciones), 've solo su propia notificación');
select pruebas.afirmar((select count(*) = 1 from public.zonas_alerta), 've solo su propia zona');
select pruebas.afirmar((select count(*) = 0 from public.alertas_ubicacion), 'no ve el punto exacto de la alerta');
select pruebas.afirmar(pruebas.filas('update public.notificaciones set leida = true') = 1, 'puede marcar su notificación como leída');
select pruebas.debe_fallar($$update public.notificaciones set titulo = 'falso'$$, 'no puede cambiar el texto de una notificación');
select pruebas.debe_fallar($$insert into public.notificaciones (usuario_id, tipo, titulo, cuerpo)
  values ('30000000-0000-0000-0000-000000000003','alerta_cercana','Spam','Spam')$$, 'no puede crear notificaciones para otros');
select pruebas.debe_fallar($$insert into public.zonas_alerta (usuario_id, latitud, longitud)
  values ('30000000-0000-0000-0000-000000000009', 32.5, -117.0)$$, 'no puede crear la zona de otra persona');
select pruebas.afirmar(public.telefono_contacto_alerta('40000000-0000-0000-0000-000000000001') is null,
  'no recibe el teléfono si la dueña no lo autorizó');
select pruebas.afirmar(pruebas.filas($$update public.alertas set descripcion = 'hackeado'
  where id = '40000000-0000-0000-0000-000000000001'$$) = 0, 'no puede editar la alerta de otra persona');
select pruebas.afirmar(pruebas.filas($$insert into public.avistamientos (alerta_id, reportado_por, lugar, visto_en, latitud, longitud)
  values ('40000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000002',
          'Calle Segunda y Constitución', now() - interval '20 minutes', 32.5330, -117.0360)$$) = 1,
  'puede reportar un avistamiento ("Lo vi")');
select pruebas.debe_fallar($$insert into public.avistamientos (alerta_id, reportado_por, lugar, visto_en)
  values ('40000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000003', 'Centro', now())$$,
  'no puede reportar a nombre de otra persona');
insert into public.avistamientos (alerta_id, reportado_por, lugar, visto_en)
  select '40000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002', 'Centro ' || g, now()
  from generate_series(1, 4) g;
select pruebas.debe_fallar($$insert into public.avistamientos (alerta_id, reportado_por, lugar, visto_en)
  values ('40000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000002', 'Centro 6', now())$$,
  'el sexto avistamiento en 24 horas se rechaza (anti-spam)');
commit;

\echo '== La dueña revisa y autoriza su teléfono'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000001"}';
select pruebas.afirmar((select count(*) = 5 from public.avistamientos), 've los avistamientos de su alerta');
select pruebas.afirmar((select count(*) = 5 from public.notificaciones where tipo = 'avistamiento'),
  'recibió una notificación por cada avistamiento');
select pruebas.afirmar((select count(*) = 1 from public.alertas_ubicacion), 've el punto exacto de su propia alerta');
select pruebas.debe_fallar($$insert into public.avistamientos (alerta_id, reportado_por, lugar, visto_en)
  values ('40000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000001', 'Mi casa', now())$$,
  'no puede reportar avistamientos de su propia alerta');
update public.alertas set mostrar_telefono = true where id = '40000000-0000-0000-0000-000000000001';
commit;

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000003"}';
select pruebas.afirmar(public.telefono_contacto_alerta('40000000-0000-0000-0000-000000000001') = '6640001122',
  'con autorización, una persona con sesión iniciada recibe el teléfono');
select pruebas.afirmar((select count(*) = 0 from public.avistamientos), 'no ve avistamientos que reportaron otras personas');
rollback;

\echo '== Límites contra abuso'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000001"}';
insert into public.alertas (emisor_id, nombre_mascota, especie, tamano, color, zona_referencia, visto_por_ultima_vez)
values ('30000000-0000-0000-0000-000000000001', 'Segunda', 'gato', 'pequeño', 'negro', 'Centro', now());
select pruebas.debe_fallar($$insert into public.alertas (emisor_id, nombre_mascota, especie, tamano, color, zona_referencia, visto_por_ultima_vez)
  values ('30000000-0000-0000-0000-000000000001','Tercera','gato','pequeño','gris','Centro', now())$$,
  'no puede tener más de 2 alertas activas');
update public.alertas set estado = 'cancelada' where nombre_mascota = 'Segunda';
insert into public.alertas (emisor_id, nombre_mascota, especie, tamano, color, zona_referencia, visto_por_ultima_vez)
values ('30000000-0000-0000-0000-000000000001', 'Tercera', 'gato', 'pequeño', 'gris', 'Centro', now());
update public.alertas set estado = 'cancelada' where nombre_mascota = 'Tercera';
select pruebas.debe_fallar($$insert into public.alertas (emisor_id, nombre_mascota, especie, tamano, color, zona_referencia, visto_por_ultima_vez)
  values ('30000000-0000-0000-0000-000000000001','Cuarta','gato','pequeño','gris','Centro', now())$$,
  'no puede emitir más de 3 alertas en 24 horas (aunque cancele)');
select pruebas.debe_fallar($$insert into public.alertas (emisor_id, nombre_mascota, especie, tamano, color, zona_referencia, visto_por_ultima_vez)
  values ('30000000-0000-0000-0000-000000000001','Futuro','gato','pequeño','gris','Centro', now() + interval '3 days')$$,
  'rechaza una fecha de extravío en el futuro');
rollback;

\echo '== ¡Encontrada!'
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000001"}';
update public.alertas set estado = 'encontrada' where id = '40000000-0000-0000-0000-000000000001';
select pruebas.afirmar((select cerrada_en is not null from public.alertas where id = '40000000-0000-0000-0000-000000000001'),
  'se registra la fecha de cierre');
select pruebas.debe_fallar($$update public.alertas set estado = 'activa' where id = '40000000-0000-0000-0000-000000000001'$$,
  'una alerta cerrada no se puede reabrir');
commit;
select pruebas.afirmar((select count(*) = 3 from public.notificaciones
  where alerta_id = '40000000-0000-0000-0000-000000000001' and tipo = 'alerta_cerrada'),
  'se avisa "¡ya está en casa!" a las 3 personas que recibieron la alerta');
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"30000000-0000-0000-0000-000000000003"}';
select pruebas.afirmar(public.telefono_contacto_alerta('40000000-0000-0000-0000-000000000001') is null,
  'al cerrar la alerta, el teléfono deja de entregarse');
select pruebas.debe_fallar($$insert into public.avistamientos (alerta_id, reportado_por, lugar, visto_en)
  values ('40000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000003', 'Centro', now())$$,
  'no se aceptan avistamientos de una alerta cerrada');
rollback;

\echo '== Moderación y vencimiento'
-- Como administrador del sistema (editor SQL): una alerta oculta y una vencida
insert into public.alertas (id, emisor_id, nombre_mascota, especie, tamano, color, zona_referencia, visto_por_ultima_vez, oculta)
values ('40000000-0000-0000-0000-000000000004', '30000000-0000-0000-0000-000000000003', 'Oculta', 'perro', 'grande', 'negro', 'Playas', now(), true);
insert into public.alertas_ubicacion values ('40000000-0000-0000-0000-000000000004', 32.53, -117.12);
insert into public.alertas (id, emisor_id, nombre_mascota, especie, tamano, color, zona_referencia, visto_por_ultima_vez, creada_en, expira_en)
values ('40000000-0000-0000-0000-000000000005', '30000000-0000-0000-0000-000000000003', 'Vencida', 'perro', 'grande', 'negro', 'Playas',
        now() - interval '40 days', now() - interval '40 days', now() - interval '10 days');
insert into public.alertas_ubicacion values ('40000000-0000-0000-0000-000000000005', 32.53, -117.12);
select pruebas.afirmar(not exists (select 1 from public.notificaciones
  where alerta_id in ('40000000-0000-0000-0000-000000000004', '40000000-0000-0000-0000-000000000005')),
  'las alertas ocultas o vencidas no envían avisos');
begin;
set local role anon;
select pruebas.afirmar(not exists (select 1 from public.alertas where id = '40000000-0000-0000-0000-000000000004'),
  'el público no ve alertas ocultas por moderación');
select pruebas.afirmar(public.personas_avisadas('40000000-0000-0000-0000-000000000004') = 0, 'una alerta oculta no revela datos');
rollback;

\echo '== TODAS LAS PRUEBAS DE ALERTAS PASARON'
