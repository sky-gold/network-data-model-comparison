#!/usr/bin/env python3
"""Очистка и наполнение PostgreSQL и Neo4j."""

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from db.neo4j import seed_dataset as seed_neo4j
from db.pg import seed_dataset as seed_postgres
from load_dataset import LoadParams, load_dataset
from wait_for_db import wait_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Залить тестовые данные в обе БД")
    parser.add_argument("--player-scale", choices=["S", "M", "L", "XL"], default="S")
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()

    scales = {
        "S": LoadParams(num_players=30, num_games=48, min_games_per_player=4, max_games_per_player=12, avg_friends=10),
        "M": LoadParams(num_players=200, num_games=500, min_games_per_player=10, max_games_per_player=40, avg_friends=14),
        "L": LoadParams(num_players=1000, num_games=2000, min_games_per_player=20, max_games_per_player=80, avg_friends=18),
        "XL": LoadParams(num_players=2500, num_games=4000, min_games_per_player=15, max_games_per_player=60, avg_friends=20),
    }

    if not args.no_wait:
        wait_all()

    data = load_dataset(params=scales[args.player_scale])
    seed_postgres(data, clear=True)
    seed_neo4j(data, clear=True)
    print(f"Залито: {data.stats}")


if __name__ == "__main__":
    main()
