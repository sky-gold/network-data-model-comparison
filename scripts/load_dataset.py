"""CSV игр + синтетические игроки, дружба, владение."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from db.config import (
    GAMES_CSV,
    MAX_GAMES_PER_PLAYER,
    MIN_GAMES_PER_PLAYER,
    NUM_PLAYERS,
    RANDOM_SEED,
)

DEFAULT_PLAYER_ID = 1
CLOSE_PLAYER_IDS = (2, 3, 4, 5, 6)
GAP_GAMES_COUNT = 4
POPULAR_AMONG_FRIENDS = 8
EXTRA_GAMES_PER_FRIEND = 4


@dataclass
class Dataset:
    players: list[dict]
    games: list[dict]
    genres: list[dict]
    game_genres: list[dict]
    ownerships: list[dict]
    friendships: list[dict]

    @property
    def stats(self) -> str:
        return (
            f"players={len(self.players)}, games={len(self.games)}, "
            f"ownerships={len(self.ownerships)}, friendships={len(self.friendships)}"
        )


@dataclass
class LoadParams:
    num_players: int = NUM_PLAYERS
    num_games: int | None = None
    min_games_per_player: int = MIN_GAMES_PER_PLAYER
    max_games_per_player: int = MAX_GAMES_PER_PLAYER
    avg_friends: int = 8
    seed: int = RANDOM_SEED


def _core_friend_count(num_players: int) -> int:
    """Размер ближнего круга друзей у player_id=1 (зависит от масштаба)."""
    if num_players <= 50:
        return min(12, num_players - 1)
    if num_players <= 300:
        return 18
    if num_players <= 1500:
        return 22
    return 24


def _load_games_from_csv(path: Path) -> tuple[list[dict], list[dict], list[dict]]:
    df = pd.read_csv(path)
    df = df.drop_duplicates(subset=["app_id"], keep="first")

    genre_names = sorted(df["genre"].dropna().unique().tolist())
    genres = [{"genre_id": i + 1, "name": name} for i, name in enumerate(genre_names)]
    genre_by_name = {g["name"]: g["genre_id"] for g in genres}

    games = []
    game_genres = []
    for i, row in enumerate(df.itertuples(index=False), start=1):
        games.append(
            {
                "game_id": i,
                "app_id": int(row.app_id),
                "title": str(row.title),
            }
        )
        gid = genre_by_name[str(row.genre)]
        game_genres.append({"game_id": i, "genre_id": gid})

    return games, genres, game_genres


def _expand_games(
    games: list[dict],
    game_genres: list[dict],
    target_count: int,
    rng: random.Random,
) -> tuple[list[dict], list[dict]]:
    if len(games) >= target_count:
        keep_ids = {g["game_id"] for g in games[:target_count]}
        return games[:target_count], [gg for gg in game_genres if gg["game_id"] in keep_ids]

    genre_by_game = {gg["game_id"]: gg["genre_id"] for gg in game_genres}
    extra_genres = list(game_genres)
    extra_games = list(games)

    for new_id in range(len(games) + 1, target_count + 1):
        template = games[rng.randint(0, len(games) - 1)]
        extra_games.append(
            {
                "game_id": new_id,
                "app_id": 900_000_000 + new_id,
                "title": f"{template['title']} (synthetic #{new_id})",
            }
        )
        extra_genres.append(
            {"game_id": new_id, "genre_id": genre_by_game[template["game_id"]]}
        )

    return extra_games, extra_genres


def _build_friendships(num_players: int, avg_friends: int, rng: random.Random) -> list[dict]:
    """Случайный граф дружбы; ближний круг player_id=1 добавляется отдельно."""
    edges: set[tuple[int, int]] = set()
    core_end = min(num_players, 1 + _core_friend_count(num_players))

    for i in range(core_end + 1, num_players + 1):
        j = core_end + 1 + (i - core_end - 1) % max(1, num_players - core_end)
        if j <= num_players and i != j:
            edges.add((min(i, j), max(i, j)))

    background_players = max(0, num_players - core_end)
    target_edges = max(background_players, (background_players * avg_friends) // 2)
    attempts = 0
    while len(edges) < target_edges and attempts < target_edges * 30:
        a = rng.randint(core_end + 1, num_players) if core_end < num_players else 1
        b = rng.randint(core_end + 1, num_players) if core_end < num_players else 1
        if a != b:
            edges.add((min(a, b), max(a, b)))
        attempts += 1

    return [
        {"player_low_id": low, "player_high_id": high}
        for low, high in sorted(edges)
    ]


def _friends_of(player_id: int, friendships: list[dict]) -> list[int]:
    result = []
    for f in friendships:
        if f["player_low_id"] == player_id:
            result.append(f["player_high_id"])
        elif f["player_high_id"] == player_id:
            result.append(f["player_low_id"])
    return result


def _ownership_index(ownerships: list[dict]) -> dict[int, set[int]]:
    owned: dict[int, set[int]] = {}
    for o in ownerships:
        owned.setdefault(o["player_id"], set()).add(o["game_id"])
    return owned


def _flatten_ownerships(owned: dict[int, set[int]]) -> list[dict]:
    return [
        {"player_id": pid, "game_id": gid}
        for pid, games in sorted(owned.items())
        for gid in sorted(games)
    ]


def _add_edge(edges: set[tuple[int, int]], a: int, b: int) -> None:
    if a != b:
        edges.add((min(a, b), max(a, b)))


def _core_friend_ids(num_players: int) -> list[int]:
    n = _core_friend_count(num_players)
    return list(range(2, min(num_players, 1 + n) + 1))


def _genre_ids_for_games(game_ids: set[int], game_genres: list[dict]) -> set[int]:
    return {gg["genre_id"] for gg in game_genres if gg["game_id"] in game_ids}


def _games_with_genres(
    candidates: list[int],
    genre_ids: set[int],
    game_genres: list[dict],
) -> list[int]:
    genre_by_game = {gg["game_id"]: gg["genre_id"] for gg in game_genres}
    return [g for g in candidates if genre_by_game.get(g) in genre_ids]


def _apply_social_structure(
    ownerships: list[dict],
    friendships: list[dict],
    game_ids: list[int],
    game_genres: list[dict],
    num_players: int,
    rng: random.Random,
) -> tuple[list[dict], list[dict]]:
    """
    Дополнительная социальная структура:
    - ближний круг друзей у player_id=1;
    - похожие библиотеки у игроков 2–6;
    - популярные игры в круге друзей;
    - общие «паки» игр у группы игроков.
    """
    owned = _ownership_index(ownerships)
    for pid in range(1, num_players + 1):
        owned.setdefault(pid, set())

    edges = {(f["player_low_id"], f["player_high_id"]) for f in friendships}
    core_friends = _core_friend_ids(num_players)
    similar_ids = [p for p in CLOSE_PLAYER_IDS if p <= num_players][:5]

    for fid in core_friends:
        _add_edge(edges, DEFAULT_PLAYER_ID, fid)

    player_games = owned[DEFAULT_PLAYER_ID]
    if len(player_games) < 5:
        for gid in rng.sample(game_ids, min(8, len(game_ids))):
            player_games.add(gid)

    player_genres = _genre_ids_for_games(player_games, game_genres)
    other_games = [g for g in game_ids if g not in player_games]
    same_genre = _games_with_genres(other_games, player_genres, game_genres)
    if len(same_genre) < POPULAR_AMONG_FRIENDS:
        same_genre = other_games

    popular = rng.sample(
        same_genre,
        min(POPULAR_AMONG_FRIENDS, len(same_genre)),
    )
    gap_games = rng.sample(
        [g for g in other_games if g not in popular],
        min(GAP_GAMES_COUNT, len(other_games)),
    )

    overlap_n = max(2, int(len(player_games) * 0.65))
    shared_library = set(rng.sample(list(player_games), min(overlap_n, len(player_games))))

    for pid in similar_ids:
        owned[pid] = set(shared_library) | set(gap_games) | set(popular)

    for friend_id in core_friends:
        if friend_id in similar_ids:
            continue
        extra = [g for g in other_games if g not in popular]
        unique = set(rng.sample(extra, min(EXTRA_GAMES_PER_FRIEND, len(extra))))
        owned[friend_id] = set(popular) | unique

    bundle_size = min(8, len(game_ids))
    if num_players > len(core_friends) + 6:
        bundle = rng.sample(game_ids, bundle_size)
        group = list(range(max(similar_ids) + 1, min(num_players, max(similar_ids) + 41)))
        for pid in group:
            owned[pid].update(bundle)

    friendships_out = [
        {"player_low_id": low, "player_high_id": high}
        for low, high in sorted(edges)
    ]
    return _flatten_ownerships(owned), friendships_out


def _build_ownerships(
    num_players: int,
    game_ids: list[int],
    friendships: list[dict],
    min_games: int,
    max_games: int,
    rng: random.Random,
) -> list[dict]:
    owned: dict[int, set[int]] = {p: set() for p in range(1, num_players + 1)}
    core_end = min(num_players, 1 + _core_friend_count(num_players))

    max_games = min(max_games, len(game_ids))
    min_games = min(min_games, max_games)

    for player_id in range(1, num_players + 1):
        n = rng.randint(min_games, max_games)
        picks = rng.sample(game_ids, n)
        owned[player_id].update(picks)

    for player_id in range(1, num_players + 1):
        if player_id <= core_end:
            continue
        for friend_id in _friends_of(player_id, friendships):
            if rng.random() < 0.2:
                owned[friend_id].add(rng.choice(game_ids))

    return _flatten_ownerships(owned)


def load_dataset(
    csv_path: Path | None = None,
    params: LoadParams | None = None,
) -> Dataset:
    path = csv_path or GAMES_CSV
    p = params or LoadParams()
    rng = random.Random(p.seed)

    games, genres, game_genres = _load_games_from_csv(path)
    if p.num_games is not None and p.num_games > len(games):
        games, game_genres = _expand_games(games, game_genres, p.num_games, rng)
    elif p.num_games is not None:
        games = games[: p.num_games]
        keep = {g["game_id"] for g in games}
        game_genres = [gg for gg in game_genres if gg["game_id"] in keep]

    game_ids = [g["game_id"] for g in games]

    players = [
        {
            "player_id": i,
            "steam_id": f"76561198{i:010d}",
            "username": f"player_{i:04d}",
        }
        for i in range(1, p.num_players + 1)
    ]

    friendships = _build_friendships(p.num_players, p.avg_friends, rng)
    ownerships = _build_ownerships(
        p.num_players,
        game_ids,
        friendships,
        p.min_games_per_player,
        p.max_games_per_player,
        rng,
    )
    ownerships, friendships = _apply_social_structure(
        ownerships,
        friendships,
        game_ids,
        game_genres,
        p.num_players,
        rng,
    )

    return Dataset(
        players=players,
        games=games,
        genres=genres,
        game_genres=game_genres,
        ownerships=ownerships,
        friendships=friendships,
    )
