-- =============================================================================
-- Patitas · Migración 001 · Esquema inicial
-- Tablas: perfiles, datos privados, administradores, refugios, ubicación privada
--         de refugios, animales, fotos, historial de estados y favoritos.
--
-- Dónde ejecutarla: en el panel de tu proyecto de Supabase, en el editor de SQL.
-- Ejecútala UNA sola vez, completa. Las siguientes etapas agregarán migraciones
-- nuevas (002, 003…) en lugar de modificar esta.
--
-- Principios de seguridad:
--  * Todas las tablas tienen RLS (seguridad a nivel de fila) activada.
--  * Los permisos se dan columna por columna: un usuario no puede cambiarse a sí
--    mismo el nivel de verificación ni aprobar su propio refugio.
--  * Los datos privados (teléfono, dirección exacta) están en tablas separadas.
-- =============================================================================

begin;

-- -----------------------------------------------------------------------------
-- 1. Tipos (listas de valores permitidos)
-- -----------------------------------------------------------------------------
create type public.tipo_cuenta as enum
  ('adoptante', 'rescatista', 'refugio', 'reportante', 'voluntario', 'negocio');

create type public.nivel_verificacion as enum
  ('registrada', 'identidad_verificada', 'habilitada');

create type public.estado_refugio as enum
  ('pendiente', 'verificado', 'rechazado', 'suspendido');

create type public.especie_animal as enum ('perro', 'gato', 'conejo', 'ave', 'otro');
create type public.tamano_animal  as enum ('pequeño', 'mediano', 'grande');
create type public.sexo_animal    as enum ('hembra', 'macho', 'desconocido');
create type public.nivel_energia  as enum ('baja', 'media', 'alta');

create type public.estado_animal as enum
  ('disponible', 'en_proceso', 'adoptado', 'hogar_temporal',
   'perdido', 'encontrado', 'recuperacion', 'urgente');

-- -----------------------------------------------------------------------------
-- 2. Función genérica: actualiza la columna actualizado_en
-- -----------------------------------------------------------------------------
create function public.poner_fecha_actualizacion()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.actualizado_en := now();
  return new;
end;
$$;

-- -----------------------------------------------------------------------------
-- 3. Administradores
--    Sin políticas: nadie puede leer ni escribir esta tabla desde la app.
--    Un administrador se agrega solo desde el editor SQL de Supabase.
-- -----------------------------------------------------------------------------
create table public.administradores (
  usuario_id uuid primary key references auth.users (id) on delete cascade,
  creado_en  timestamptz not null default now()
);
alter table public.administradores enable row level security;
revoke all on table public.administradores from anon, authenticated;

-- ¿La persona que hace la consulta es administradora?
create function public.es_admin()
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.administradores where usuario_id = auth.uid());
$$;

-- -----------------------------------------------------------------------------
-- 4. Perfiles públicos (lo que cualquiera puede ver)
-- -----------------------------------------------------------------------------
create table public.perfiles (
  id                 uuid primary key references auth.users (id) on delete cascade,
  nombre_publico     text not null check (char_length(nombre_publico) between 2 and 60),
  tipo_cuenta        public.tipo_cuenta not null default 'adoptante',
  nivel_verificacion public.nivel_verificacion not null default 'registrada',
  biografia          text check (char_length(biografia) <= 500),
  municipio          text not null default 'Tijuana' check (char_length(municipio) <= 60),
  creado_en          timestamptz not null default now(),
  actualizado_en     timestamptz not null default now()
);
create trigger perfiles_fecha before update on public.perfiles
  for each row execute function public.poner_fecha_actualizacion();

-- -----------------------------------------------------------------------------
-- 5. Datos privados del perfil (solo la persona dueña y administradores)
-- -----------------------------------------------------------------------------
create table public.perfiles_privados (
  id                          uuid primary key references public.perfiles (id) on delete cascade,
  telefono                    text check (telefono ~ '^\+?[0-9]{10,15}$'),
  telefono_verificado         boolean not null default false,
  acepto_aviso_privacidad_en  timestamptz,
  actualizado_en              timestamptz not null default now()
);
create trigger perfiles_privados_fecha before update on public.perfiles_privados
  for each row execute function public.poner_fecha_actualizacion();

