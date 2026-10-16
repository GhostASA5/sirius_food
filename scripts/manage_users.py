import argparse
from getpass import getpass

from app.core.security import hash_password
from app.database import SessionLocal
from app.models import Role, User


def main():
    parser = argparse.ArgumentParser(description="Настройка учётной записи пользователя")
    parser.add_argument("email")
    parser.add_argument("--role", choices=("student", "cook", "courier", "admin"))
    parser.add_argument("--set-password", action="store_true")
    args = parser.parse_args()
    if args.role is None and not args.set_password:
        parser.error("Укажите --role или --set-password")
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == args.email).one_or_none()
        if user is None:
            parser.error("Пользователь не найден")
        if args.role:
            role = db.query(Role).filter(Role.name == args.role).one()
            user.role_id = role.id
        if args.set_password:
            password = getpass("Новый пароль: ")
            if not password:
                parser.error("Пароль не должен быть пустым")
            user.password_hash = hash_password(password)
        db.add(user)
        db.commit()


if __name__ == "__main__":
    main()
