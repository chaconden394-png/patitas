# Registro de avance — Patitas

## Estado actual (17 de noviembre de 2026)
- **Etapa 1:** probada; la app arranca en tu Codespace.
- **Etapa 2:** funcionó en tu primer proyecto de Supabase. Estás empezando desde cero con `GUIA_SUPABASE.md`.
- **Alerta Patitas, Parte A:** lista y probada localmente.
- **Etapa 3 (cuentas):** ✅ **terminada** (9 nov 2026): probada en tu Supabase y en el navegador.
- **Alerta Patitas, Parte B:** ✅ **terminada** (9 nov 2026): probada en tu Supabase con dos cuentas.
- **Correo de confirmación de cuentas nuevas:** ✅ ya llega (confirmado el 17 nov 2026).
- **Etapa 4 (animales y fotos):** construida y probada aquí (17 nov 2026). **Falta tu prueba en Supabase** (`GUIA_ETAPA4.md`).

---

## Etapa 4 · Animales y fotos

### Decisiones tuyas (17 nov 2026)
- **Quién publica:** cualquier cuenta de **refugio o rescatista** desde que confirma su correo. Sus animales muestran
  **"Sin verificar"** hasta que un administrador apruebe su refugio o su cuenta (siempre a mano).
- **Fotos:** máximo **3 por animal**.

### ✅ Construido y probado (falta tu prueba en Supabase)
| Función | Cómo se probó |
|---|---|
| Migración 005: quién publica, bloqueos, refugio suspendido, 10 animales/día, borrar propios | 28 pruebas SQL nuevas (`tests/sql/60_pruebas_animales.sql`); 164 en total |
| Contenedor `fotos-animales`: solo en la carpeta propia, máx. 3 por animal, sin repetir archivos | Pruebas SQL |
| Mi panel: resumen, mis animales, publicar, editar, cambiar estado, borrar (con confirmación) | 34 pruebas nuevas (`tests/test_animales.py`); 147 en total |
| Fotos: limpias (sin GPS), reducidas, foto principal, borrar; si falla el registro se borra el archivo | Pruebas + navegador |
| Mi refugio: datos públicos + dirección privada (nunca en páginas públicas); queda pendiente | Pruebas + navegador |
| Ficha: galería, convivencia, salud, requisitos, quién lo cuida, insignia "Sin verificar" | Pruebas + navegador |
| Catálogo: filtros de edad, vacunas, esterilización, convivencia; 12 por página | Pruebas (con Supabase simulado y en modo de ejemplo) |
| Vista en computadora (1280 px) y celular (390 px) sin desbordes ni errores de JavaScript | Recorrido automático en navegador |

Revisión de calidad: se rompió el código a propósito 11 veces (fotos sin limpiar, archivo suelto, todos
"verificados", relación ambigua, sin límite de fotos, borrar sin fotos, estado "perdido", y 4 reglas de la
migración) y las pruebas lo detectaron siempre.

### 📌 Decisiones técnicas
1. **Las reglas viven en la base de datos** (migración 005); Flask solo da mensajes claros.
2. **Bloqueos en tabla privada** (`bloqueos_publicacion`): nadie puede leerla desde la app; se usa desde el SQL Editor.
3. **Una cuenta bloqueada** no publica ni edita, pero sí puede marcar animales como adoptados o en proceso.
4. **Perdidos y encontrados no se publican aquí**: van por Alerta Patitas (y la sección de reportes, Etapa 6).
5. **Relación explícita** `perfiles!responsable_id`: sin ella Supabase no sabría qué relación usar (también existe la de favoritos).
6. **Borrar**: primero el registro y después los archivos; si un archivo no se puede borrar, queda anotado en la terminal.

### ⚠️ No probado todavía
- La migración 005 en tu Supabase real y las fotos en su Storage real.
- La consulta con relaciones incrustadas contra la API real (el simulador la revisa, pero no es Supabase).

