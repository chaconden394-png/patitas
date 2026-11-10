# Registro de avance — Patitas

## Estado actual (6 de noviembre de 2026)
- **Etapa 1:** probada; la app arranca en tu Codespace.
- **Etapa 2:** funcionó en tu primer proyecto de Supabase. Estás empezando desde cero con `GUIA_SUPABASE.md`.
- **Alerta Patitas, Parte A:** lista y probada localmente.
- **Etapa 3 (cuentas):** lista y probada con un simulador de Supabase. **Falta probarla con tu Supabase real** (`GUIA_ETAPA3.md`).

---

## Etapa 3 · Cuentas

### ✅ Terminado y probado
| Función | Cómo se probó |
|---|---|
| Registro con tipo de cuenta, nombre, correo, contraseña y aceptación del aviso | Pruebas con la librería real de Supabase + simulador; recorrido en navegador |
| Confirmación de correo (enlace con botón "Continuar" para que los antivirus de correo no lo gasten) | Pruebas + navegador |
| Inicio y cierre de sesión (la sesión se revoca también en Supabase) | Pruebas + navegador |
| Recuperar y cambiar contraseña | Pruebas |
| Renovación automática del token; si falla, se cierra la sesión | Pruebas |
| Mi cuenta: nombre público, biografía, municipio, teléfono privado | Pruebas + navegador; los cambios usan el token de la persona (RLS) |
| Perfil público sin correo ni teléfono | Pruebas |
| Permisos por rol: panel solo para refugios/rescatistas; administración comprobada en la base de datos cada vez | Pruebas |
| Protección CSRF en todos los formularios | Pruebas (y una prueba "rompiendo" la protección a propósito) |
| Límite de intentos: inicio de sesión, registro, recuperación y reenvío | Pruebas |
| Redirecciones solo dentro de Patitas | Pruebas con `//sitio-malo.com` y similares |
| Migración 003: consentimiento del aviso guardado al registrarse; nadie puede inventar esa fecha | 12 pruebas SQL |

### ⚠️ No probado todavía (requiere tu Supabase real)
- Envío y recepción real de correos (confirmación y recuperación).
- Las plantillas de correo y la Site URL configuradas en tu proyecto.
- El simulador imita a Supabase; las reglas RLS reales están probadas aparte en `tests/sql/`.

### 📌 Decisiones técnicas
1. **Sesión en cookie firmada de Flask** (HttpOnly, SameSite=Lax, Secure en producción), 7 días.
   Guarda los tokens de Supabase; el navegador no puede leerlos con JavaScript.
2. **Un cliente de Supabase nuevo por persona y petición** (`cliente_de_usuario`): las sesiones nunca se mezclan.
3. **Enlaces de correo con `token_hash`** verificados por el servidor (`/auth/confirmar`), en lugar del enlace por defecto.
   Requiere cambiar 2 plantillas de correo en Supabase.
4. **CSRF sin librerías extra** (`services/seguridad.py`).
5. **Límite de intentos en memoria**: suficiente en desarrollo. En producción (Etapa 9) habrá que revisarlo,
   porque se reinicia al reiniciar la app y Supabase verá la IP del servidor, no la de cada persona.
6. **Contraseñas**: mínimo 8 caracteres con letras y números (validado en el servidor).
7. **Administradores** solo desde la tabla `administradores` (SQL Editor); el registro nunca los crea.
8. "Eliminar mi cuenta" queda pendiente: requiere la clave secreta en el servidor y el procedimiento de derechos ARCO.

### Pendientes de la etapa
- [ ] Servicio de correo propio (SMTP) para que lleguen correos a cualquier persona.
- [ ] Verificación de teléfono por SMS (proveedor de pago, decisión pendiente).
- [ ] Solicitudes de acceso, corrección y eliminación de datos (con el aviso de privacidad definitivo).

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

### Parte B (ya se puede construir: la Etapa 3 está lista)
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
