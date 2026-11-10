"""
Comprueba la conexión con Supabase, paso a paso.

Ejecutar en la terminal de Codespaces, dentro de la carpeta del proyecto:
    python comprobar_supabase.py

No muestra tus claves completas en pantalla.
"""
import sys

from app import app
from services.supabase_cliente import es_clave_secreta


def paso(numero, texto):
    print(f"\n[{numero}] {texto}")


def main():
    cfg = app.config
    url = cfg.get("SUPABASE_URL", "")
    clave = cfg.get("SUPABASE_CLAVE_PUBLICA", "")

    paso(1, "Revisando el archivo .env")
    if not url or not clave:
        print("  ✗ Falta SUPABASE_URL o SUPABASE_CLAVE_PUBLICA en .env")
        return 1
    if not url.startswith("https://"):
        print("  ✗ SUPABASE_URL debe empezar con https://")
        return 1
    if es_clave_secreta(clave):
        print("  ✗ ¡Pusiste la clave SECRETA! Bórrala de .env y usa la clave pública (publishable/anon).")
        return 1
    print(f"  ✓ URL: {url}")
    print(f"  ✓ Clave pública: {clave[:14]}… (oculta)")

    with app.app_context():
        from services import animales as servicio
        from services.supabase_cliente import obtener_cliente

        paso(2, "Consultando la tabla de animales como visitante")
        try:
            filas = obtener_cliente().table("animales").select("id,nombre,estado").limit(5).execute().data
        except Exception as error:
            print(f"  ✗ No se pudo consultar: {error}")
            print("    ¿Ejecutaste la migración 001 en el editor SQL de Supabase?")
            return 1
        print(f"  ✓ Conexión correcta. Animales visibles: {len(filas)}")
        for f in filas:
            print(f"    - {f['nombre']} ({f['estado']})")
        if not filas:
            print("    (vacío: ejecuta supabase/datos_prueba/datos_ficticios.sql para ver datos)")

        paso(3, "Comprobando que los datos privados están protegidos")
        try:
            privados = obtener_cliente().table("perfiles_privados").select("id").limit(1).execute().data
            if privados:
                print("  ✗ ¡PELIGRO! Un visitante puede leer datos privados. Revisa las políticas RLS.")
                return 1
            print("  ✓ Un visitante no obtiene datos privados (lista vacía).")
        except Exception:
            print("  ✓ Un visitante no tiene permiso para leer datos privados.")

        paso(4, "Probando las consultas que usa la app")
        try:
            print(f"  ✓ Catálogo: {len(servicio.listar_catalogo({}))} animales")
            print(f"  ✓ Perdidos y encontrados: {len(servicio.listar_perdidos_encontrados())}")
            print(f"  ✓ Refugios: {len(servicio.listar_refugios())}")
        except servicio.ErrorBaseDeDatos as error:
            print(f"  ✗ Error: {error}")
            return 1

        paso(5, "Revisando Alerta Patitas (migración 002)")
        try:
            from services import alertas as servicio_alertas
            vigentes = servicio_alertas.listar_vigentes()
            print(f"  ✓ Alertas activas: {len(vigentes)}")
            for a in vigentes[:5]:
                print(f"    - {a['nombre']} ({a['zona_referencia']})")
            if not vigentes:
                print("    (vacío: ejecuta supabase/datos_prueba/alerta_ficticia.sql para ver una)")
        except servicio.ErrorBaseDeDatos as error:
            print(f"  ✗ No se pudieron leer las alertas: {error}")
            print("    ¿Ejecutaste supabase/migraciones/002_alertas_patitas.sql?")
            return 1
        try:
            zonas = obtener_cliente().table("zonas_alerta").select("usuario_id").limit(1).execute().data
            if zonas:
                print("  ✗ ¡PELIGRO! Un visitante puede ver zonas de alerta. Revisa las políticas RLS.")
                return 1
            print("  ✓ Un visitante no obtiene zonas de alerta (lista vacía).")
        except Exception:
            print("  ✓ Un visitante no tiene permiso para ver zonas de alerta.")

        paso(6, "Revisando cuentas (migración 003)")
        try:
            obtener_cliente().rpc("aceptar_aviso_privacidad", {}).execute()
            print("  ✗ ¡PELIGRO! Un visitante pudo usar una función de cuentas. Revisa la migración 003.")
            return 1
        except Exception as error:
            texto = str(error)
            if "PGRST202" in texto or "Could not find the function" in texto:
                print("  ✗ Falta la migración 003. Ejecuta supabase/migraciones/003_cuentas.sql")
                return 1
            print("  ✓ La migración 003 está instalada y protegida.")

    print("\nTodo listo: la app puede leer datos de Supabase.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