### Pendientes conocidos
- Panel de administración para aprobar refugios y moderar (Etapa 7). Por ahora: SQL Editor (ver `GUIA_ETAPA4.md`).
- Fotos de animales ocultos por moderación: siguen accesibles con el enlace directo (igual que en alertas; Etapa 7).
- Conteo de animales por refugio en la página Refugios.
- Filtro por distancia (necesita ubicación aproximada de cada animal; se decidirá después).

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

### Registro de problemas resueltos
- **9 nov 2026 · "No pudimos completar la operación" al crear cuenta.** La app no anotaba la causa.
  Se agregó el detalle en la terminal (`services/autenticacion.py`) y apareció
  `unexpected_failure · Error sending confirmation email`. Con `probar_smtp.py` se encontró
  un correo mal escrito en la configuración SMTP de Supabase. ✅ Resuelto.

### Pendientes de la etapa
- [x] Servicio de correo propio (SMTP con Gmail) configurado. Antes del lanzamiento: cambiar a un servicio con dominio propio.
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

### Parte B ✅ construida y probada (falta tu prueba en Supabase)
| Función | Cómo se probó |
|---|---|
| Emitir alerta con foto, datos, mapa y "Usar mi ubicación" | Pruebas + navegador (computadora y celular) |
| Foto limpia: sin EXIF/GPS, girada, máx. 1600 px, solo JPEG | Pruebas (una foto con GPS sale sin datos ocultos) |
| Foto en Storage, en la carpeta de cada persona; se borra si la alerta no se guarda | SQL (reglas de Storage) + pruebas |
| `emitir_alerta()`: alerta y ubicación en una sola operación | 19 pruebas SQL nuevas |
| Mi zona de alertas: guardar, cambiar, desactivar, borrar | Pruebas + navegador |
| Distancia de cada alerta a tu zona en la lista | Pruebas |
| "Lo vi": aviso a la familia; solo la dueña ve la lista y los puntos | Pruebas + navegador |
| Teléfono solo con sesión, autorización y alerta activa | Pruebas |
| Cerrar (encontrada/cancelada) y renovar (≤ 7 días) | SQL + pruebas + navegador |
| Mis alertas; campana con contador; notificaciones y "marcar leídas" | Pruebas + navegador |

Revisión de calidad: se introdujeron 3 fallos a propósito (foto con GPS, foto sin borrar, zona con
`usuario_id`) y las pruebas los detectaron. Se corrigió un riesgo de seguridad (texto de "Lo vi" mostrado
como HTML en el mapa) y un problema que habría fallado en Supabase (guardar la zona con "upsert").

### Decisiones técnicas (Parte B)
1. **Pillow** (gratis) limpia las fotos antes de subirlas: protege la ubicación de las casas.
2. **Contenedor `fotos-alertas` público**: la alerta es pública. Solo JPEG, máximo 5 MB.
3. **`emitir_alerta()` con permisos de la persona** (no salta RLS) y en una sola operación.
4. **Renovar** solo cuando faltan 7 días o menos, para que las alertas no queden activas para siempre.
5. **Las notificaciones se calculan al emitir**: quien elige su zona después no recibe alertas viejas,
   pero las ve en la lista ordenadas por distancia.

### Pendientes conocidos
- Las fotos de alertas ocultadas por moderación siguen accesibles si alguien tiene el enlace directo (Etapa 7).
- Fotos de alertas cerradas: definir cuánto tiempo se conservan (política de conservación).

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
- [ ] Ejecutar la migración 005 y probar la Etapa 4 en tu Supabase (`GUIA_ETAPA4.md`).
- [ ] Etapa 3: registro, inicio de sesión, recuperación de contraseña y verificación de correo.

## ❓ Decisiones abiertas (no se han inventado)
Proveedor de verificación de identidad · proveedor de pagos · costos máximos · reglas de aprobación
de refugios · requisitos para particulares · conservación de documentos · reglas de moderación ·
condiciones de lanzamiento.
