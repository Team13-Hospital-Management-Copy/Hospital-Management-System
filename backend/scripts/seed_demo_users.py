"""Create the staff accounts needed to click through the Sprint 1 demo UI.

There is no self-service staff registration endpoint by design (RBAC: staff accounts are
provisioned by an administrator - see US-19, not yet built), so for local/demo use this
script inserts them directly. Safe to re-run: existing usernames are left untouched.

Usage:
    python -m scripts.seed_demo_users
"""

from app.database import Base, SessionLocal, engine
from app.models import User
from app.roles import ADMINISTRATOR, RECEPTIONIST
from app.security import hash_password

DEMO_USERS = [
    ("admin1", "Admin#12345", ADMINISTRATOR),
    ("reception1", "Reception#12345", RECEPTIONIST),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for username, password, role in DEMO_USERS:
            if db.query(User).filter(User.username == username).one_or_none() is not None:
                print(f"skip {username}: already exists")
                continue
            db.add(User(username=username, password_hash=hash_password(password), role=role))
            db.commit()
            print(f"created {username} ({role})")


if __name__ == "__main__":
    main()
