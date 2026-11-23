"""The automatic emails of the account, the family and the subscription. Each function sends in the background and
never fails: an email that cannot go is written in the log (see app.core.mailer). The texts are in Spanish, like the
app; everything that comes from a person (names) is escaped."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape as esc

from app.core import config, crypto, mailer


def base() -> str:
    return config.settings.public_url or "https://mamia.jtgcloud.com"


def _first(name: str) -> str:
    return esc((name or "").split()[0]) if (name or "").strip() else ""


def _hello(name: str) -> str:
    return f"Hola, {_first(name)}." if _first(name) else "Hola."


def day(ms_or_dt) -> str:
    d = ms_or_dt if isinstance(ms_or_dt, datetime) else datetime.fromtimestamp(ms_or_dt / 1000, timezone.utc)
    return d.strftime("%d/%m/%Y")


def unsubscribe_link(user_id: int, what: str) -> str:
    """A link (and the one-click header of the email apps) that turns off one kind of email without signing in."""
    text = f"{user_id}:{what}"
    return f"{base()}/correo/baja?u={user_id}&t={what}&s={crypto.sign(text)}"


def unsubscribe_foot(link: str, what: str) -> str:
    return (f'Recibes este correo porque tienes activados {what} en Mam-IA. '
            f'<a href="{esc(link, quote=True)}" style="color:#5F5568">Dejar de recibirlos</a> · '
            f'o cámbialo en la app, en Ajustes.')


# ---------- account ----------

def welcome_owner(u, family_name: str) -> None:
    mailer.send_later(u.email, "Ya tenéis Mam-IA", mailer.page("¡Ya tenéis Mam-IA!", [
        _hello(u.name),
        f"Hemos creado <b>{esc(family_name)}</b>. Estos son los primeros pasos para que Mam-IA os quite cosas de la cabeza:",
        "<b>1.</b> Apunta lo de esta semana con el botón <b>+</b>: «Dentista Lucas el jueves a las 17:30, lo lleva Pablo».<br>"
        "<b>2.</b> Invita a tu pareja o a quien te ayuda en Familia → Invitar (por correo o por WhatsApp).<br>"
        "<b>3.</b> Activa los avisos en Ajustes. En Android, instala la app para tener alarmas en el móvil.",
        "Los recordatorios también te llegarán por correo; puedes cambiarlo en Ajustes.",
    ], ("Abrir Mam-IA", f"{base()}/app")))


def welcome_member(u, family_name: str) -> None:
    mailer.send_later(u.email, f"Ya estás en {family_name}", mailer.page(f"Ya estás en {family_name}", [
        _hello(u.name),
        f"Ya formas parte de <b>{esc(family_name)}</b> en Mam-IA: veis la misma agenda, las mismas tareas y la misma lista "
        "de la compra, y lo que apunta uno lo ven los demás al momento.",
        "Activa los avisos en Ajustes para que te recuerde lo que te toca. Los recordatorios también te llegarán por "
        "correo; puedes cambiarlo en Ajustes.",
    ], ("Abrir Mam-IA", f"{base()}/app")))


def password_changed(u) -> None:
    mailer.send_later(u.email, "Tu contraseña ha cambiado", mailer.page("Tu contraseña ha cambiado", [
        _hello(u.name),
        "La contraseña de tu cuenta de Mam-IA se acaba de cambiar.",
        "Si has sido tú, no tienes que hacer nada. Si no, cámbiala ahora mismo con «He olvidado mi contraseña».",
    ], ("Recuperar mi cuenta", f"{base()}/recuperar")))


def email_changed(old_email: str, u) -> None:
    mailer.send_later(old_email, "El correo de tu cuenta ha cambiado", mailer.page("El correo de tu cuenta ha cambiado", [
        _hello(u.name),
        f"Tu cuenta de Mam-IA ahora usa la dirección <b>{esc(u.email)}</b>: con ella entras y a ella te llegarán los "
        "avisos. Esta dirección ya no se usa.",
        f"Si no has sido tú, escríbenos cuanto antes a {esc(config.settings.contact_email)}.",
    ]))


def account_deleted(email: str, name: str, family_too: bool) -> None:
    mailer.send_later(email, "Tu cuenta se ha borrado", mailer.page("Tu cuenta se ha borrado", [
        _hello(name),
        "Hemos borrado tu cuenta de Mam-IA" + (", y con ella tu familia y todos sus datos." if family_too else "."),
        "Gracias por haberla usado. Si algún día quieres volver, aquí estaremos.",
    ]))


# ---------- family ----------

def joined(admins: list, u, family_name: str) -> None:
    """To the family's administrators: someone has joined with an invitation."""
    to = [a.email for a in admins if a.id != u.id]
    mailer.send_later(to, f"{u.name} se ha unido a {family_name}", mailer.page(f"{u.name} ya está en la familia", [
        f"<b>{esc(u.name)}</b> ({esc(u.email)}) ha aceptado la invitación y ya forma parte de <b>{esc(family_name)}</b> "
        "en Mam-IA.",
        "Ya podéis repartiros las tareas y los recados: en Reparto veréis quién hace qué.",
    ], ("Abrir Mam-IA", f"{base()}/app#familia")))


