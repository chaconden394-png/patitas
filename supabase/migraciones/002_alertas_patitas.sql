-- =============================================================================
-- Patitas · Migración 002 · Alerta Patitas (mascotas perdidas)
--
-- Una persona emite una alerta con los datos de su mascota y el lugar donde se
-- vio por última vez. La base de datos avisa automáticamente a los usuarios
-- cuya ZONA DE ALERTAS está a 15 km o menos de ese lugar.
--
-- Requisito: haber ejecutado antes la migración 001.
-- Dónde ejecutarla: editor de SQL de tu proyecto de Supabase, UNA sola vez.
--
-- Privacidad:
--  * El punto exacto de extravío (que suele ser la casa del dueño) es privado.
--    El público solo ve un punto aproximado (≈ 1 km).
--  * La zona de alertas de cada usuario es privada y se guarda redondeada.
--  * El teléfono del dueño solo se entrega si él lo autoriza, y solo a personas
--    con sesión iniciada.
-- =============================================================================

begin;

create type public.estado_alerta as enum ('activa', 'encontrada', 'cancelada');
create type public.tipo_notificacion as enum ('alerta_cercana', 'avistamiento', 'alerta_cerrada');

-- -----------------------------------------------------------------------------
-- 1. Distancia en km entre dos puntos (fórmula de Haversine)
-- -----------------------------------------------------------------------------
create function public.distancia_km(lat1 numeric, lng1 numeric, lat2 numeric, lng2 numeric)
returns numeric language sql immutable set search_path = '' as $$
  select (2 * 6371 * asin(sqrt(
           power(sin(radians((lat2 - lat1)::float8) / 2), 2)
         + cos(radians(lat1::float8)) * cos(radians(lat2::float8))
         * power(sin(radians((lng2 - lng1)::float8) / 2), 2))))::numeric;
$$;

-- -----------------------------------------------------------------------------
-- 2. Zona de alertas de cada usuario (privada)
--    Se guarda con 2 decimales (≈ 1 km): suficiente para un radio de 15 km y
--    no revela la dirección exacta.
-- -----------------------------------------------------------------------------
create table public.zonas_alerta (
  usuario_id     uuid primary key references public.perfiles (id) on delete cascade,
  latitud        numeric(5, 2) not null check (latitud between -90 and 90),
  longitud       numeric(5, 2) not null check (longitud between -180 and 180),
  acepta_alertas boolean not null default true,
  actualizado_en timestamptz not null default now()
);
create index zonas_alerta_coordenadas_idx on public.zonas_alerta (latitud, longitud) where acepta_alertas;
create trigger zonas_alerta_fecha before update on public.zonas_alerta
  for each row execute function public.poner_fecha_actualizacion();

-- Redondea siempre a 2 decimales, aunque la app envíe más precisión.
create function public.redondear_zona()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.latitud := round(new.latitud, 2);
  new.longitud := round(new.longitud, 2);
  return new;
end;
$$;
create trigger zonas_alerta_redondeo before insert or update on public.zonas_alerta
  for each row execute function public.redondear_zona();

-- -----------------------------------------------------------------------------
-- 3. Alertas (lo que el público ve)
-- -----------------------------------------------------------------------------
create table public.alertas (
  id                   uuid primary key default gen_random_uuid(),
  emisor_id            uuid not null references public.perfiles (id) on delete cascade,
  nombre_mascota       text not null check (char_length(nombre_mascota) between 1 and 60),
  especie              public.especie_animal not null,
  raza                 text not null default 'No especificada' check (char_length(raza) <= 60),
  sexo                 public.sexo_animal not null default 'desconocido',
  tamano               public.tamano_animal not null,
  edad_aproximada      text check (char_length(edad_aproximada) <= 40),
  color                text not null check (char_length(color) between 2 and 80),
  senas_particulares   text check (char_length(senas_particulares) <= 500),
  collar               text check (char_length(collar) <= 200),
  descripcion          text check (char_length(descripcion) <= 1000),
  ruta_foto            text check (char_length(ruta_foto) <= 300),  -- Supabase Storage (Etapa 4)
  zona_referencia      text not null check (char_length(zona_referencia) between 3 and 120),
  municipio            text not null default 'Tijuana' check (char_length(municipio) <= 60),
  visto_por_ultima_vez timestamptz not null check (visto_por_ultima_vez <= now() + interval '1 hour'),
  -- Punto PÚBLICO aproximado (lo calcula la base de datos a partir del exacto)
  latitud_aprox        numeric(5, 2),
  longitud_aprox       numeric(5, 2),
  radio_km             smallint not null default 15 check (radio_km = 15),
  mostrar_telefono     boolean not null default false,
  estado               public.estado_alerta not null default 'activa',
  oculta               boolean not null default false,          -- moderación (Etapa 7)
  creada_en            timestamptz not null default now(),
  expira_en            timestamptz not null default now() + interval '30 days',
  cerrada_en           timestamptz,
  actualizado_en       timestamptz not null default now()
);
create index alertas_activas_idx on public.alertas (creada_en desc) where estado = 'activa' and not oculta;
create index alertas_emisor_idx on public.alertas (emisor_id);
create index alertas_coordenadas_idx on public.alertas (latitud_aprox, longitud_aprox);
create trigger alertas_fecha before update on public.alertas
  for each row execute function public.poner_fecha_actualizacion();

