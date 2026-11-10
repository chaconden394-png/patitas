-- =============================================================================
-- Patitas · Migración 003 · Cuentas (Etapa 3)
--
-- 1. Al registrarse, guarda la fecha en que la persona aceptó el aviso de
--    privacidad (si lo aceptó en el formulario).
-- 2. Esa fecha ya no se puede cambiar a mano desde la app: es un registro de
--    consentimiento. Para volver a aceptar (por ejemplo, si el aviso cambia) se
--    usa la función aceptar_aviso_privacidad(), que siempre pone la hora actual.
--
-- Requisito: migraciones 001 y 002.
-- Dónde ejecutarla: editor de SQL de Supabase, UNA sola vez.
-- =============================================================================

begin;

-- Reemplaza la función de la migración 001 (mismo nombre, mismo trigger).
create or replace function public.crear_perfil_nuevo_usuario()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  nombre  text := left(trim(coalesce(new.raw_user_meta_data ->> 'nombre_publico', '')), 60);
  tipo    text := coalesce(new.raw_user_meta_data ->> 'tipo_cuenta', 'adoptante');
  acepto  boolean := coalesce(new.raw_user_meta_data ->> 'acepto_aviso_privacidad', '') = 'true';
begin
  if char_length(nombre) < 2 then
    nombre := 'Usuario de Patitas';
  end if;
  -- Nunca "administrador": esa cuenta solo se da desde la tabla administradores.
  if tipo not in ('adoptante', 'rescatista', 'refugio', 'reportante', 'voluntario', 'negocio') then
    tipo := 'adoptante';
  end if;

  insert into public.perfiles (id, nombre_publico, tipo_cuenta)
  values (new.id, nombre, tipo::public.tipo_cuenta);
  insert into public.perfiles_privados (id, acepto_aviso_privacidad_en)
  values (new.id, case when acepto then now() end);
  return new;
end;
$$;
revoke execute on function public.crear_perfil_nuevo_usuario() from public, anon, authenticated;

-- La fecha de aceptación ya no se edita directamente.
revoke update (acepto_aviso_privacidad_en) on public.perfiles_privados from authenticated;

create function public.aceptar_aviso_privacidad()
returns timestamptz language plpgsql security definer set search_path = '' as $$
declare
  momento timestamptz := now();
begin
  if auth.uid() is null then
    raise exception 'Necesitas iniciar sesión.' using errcode = 'insufficient_privilege';
  end if;
  update public.perfiles_privados set acepto_aviso_privacidad_en = momento where id = auth.uid();
  return momento;
end;
$$;
revoke execute on function public.aceptar_aviso_privacidad() from public, anon;
grant execute on function public.aceptar_aviso_privacidad() to authenticated;

commit;
