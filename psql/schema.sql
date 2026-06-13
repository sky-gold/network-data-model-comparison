-- PostgreSQL DDL: игровая соцсеть Steam

CREATE TABLE IF NOT EXISTS players (
    player_id SERIAL PRIMARY KEY,
    steam_id VARCHAR(64) NOT NULL UNIQUE,
    username VARCHAR(128) NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    game_id SERIAL PRIMARY KEY,
    app_id INTEGER NOT NULL UNIQUE,
    title VARCHAR(512) NOT NULL
);

CREATE TABLE IF NOT EXISTS genres (
    genre_id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS game_genres (
    game_id INTEGER NOT NULL REFERENCES games(game_id),
    genre_id INTEGER NOT NULL REFERENCES genres(genre_id),
    PRIMARY KEY (game_id, genre_id)
);
CREATE INDEX IF NOT EXISTS ix_game_genres_genre_id ON game_genres(genre_id);

CREATE TABLE IF NOT EXISTS ownerships (
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    game_id INTEGER NOT NULL REFERENCES games(game_id),
    PRIMARY KEY (player_id, game_id)
);
CREATE INDEX IF NOT EXISTS ix_ownerships_game_id ON ownerships(game_id);
CREATE INDEX IF NOT EXISTS ix_ownerships_player_id ON ownerships(player_id);

CREATE TABLE IF NOT EXISTS friendships (
    player_low_id INTEGER NOT NULL REFERENCES players(player_id),
    player_high_id INTEGER NOT NULL REFERENCES players(player_id),
    PRIMARY KEY (player_low_id, player_high_id),
    CHECK (player_low_id < player_high_id)
);
CREATE INDEX IF NOT EXISTS ix_friendships_low ON friendships(player_low_id);
CREATE INDEX IF NOT EXISTS ix_friendships_high ON friendships(player_high_id);