-- Punto EXACTO de extravío: privado (solo el emisor y administradores).
create table public.alertas_ubicacion (
  alerta_id uuid primary key references public.alertas (id) on delete cascade,
  latitud   numeric(9, 6) not null check (latitud between -90 and 90),
  longitud  numeric(9, 6) not null check (longitud between -180 and 180)
);

-- ¿La alerta está vigente? (activa, no oculta y sin vencer)
create function public.alerta_vigente(a public.alertas)
returns boolean language sql stable set search_path = '' as $$
  select a.estado = 'activa' and not a.oculta and a.expira_en > now();
$$;

-- -----------------------------------------------------------------------------
-- 4. Límites: máximo 2 alertas vigentes y 3 emitidas en 24 horas por persona
-- -----------------------------------------------------------------------------
create function public.limitar_alertas_activas()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if (select count(*) from public.alertas
       where emisor_id = new.emisor_id and estado = 'activa' and expira_en > now()) >= 2 then
    raise exception 'Ya tienes 2 alertas activas. Cierra una antes de emitir otra.'
      using errcode = 'check_violation';
  end if;
  -- Evita cancelar y volver a emitir para enviar notificaciones en masa.
  if (select count(*) from public.alertas
       where emisor_id = new.emisor_id and creada_en > now() - interval '24 hours') >= 3 then
    raise exception 'Llegaste al límite de 3 alertas en 24 horas.' using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
create trigger alertas_limite before insert on public.alertas
  for each row execute function public.limitar_alertas_activas();

-- -----------------------------------------------------------------------------
-- 5. Cambios de estado permitidos
--    activa -> encontrada | cancelada. Una alerta cerrada no se reabre.
-- -----------------------------------------------------------------------------
create function public.validar_estado_alerta()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.estado is distinct from old.estado then
    if old.estado <> 'activa' then
      raise exception 'Esta alerta ya está cerrada.' using errcode = 'check_violation';
    end if;
    new.cerrada_en := now();
  end if;
  return new;
end;
$$;
create trigger alertas_estado before update of estado on public.alertas
  for each row execute function public.validar_estado_alerta();

-- -----------------------------------------------------------------------------
-- 6. Notificaciones dentro de Patitas
--    Solo las crea la base de datos (triggers). Cada quien ve las suyas.
-- -----------------------------------------------------------------------------
create table public.notificaciones (
  id         bigint generated always as identity primary key,
  usuario_id uuid not null references public.perfiles (id) on delete cascade,
  tipo       public.tipo_notificacion not null,
  alerta_id  uuid references public.alertas (id) on delete cascade,
  titulo     text not null,
  cuerpo     text not null,
  leida      boolean not null default false,
  creada_en  timestamptz not null default now()
);
create index notificaciones_usuario_idx on public.notificaciones (usuario_id, creada_en desc);
create unique index notificaciones_una_por_alerta_idx on public.notificaciones (usuario_id, alerta_id, tipo)
  where tipo in ('alerta_cercana', 'alerta_cerrada');

-- -----------------------------------------------------------------------------
-- 7. Al emitir una alerta: guardar el punto aproximado y avisar a los usuarios
--    cuya zona está a 15 km o menos.
-- -----------------------------------------------------------------------------
create function public.procesar_ubicacion_alerta()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  a public.alertas;
begin
  -- Punto público aproximado
  update public.alertas
     set latitud_aprox = round(new.latitud, 2), longitud_aprox = round(new.longitud, 2)
   where id = new.alerta_id
   returning * into a;

  if not public.alerta_vigente(a) then
    return new;
  end if;

  -- Avisar en radio de 15 km (primero un filtro rápido por "caja", luego distancia real)
  insert into public.notificaciones (usuario_id, tipo, alerta_id, titulo, cuerpo)
  select z.usuario_id, 'alerta_cercana', a.id,
         'Alerta Patitas: se busca a ' || a.nombre_mascota,
         initcap(a.especie::text) || ' ' || a.color || ', visto por última vez en '
           || a.zona_referencia || '. Si lo ves, avísale a su familia.'
    from public.zonas_alerta z
   where z.acepta_alertas
     and z.usuario_id <> a.emisor_id
     and z.latitud  between new.latitud  - 0.15 and new.latitud  + 0.15
     and z.longitud between new.longitud - 0.18 and new.longitud + 0.18
     and public.distancia_km(z.latitud, z.longitud, new.latitud, new.longitud) <= a.radio_km
  on conflict do nothing;
  return new;