-- Si alguien cambia su teléfono, deja de estar verificado.
create function public.reiniciar_verificacion_telefono()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.telefono is distinct from old.telefono then
    new.telefono_verificado := false;
  end if;
  return new;
end;
$$;
create trigger perfiles_privados_telefono before update of telefono on public.perfiles_privados
  for each row execute function public.reiniciar_verificacion_telefono();

-- -----------------------------------------------------------------------------
-- 6. Crear perfil automáticamente cuando alguien se registra
--    Toma nombre y tipo de cuenta de los datos de registro, pero NUNCA el nivel
--    de verificación (siempre empieza en "registrada").
-- -----------------------------------------------------------------------------
create function public.crear_perfil_nuevo_usuario()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  nombre text := left(trim(coalesce(new.raw_user_meta_data ->> 'nombre_publico', '')), 60);
  tipo   text := coalesce(new.raw_user_meta_data ->> 'tipo_cuenta', 'adoptante');
begin
  if char_length(nombre) < 2 then
    nombre := 'Usuario de Patitas';
  end if;
  if tipo not in ('adoptante', 'rescatista', 'refugio', 'reportante', 'voluntario', 'negocio') then
    tipo := 'adoptante';
  end if;

  insert into public.perfiles (id, nombre_publico, tipo_cuenta)
  values (new.id, nombre, tipo::public.tipo_cuenta);
  insert into public.perfiles_privados (id) values (new.id);
  return new;
end;
$$;
create trigger al_crear_usuario after insert on auth.users
  for each row execute function public.crear_perfil_nuevo_usuario();

