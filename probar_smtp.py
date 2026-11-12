"""
Diagnóstico del correo (SMTP) de Gmail.

Prueba, con los MISMOS datos que pusiste en Supabase, si Gmail acepta la
conexión y envía un correo de prueba. Te dice en español qué está mal.

Ejecutar en la terminal de Codespaces:
    python probar_smtp.py

Tu contraseña de aplicación se escribe oculta y NO se guarda en ningún lado.
"""
import getpass
import smtplib
import socket
import ssl
import sys
from email.message import EmailMessage

HOST = "smtp.gmail.com"
TIEMPO_LIMITE = 20  # segundos


def explicar(error):
    """Traduce el error de Gmail a una explicación con solución."""
    texto = str(error)
    if isinstance(error, smtplib.SMTPAuthenticationError):
        if "534" in texto or "Application-specific password required" in texto:
            return ("Gmail pide una CONTRASEÑA DE APLICACIÓN. Usaste la contraseña normal de Gmail.\n"
                    "   → Crea una en tu cuenta de Google: busca 'Contraseñas de aplicaciones'.")
        return ("Gmail RECHAZÓ el usuario o la contraseña (error 535).\n"
                "   → Revisa que el correo esté completo (con @gmail.com).\n"
                "   → Crea una contraseña de aplicación NUEVA y escríbela sin espacios.\n"
                "   → Verifica que la verificación en dos pasos siga activada.")
    if isinstance(error, smtplib.SMTPSenderRefused):
        return "Gmail no acepta ese remitente. El remitente debe ser el mismo Gmail del usuario."
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return "Gmail rechazó el destinatario. Revisa que el correo de prueba esté bien escrito."
    if isinstance(error, (socket.timeout, TimeoutError)):
        return "La conexión tardó demasiado (bloqueada o lenta). Prueba con el otro puerto."
    if isinstance(error, (ConnectionRefusedError, OSError)) and not isinstance(error, smtplib.SMTPException):
        return f"No se pudo conectar con Gmail en ese puerto ({texto}). Prueba con el otro puerto."
    return f"Error inesperado: {type(error).__name__}: {texto}"


def probar(puerto, usuario, contrasena, destino):
    print(f"\nProbando {HOST}, puerto {puerto}…")
    contexto = ssl.create_default_context()
    try:
        if puerto == 465:
            servidor = smtplib.SMTP_SSL(HOST, puerto, timeout=TIEMPO_LIMITE, context=contexto)
        else:
            servidor = smtplib.SMTP(HOST, puerto, timeout=TIEMPO_LIMITE)
            servidor.starttls(context=contexto)
        with servidor:
            print("  ✓ Conexión con Gmail correcta")
            servidor.login(usuario, contrasena)
            print("  ✓ Gmail aceptó el usuario y la contraseña de aplicación")
            mensaje = EmailMessage()
            mensaje["From"] = f"Patitas <{usuario}>"
            mensaje["To"] = destino
            mensaje["Subject"] = "Prueba de correo de Patitas"
            mensaje.set_content("Si recibiste este correo, el SMTP de Gmail funciona.")
            servidor.send_message(mensaje)
            print(f"  ✓ Correo de prueba enviado a {destino}")
            return True
    except Exception as error:  # noqa: BLE001 - queremos explicar cualquier fallo
        print("  ✗ " + explicar(error))
        return False


def main():
    print("Diagnóstico del correo de Patitas (Gmail)")
    print("Escribe los MISMOS datos que pusiste en Supabase.\n")
    usuario = input("Gmail de Patitas (Username): ").strip()
    # replace quita los espacios que Google muestra en la contraseña de aplicación
    contrasena = getpass.getpass("Contraseña de aplicación (no se verá al escribir): ").replace(" ", "")
    destino = input("¿A qué correo envío la prueba? (Enter = el mismo Gmail): ").strip() or usuario

    if "@" not in usuario:
        print("\n✗ El usuario debe ser el correo completo, por ejemplo patitas.tijuana.app@gmail.com")
        return 1
    if len(contrasena) != 16:
        print(f"\n⚠ La contraseña tiene {len(contrasena)} caracteres; las de aplicación tienen 16. "
              "Puede que no sea una contraseña de aplicación.")

    resultados = {puerto: probar(puerto, usuario, contrasena, destino) for puerto in (587, 465)}
    print()
    if any(resultados.values()):
        buenos = [str(p) for p, ok in resultados.items() if ok]
        print(f"RESULTADO: tus datos de Gmail funcionan (puerto {' y '.join(buenos)}).")
        print("Si Supabase sigue fallando, el problema está en lo que se escribió en Supabase")
        print("o en la plantilla de correo. Compara campo por campo con lo que escribiste aquí.")
        return 0
    print("RESULTADO: Gmail no aceptó la conexión. Corrige lo que indica arriba y vuelve a probar.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
