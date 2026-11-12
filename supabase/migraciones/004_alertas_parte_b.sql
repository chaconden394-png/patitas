-- =============================================================================
-- Patitas · Migración 004 · Alerta Patitas, Parte B
--
-- 1. Contenedor de fotos "fotos-alertas" en Supabase Storage.
--    Cada persona solo puede subir y borrar fotos dentro de SU carpeta
--    (fotos-alertas/<su id>/...). Las fotos son públicas porque la alerta lo es.
-- 2. emitir_alerta(): guarda la alerta y su ubicación en UNA sola operación.
--    Si algo falla, no queda nada a medias. Se ejecuta con los permisos de la
--    persona (RLS aplica normalmente).
-- 3. La foto de una alerta debe estar en la carpeta de quien la emite.
-- 4. renovar_alerta(): extiende 30 días una alerta que está por vencer o vencida.
--
-- Requisito: migraciones 001, 002 y 003.
-- Dónde ejecutarla: editor de SQL de Supabase, UNA sola vez.
-- =============================================================================

begin;

-- -----------------------------------------------------------------------------
-- 1. Fotos en Storage
-- -----------------------------------------------------------------------------
-- Solo JPEG y máximo 5 MB: la app convierte toda foto a JPEG y le quita los
-- datos ocultos (como la ubicación GPS de la cámara) antes de subirla.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos-alertas', 'fotos-alertas', true, 5242880, array['image/jpeg'])
on conflict (id) do nothing;

create policy "fotos-alertas: subir en mi carpeta" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'fotos-alertas' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "fotos-alertas: ver mis archivos" on storage.objects
  for select to authenticated
  using (bucket_id = 'fotos-alertas' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "fotos-alertas: borrar mis archivos" on storage.objects
  for delete to authenticated
  using (bucket_id = 'fotos-alertas' and (storage.foldername(name))[1] = auth.uid()::text);

-- -----------------------------------------------------------------------------
-- 2. La foto de una alerta debe ser de quien la emite
--    Formato: <id de la persona>/<id aleatorio>.jpg
-- -----------------------------------------------------------------------------
create function public.validar_foto_alerta()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.ruta_foto is not null and (
       new.ruta_foto !~ '^[0-9a-f-]{36}/[0-9a-f-]{36}\.jpg$'
       or split_part(new.ruta_foto, '/', 1) <> new.emisor_id::text) then
    raise exception 'La foto no pertenece a quien emite la alerta.' using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
create trigger alertas_foto before insert or update of ruta_foto on public.alertas
  for each row execute function public.validar_foto_alerta();

-- -----------------------------------------------------------------------------
-- 3. Emitir alerta en una sola operación
--    SECURITY INVOKER (por defecto): corre con los permisos de quien la llama,
--    así que se aplican todas las reglas de la migración 002 (límites, RLS…).
-- -----------------------------------------------------------------------------
create function public.emitir_alerta(
  p_nombre text, p_especie public.especie_animal, p_raza text, p_sexo public.sexo_animal,
  p_tamano public.tamano_animal, p_edad text, p_color text, p_senas text, p_collar text,
  p_descripcion text, p_ruta_foto text, p_zona text, p_visto timestamptz,
  p_mostrar_telefono boolean, p_latitud numeric, p_longitud numeric)
returns uuid language plpgsql set search_path = '' as $$
declare
  nueva uuid;
begin
  if auth.uid() is null then
    raise exception 'Necesitas iniciar sesión.' using errcode = 'insufficient_privilege';
  end if;

  insert into public.alertas
    (emisor_id, nombre_mascota, especie, raza, sexo, tamano, edad_aproximada, color,
     senas_particulares, collar, descripcion, ruta_foto, zona_referencia, visto_por_ultima_vez,
     mostrar_telefono)
  values
    (auth.uid(), p_nombre, p_especie, coalesce(nullif(trim(p_raza), ''), 'No especificada'), p_sexo,
     p_tamano, nullif(trim(p_edad), ''), p_color, nullif(trim(p_senas), ''), nullif(trim(p_collar), ''),
     nullif(trim(p_descripcion), ''), p_ruta_foto, p_zona, p_visto, coalesce(p_mostrar_telefono, false))
  returning id into nueva;

  -- Al guardar la ubicación, la migración 002 avisa a quienes están a 15 km o menos.
  insert into public.alertas_ubicacion (alerta_id, latitud, longitud)
  values (nueva, p_latitud, p_longitud);

  return nueva;
end;
$$;
revoke execute on function public.emitir_alerta(text, public.especie_animal, text, public.sexo_animal,
  public.tamano_animal, text, text, text, text, text, text, text, timestamptz, boolean, numeric, numeric)
  from public, anon;
grant execute on function public.emitir_alerta(text, public.especie_animal, text, public.sexo_animal,
  public.tamano_animal, text, text, text, text, text, text, text, timestamptz, boolean, numeric, numeric)
  to authenticated;

-- -----------------------------------------------------------------------------
-- 4. Renovar una alerta (30 días más)
--    Solo su dueña, solo si sigue activa, solo cuando faltan 7 días o menos, y
--    respetando el máximo de 2 alertas vigentes.
-- -----------------------------------------------------------------------------
create function public.renovar_alerta(p_alerta uuid)
returns timestamptz language plpgsql security definer set search_path = '' as $$
declare
  a public.alertas;
  nueva_fecha timestamptz := now() + interval '30 days';
begin
  select * into a from public.alertas
   where id = p_alerta and emisor_id = auth.uid() for update;
  if not found then
    raise exception 'No encontramos esa alerta.' using errcode = 'insufficient_privilege';
  end if;
  if a.estado <> 'activa' or a.oculta then
    raise exception 'Solo se pueden renovar alertas activas.' using errcode = 'check_violation';
  end if;
  if a.expira_en > now() + interval '7 days' then
    raise exception 'Podrás renovarla cuando falten 7 días o menos.' using errcode = 'check_violation';
  end if;
  if a.expira_en <= now() and (select count(*) from public.alertas
       where emisor_id = auth.uid() and estado = 'activa' and expira_en > now()) >= 2 then
    raise exception 'Ya tienes 2 alertas activas. Cierra una antes de renovar otra.' using errcode = 'check_violation';
  end if;
  update public.alertas set expira_en = nueva_fecha where id = p_alerta;
  return nueva_fecha;
end;
$$;
revoke execute on function public.renovar_alerta(uuid) from public, anon;
grant execute on function public.renovar_alerta(uuid) to authenticated;

commit;
