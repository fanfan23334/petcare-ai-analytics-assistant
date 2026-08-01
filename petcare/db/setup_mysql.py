"""PetCare MySQL setup: create database, tables and seed data.

Usage:
    python setup_mysql.py
    python setup_mysql.py --password yourpass
    python setup_mysql.py --host 127.0.0.1 --user root --password YOUR_MYSQL_PASSWORD

Config from environment variables (used by later stages / .env):
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
"""

import argparse
import os
import sys
from pathlib import Path

import pymysql

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
SEED_PATH = BASE_DIR / "seed.sql"


def env_or_default(name: str, default: str) -> str:
    return os.getenv(name, default)


def run_sql_file(conn, path: Path) -> int:
    """Execute a .sql file by splitting on semicolons.

    All statements in PetCare .sql files are single-line INSERTs / DDLs
    without semicolons inside string literals, so simple splitting is safe.
    """
    content = path.read_text(encoding="utf-8")
    statements = [s.strip() for s in content.split(";") if s.strip()]
    with conn.cursor() as cursor:
        for stmt in statements:
            cursor.execute(stmt)
        conn.commit()
    return len(statements)


def main() -> int:
    parser = argparse.ArgumentParser(description="PetCare MySQL database setup")
    parser.add_argument("--host", default=env_or_default("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(env_or_default("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=env_or_default("MYSQL_USER", "root"))
    parser.add_argument("--password", default=env_or_default("MYSQL_PASSWORD", ""))
    parser.add_argument("--database", default=env_or_default("MYSQL_DATABASE", "petcare_db"))
    args = parser.parse_args()

    conn = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        charset="utf8mb4",
    )
    try:
        n_schema = run_sql_file(conn, SCHEMA_PATH)
        print(f"[ok] schema.sql executed ({n_schema} statements)")

        n_seed = run_sql_file(conn, SEED_PATH)
        print(f"[ok] seed.sql executed ({n_seed} statements)")

        with conn.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {args.database}.owners")
            owners = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {args.database}.pets")
            pets = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {args.database}.doctors")
            doctors = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {args.database}.appointments")
            appointments = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {args.database}.medical_records")
            records = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {args.database}.bills")
            bills = cursor.fetchone()[0]

        print("-" * 40)
        print(f"owners={owners}  pets={pets}  doctors={doctors}")
        print(f"appointments={appointments}  medical_records={records}  bills={bills}")
        print(f"database `{args.database}` ready.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
