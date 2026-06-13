from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from db.config import DATABASE_URL

QUERIES = {
    "Q1": """
        SELECT DISTINCT g.game_id, g.title
        FROM games g
        JOIN ownerships o ON o.game_id = g.game_id
        JOIN friendships f ON (
            (f.player_low_id = :player_id AND o.player_id = f.player_high_id)
            OR (f.player_high_id = :player_id AND o.player_id = f.player_low_id)
        )
        WHERE NOT EXISTS (
            SELECT 1 FROM ownerships ox
            WHERE ox.player_id = :player_id AND ox.game_id = g.game_id
        )
        ORDER BY g.title
    """,
    "Q2": """
        SELECT gr.name AS genre, COUNT(*) AS friend_ownerships
        FROM friendships f
        JOIN ownerships o ON (
            (f.player_low_id = :player_id AND o.player_id = f.player_high_id)
            OR (f.player_high_id = :player_id AND o.player_id = f.player_low_id)
        )
        JOIN game_genres gg ON gg.game_id = o.game_id
        JOIN genres gr ON gr.genre_id = gg.genre_id
        GROUP BY gr.genre_id, gr.name
        ORDER BY friend_ownerships DESC, gr.name
    """,
    "Q3": """
        SELECT g1.title AS game1, g2.title AS game2, COUNT(*) AS coowners
        FROM ownerships o1
        JOIN ownerships o2 ON o1.player_id = o2.player_id AND o1.game_id < o2.game_id
        JOIN games g1 ON g1.game_id = o1.game_id
        JOIN games g2 ON g2.game_id = o2.game_id
        GROUP BY o1.game_id, o2.game_id, g1.title, g2.title
        ORDER BY coowners DESC, g1.title, g2.title
        LIMIT 10
    """,
    "Q4": """
        WITH friend_owned AS (
            SELECT DISTINCT fo.player_id AS friend_id, g.game_id, g.title
            FROM friendships f
            JOIN ownerships fo ON (
                (f.player_low_id = :player_id AND fo.player_id = f.player_high_id)
                OR (f.player_high_id = :player_id AND fo.player_id = f.player_low_id)
            )
            JOIN games g ON g.game_id = fo.game_id
            WHERE NOT EXISTS (
                SELECT 1 FROM ownerships ox
                WHERE ox.player_id = :player_id AND ox.game_id = g.game_id
            )
        )
        SELECT fo.game_id, fo.title,
               COUNT(DISTINCT fo.friend_id) AS friend_count,
               COUNT(DISTINCT fo.friend_id) FILTER (WHERE EXISTS (
                   SELECT 1
                   FROM ownerships o_sim
                   JOIN game_genres gg_sim ON gg_sim.game_id = o_sim.game_id
                   JOIN ownerships o_mine ON o_mine.player_id = :player_id
                   JOIN game_genres gg_mine ON gg_mine.game_id = o_mine.game_id
                   WHERE o_sim.player_id = fo.friend_id
                     AND gg_sim.genre_id = gg_mine.genre_id
               )) AS similar_friend_count
        FROM friend_owned fo
        GROUP BY fo.game_id, fo.title
        ORDER BY friend_count DESC, similar_friend_count DESC, fo.title
        LIMIT 10
    """,
    "Q5": """
        WITH my_games AS (
            SELECT game_id FROM ownerships WHERE player_id = :player_id
        ),
        my_count AS (
            SELECT COUNT(*) AS n FROM my_games
        ),
        player_sets AS (
            SELECT p.player_id,
                   COUNT(*) FILTER (WHERE o.game_id IN (SELECT game_id FROM my_games)) AS inter_cnt,
                   (SELECT n FROM my_count) + COUNT(DISTINCT o.game_id)
                     - COUNT(*) FILTER (WHERE o.game_id IN (SELECT game_id FROM my_games)) AS union_cnt
            FROM players p
            JOIN ownerships o ON o.player_id = p.player_id
            WHERE p.player_id != :player_id
            GROUP BY p.player_id
        ),
        top_twins AS (
            SELECT player_id AS twin_id
            FROM player_sets
            WHERE union_cnt > 0
            ORDER BY inter_cnt::float / union_cnt DESC, player_id
            LIMIT 5
        ),
        twin_count AS (
            SELECT COUNT(*) AS n FROM top_twins
        ),
        gap_games AS (
            SELECT o.game_id, COUNT(DISTINCT o.player_id) AS twin_coverage
            FROM ownerships o
            JOIN top_twins t ON t.twin_id = o.player_id
            GROUP BY o.game_id
            HAVING COUNT(DISTINCT o.player_id) >= LEAST(4, (SELECT n FROM twin_count))
        )
        SELECT g.game_id, g.title, ug.twin_coverage
        FROM gap_games ug
        JOIN games g ON g.game_id = ug.game_id
        WHERE ug.game_id NOT IN (SELECT game_id FROM my_games)
        ORDER BY ug.twin_coverage DESC, g.title
        LIMIT 10
    """,
}


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    player_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)


