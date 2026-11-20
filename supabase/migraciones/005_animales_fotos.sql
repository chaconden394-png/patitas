-- =============================================================================
-- Patitas · Migración 005 · Etapa 4: animales y fotos
--
-- 1. Quién puede publicar animales (decisión del 17 nov 2026):
--    cualquier cuenta de REFUGIO o RESCATISTA (con su correo confirmado, porque
--    sin confirmarlo no puede iniciar sesión). Sus animales muestran la insignia
--    "Sin verificar" hasta que un administrador apruebe su refugio.
--    Siguen pudiendo publicar las personas "habilitadas" y los refugios verificados.
-- 2. Bloqueo de publicación: un administrador puede bloquear a una cuenta desde
--    el editor SQL (tabla bloqueos_publicacion). Un refugio suspendido tampoco publica.
-- 3. Máximo 10 animales nuevos cada 24 horas por cuenta (contra spam).
-- 4. Un animal solo puede ligarse a un refugio propio que esté pendiente o verificado.
-- 5. Cada quien puede borrar sus propios animales.
-- 6. Fotos en Storage ("fotos-animales"): cada persona sube y borra solo en su
--    carpeta; máximo 3 fotos por animal; la foto debe ser de quien publica el animal.
--
-- Requisito: migraciones 001 a 004.
-- Dónde ejecutarla: editor de SQL de Supabase, UNA sola vez.
-- =============================================================================

begin;

-- -----------------------------------------------------------------------------
-- 1 y 2. Quién puede publicar
-- -----------------------------------------------------------------------------
-- Cuentas bloqueadas para publicar. Nadie puede leerla ni escribirla desde la app:
-- solo administradores desde el editor SQL de Supabase.
create table public.bloqueos_publicacion (
  usuario_id uuid primary key references public.perfiles (id) on delete cascade,
  motivo     text not null check (char_length(motivo) between 3 and 500),
  creado_en  timestamptz not null default now()
);
alter table public.bloqueos_publicacion enable row level security;
revoke all on table public.bloqueos_publicacion from anon, authenticated;

create or replace function public.puede_publicar()
returns boolean language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null
     and not exists (select 1 from public.bloqueos_publicacion where usuario_id = auth.uid())
     and not exists (select 1 from public.refugios
                      where responsable_id = auth.uid() and estado_verificacion = 'suspendido')
     and (
       exists (select 1 from public.perfiles
                where id = auth.uid()
                  and (nivel_verificacion = 'habilitada' or tipo_cuenta in ('refugio', 'rescatista')))
       or exists (select 1 from public.refugios
                   where responsable_id = auth.uid() and estado_verificacion = 'verificado')
     );
$$;

-- -----------------------------------------------------------------------------
-- 3. Límite: 10 animales nuevos cada 24 horas por cuenta
-- -----------------------------------------------------------------------------
create function public.limitar_animales_nuevos()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if (select count(*) from public.animales
       where responsable_id = new.responsable_id and publicado_en > now() - interval '24 hours') >= 10 then
    raise exception 'Llegaste al límite de 10 animales nuevos en 24 horas. Inténtalo mañana.'
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
create trigger animales_limite before insert on public.animales
  for each row execute function public.limitar_animales_nuevos();

-- -----------------------------------------------------------------------------
-- 4. El refugio del animal debe estar activo (pendiente o verificado)
-- -----------------------------------------------------------------------------
create function public.validar_refugio_animal()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.refugio_id is not null and not exists (
       select 1 from public.refugios
        where id = new.refugio_id and estado_verificacion in ('pendiente', 'verificado')) then
    raise exception 'Ese refugio no está activo en Patitas.' using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
create trigger animales_refugio before insert or update of refugio_id on public.animales
  for each row execute function public.validar_refugio_animal();

-- Los animales también se pueden editar solo si la cuenta sigue pudiendo publicar
-- (excepto marcarlos como adoptados o en proceso: eso siempre se permite).
drop policy "animales: editar los propios" on public.animales;
create policy "animales: editar los propios" on public.animales
  for update to authenticated
  using (responsable_id = auth.uid())
  with check (
    responsable_id = auth.uid()
    and (public.puede_publicar() or estado in ('adoptado', 'en_proceso'))
    and (refugio_id is null or exists (select 1 from public.refugios r
         where r.id = refugio_id and r.responsable_id = auth.uid()))
  );

-- -----------------------------------------------------------------------------
-- 5. Borrar los propios animales (las fotos de la tabla se borran en cascada;
--    la app borra antes los archivos de Storage)
-- -----------------------------------------------------------------------------
grant delete on public.animales to authenticated;
create policy "animales: borrar los propios" on public.animales
  for delete to authenticated using (responsable_id = auth.uid());

-- -----------------------------------------------------------------------------
-- 6. Fotos de animales
-- -----------------------------------------------------------------------------
-- Solo JPEG y máximo 5 MB: la app convierte toda foto a JPEG y le quita los
-- datos ocultos (como la ubicación GPS) antes de subirla.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos-animales', 'fotos-animales', true, 5242880, array['image/jpeg'])
on conflict (id) do nothing;

create policy "fotos-animales: subir en mi carpeta" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'fotos-animales' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "fotos-animales: ver mis archivos" on storage.objects
  for select to authenticated
  using (bucket_id = 'fotos-animales' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "fotos-animales: borrar mis archivos" on storage.objects
  for delete to authenticated
  using (bucket_id = 'fotos-animales' and (storage.foldername(name))[1] = auth.uid()::text);

-- Formato: <id de quien publica el animal>/<id aleatorio>.jpg · máximo 3 por animal
create function public.validar_foto_animal()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  dueno uuid;
begin
  -- Bloquea el animal mientras se cuenta, para que dos fotos subidas a la vez
  -- no se salten el límite.
  select responsable_id into dueno from public.animales where id = new.animal_id for update;
  if new.ruta_archivo !~ '^[0-9a-f-]{36}/[0-9a-f-]{36}\.jpg$'
     or split_part(new.ruta_archivo, '/', 1) <> dueno::text then
    raise exception 'La foto no pertenece a quien publicó el animal.' using errcode = 'check_violation';
  end if;
  if tg_op = 'INSERT' and (select count(*) from public.animales_fotos where animal_id = new.animal_id) >= 3 then
    raise exception 'Cada animal puede tener máximo 3 fotos. Borra una para subir otra.'
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
create trigger animales_fotos_validar before insert or update of ruta_archivo, animal_id on public.animales_fotos
  for each row execute function public.validar_foto_animal();

-- Una sola vez cada archivo
create unique index animales_fotos_ruta_idx on public.animales_fotos (ruta_archivo);

commit;
