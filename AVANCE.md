# Registro de avance — Patitas

## Estado actual (6 de noviembre de 2026)
- **Etapa 1:** probada en el entorno de Claude; la app arranca en tu Codespace.
- **Etapa 2:** ✅ confirmada en tu Supabase (`comprobar_supabase.py` → "Todo listo"). Falta revisar las páginas en el navegador.
- **Alerta Patitas, Parte A:** lista y probada localmente. Falta ejecutar la migración 002 en tu Supabase.

---

## Alerta Patitas (mascotas perdidas)

### Decisiones tuyas (6 nov 2026)
- **Contacto:** el dueño decide si muestra su teléfono; solo lo ven personas con sesión iniciada.
- **Quién emite:** cualquier cuenta registrada. Por eso los límites contra abuso están en la base de datos.
- **Orden:** Parte A ahora; emitir y recibir después de la Etapa 3.

### Parte A ✅ terminada y probada
| Función | Cómo se probó |
|---|---|
| Migración 002: alertas, punto exacto privado, zonas de alerta, avistamientos, notificaciones | PostgreSQL 16 que imita Supabase |
| Regla de 15 km con la fórmula de Haversine | Personas ficticias a 2.4, 7.9, 13.9, 15.02, 17.4 y 25.5 km; solo avisa a ≤ 15 km |
| Permisos, privacidad y límites contra abuso | 50 pruebas en `tests/sql/30_pruebas_alertas.sql` |
| Páginas: lista de alertas, detalle con mapa aproximado, formulario (visual), banda en inicio | 21 pruebas en `tests/test_alertas.py` + capturas a 1280 px y 390 px |
| Mapa con zona aproximada y radio de 15 km (Leaflet) | Los círculos se dibujan; los mosaicos de OpenStreetMap no se pudieron probar aquí |

### ⚠️ No probado todavía
- La migración 002 en tu Supabase real.
- La consulta que une la alerta con el perfil del dueño, contra la API real de Supabase.
- Los mosaicos del mapa (OpenStreetMap) en tu navegador.

### Parte B (después de la Etapa 3: cuentas)
- [ ] Formulario real para emitir alertas (con foto en Supabase Storage).
- [ ] Elegir zona de alertas y activarlas o desactivarlas.
- [ ] Campana de notificaciones dentro de Patitas.
- [ ] Botón "Lo vi" y lista de avistamientos para el dueño.
- [ ] Marcar como encontrada o cancelar; renovar una alerta vencida.
- [ ] Mostrar el teléfono (función `telefono_contacto_alerta`) con sesión iniciada.

### Parte C (al final)
- [ ] Notificaciones push del navegador (Web Push, gratuito). En iPhone requiere agregar Patitas a la pantalla de inicio.

### Decisiones técnicas
1. **La base de datos decide quién recibe la alerta** (trigger), no Flask. Así nadie puede saltarse el radio.
2. **Zonas elegidas por el usuario**, no rastreo de ubicación: una página web no puede rastrear en segundo plano, y es más respetuoso con la privacidad.
3. **Haversine en SQL** en lugar de PostGIS: suficiente para 15 km y sin extensiones extra.
4. **Leaflet + OpenStreetMap** para mapas: gratis, sin clave. Si el uso crece mucho, habrá que cambiar a un proveedor de mosaicos con plan (OpenStreetMap pide no usarlo para mucho tráfico).
5. **Rojo coral solo para alertas**, para que nunca se confundan con botones normales.
6. "Cómo funciona" se movió del menú superior al pie de página para dejar lugar a "Alertas".

---

## Etapa 2 · Supabase

### ✅ Terminado y probado
| Función | Cómo se probó |
|---|---|
| Migración 001: 9 tablas, índices, reglas RLS y permisos por columna | Ejecutada en PostgreSQL 16 que imita Supabase |
| Seguridad de datos (privados, verificación, refugios, animales, favoritos, historial) | 50 pruebas de permisos en `tests/sql/10_pruebas_permisos.sql` |
| Datos ficticios (2 refugios, 7 animales), repetibles sin duplicar | 3 pruebas en `tests/sql/20_datos_prueba.sql` |
| La app lee de Supabase si está configurado; si no, modo de ejemplo | 12 pruebas con un cliente simulado (`tests/test_supabase.py`) |
| La app rechaza la clave secreta si se pone por error | Pruebas con ambos formatos de clave |
| Página amable si la base de datos no responde (sin mostrar detalles técnicos) | Prueba automática |

### ⚠️ No probado todavía (requiere tu proyecto de Supabase)
- Ejecutar la migración en Supabase real.
- La conexión real de la app (`python comprobar_supabase.py`).

### 📌 Decisiones técnicas
1. **Solo clave pública en la app.** Todas las reglas las aplica la base de datos (RLS). La clave secreta no se usa en esta etapa.
2. **Datos privados en tablas separadas:** `perfiles_privados` (teléfono) y `refugios_ubicacion` (dirección exacta).
3. **Permisos por columna:** nadie puede cambiar desde la app su nivel de verificación, su tipo de cuenta, la aprobación de un refugio ni la ocultación de moderación.
4. **Administradores en una tabla aparte** que la app no puede leer ni escribir. Por ahora se agregan desde el editor SQL.
5. **Ubicación aproximada de animales** con 2 decimales (≈ 1 km).
6. **Edad en meses** en la base de datos; la app la muestra como "8 meses" o "2 años".
7. **Historial de estados automático** con un trigger; no se puede editar a mano.
8. **Modo de ejemplo** si `.env` no tiene Supabase, para poder trabajar sin conexión.

### Tablas creadas
`administradores`, `perfiles`, `perfiles_privados`, `refugios`, `refugios_ubicacion`,
`animales`, `animales_historial_estados`, `animales_fotos`, `favoritos`.
Adopciones, mensajes, reportes, notificaciones, campañas y donaciones se agregarán con migraciones nuevas en sus etapas.

---

## Etapa 1 · Proyecto y diseño
- App Flask con 10 páginas, menú adaptable, sin desbordes en celular (390 px).
- Catálogo con filtros validados en el servidor; perdidos/encontrados separados de adopción.
- 8 insignias de estado; insignia "Refugio verificado" solo en refugios aprobados.
- Cabeceras básicas de seguridad; página 404.

---

## ⏳ Pendientes
- [ ] Revisar las páginas de la Etapa 2 en el navegador (animales desde Supabase).
- [ ] Ejecutar la migración 002 y la alerta ficticia en tu Supabase.
- [ ] Empezar desde cero con `GUIA_SUPABASE.md` (repositorio y proyecto de Supabase nuevos).
- [ ] Recibir moodboard y logotipo oficiales.
- [ ] Fotos reales de animales (Etapa 4, con Supabase Storage).
- [ ] Etapa 3: registro, inicio de sesión, recuperación de contraseña y verificación de correo.

## ❓ Decisiones abiertas (no se han inventado)
Proveedor de verificación de identidad · proveedor de pagos · costos máximos · reglas de aprobación
de refugios · requisitos para particulares · conservación de documentos · reglas de moderación ·
condiciones de lanzamiento.
