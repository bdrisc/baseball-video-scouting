SELECT 'players' AS table_name, COUNT(*) AS records FROM players
UNION ALL
SELECT 'games', COUNT(*) FROM games
UNION ALL
SELECT 'pitches', COUNT(*) FROM pitches
UNION ALL
SELECT 'videos', COUNT(*) FROM videos;

SELECT
    p.pitch_id,
    pitcher.player_name AS pitcher,
    g.game_date,
    g.away_team,
    g.home_team,
    p.pitch_type,
    p.velocity,
    p.balls,
    p.strikes,
    v.video_url
FROM pitches AS p
INNER JOIN players AS pitcher
    ON pitcher.player_id = p.pitcher_id
INNER JOIN games AS g
    ON g.game_pk = p.game_pk
LEFT JOIN videos AS v
    ON v.pitch_id = p.pitch_id
ORDER BY g.game_date, p.at_bat_number, p.pitch_number
LIMIT 20;