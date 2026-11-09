-- =============================================================================
-- Patitas · Alerta Patitas de prueba (FICTICIA)
--
-- Requisitos:
--   1. Ya ejecutaste las migraciones 001 y 002.
--   2. Existe el usuario de prueba refugio.prueba@example.com
--      (el mismo de datos_ficticios.sql).
--
-- Dónde ejecutar: editor de SQL de tu proyecto de Supabase.
-- Se puede repetir: borra y vuelve a crear solo la alerta de prueba.
-- =============================================================================
do $$
declare
  usuario_id uuid;
  alerta_id uuid;
begin
  select id into usuario_id from auth.users where email = 'refugio.prueba@example.com';
  if usuario_id is null then
    raise exception 'Primero crea en Supabase el usuario refugio.prueba@example.com';
  end if;

  delete from public.alertas where emisor_id = usuario_id;

  insert into public.alertas
    (emisor_id, nombre_mascota, especie, raza, sexo, tamano, edad_aproximada, color,
     senas_particulares, collar, descripcion, zona_referencia, visto_por_ultima_vez, mostrar_telefono)
  values
    (usuario_id, 'Chispa (prueba)', 'perro', 'Mestiza', 'hembra', 'pequeño', '3 años', 'Café con blanco',
     'Oreja izquierda doblada y una mancha blanca en el pecho.', 'Collar rosa con cascabel, sin placa.',
     'Se asustó con los cohetes y salió corriendo. Es miedosa: háblale despacio y no la persigas.',
     'Centro, cerca del Parque Teniente Guerrero', now() - interval '3 hours', false)
  returning id into alerta_id;

  -- Punto exacto (privado). El público solo verá el punto aproximado.
  insert into public.alertas_ubicacion (alerta_id, latitud, longitud)
  values (alerta_id, 32.5149, -117.0382);

  raise notice 'Alerta de prueba creada: %', alerta_id;
end $$;
