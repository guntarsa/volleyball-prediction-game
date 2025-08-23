-- PostgreSQL Database Backup Script for Volleyball Prediction Game
-- Run this script in pgAdmin to backup all data
-- This creates INSERT statements that can be used to restore data

-- ==========================================
-- BACKUP ALL DATABASE TABLES
-- ==========================================

-- Backup Users table
SELECT 'Backing up Users table...' as status;
-- For Windows: Replace 'C:\temp\' with your desired backup folder path
-- Make sure the folder exists before running the script
COPY (
    SELECT 'INSERT INTO "user" (id, name, email, password_hash, is_admin, is_verified, password_reset_required, created_at) VALUES (' ||
           id || ', ' ||
           '''' || REPLACE(name, '''', '''''') || ''', ' ||
           '''' || REPLACE(email, '''', '''''') || ''', ' ||
           '''' || REPLACE(password_hash, '''', '''''') || ''', ' ||
           is_admin || ', ' ||
           is_verified || ', ' ||
           password_reset_required || ', ' ||
           '''' || created_at || '''' ||
           ');' as backup_sql
    FROM "user"
    ORDER BY id
) TO 'C:\temp\users_backup.sql';

-- Backup Games table
SELECT 'Backing up Games table...' as status;
COPY (
    SELECT 'INSERT INTO game (id, team1, team2, game_date, prediction_deadline, round_name, team1_score, team2_score, is_finished) VALUES (' ||
           id || ', ' ||
           '''' || REPLACE(team1, '''', '''''') || ''', ' ||
           '''' || REPLACE(team2, '''', '''''') || ''', ' ||
           '''' || game_date || ''', ' ||
           '''' || prediction_deadline || ''', ' ||
           '''' || REPLACE(round_name, '''', '''''') || ''', ' ||
           COALESCE(team1_score::text, 'NULL') || ', ' ||
           COALESCE(team2_score::text, 'NULL') || ', ' ||
           is_finished ||
           ');' as backup_sql
    FROM game
    ORDER BY id
) TO 'C:\temp\games_backup.sql';