def member_joined(u) -> None:
    """Someone has just joined a family with an invitation: welcome to them, a notice to the family's administrators."""
    from app.accounts import users
    from app.core import db
    with db.ro() as con:
        f = con.execute("SELECT name FROM families WHERE id=?", (u.family_id,)).fetchone()
        admins = [x for x in users.family_users(con, u.family_id) if x.role == "admin"]
    if f:
        welcome_member(u, f["name"])
        joined(admins, u, f["name"])


def removed(email: str, name: str, by_name: str, family_name: str) -> None:
    mailer.send_later(email, f"Ya no estás en {family_name}", mailer.page(f"Ya no estás en {family_name}", [
        _hello(name),
        f"{esc(by_name)} te ha quitado de <b>{esc(family_name)}</b> en Mam-IA, y tu cuenta se ha borrado.",
        "Si crees que es un error, habla con esa persona: puede volver a invitarte.",
    ]))


def new_owner(u, by_name: str, family_name: str) -> None:
    mailer.send_later(u.email, f"Ahora gestionas {family_name}", mailer.page(f"Ahora gestionas {family_name}", [
        _hello(u.name),
        f"{esc(by_name)} te ha pasado <b>{esc(family_name)}</b>: ahora eres quien gestiona la familia y su suscripción.",
        "Puedes ver la suscripción y cambiar el plan en Tu cuenta.",
    ], ("Ver la suscripción", f"{base()}/cuenta")))


def family_deleted_by_owner(emails: list[str], by_name: str, family_name: str) -> None:
    mailer.send_later(emails, f"{family_name} se ha borrado de Mam-IA", mailer.page("Vuestra familia se ha borrado", [
        f"{esc(by_name)} ha borrado <b>{esc(family_name)}</b> de Mam-IA, y con ella vuestras cuentas y todos los datos "
        "de la familia.",
        "Si crees que es un error, habla con esa persona.",
    ]))


def family_deleted_by_admin(emails: list[str], family_name: str) -> None:
    mailer.send_later(emails, f"{family_name} se ha borrado de Mam-IA", mailer.page("Vuestra familia se ha borrado", [
        f"La administración del servidor ha borrado <b>{esc(family_name)}</b> de Mam-IA, con sus cuentas y sus datos.",
        f"Si crees que es un error, escríbenos a {esc(config.settings.contact_email)}.",
    ]))


def new_family_to_admins(admins: list, owner, family_name: str, how: str) -> None:
    """To the server's administrators: a family has signed up."""
    to = [a.email for a in admins if a.id != owner.id]
    mailer.send_later(to, f"Nueva familia: {family_name}", mailer.page("Nueva familia en Mam-IA", [
        f"<b>{esc(family_name)}</b> se ha dado de alta: {esc(owner.name)} ({esc(owner.email)}).",
        f"Acceso: {esc(how)}.",
    ], ("Ver en Administración", f"{base()}/admin")))


# ---------- subscription ----------

def access_ending(owner, family_name: str, until_ms: int, days: int) -> None:
    when = "mañana" if days <= 1 else f"dentro de {days} días"
    mailer.send_later(owner.email, f"Tu acceso gratis termina {when}", mailer.page("Tu acceso gratis termina pronto", [
        _hello(owner.name),
        f"El acceso gratis de <b>{esc(family_name)}</b> a Mam-IA termina {when}, el {day(until_ms)}.",
        "Para seguir apuntando sin cortes, elige un plan (2,50 € al mes o 25 € al año para toda la familia). "
        "Si no, la familia pasará a solo lectura: podréis ver y descargar todo, pero no apuntar nada nuevo. "
        "No se borra nada.",
    ], ("Elegir un plan", f"{base()}/cuenta")))


def read_only(owner, family_name: str) -> None:
    mailer.send_later(owner.email, "Tu familia está en solo lectura", mailer.page("Renueva para seguir apuntando", [
        _hello(owner.name),
        f"La suscripción de <b>{esc(family_name)}</b> ha terminado, así que Mam-IA está en modo solo lectura: podéis ver "
        "y descargar todo, pero no apuntar ni cambiar nada.",
        "No se ha borrado nada. En cuanto renuevas, todo vuelve a funcionar como antes.",
    ], ("Renovar la suscripción", f"{base()}/cuenta")))


def payment_failed(owner, family_name: str) -> None:
    mailer.send_later(owner.email, "No hemos podido cobrar tu suscripción", mailer.page("Revisa tu forma de pago", [
        _hello(owner.name),
        f"No hemos podido cobrar la suscripción de <b>{esc(family_name)}</b>. Stripe lo volverá a intentar en los "
        "próximos días.",
        "Para que no se corte, revisa la tarjeta o cámbiala desde Tu cuenta.",
    ], ("Revisar la forma de pago", f"{base()}/cuenta")))