end;
$$;
create trigger alertas_ubicacion_avisar after insert on public.alertas_ubicacion
  for each row execute function public.procesar_ubicacion_alerta();

-- Al cerrar como "encontrada": avisar a todas las personas que recibieron la alerta.
create function public.avisar_alerta_cerrada()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.estado = 'encontrada' and old.estado = 'activa' then
    insert into public.notificaciones (usuario_id, tipo, alerta_id, titulo, cuerpo)
    select n.usuario_id, 'alerta_cerrada', new.id,
           '¡' || new.nombre_mascota || ' ya está en casa!',
           'Gracias por ayudar a buscarlo. La alerta se cerró.'
      from public.notificaciones n
     where n.alerta_id = new.id and n.tipo = 'alerta_cercana'
    on conflict do nothing;
  end if;
  return new;
end;
$$;
create trigger alertas_cerrada_avisar after update of estado on public.alertas
  for each row execute function public.avisar_alerta_cerrada();

-- -----------------------------------------------------------------------------
-- 8. Avistamientos ("Lo vi")
-- -----------------------------------------------------------------------------
create table public.avistamientos (
  id            bigint generated always as identity primary key,
  alerta_id     uuid not null references public.alertas (id) on delete cascade,
  reportado_por uuid not null references public.perfiles (id) on delete cascade,
  latitud       numeric(9, 6) check (latitud between -90 and 90),
  longitud      numeric(9, 6) check (longitud between -180 and 180),
  lugar         text not null check (char_length(lugar) between 3 and 200),
  comentario    text check (char_length(comentario) <= 500),
  visto_en      timestamptz not null check (visto_en <= now() + interval '1 hour'),
  creado_en     timestamptz not null default now()
);
create index avistamientos_alerta_idx on public.avistamientos (alerta_id, creado_en desc);

-- Límite anti-spam: máximo 5 avistamientos por persona y alerta cada 24 horas.
create function public.limitar_avistamientos()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if (select count(*) from public.avistamientos
       where alerta_id = new.alerta_id and reportado_por = new.reportado_por
         and creado_en > now() - interval '24 hours') >= 5 then
    raise exception 'Ya enviaste varios avistamientos hoy para esta alerta.' using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
create trigger avistamientos_limite before insert on public.avistamientos
  for each row execute function public.limitar_avistamientos();

-- Avisar al dueño de cada avistamiento nuevo.
create function public.avisar_avistamiento()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.notificaciones (usuario_id, tipo, alerta_id, titulo, cuerpo)
  select a.emisor_id, 'avistamiento', a.id,
         'Alguien vio a ' || a.nombre_mascota,
         'Visto en ' || new.lugar || '. Abre la alerta para ver los detalles.'
    from public.alertas a where a.id = new.alerta_id;
  return new;
end;
$$;
create trigger avistamientos_avisar after insert on public.avistamientos
  for each row execute function public.avisar_avistamiento();

-- -----------------------------------------------------------------------------
-- 9. Funciones que la app puede llamar
-- -----------------------------------------------------------------------------
-- Teléfono del dueño: solo si él lo autorizó, la alerta está vigente y quien
-- pregunta tiene sesión iniciada.
create function public.telefono_contacto_alerta(id_alerta uuid)
returns text language sql stable security definer set search_path = '' as $$
  select p.telefono
    from public.alertas a
    join public.perfiles_privados p on p.id = a.emisor_id
   where a.id = id_alerta
     and a.mostrar_telefono
     and public.alerta_vigente(a)
     and auth.uid() is not null;
$$;

-- Cuántas personas recibieron la alerta (un número, sin revelar quiénes).
create function public.personas_avisadas(id_alerta uuid)
returns integer language sql stable security definer set search_path = '' as $$
  select count(*)::integer from public.notificaciones
   where alerta_id = id_alerta and tipo = 'alerta_cercana'
     and exists (select 1 from public.alertas a where a.id = id_alerta and not a.oculta);
$$;

-- =============================================================================
-- 10. Permisos por columna
-- =============================================================================
revoke all on table public.zonas_alerta, public.alertas, public.alertas_ubicacion,
  public.notificaciones, public.avistamientos from anon, authenticated;

