#!/usr/bin/env python3
"""Ожидание готовности PostgreSQL и Neo4j."""

import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from sqlalchemy import create_engine, text

from db.config import DATABASE_URL, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


def wait_postgres(timeout: float = 60) -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("PostgreSQL: ready")
            return
        except Exception as e:
            print(f"PostgreSQL: waiting... ({e})")
            time.sleep(2)
    raise TimeoutError("PostgreSQL не ответил вовремя")


def wait_neo4j(timeout: float = 90) -> None:
    from neo4j import GraphDatabase

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            driver.verify_connectivity()
            driver.close()
            print("Neo4j: ready")
            return
        except Exception as e:
            print(f"Neo4j: waiting... ({e})")
            time.sleep(3)
    raise TimeoutError("Neo4j не ответил вовремя")


def wait_all() -> None:
    wait_postgres()
    wait_neo4j()


if __name__ == "__main__":
    wait_all()
