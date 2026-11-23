"""The account Google Play's reviewers sign in with (Play Console → App content → App access): a family with believable,
made-up data, so the reviewer sees what Mam-IA does. Modelled on BodyLens's tools/demo_data.py.

    docker exec -it mamia python -m app.demo.play_review playreview@jtgcloud.com
    docker exec mamia python -m app.demo.play_review playreview@jtgcloud.com --password-file /data/secrets/playreview.txt

- If the account does not exist, it is made now: the password is asked for in the terminal and never printed or kept
  anywhere else; or, with --password-file, a random one is made and written only to that file (mode 600), never
  shown (the family is free for life, like the administrator's).
- It can be run again at any time: the same documents are rewritten with dates around today (the agenda is always
  current) and nothing is duplicated. What the reviewer adds is left alone.
- The partner is a demo account: an address on a domain that does not exist (.invalid) and no password, so nobody can
  sign in with it. Every person and place is invented."""
from __future__ import annotations

import getpass
import sys
from datetime import date, timedelta

from app.accounts import users
from app.billing import codes
from app.core import db
from app.data import store
from app.families import service as families

DEMO_DOMAIN = "demo.mamia.invalid"
FAMILY = "Familia Martín (demo)"


def _docs(today: date, me: str, partner: str) -> list[dict]:
    d = lambda n: (today + timedelta(days=n)).isoformat()   # noqa: E731
    wd = today.weekday()   # Monday = 0
    monday = today - timedelta(days=wd)
    kid1, kid2 = "demo-lucas", "demo-vega"
    out = [
        {"c": "members", "id": kid1, "data": {"name": "Lucas", "kind": "kid", "color": "c3", "order": 2, "birthday": f"{today.year - 8}-03-14",
         "info": {"school": "CEIP Los Almendros", "course": "3.º B", "teacher": "Marta · tutoria3b@cole.invalid",
                  "schedule": "Cole de 9:00 a 16:00 · Natación lunes y miércoles 17:30", "allergies": "Frutos secos",
                  "doctor": "Dra. Ruiz · C. S. Las Delicias", "clothes": "8-9 años", "shoes": "32",
                  "contacts": "Ana (madre de Hugo) 600 000 000"}}},
        {"c": "members", "id": kid2, "data": {"name": "Vega", "kind": "kid", "color": "c4", "order": 3, "birthday": f"{today.year - 4}-09-02",
         "info": {"school": "Escuela infantil Rayuela", "course": "2.º de infantil", "schedule": "De 9:00 a 13:30 · Inglés los jueves",
                  "health": "Ventolín si tose de noche", "clothes": "4 años", "shoes": "26"}}},
        # the agenda: this week and the next (fixed ids, so running it again rewrites them)
        {"c": "events", "id": "demo-natacion", "data": {"title": "Natación", "start": f"{monday.isoformat()}T17:30", "end": f"{monday.isoformat()}T18:30",
         "who": [kid1], "driver": me, "cat": "peques", "remind": 30, "repeat": {"freq": "weekly", "every": 1, "days": [0, 2]}}},
        {"c": "events", "id": "demo-ingles", "data": {"title": "Inglés", "start": f"{(monday + timedelta(days=3)).isoformat()}T17:00",
         "who": [kid2], "pickup": partner, "cat": "peques", "remind": 60, "repeat": {"freq": "weekly", "every": 1, "days": [3]}}},
        {"c": "events", "id": "demo-dentista", "data": {"title": "Dentista", "start": f"{d(1)}T16:00", "who": [kid2], "driver": partner,
         "place": "Clínica Sonrisas", "cat": "salud", "remind": 60}},
        {"c": "events", "id": "demo-reunion", "data": {"title": "Reunión con la tutora", "start": f"{d(2)}T13:00", "who": [me, kid1],
         "place": "CEIP Los Almendros", "cat": "cole", "remind": 1440}},
        {"c": "events", "id": "demo-excursion", "data": {"title": "Excursión al Retiro", "start": d(3), "allDay": True, "who": [kid1],
         "cat": "cole", "notes": "Llevar almuerzo, gorra y la autorización firmada."}},
        {"c": "events", "id": "demo-cumple", "data": {"title": "Cumple de la abuela", "start": f"{d(5)}T14:00", "who": [me, partner, kid1, kid2],
         "place": "Casa de los abuelos", "cat": "ocio", "remind": 120}},
        {"c": "events", "id": "demo-trabajo", "data": {"title": "Presentación en el trabajo", "start": f"{d(1)}T10:00", "end": f"{d(1)}T11:30",
         "who": [me], "cat": "trabajo"}},
        {"c": "events", "id": "demo-cena", "data": {"title": "Cena con amigos", "start": f"{d(6)}T21:00", "who": [me, partner], "cat": "pareja"}},
        {"c": "events", "id": "demo-pediatra", "data": {"title": "Revisión del pediatra", "start": f"{d(9)}T09:30", "who": [kid2],
         "driver": me, "cat": "salud", "remind": 1440}},
        # tasks and routines
        {"c": "tasks", "id": "demo-comedor", "data": {"title": "Pagar el comedor de diciembre", "due": d(0), "who": me, "cat": "cole", "prio": "alta", "remind": 0, "time": "10:00"}},
        {"c": "tasks", "id": "demo-autorizacion", "data": {"title": "Firmar la autorización de la excursión", "due": d(1), "who": partner, "cat": "papeleo"}},
        {"c": "tasks", "id": "demo-regalo", "data": {"title": "Comprar el regalo de la abuela", "due": d(3), "who": partner, "cat": "compras"}},
        {"c": "tasks", "id": "demo-itv", "data": {"title": "Pedir cita para la ITV", "due": d(-2), "cat": "papeleo"}},
        {"c": "tasks", "id": "demo-basura", "data": {"title": "Sacar la basura", "due": d(0), "who": partner, "cat": "casa",
         "repeat": {"freq": "daily", "every": 1}, "rotate": [me, partner]}},
        {"c": "tasks", "id": "demo-lavadora", "data": {"title": "Poner una lavadora", "due": d(1), "who": me, "cat": "casa",
         "repeat": {"freq": "weekly", "every": 1, "days": [1, 4]}}},
        {"c": "tasks", "id": "demo-mochila", "data": {"title": "Preparar la mochila de natación", "due": d(0), "who": kid1, "cat": "peques",
         "repeat": {"freq": "weekly", "every": 1, "days": [0, 2]}}},
        # done this week (the "Reparto" screen)
        {"c": "done", "id": "demo-hecho-1", "data": {"title": "Sacar la basura", "by": me, "date": d(-1), "cat": "casa"}},
        {"c": "done", "id": "demo-hecho-2", "data": {"title": "Poner una lavadora", "by": partner, "date": d(-2), "cat": "casa"}},
        {"c": "done", "id": "demo-hecho-3", "data": {"title": "Hacer la compra del súper", "by": partner, "date": d(-3), "cat": "compras"}},
        # shopping
        {"c": "items", "id": "demo-leche", "data": {"list": "super", "text": "Leche", "qty": "6", "section": "Lácteos y huevos"}},
        {"c": "items", "id": "demo-platanos", "data": {"list": "super", "text": "Plátanos", "section": "Fruta y verdura"}},
        {"c": "items", "id": "demo-yogures", "data": {"list": "super", "text": "Yogures naturales", "qty": "8", "section": "Lácteos y huevos"}},
        {"c": "items", "id": "demo-pan", "data": {"list": "super", "text": "Pan de molde", "section": "Panadería"}},
        {"c": "items", "id": "demo-detergente", "data": {"list": "super", "text": "Detergente", "section": "Limpieza"}},
        {"c": "items", "id": "demo-tortilla", "data": {"list": "super", "text": "Patatas", "qty": "1 kg", "section": "Fruta y verdura", "src": "menu"}},
        {"c": "items", "id": "demo-termometro", "data": {"list": "farmacia", "text": "Paracetamol infantil", "section": "Farmacia"}},
    ]
    # the menu of this week
    dishes = [("Crema de calabacín", "Macarrones con tomate"), ("Tortilla de patatas", "Lentejas"), ("Pescado al horno", "Arroz a la cubana"),
              ("Pizza casera", "Pollo asado"), ("Sopa y croquetas", "Merluza rebozada"), ("Hamburguesas", ""), ("Cena fuera", "")]
    for i, (dinner, school) in enumerate(dishes):
        day = (monday + timedelta(days=i)).isoformat()
        out.append({"c": "meals", "id": f"{day}:cena", "data": {"date": day, "slot": "cena", "dish": dinner,
                                                               **({"ingredients": ["patatas", "huevos", "cebolla"]} if dinner == "Tortilla de patatas" else {})}})
        if school:
            out.append({"c": "meals", "id": f"{day}:comida", "data": {"date": day, "slot": "comida", "school": school}})
    return out


