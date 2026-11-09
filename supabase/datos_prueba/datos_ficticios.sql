-- =============================================================================
-- Patitas · Datos de prueba FICTICIOS (no son personas ni animales reales)
--
-- Requisitos antes de ejecutar:
--   1. Ya ejecutaste supabase/migraciones/001_esquema_inicial.sql
--   2. Creaste en Supabase (sección de autenticación/usuarios) un usuario de
--      prueba con el correo:  refugio.prueba@example.com
--      (example.com es un dominio reservado para ejemplos; nadie lo usa).
--
-- Dónde ejecutar: editor de SQL de tu proyecto de Supabase.
-- Se puede ejecutar más de una vez: borra y vuelve a crear SOLO estos datos.
-- =============================================================================
do $$
declare
  usuario_id uuid;
  refugio1 uuid;
  refugio2 uuid;
begin
  select id into usuario_id from auth.users where email = 'refugio.prueba@example.com';
  if usuario_id is null then
    raise exception 'Primero crea en Supabase el usuario refugio.prueba@example.com';
  end if;

  -- Limpia datos de prueba anteriores de este usuario
  delete from public.animales where responsable_id = usuario_id;
  delete from public.refugios where responsable_id = usuario_id;

  update public.perfiles
     set nombre_publico = 'Refugio de prueba', tipo_cuenta = 'refugio'
   where id = usuario_id;

  insert into public.refugios (responsable_id, nombre, descripcion, zona, estado_verificacion, verificado_en)
  values (usuario_id, 'Refugio Huellitas TJ (prueba)',
          'Rescate y rehabilitación de perros y gatos en situación de calle.', 'Otay', 'verificado', now())
  returning id into refugio1;

  insert into public.refugios (responsable_id, nombre, descripcion, zona)
  values (usuario_id, 'Gatitos de la Mesa (prueba)',
          'Colectivo dedicado a gatos rescatados y campañas de esterilización.', 'La Mesa')
  returning id into refugio2;

  insert into public.refugios_ubicacion (refugio_id, direccion)
  values (refugio1, 'Dirección ficticia de prueba, Tijuana');

  insert into public.animales
    (responsable_id, refugio_id, nombre, especie, raza, edad_aproximada_meses, tamano, sexo, energia,
     personalidad, convive_ninos, convive_perros, convive_gatos, vacunado, esterilizado, zona, estado)
  values
    (usuario_id, refugio1, 'Canela', 'perro', 'No especificada', 24, 'mediano', 'hembra', 'media',
     'Cariñosa, tranquila en casa y le encanta pasear por la playa.', true, true, null, true, true, 'Playas de Tijuana', 'disponible'),
    (usuario_id, refugio1, 'Michi', 'gato', 'Doméstico de pelo corto', 8, 'pequeño', 'macho', 'alta',
     'Juguetón y curioso. Se lleva bien con otros gatos.', true, null, true, true, true, 'Zona Río', 'disponible'),
    (usuario_id, refugio1, 'Rocky', 'perro', 'Mestizo', 72, 'grande', 'macho', 'baja',
     'Noble y paciente. Necesita hogar pronto: el refugio está lleno.', true, true, false, true, false, 'Otay', 'urgente'),
    (usuario_id, refugio1, 'Luna', 'gato', 'No especificada', 36, 'pequeño', 'hembra', 'baja',
     'Tímida al principio, muy dulce cuando toma confianza.', null, null, true, true, true, 'La Mesa', 'en_proceso'),
    (usuario_id, refugio1, 'Toby', 'perro', 'Chihuahua cruza', 48, 'pequeño', 'macho', 'alta',
     'Valiente y alegre. Se recupera de una cirugía en la pata.', true, true, true, true, true, 'Cacho', 'recuperacion'),
    (usuario_id, null, 'Pelusa', 'gato', 'Persa cruza', 60, 'pequeño', 'hembra', 'baja',
     'Vista por última vez cerca de un parque de la colonia.', null, null, null, true, true, 'Cacho', 'perdido'),
    (usuario_id, null, 'Sin nombre', 'perro', 'No especificada', null, 'mediano', 'macho', 'media',
     'Encontrado con collar rojo, sin placa. Está resguardado.', null, null, null, false, false, 'Playas de Tijuana', 'encontrado');

  raise notice 'Datos de prueba creados: 2 refugios y 7 animales.';
end $$;
