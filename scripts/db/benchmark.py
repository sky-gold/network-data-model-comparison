"""Замер времени Q1–Q5 в PostgreSQL и Neo4j."""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from db.neo4j import QUERIES as CYPHER_QUERIES, get_driver, seed_dataset as seed_neo4j
from db.pg import QUERIES as SQL_QUERIES, engine as pg_engine, seed_dataset as seed_postgres
from load_dataset import LoadParams, load_dataset


@dataclass(frozen=True)
class BenchmarkScale:
    label: str
    num_players: int
    num_games: int
    min_games_per_player: int
    max_games_per_player: int
    avg_friends: int


DEFAULT_SCALES: tuple[BenchmarkScale, ...] = (
    BenchmarkScale("S", 30, 48, 4, 12, 10),
    BenchmarkScale("M", 200, 500, 10, 40, 14),
    BenchmarkScale("L", 1000, 2000, 20, 80, 18),
    BenchmarkScale("XL", 2500, 4000, 15, 60, 20),
)


@dataclass
class QueryTiming:
    query: str
    engine: str
    median_ms: float
    min_ms: float
    max_ms: float
    rows: int


def _params_for(query: str, player_id: int) -> dict:
    return {} if query == "Q3" else {"player_id": player_id}


def _norm_val(v):
    if hasattr(v, "item"):
        return v.item()
    return v


def _normalize_rows(rows: list[dict]) -> list[tuple]:
    out = []
    for r in rows:
        out.append(tuple(sorted((k, _norm_val(v)) for k, v in r.items())))
    return sorted(out)


def compare_results(player_id: int = 1) -> bool:
    driver = get_driver()
    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    ok = True
    with Session() as sql_session, driver.session() as neo_session:
        for name in SQL_QUERIES:
            sql_r = _run_sql(sql_session, name, player_id)
            neo_r = _run_cypher(neo_session, name, player_id)
            match = _normalize_rows(sql_r) == _normalize_rows(neo_r)
            status = "OK" if match else "MISMATCH"
            print(f"  {name}: {status}  SQL={len(sql_r)} Neo4j={len(neo_r)}", flush=True)
            if not match:
                ok = False
    driver.close()
    return ok


def _run_sql(session, query: str, player_id: int) -> list[dict]:
    params = _params_for(query, player_id)
    return [dict(r) for r in session.execute(text(SQL_QUERIES[query]), params).mappings().all()]


def _run_cypher(session, query: str, player_id: int) -> list[dict]:
    params = _params_for(query, player_id)
    return [dict(r) for r in session.run(CYPHER_QUERIES[query], params)]


def _time_sql(session, query: str, player_id: int, repeats: int) -> tuple[float, float, float, int]:
    params = _params_for(query, player_id)
    samples: list[float] = []
    rows = 0
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = session.execute(text(SQL_QUERIES[query]), params).mappings().all()
        samples.append((time.perf_counter() - t0) * 1000)
        rows = len(result)
    return statistics.median(samples), min(samples), max(samples), rows


def _time_cypher(session, query: str, player_id: int, repeats: int) -> tuple[float, float, float, int]:
    params = _params_for(query, player_id)
    samples: list[float] = []
    rows = 0
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = list(session.run(CYPHER_QUERIES[query], params))
        samples.append((time.perf_counter() - t0) * 1000)
        rows = len(result)
    return statistics.median(samples), min(samples), max(samples), rows


def run_benchmark(
    scales: tuple[BenchmarkScale, ...] = DEFAULT_SCALES,
    player_id: int = 1,
    repeats: int = 5,
    warmup: int = 1,
    seed: int = 42,
    verify: bool = True,
) -> list[QueryTiming]:
    results: list[QueryTiming] = []
    driver = get_driver()
    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)

    for scale in scales:
        params = LoadParams(
            num_players=scale.num_players,
            num_games=scale.num_games,
            min_games_per_player=scale.min_games_per_player,
            max_games_per_player=scale.max_games_per_player,
            avg_friends=scale.avg_friends,
            seed=seed,
        )
        data = load_dataset(params=params)
        print(f"\n=== {scale.label}: {data.stats} ===", flush=True)
        print("  Заливка PostgreSQL...", flush=True)
        seed_postgres(data, eng=pg_engine, clear=True)
        print("  Заливка Neo4j...", flush=True)
        seed_neo4j(data, clear=True, driver=driver)
        print("  Заливка завершена.", flush=True)

        if verify:
            print(f"  Сверка PostgreSQL vs Neo4j ({scale.label}):", flush=True)
            if not compare_results(player_id):
                driver.close()
                raise RuntimeError(
                    f"Результаты PostgreSQL и Neo4j не совпали (масштаб {scale.label})"
                )

            print(f"  OK: ответы совпали ({scale.label})", flush=True)

        neo_session = driver.session()
        with Session() as sql_session:
            for q in SQL_QUERIES:
                print(f"  PostgreSQL {q} (warmup + {repeats} repeats)...", flush=True)
                for _ in range(warmup):
                    _time_sql(sql_session, q, player_id, 1)
                med, mn, mx, rows = _time_sql(sql_session, q, player_id, repeats)
                print(f"    -> median={med:.1f}ms rows={rows}", flush=True)
                results.append(
                    QueryTiming(
                        query=f"{scale.label} | {q}",
                        engine="PostgreSQL",
                        median_ms=round(med, 2),
                        min_ms=round(mn, 2),
                        max_ms=round(mx, 2),
                        rows=rows,
                    )
                )

            for q in CYPHER_QUERIES:
                print(f"  Neo4j {q} (warmup + {repeats} repeats)...", flush=True)
                for _ in range(warmup):
                    _time_cypher(neo_session, q, player_id, 1)
                med, mn, mx, rows = _time_cypher(neo_session, q, player_id, repeats)
                print(f"    -> median={med:.1f}ms rows={rows}", flush=True)
                results.append(
                    QueryTiming(
                        query=f"{scale.label} | {q}",
                        engine="Neo4j",
                        median_ms=round(med, 2),
                        min_ms=round(mn, 2),
                        max_ms=round(mx, 2),
                        rows=rows,
                    )
                )
        neo_session.close()

    driver.close()
    return results


def format_table(results: list[QueryTiming]) -> str:
    header = f"{'Масштаб | Запрос':<16} {'Движок':<12} {'median_ms':>10} {'min_ms':>8} {'max_ms':>8} {'rows':>6}"
    lines = [header, "-" * len(header)]
    for r in results:
        lines.append(
            f"{r.query:<16} {r.engine:<12} {r.median_ms:>10.2f} {r.min_ms:>8.2f} {r.max_ms:>8.2f} {r.rows:>6}"
        )
    return "\n".join(lines)


def dataset_summary_for_scales(
    scales: tuple[BenchmarkScale, ...] = DEFAULT_SCALES,
    seed: int = 42,
) -> list[tuple[str, str]]:
    rows = []
    for scale in scales:
        params = LoadParams(
            num_players=scale.num_players,
            num_games=scale.num_games,
            min_games_per_player=scale.min_games_per_player,
            max_games_per_player=scale.max_games_per_player,
            avg_friends=scale.avg_friends,
            seed=seed,
        )
        data = load_dataset(params=params)
        rows.append((scale.label, data.stats))
    return rows
