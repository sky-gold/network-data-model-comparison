-- Параметр :player_id — id игрока X (например 1)

-- Q1: Игры, которых нет у X, но есть у его друзей
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
ORDER BY g.title;

-- Q2: Популярные жанры среди друзей игрока X
SELECT gr.name AS genre, COUNT(*) AS friend_ownerships
FROM friendships f
JOIN ownerships o ON (
    (f.player_low_id = :player_id AND o.player_id = f.player_high_id)
    OR (f.player_high_id = :player_id AND o.player_id = f.player_low_id)
)
JOIN game_genres gg ON gg.game_id = o.game_id
JOIN genres gr ON gr.genre_id = gg.genre_id
GROUP BY gr.genre_id, gr.name
ORDER BY friend_ownerships DESC, gr.name;

-- Q3: Пары игр, часто встречающиеся вместе (top-10)
SELECT g1.title AS game1, g2.title AS game2, COUNT(*) AS coowners
FROM ownerships o1
JOIN ownerships o2 ON o1.player_id = o2.player_id AND o1.game_id < o2.game_id
JOIN games g1 ON g1.game_id = o1.game_id
JOIN games g2 ON g2.game_id = o2.game_id
GROUP BY o1.game_id, o2.game_id, g1.title, g2.title
ORDER BY coowners DESC, g1.title, g2.title
LIMIT 10;

-- Q4: Рекомендация — N друзей играют в Y, K из них играют в жанры из библиотеки X
WITH my_genres AS (
    SELECT DISTINCT gg.genre_id
    FROM ownerships o
    JOIN game_genres gg ON gg.game_id = o.game_id
    WHERE o.player_id = :player_id
),
friend_owned AS (
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
           WHERE o_sim.player_id = fo.friend_id
             AND gg_sim.genre_id IN (SELECT genre_id FROM my_genres)
       )) AS similar_friend_count
FROM friend_owned fo
GROUP BY fo.game_id, fo.title
ORDER BY friend_count DESC, similar_friend_count DESC, fo.title
LIMIT 10;

-- Q5: Игры у top-5 «двойников» (Jaccard по библиотеке), которых нет у X
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
LIMIT 10;