-- -----------------------------------------------------------------------------
-- 7. Refugios y asociaciones
-- -----------------------------------------------------------------------------
create table public.refugios (
  id                  uuid primary key default gen_random_uuid(),
  responsable_id      uuid not null references public.perfiles (id) on delete restrict,
  nombre              text not null check (char_length(nombre) between 3 and 100),
  descripcion         text check (char_length(descripcion) <= 1000),
  zona                text check (char_length(zona) <= 80),
  municipio           text not null default 'Tijuana' check (char_length(municipio) <= 60),
  telefono_publico    text check (telefono_publico ~ '^\+?[0-9]{10,15}$'),
  correo_publico      text check (correo_publico ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  redes_sociales      jsonb not null default '{}'::jsonb,
  estado_verificacion public.estado_refugio not null default 'pendiente',
  verificado_en       timestamptz,
  creado_en           timestamptz not null default now(),
  actualizado_en      timestamptz not null default now()
);
create index refugios_responsable_idx on public.refugios (responsable_id);
create index refugios_estado_idx on public.refugios (estado_verificacion);
create trigger refugios_fecha before update on public.refugios
  for each row execute function public.poner_fecha_actualizacion();

-- Dirección exacta: protegida, separada de los datos públicos.
create table public.refugios_ubicacion (
  refugio_id     uuid primary key references public.refugios (id) on delete cascade,
  direccion      text not null check (char_length(direccion) between 5 and 200),
  latitud        numeric(9, 6) check (latitud between -90 and 90),
  longitud       numeric(9, 6) check (longitud between -180 and 180),
  actualizado_en timestamptz not null default now()
);
create trigger refugios_ubicacion_fecha before update on public.refugios_ubicacion
  for each row execute function public.poner_fecha_actualizacion();

-- -----------------------------------------------------------------------------
-- 8. Animales
-- -----------------------------------------------------------------------------
create table public.animales (
  id                      uuid primary key default gen_random_uuid(),
  responsable_id          uuid not null references public.perfiles (id) on delete restrict,
  refugio_id              uuid references public.refugios (id) on delete set null,
  nombre                  text not null check (char_length(nombre) between 1 and 60),
  especie                 public.especie_animal not null,
  raza                    text not null default 'No especificada' check (char_length(raza) <= 60),
  edad_aproximada_meses   integer check (edad_aproximada_meses between 0 and 400),
  tamano                  public.tamano_animal not null,
  sexo                    public.sexo_animal not null default 'desconocido',
  energia                 public.nivel_energia,
  personalidad            text check (char_length(personalidad) <= 1000),
  -- Convivencia: verdadero, falso o vacío (= no se sabe)
  convive_ninos           boolean,
  convive_perros          boolean,
  convive_gatos           boolean,
  vacunado                boolean not null default false,
  esterilizado            boolean not null default false,
  enfermedades_conocidas  text check (char_length(enfermedades_conocidas) <= 1000),
  necesidades_especiales  text check (char_length(necesidades_especiales) <= 1000),
  requisitos_adopcion     text check (char_length(requisitos_adopcion) <= 1000),
  zona                    text not null check (char_length(zona) <= 80),
  municipio               text not null default 'Tijuana' check (char_length(municipio) <= 60),
  -- Ubicación APROXIMADA: dos decimales (≈ 1 km), nunca la dirección exacta.
  latitud_aprox           numeric(5, 2) check (latitud_aprox between -90 and 90),
  longitud_aprox          numeric(5, 2) check (longitud_aprox between -180 and 180),
  estado                  public.estado_animal not null default 'disponible',
  oculto                  boolean not null default false,  -- para moderación (Etapa 7)
  publicado_en            timestamptz not null default now(),
  actualizado_en          timestamptz not null default now()
);
create index animales_visibles_idx on public.animales (estado, publicado_en desc) where not oculto;
create index animales_busqueda_idx on public.animales (especie, tamano, sexo);
create index animales_responsable_idx on public.animales (responsable_id);
create index animales_refugio_idx on public.animales (refugio_id);
create trigger animales_fecha before update on public.animales
  for each row execute function public.poner_fecha_actualizacion();

-- ¿Puede la persona actual publicar animales?
-- Sí, si su perfil está "habilitada" o si tiene un refugio verificado.
create function public.puede_publicar()
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.perfiles
                  where id = auth.uid() and nivel_verificacion = 'habilitada')
      or exists (select 1 from public.refugios
                  where responsable_id = auth.uid() and estado_verificacion = 'verificado');
$$;

-- -----------------------------------------------------------------------------
-- 9. Historial de estados (se llena solo, nadie lo edita a mano)
-- -----------------------------------------------------------------------------
create table public.animales_historial_estados (
  id              bigint generated always as identity primary key,
  animal_id       uuid not null references public.animales (id) on delete cascade,
  estado_anterior public.estado_animal,
  estado_nuevo    public.estado_animal not null,
  cambiado_por    uuid references auth.users (id) on delete set null,
  cambiado_en     timestamptz not null default now()
);
create index historial_animal_idx on public.animales_historial_estados (animal_id, cambiado_en desc);

create function public.registrar_cambio_estado()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' or new.estado is distinct from old.estado then
    insert into public.animales_historial_estados (animal_id, estado_anterior, estado_nuevo, cambiado_por)
    values (new.id, case when tg_op = 'UPDATE' then old.estado end, new.estado, auth.uid());
  end if;
  return new;
end;
$$;
create trigger animales_historial after insert or update of estado on public.animales
  for each row execute function public.registrar_cambio_estado();

-- -----------------------------------------------------------------------------
-- 10. Fotos de animales (los archivos vivirán en Supabase Storage, Etapa 4)
-- -----------------------------------------------------------------------------
create table public.animales_fotos (
  id           uuid primary key default gen_random_uuid(),
  animal_id    uuid not null references public.animales (id) on delete cascade,
  ruta_archivo text not null check (char_length(ruta_archivo) <= 300),
  orden        smallint not null default 0 check (orden between 0 and 20),
  creado_en    timestamptz not null default now()
);
create index fotos_animal_idx on public.animales_fotos (animal_id, orden);

