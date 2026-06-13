from neo4j import GraphDatabase, Driver

from db.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

QUERIES = {
    "Q1": """
        MATCH (x:Player {player_id: $player_id})-[:FRIEND_OF]-(f:Player)-[:OWNS]->(g:Game)
        WHERE NOT (x)-[:OWNS]->(g)
        RETURN DISTINCT g.game_id AS game_id, g.title AS title
        ORDER BY title
    """,
    "Q2": """
        MATCH (x:Player {player_id: $player_id})-[:FRIEND_OF]-(f:Player)-[:OWNS]->(g:Game)-[:IN_GENRE]->(gn:Genre)
        RETURN gn.name AS genre, count(*) AS friend_ownerships
        ORDER BY friend_ownerships DESC, genre
    """,
    "Q3": """
        MATCH (g1:Game)<-[:OWNS]-(p:Player)-[:OWNS]->(g2:Game)
        WHERE g1.game_id < g2.game_id
        WITH g1, g2, count(p) AS coowners
        RETURN g1.title AS game1, g2.title AS game2, coowners
        ORDER BY coowners DESC, game1, game2
        LIMIT 10
    """,
    "Q4": """
        MATCH (x:Player {player_id: $player_id})
        MATCH (x)-[:FRIEND_OF]-(f:Player)-[:OWNS]->(g:Game)
        WHERE NOT (x)-[:OWNS]->(g)
        OPTIONAL MATCH (f)-[:OWNS]->(:Game)-[:IN_GENRE]->(gn:Genre)<-[:IN_GENRE]-(:Game)<-[:OWNS]-(x)
        WITH g, f, count(gn) > 0 AS has_similar
        RETURN g.game_id AS game_id, g.title AS title,
               count(DISTINCT f) AS friend_count,
               count(DISTINCT CASE WHEN has_similar THEN f END) AS similar_friend_count
        ORDER BY friend_count DESC, similar_friend_count DESC, title
        LIMIT 10
    """,
    "Q5": """
        MATCH (me:Player {player_id: $player_id})-[:OWNS]->(mg:Game)
        WITH me, collect(DISTINCT mg.game_id) AS myGames
        MATCH (other:Player)
        WHERE other <> me
        OPTIONAL MATCH (other)-[:OWNS]->(og:Game)
        WITH me, myGames, other, collect(DISTINCT og.game_id) AS theirGames
        WITH me, myGames, other,
             size([g IN myGames WHERE g IN theirGames]) AS inter,
             size(myGames) + size(theirGames) - size([g IN myGames WHERE g IN theirGames]) AS unionSize
        WHERE unionSize > 0
        WITH me, myGames, other, inter * 1.0 / unionSize AS jaccard
        ORDER BY jaccard DESC, other.player_id
        LIMIT 5
        WITH me, myGames, collect(other) AS twins
        UNWIND twins AS t
        MATCH (t)-[:OWNS]->(g:Game)
        WITH me, myGames, g, count(DISTINCT t) AS twinOwns, size(twins) AS twinCount
        WHERE twinOwns >= CASE WHEN twinCount >= 4 THEN 4 ELSE twinCount END
          AND NOT g.game_id IN myGames
        RETURN DISTINCT g.game_id AS game_id, g.title AS title, twinOwns AS twin_coverage
        ORDER BY twin_coverage DESC, title
        LIMIT 10
    """,
}

CONSTRAINTS = [
    "CREATE CONSTRAINT player_id IF NOT EXISTS FOR (p:Player) REQUIRE p.player_id IS UNIQUE",
    "CREATE CONSTRAINT game_id IF NOT EXISTS FOR (g:Game) REQUIRE g.game_id IS UNIQUE",
    "CREATE CONSTRAINT genre_id IF NOT EXISTS FOR (g:Genre) REQUIRE g.genre_id IS UNIQUE",
]

BATCH = 5000


def get_driver() -> Driver:
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _batched(rows: list[dict], size: int = BATCH):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def seed_dataset(data, *, clear: bool = True, driver: Driver | None = None) -> None:
    own_driver = driver is None
    drv = driver or get_driver()

    with drv.session() as session:
        if clear:
            session.run("MATCH (n) DETACH DELETE n")
        for stmt in CONSTRAINTS:
            session.run(stmt)

        for batch in _batched(data.players):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (p:Player {player_id: row.player_id})
                SET p.steam_id = row.steam_id, p.username = row.username
                """,
                rows=batch,
            )
        for batch in _batched(data.games):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (g:Game {game_id: row.game_id})
                SET g.app_id = row.app_id, g.title = row.title
                """,
                rows=batch,
            )
        for batch in _batched(data.genres):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (g:Genre {genre_id: row.genre_id})
                SET g.name = row.name
                """,
                rows=batch,
            )
        for batch in _batched(data.game_genres):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (g:Game {game_id: row.game_id})
                MATCH (gn:Genre {genre_id: row.genre_id})
                MERGE (g)-[:IN_GENRE]->(gn)
                """,
                rows=batch,
            )
        for batch in _batched(data.ownerships):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (p:Player {player_id: row.player_id})
                MATCH (g:Game {game_id: row.game_id})
                MERGE (p)-[:OWNS]->(g)
                """,
                rows=batch,
            )
        for batch in _batched(data.friendships):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (a:Player {player_id: row.player_low_id})
                MATCH (b:Player {player_id: row.player_high_id})
                MERGE (a)-[:FRIEND_OF]-(b)
                """,
                rows=batch,
            )

    if own_driver:
        drv.close()


def run_query(session, name: str, player_id: int) -> list[dict]:
    params = {} if name == "Q3" else {"player_id": player_id}
    return [dict(r) for r in session.run(QUERIES[name], params)]