class Game(Base):
    __tablename__ = "games"

    game_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)


class Genre(Base):
    __tablename__ = "genres"

    genre_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class GameGenre(Base):
    __tablename__ = "game_genres"
    __table_args__ = (
        UniqueConstraint("game_id", "genre_id"),
        Index("ix_game_genres_genre_id", "genre_id"),
    )

    game_id: Mapped[int] = mapped_column(ForeignKey("games.game_id"), primary_key=True)
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.genre_id"), primary_key=True)


class Ownership(Base):
    __tablename__ = "ownerships"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id"),
        Index("ix_ownerships_game_id", "game_id"),
        Index("ix_ownerships_player_id", "player_id"),
    )

    player_id: Mapped[int] = mapped_column(ForeignKey("players.player_id"), primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.game_id"), primary_key=True)


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("player_low_id", "player_high_id"),
        Index("ix_friendships_low", "player_low_id"),
        Index("ix_friendships_high", "player_high_id"),
    )

    player_low_id: Mapped[int] = mapped_column(ForeignKey("players.player_id"), primary_key=True)
    player_high_id: Mapped[int] = mapped_column(ForeignKey("players.player_id"), primary_key=True)


engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _clear_tables(session) -> None:
    session.execute(
        text(
            """
            TRUNCATE TABLE
                ownerships,
                friendships,
                game_genres,
                games,
                genres,
                players
            RESTART IDENTITY CASCADE
            """
        )
    )


def _sync_sequences(session) -> None:
    for table, col in (
        ("players", "player_id"),
        ("games", "game_id"),
        ("genres", "genre_id"),
    ):
        session.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', '{col}'),
                    COALESCE((SELECT MAX({col}) FROM {table}), 1)
                )
                """
            )
        )


def seed_dataset(data, *, eng=None, clear: bool = True):
    db_engine = eng or engine
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(db_engine)

    with Session() as session:
        if clear:
            _clear_tables(session)

        session.add_all(
            Player(player_id=p["player_id"], steam_id=p["steam_id"], username=p["username"])
            for p in data.players
        )
        session.flush()
        session.add_all(
            Game(game_id=g["game_id"], app_id=g["app_id"], title=g["title"])
            for g in data.games
        )
        session.add_all(Genre(genre_id=g["genre_id"], name=g["name"]) for g in data.genres)
        session.flush()
        session.add_all(
            GameGenre(game_id=gg["game_id"], genre_id=gg["genre_id"]) for gg in data.game_genres
        )
        session.flush()
        session.add_all(
            Ownership(player_id=o["player_id"], game_id=o["game_id"]) for o in data.ownerships
        )
        session.flush()
        session.add_all(
            Friendship(
                player_low_id=f["player_low_id"],
                player_high_id=f["player_high_id"],
            )
            for f in data.friendships
        )
        _sync_sequences(session)
        session.commit()
    return db_engine


def run_query(session, name: str, player_id: int) -> list[dict]:
    params = {} if name == "Q3" else {"player_id": player_id}
    rows = session.execute(text(QUERIES[name]), params).mappings().all()
    return [dict(r) for r in rows]