def _partner(con, family_id: int) -> users.User:
    """The demo partner: an account nobody can sign in with (an address that cannot exist and no usable password)."""
    email = f"sam@{DEMO_DOMAIN}"
    u = users.get_by_email(con, email)
    if u is None:
        con.execute("INSERT INTO users(email, name, pw_hash, family_id, role, created_at) VALUES(?,?,?,?,?,?)",
                    (email, "Sam (demo)", "!demo-account-no-password", family_id, "admin", db.now_iso()))
        u = users.get_by_email(con, email)
    if not u.member_id:
        families._link_member(con, u)
        u = users.get_by_email(con, email)
    return u


def fill(email: str, password: str | None = None) -> dict:
    """Make (if needed) and fill the reviewer's family. Returns what was done."""
    db.init_db()
    with db.tx() as con:
        u = users.get_by_email(con, email)
        made = False
        if u is None:
            if not password:
                raise SystemExit(f"{email} does not exist: give it a password (asked in the terminal).")
            u = families.create_family(con, FAMILY, "Alex", email, password)
            made = True
        codes.grant(con, u.family_id, "playreview", None)   # free for life: never read-only
        partner = _partner(con, u.family_id)
        u = users.get_user(con, u.id)
        results = store.apply(con, u.family_id, partner.id, _docs(date.today(), u.member_id, partner.member_id))
    bad = [r for r in results if not r.get("ok")]
    if bad:
        raise SystemExit(f"Some demo documents were refused: {bad[:3]}")
    return {"account": email, "made": made, "documents": len(results), "family": u.family_id}