-- Backup Predictions table
SELECT 'Backing up Predictions table...' as status;
COPY (
    SELECT 'INSERT INTO prediction (id, user_id, game_id, team1_score, team2_score, predicted_winner, points, created_at) VALUES (' ||
           id || ', ' ||
           user_id || ', ' ||
           game_id || ', ' ||
           COALESCE(team1_score::text, 'NULL') || ', ' ||
           COALESCE(team2_score::text, 'NULL') || ', ' ||
           COALESCE('''' || REPLACE(predicted_winner, '''', '''''') || '''', 'NULL') || ', ' ||
           COALESCE(points::text, 'NULL') || ', ' ||
           '''' || created_at || '''' ||
           ');' as backup_sql
    FROM prediction
    ORDER BY id
) TO 'C:\temp\predictions_backup.sql';

-- Backup Tournament Config table
SELECT 'Backing up Tournament Config table...' as status;
COPY (
    SELECT 'INSERT INTO tournament_config (id, prediction_deadline, first_place_result, second_place_result, third_place_result, is_finalized) VALUES (' ||
           id || ', ' ||
           '''' || prediction_deadline || ''', ' ||
           COALESCE('''' || REPLACE(first_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
           COALESCE('''' || REPLACE(second_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
           COALESCE('''' || REPLACE(third_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
           COALESCE(is_finalized::text, 'false') ||
           ');' as backup_sql
    FROM tournament_config
    ORDER BY id
) TO 'C:\temp\tournament_config_backup.sql';

-- Backup Tournament Predictions table
SELECT 'Backing up Tournament Predictions table...' as status;
COPY (
    SELECT 'INSERT INTO tournament_prediction (id, user_id, first_place, second_place, third_place, points_earned, created_at, updated_at) VALUES (' ||
           id || ', ' ||
           user_id || ', ' ||
           COALESCE('''' || REPLACE(first_place, '''', '''''') || '''', 'NULL') || ', ' ||
           COALESCE('''' || REPLACE(second_place, '''', '''''') || '''', 'NULL') || ', ' ||
           COALESCE('''' || REPLACE(third_place, '''', '''''') || '''', 'NULL') || ', ' ||
           COALESCE(points_earned::text, 'NULL') || ', ' ||
           '''' || created_at || ''', ' ||
           COALESCE('''' || updated_at || '''', 'NULL') ||
           ');' as backup_sql
    FROM tournament_prediction
    ORDER BY id
) TO 'C:\temp\tournament_predictions_backup.sql';

-- Backup Tournament Teams table
SELECT 'Backing up Tournament Teams table...' as status;
COPY (
    SELECT 'INSERT INTO tournament_team (id, name, country_code, created_at) VALUES (' ||
           id || ', ' ||
           '''' || REPLACE(name, '''', '''''') || ''', ' ||
           COALESCE('''' || country_code || '''', 'NULL') || ', ' ||
           '''' || created_at || '''' ||
           ');' as backup_sql
    FROM tournament_team
    ORDER BY id
) TO 'C:\temp\tournament_teams_backup.sql';

-- Create a master backup file that includes all tables
COPY (
    SELECT '-- Volleyball Prediction Game Database Backup' ||
           E'\n-- Generated on: ' || NOW() ||
           E'\n-- ===========================================' ||
           E'\n\n-- Disable foreign key checks during restore' ||
           E'\nSET session_replication_role = replica;' ||
           E'\n\n-- Clear existing data (DANGEROUS - only for full restore)' ||
           E'\n-- TRUNCATE TABLE prediction, tournament_prediction, game, "user", tournament_config, tournament_team RESTART IDENTITY CASCADE;' ||
           E'\n\n-- Users Data' as backup_content
    UNION ALL
    SELECT backup_sql FROM (
        SELECT 'INSERT INTO "user" (id, name, email, password_hash, is_admin, is_verified, password_reset_required, created_at) VALUES (' ||
               id || ', ' ||
               '''' || REPLACE(name, '''', '''''') || ''', ' ||
               '''' || REPLACE(email, '''', '''''') || ''', ' ||
               '''' || REPLACE(password_hash, '''', '''''') || ''', ' ||
               is_admin || ', ' ||
               is_verified || ', ' ||
               password_reset_required || ', ' ||
               '''' || created_at || '''' ||
               ');' as backup_sql,
               1 as table_order, id as record_order
        FROM "user"
    ) u
    UNION ALL
    SELECT E'\n-- Games Data' as backup_content
    UNION ALL
    SELECT backup_sql FROM (
        SELECT 'INSERT INTO game (id, team1, team2, game_date, prediction_deadline, round_name, team1_score, team2_score, is_finished) VALUES (' ||
               id || ', ' ||
               '''' || REPLACE(team1, '''', '''''') || ''', ' ||
               '''' || REPLACE(team2, '''', '''''') || ''', ' ||
               '''' || game_date || ''', ' ||
               '''' || prediction_deadline || ''', ' ||
               '''' || REPLACE(round_name, '''', '''''') || ''', ' ||
               COALESCE(team1_score::text, 'NULL') || ', ' ||
               COALESCE(team2_score::text, 'NULL') || ', ' ||
               is_finished ||
               ');' as backup_sql,
               2 as table_order, id as record_order
        FROM game
    ) g
    UNION ALL
    SELECT E'\n-- Tournament Teams Data' as backup_content
    UNION ALL
    SELECT backup_sql FROM (
        SELECT 'INSERT INTO tournament_team (id, name, country_code, created_at) VALUES (' ||
               id || ', ' ||
               '''' || REPLACE(name, '''', '''''') || ''', ' ||
               COALESCE('''' || country_code || '''', 'NULL') || ', ' ||
               '''' || created_at || '''' ||
               ');' as backup_sql,
               3 as table_order, id as record_order
        FROM tournament_team
    ) tt
    UNION ALL
    SELECT E'\n-- Tournament Config Data' as backup_content
    UNION ALL
    SELECT backup_sql FROM (
        SELECT 'INSERT INTO tournament_config (id, prediction_deadline, first_place_result, second_place_result, third_place_result, is_finalized) VALUES (' ||
               id || ', ' ||
               '''' || prediction_deadline || ''', ' ||
               COALESCE('''' || REPLACE(first_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
               COALESCE('''' || REPLACE(second_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
               COALESCE('''' || REPLACE(third_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
               COALESCE(is_finalized::text, 'false') ||
               ');' as backup_sql,
               4 as table_order, id as record_order
        FROM tournament_config
    ) tc
    UNION ALL
    SELECT E'\n-- Predictions Data' as backup_content
    UNION ALL
    SELECT backup_sql FROM (
        SELECT 'INSERT INTO prediction (id, user_id, game_id, team1_score, team2_score, predicted_winner, points, created_at) VALUES (' ||
               id || ', ' ||
               user_id || ', ' ||
               game_id || ', ' ||
               COALESCE(team1_score::text, 'NULL') || ', ' ||
               COALESCE(team2_score::text, 'NULL') || ', ' ||
               COALESCE('''' || REPLACE(predicted_winner, '''', '''''') || '''', 'NULL') || ', ' ||
               COALESCE(points::text, 'NULL') || ', ' ||
               '''' || created_at || '''' ||
               ');' as backup_sql,
               5 as table_order, id as record_order
        FROM prediction
    ) p
    UNION ALL
    SELECT E'\n-- Tournament Predictions Data' as backup_content
    UNION ALL
    SELECT backup_sql FROM (
        SELECT 'INSERT INTO tournament_prediction (id, user_id, first_place, second_place, third_place, points_earned, created_at, updated_at) VALUES (' ||
               id || ', ' ||
               user_id || ', ' ||
               COALESCE('''' || REPLACE(first_place, '''', '''''') || '''', 'NULL') || ', ' ||
               COALESCE('''' || REPLACE(second_place, '''', '''''') || '''', 'NULL') || ', ' ||
               COALESCE('''' || REPLACE(third_place, '''', '''''') || '''', 'NULL') || ', ' ||
               COALESCE(points_earned::text, 'NULL') || ', ' ||
               '''' || created_at || ''', ' ||
               COALESCE('''' || updated_at || '''', 'NULL') ||
               ');' as backup_sql,
               6 as table_order, id as record_order
        FROM tournament_prediction
    ) tp
    UNION ALL
    SELECT E'\n\n-- Re-enable foreign key checks' ||
           E'\nSET session_replication_role = DEFAULT;' ||
           E'\n\n-- Update sequences to prevent ID conflicts' ||
           E'\nSELECT setval(''user_id_seq'', (SELECT MAX(id) FROM "user"));' ||
           E'\nSELECT setval(''game_id_seq'', (SELECT MAX(id) FROM game));' ||
           E'\nSELECT setval(''prediction_id_seq'', (SELECT MAX(id) FROM prediction));' ||
           E'\nSELECT setval(''tournament_team_id_seq'', (SELECT MAX(id) FROM tournament_team));' ||
           E'\nSELECT setval(''tournament_config_id_seq'', (SELECT MAX(id) FROM tournament_config));' ||
           E'\nSELECT setval(''tournament_prediction_id_seq'', (SELECT MAX(id) FROM tournament_prediction));' ||
           E'\n\n-- Backup completed successfully!'
) TO 'C:\temp\full_database_backup.sql';

-- Show backup summary
SELECT 
    'BACKUP SUMMARY' as status,
    (SELECT COUNT(*) FROM "user") as users_count,
    (SELECT COUNT(*) FROM game) as games_count,
    (SELECT COUNT(*) FROM prediction) as predictions_count,
    (SELECT COUNT(*) FROM tournament_team) as tournament_teams_count,
    (SELECT COUNT(*) FROM tournament_config) as tournament_configs_count,
    (SELECT COUNT(*) FROM tournament_prediction) as tournament_predictions_count,
    NOW() as backup_timestamp;

SELECT 'Backup files created in C:\temp\ directory:' as info
UNION ALL SELECT '- C:\temp\full_database_backup.sql (complete backup)'
UNION ALL SELECT '- C:\temp\users_backup.sql'
UNION ALL SELECT '- C:\temp\games_backup.sql' 
UNION ALL SELECT '- C:\temp\predictions_backup.sql'
UNION ALL SELECT '- C:\temp\tournament_config_backup.sql'
UNION ALL SELECT '- C:\temp\tournament_predictions_backup.sql'
UNION ALL SELECT '- C:\temp\tournament_teams_backup.sql';