-- -----------------------------------------------------------------------------
-- 11. Favoritos
-- -----------------------------------------------------------------------------
create table public.favoritos (
  usuario_id uuid not null references public.perfiles (id) on delete cascade,
  animal_id  uuid not null references public.animales (id) on delete cascade,
  creado_en  timestamptz not null default now(),
  primary key (usuario_id, animal_id)
);
create index favoritos_animal_idx on public.favoritos (animal_id);

-- =============================================================================
-- 12. Permisos (qué columnas puede tocar cada rol)
--     anon = visitante sin sesión · authenticated = persona con sesión iniciada
-- =============================================================================
revoke all on table public.perfiles, public.perfiles_privados, public.refugios,
  public.refugios_ubicacion, public.animales, public.animales_historial_estados,
  public.animales_fotos, public.favoritos from anon, authenticated;

grant select on public.perfiles, public.refugios, public.animales, public.animales_fotos
  to anon, authenticated;
grant select on public.perfiles_privados, public.refugios_ubicacion,
  public.animales_historial_estados, public.favoritos to authenticated;

-- Perfil: solo campos personales, nunca tipo de cuenta ni nivel de verificación.
grant update (nombre_publico, biografia, municipio) on public.perfiles to authenticated;
grant update (telefono, acepto_aviso_privacidad_en) on public.perfiles_privados to authenticated;

-- Refugio: el estado de verificación no se puede escribir desde la app.
grant insert (responsable_id, nombre, descripcion, zona, municipio, telefono_publico,
              correo_publico, redes_sociales) on public.refugios to authenticated;
grant update (nombre, descripcion, zona, municipio, telefono_publico,
              correo_publico, redes_sociales) on public.refugios to authenticated;
grant insert (refugio_id, direccion, latitud, longitud) on public.refugios_ubicacion to authenticated;
grant update (direccion, latitud, longitud) on public.refugios_ubicacion to authenticated;

-- Animal: no se puede escribir "oculto", "responsable_id" (al editar) ni la fecha de publicación.
grant insert (responsable_id, refugio_id, nombre, especie, raza, edad_aproximada_meses, tamano,
              sexo, energia, personalidad, convive_ninos, convive_perros, convive_gatos,
              vacunado, esterilizado, enfermedades_conocidas, necesidades_especiales,
              requisitos_adopcion, zona, municipio, latitud_aprox, longitud_aprox, estado)
  on public.animales to authenticated;
grant update (refugio_id, nombre, especie, raza, edad_aproximada_meses, tamano, sexo, energia,
              personalidad, convive_ninos, convive_perros, convive_gatos, vacunado, esterilizado,
              enfermedades_conocidas, necesidades_especiales, requisitos_adopcion, zona,
              municipio, latitud_aprox, longitud_aprox, estado)
  on public.animales to authenticated;

grant insert (animal_id, ruta_archivo, orden), delete on public.animales_fotos to authenticated;
grant update (orden) on public.animales_fotos to authenticated;
grant insert (usuario_id, animal_id), delete on public.favoritos to authenticated;

-- =============================================================================
-- 13. Políticas RLS (qué FILAS puede ver o cambiar cada persona)
-- =============================================================================
alter table public.perfiles                   enable row level security;
alter table public.perfiles_privados          enable row level security;
alter table public.refugios                   enable row level security;
alter table public.refugios_ubicacion         enable row level security;
alter table public.animales                   enable row level security;
alter table public.animales_historial_estados enable row level security;
alter table public.animales_fotos             enable row level security;
alter table public.favoritos                  enable row level security;

-- Perfiles: públicos para lectura; cada quien edita el suyo.
create policy "perfiles: lectura pública" on public.perfiles
  for select to anon, authenticated using (true);
create policy "perfiles: editar el propio" on public.perfiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

-- Datos privados: solo la persona dueña (y administradores para leer).
create policy "privados: ver los propios" on public.perfiles_privados
  for select to authenticated using (id = auth.uid() or public.es_admin());