def main(argv: list[str]) -> int:
    pw_file = None
    if "--password-file" in argv:
        i = argv.index("--password-file")
        if i + 1 >= len(argv):
            print("--password-file needs a path", file=sys.stderr)
            return 2
        pw_file = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 1 or "@" not in argv[0]:
        print("Usage: python -m app.demo.play_review <reviewer's email> [--password-file FILE]", file=sys.stderr)
        return 2
    email = argv[0].strip()
    db.init_db()
    with db.ro() as con:
        exists = users.get_by_email(con, email) is not None
    password = None
    if not exists and pw_file:   # a random password, written only to that file (never printed)
        import os
        import secrets
        password = secrets.token_urlsafe(12)
        os.makedirs(os.path.dirname(pw_file) or ".", exist_ok=True)
        fd = os.open(pw_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(f"{email}\n{password}\n")
        print(f"The password of {email} is in {pw_file} (not shown here).")
    elif not exists:
        password = getpass.getpass(f"{email} does not exist yet. Password for it (it is not shown or saved): ")
        if getpass.getpass("Again: ") != password:
            print("The passwords do not match.", file=sys.stderr)
            return 1
    r = fill(email, password)
    print(f"{'Made and filled' if r['made'] else 'Filled'} {r['account']}: {r['documents']} demo documents (family {r['family']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