grant select on public.alertas to anon, authenticated;
grant select, delete on public.zonas_alerta to authenticated;
grant insert (usuario_id, latitud, longitud, acepta_alertas) on public.zonas_alerta to authenticated;
grant update (latitud, longitud, acepta_alertas) on public.zonas_alerta to authenticated;

grant insert (emisor_id, nombre_mascota, especie, raza, sexo, tamano, edad_aproximada, color,
              senas_particulares, collar, descripcion, ruta_foto, zona_referencia, municipio,
              visto_por_ultima_vez, mostrar_telefono)
  on public.alertas to authenticated;
grant update (raza, edad_aproximada, color, senas_particulares, collar, descripcion, ruta_foto,
              zona_referencia, mostrar_telefono, estado)
  on public.alertas to authenticated;

grant select on public.alertas_ubicacion to authenticated;
grant insert (alerta_id, latitud, longitud) on public.alertas_ubicacion to authenticated;

grant select on public.notificaciones to authenticated;
grant update (leida) on public.notificaciones to authenticated;

grant select on public.avistamientos to authenticated;
grant insert (alerta_id, reportado_por, latitud, longitud, lugar, comentario, visto_en)
  on public.avistamientos to authenticated;

revoke execute on function public.telefono_contacto_alerta(uuid) from public, anon;
grant execute on function public.telefono_contacto_alerta(uuid) to authenticated;
grant execute on function public.personas_avisadas(uuid) to anon, authenticated;
revoke execute on function public.procesar_ubicacion_alerta() from public, anon, authenticated;
revoke execute on function public.avisar_alerta_cerrada() from public, anon, authenticated;
revoke execute on function public.avisar_avistamiento() from public, anon, authenticated;
revoke execute on function public.limitar_alertas_activas() from public, anon, authenticated;
revoke execute on function public.limitar_avistamientos() from public, anon, authenticated;

-- =============================================================================
-- 11. Políticas RLS
-- =============================================================================
alter table public.zonas_alerta      enable row level security;
alter table public.alertas           enable row level security;
alter table public.alertas_ubicacion enable row level security;
alter table public.notificaciones    enable row level security;
alter table public.avistamientos     enable row level security;

-- Zona de alertas: cada quien la suya.
create policy "zona: ver la propia" on public.zonas_alerta
  for select to authenticated using (usuario_id = auth.uid());
create policy "zona: crear la propia" on public.zonas_alerta
  for insert to authenticated with check (usuario_id = auth.uid());
create policy "zona: editar la propia" on public.zonas_alerta
  for update to authenticated using (usuario_id = auth.uid()) with check (usuario_id = auth.uid());
create policy "zona: borrar la propia" on public.zonas_alerta
  for delete to authenticated using (usuario_id = auth.uid());

-- Alertas: el público ve las no ocultas; el emisor y administradores ven todas las suyas.
create policy "alertas: lectura" on public.alertas
  for select to anon, authenticated
  using (not oculta or emisor_id = auth.uid() or public.es_admin());
-- "Cualquier cuenta registrada" puede emitir (decisión del 6 de noviembre de 2026).
create policy "alertas: emitir" on public.alertas
  for insert to authenticated with check (emisor_id = auth.uid());
create policy "alertas: editar las propias" on public.alertas
  for update to authenticated using (emisor_id = auth.uid()) with check (emisor_id = auth.uid());

-- Punto exacto: solo el emisor (al crearla) y administradores.
create policy "ubicacion alerta: lectura" on public.alertas_ubicacion
  for select to authenticated
  using (public.es_admin() or exists (select 1 from public.alertas a
         where a.id = alerta_id and a.emisor_id = auth.uid()));
create policy "ubicacion alerta: registrar" on public.alertas_ubicacion
  for insert to authenticated
  with check (exists (select 1 from public.alertas a
              where a.id = alerta_id and a.emisor_id = auth.uid()));

-- Notificaciones: cada quien las suyas; solo puede marcarlas como leídas.
create policy "notificaciones: ver las propias" on public.notificaciones
  for select to authenticated using (usuario_id = auth.uid());
create policy "notificaciones: marcar leídas" on public.notificaciones
  for update to authenticated using (usuario_id = auth.uid()) with check (usuario_id = auth.uid());

-- Avistamientos: los ve el dueño de la alerta, quien lo reportó y administradores.
create policy "avistamientos: lectura" on public.avistamientos
  for select to authenticated
  using (reportado_por = auth.uid() or public.es_admin()
         or exists (select 1 from public.alertas a where a.id = alerta_id and a.emisor_id = auth.uid()));
create policy "avistamientos: reportar" on public.avistamientos
  for insert to authenticated
  with check (reportado_por = auth.uid()
              and exists (select 1 from public.alertas a
                          where a.id = alerta_id and public.alerta_vigente(a)
                            and a.emisor_id <> auth.uid()));

commit;