create policy "privados: editar los propios" on public.perfiles_privados
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

-- Refugios: se ven los pendientes y verificados; rechazados/suspendidos solo su
-- responsable y administradores.
create policy "refugios: lectura" on public.refugios
  for select to anon, authenticated
  using (estado_verificacion in ('pendiente', 'verificado')
         or responsable_id = auth.uid() or public.es_admin());
create policy "refugios: registrar el propio" on public.refugios
  for insert to authenticated with check (responsable_id = auth.uid());
create policy "refugios: editar el propio" on public.refugios
  for update to authenticated
  using (responsable_id = auth.uid()) with check (responsable_id = auth.uid());

-- Ubicación exacta de refugios: solo responsable y administradores (por ahora).
create policy "ubicacion: lectura restringida" on public.refugios_ubicacion
  for select to authenticated
  using (public.es_admin() or exists (select 1 from public.refugios r
          where r.id = refugio_id and r.responsable_id = auth.uid()));
create policy "ubicacion: registrar la propia" on public.refugios_ubicacion
  for insert to authenticated
  with check (exists (select 1 from public.refugios r
              where r.id = refugio_id and r.responsable_id = auth.uid()));
create policy "ubicacion: editar la propia" on public.refugios_ubicacion
  for update to authenticated
  using (exists (select 1 from public.refugios r
         where r.id = refugio_id and r.responsable_id = auth.uid()));

-- Animales: visibles si no están ocultos; el responsable siempre ve los suyos.
create policy "animales: lectura" on public.animales
  for select to anon, authenticated
  using (not oculto or responsable_id = auth.uid() or public.es_admin());
create policy "animales: publicar" on public.animales
  for insert to authenticated
  with check (
    responsable_id = auth.uid()
    and public.puede_publicar()
    and (refugio_id is null or exists (select 1 from public.refugios r
         where r.id = refugio_id and r.responsable_id = auth.uid()))
  );
create policy "animales: editar los propios" on public.animales
  for update to authenticated
  using (responsable_id = auth.uid())
  with check (
    responsable_id = auth.uid()
    and (refugio_id is null or exists (select 1 from public.refugios r
         where r.id = refugio_id and r.responsable_id = auth.uid()))
  );

-- Historial: solo el responsable del animal y administradores.
create policy "historial: lectura" on public.animales_historial_estados
  for select to authenticated
  using (public.es_admin() or exists (select 1 from public.animales a
         where a.id = animal_id and a.responsable_id = auth.uid()));

-- Fotos: visibles si el animal es visible; las gestiona su responsable.
create policy "fotos: lectura" on public.animales_fotos
  for select to anon, authenticated
  using (exists (select 1 from public.animales a where a.id = animal_id));
create policy "fotos: agregar" on public.animales_fotos
  for insert to authenticated
  with check (exists (select 1 from public.animales a
              where a.id = animal_id and a.responsable_id = auth.uid()));
create policy "fotos: ordenar" on public.animales_fotos
  for update to authenticated
  using (exists (select 1 from public.animales a
         where a.id = animal_id and a.responsable_id = auth.uid()));
create policy "fotos: borrar" on public.animales_fotos
  for delete to authenticated
  using (exists (select 1 from public.animales a
         where a.id = animal_id and a.responsable_id = auth.uid()));

-- Favoritos: cada quien los suyos.
create policy "favoritos: ver los propios" on public.favoritos
  for select to authenticated using (usuario_id = auth.uid());
create policy "favoritos: agregar" on public.favoritos
  for insert to authenticated
  with check (usuario_id = auth.uid() and exists (select 1 from public.animales a where a.id = animal_id));
create policy "favoritos: quitar" on public.favoritos
  for delete to authenticated using (usuario_id = auth.uid());

-- Funciones internas: no se pueden llamar directamente desde la API.
revoke execute on function public.crear_perfil_nuevo_usuario() from public, anon, authenticated;
revoke execute on function public.registrar_cambio_estado() from public, anon, authenticated;

commit;
