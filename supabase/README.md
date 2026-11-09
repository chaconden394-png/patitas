# Carpeta supabase/

| Carpeta / archivo | Qué es |
|---|---|
| `migraciones/001_esquema_inicial.sql` | Tablas, permisos y reglas RLS base. Se ejecuta **una vez**. |
| `migraciones/002_alertas_patitas.sql` | Alerta Patitas: alertas, zonas, avistamientos, notificaciones y la regla de 15 km. **Una vez**, después de la 001. |
| `datos_prueba/datos_ficticios.sql` | 2 refugios y 7 animales inventados. Se puede repetir. |
| `datos_prueba/alerta_ficticia.sql` | Una alerta inventada ("Chispa (prueba)"). Se puede repetir. |

## Reglas
- Las migraciones se ejecutan **en orden** (001, 002, 003…) y **nunca se editan** después de ejecutarlas.
  Si algo cambia, se crea una migración nueva.
- Todas se ejecutan en el editor de SQL de tu proyecto de Supabase.
- Nunca pongas datos personales reales en `datos_prueba/`.

## Qué protege la migración 001 (50 pruebas)
- Un visitante sin sesión no puede leer teléfonos, direcciones de refugios ni la lista de administradores.
- Nadie puede subirse su propio nivel de verificación, cambiar su tipo de cuenta ni aprobar su propio refugio.
- Solo pueden publicar animales las cuentas "habilitadas" o con un refugio verificado.
- Nadie puede editar perfiles, animales o favoritos de otra persona.
- Un animal ocultado por moderación desaparece para el público (también sus fotos).
- Cada cambio de estado de un animal queda en un historial que nadie puede editar a mano.

## Qué hace y protege la migración 002 (50 pruebas)
- Al emitir una alerta, la base de datos avisa **solo** a quienes tienen su zona a 15 km o menos
  y aceptaron recibir alertas (probado con personas a 2.4, 7.9, 13.9, 15.02, 17 y 25 km).
- El punto exacto de extravío es privado; el público ve un punto aproximado (≈ 1 km).
- Las zonas de alerta son privadas y se guardan redondeadas.
- El teléfono del dueño solo se entrega si él lo autorizó, la alerta sigue activa y quien lo pide tiene sesión.
- Límites contra abuso: 2 alertas activas, 3 alertas cada 24 horas, 5 avistamientos por persona y alerta al día.
- Las alertas vencen a los 30 días; las vencidas u ocultas no envían avisos.
- Al marcarla como encontrada, se avisa a todas las personas que la recibieron.
- Nadie puede crear notificaciones falsas ni ver las de otras personas.

Las pruebas están en `tests/sql/`. Usan un PostgreSQL local que imita Supabase; **no** se ejecutan en Supabase.
