"""Create a user from the terminal. Use this to make the first administrator.

    python -m scripts.create_user --role admin --name "Your Name" --email you@example.com

You will be asked for the password (it is not shown as you type).
In Git Bash, start the command with winpty if the password prompt does not appear.
"""
import argparse
import getpass

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password, password_problem


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a nurse or administrator account.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=["nurse", "admin"], default="nurse")
    parser.add_argument("--password", help="Leave out to be asked safely.")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password (8+ characters, with a letter and a number): ")
    if problem := password_problem(password):
        raise SystemExit(problem)
    if not args.password and password != getpass.getpass("Type the password again: "):
        raise SystemExit("The passwords do not match.")

    email = args.email.strip().lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(func.lower(User.email) == email)):
            raise SystemExit(f"A user with email {email} already exists.")
        user = User(full_name=args.name, email=email, password_hash=hash_password(password), role=args.role)
        db.add(user)
        db.commit()
        print(f"Created {args.role} account for {args.name} ({email}), user ID {user.user_id}.")


if __name__ == "__main__":
    main()
