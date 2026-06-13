// Q1: Игры друзей, которых нет у X
MATCH (x:Player {player_id: $player_id})-[:FRIEND_OF]-(f:Player)-[:OWNS]->(g:Game)
WHERE NOT (x)-[:OWNS]->(g)
RETURN DISTINCT g.game_id AS game_id, g.title AS title
ORDER BY title;

// Q2: Популярные жанры среди друзей X
MATCH (x:Player {player_id: $player_id})-[:FRIEND_OF]-(f:Player)-[:OWNS]->(g:Game)-[:IN_GENRE]->(gn:Genre)
RETURN gn.name AS genre, count(*) AS friend_ownerships
ORDER BY friend_ownerships DESC, genre;

// Q3: Top-10 пар игр по co-ownership
MATCH (g1:Game)<-[:OWNS]-(p:Player)-[:OWNS]->(g2:Game)
WHERE g1.game_id < g2.game_id
WITH g1, g2, count(p) AS coowners
RETURN g1.title AS game1, g2.title AS game2, coowners
ORDER BY coowners DESC, game1, game2
LIMIT 10;

// Q4: Рекомендация — N друзей играют в Y, K из них играют в жанры из библиотеки X
MATCH (x:Player {player_id: $player_id})
MATCH (x)-[:FRIEND_OF]-(f:Player)-[:OWNS]->(g:Game)
WHERE NOT (x)-[:OWNS]->(g)
OPTIONAL MATCH (f)-[:OWNS]->(:Game)-[:IN_GENRE]->(gn:Genre)<-[:IN_GENRE]-(:Game)<-[:OWNS]-(x)
WITH g, f, count(gn) > 0 AS has_similar
RETURN g.game_id AS game_id, g.title AS title,
       count(DISTINCT f) AS friend_count,
       count(DISTINCT CASE WHEN has_similar THEN f END) AS similar_friend_count
ORDER BY friend_count DESC, similar_friend_count DESC, title
LIMIT 10;

// Q5: Игры у top-5 «двойников» (Jaccard), которых нет у X
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
LIMIT 10;
