-- PostgreSQL Database Backup Script for Volleyball Prediction Game
-- NO FILE PERMISSIONS REQUIRED - Results displayed in pgAdmin
-- Copy the results from pgAdmin and save them manually

-- ==========================================
-- BACKUP METHOD FOR RESTRICTED PERMISSIONS
-- ==========================================

-- INSTRUCTIONS:
-- 1. Run each section below one by one
-- 2. Copy the results from pgAdmin 
-- 3. Save each result to a text file on your computer
-- 4. Use these files for restore operations

-- ==========================================
-- SECTION 1: USERS BACKUP
-- ==========================================

SELECT '=== USERS BACKUP DATA ===' as section_header;
SELECT 'Copy all rows below and save as users_backup.sql' as instruction;
SELECT '' as separator;

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
ORDER BY id;

SELECT '' as end_users_section;

-- ==========================================
-- SECTION 2: GAMES BACKUP  
-- ==========================================

SELECT '=== GAMES BACKUP DATA ===' as section_header;
SELECT 'Copy all rows below and save as games_backup.sql' as instruction;
SELECT '' as separator;

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
ORDER BY id;

SELECT '' as end_games_section;

-- ==========================================
-- SECTION 3: PREDICTIONS BACKUP
-- ==========================================

SELECT '=== PREDICTIONS BACKUP DATA ===' as section_header;
SELECT 'Copy all rows below and save as predictions_backup.sql' as instruction;
SELECT '' as separator;

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
ORDER BY id;

SELECT '' as end_predictions_section;

-- ==========================================
-- SECTION 4: TOURNAMENT CONFIG BACKUP
-- ==========================================

SELECT '=== TOURNAMENT CONFIG BACKUP DATA ===' as section_header;
SELECT 'Copy all rows below and save as tournament_config_backup.sql' as instruction;
SELECT '' as separator;

SELECT 'INSERT INTO tournament_config (id, prediction_deadline, first_place_result, second_place_result, third_place_result, is_finalized) VALUES (' ||
       id || ', ' ||
       '''' || prediction_deadline || ''', ' ||
       COALESCE('''' || REPLACE(first_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
       COALESCE('''' || REPLACE(second_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
       COALESCE('''' || REPLACE(third_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
       COALESCE(is_finalized::text, 'false') ||
       ');' as backup_sql
FROM tournament_config
ORDER BY id;

SELECT '' as end_tournament_config_section;

-- ==========================================
-- SECTION 5: TOURNAMENT PREDICTIONS BACKUP
-- ==========================================

SELECT '=== TOURNAMENT PREDICTIONS BACKUP DATA ===' as section_header;
SELECT 'Copy all rows below and save as tournament_predictions_backup.sql' as instruction;
SELECT '' as separator;

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
ORDER BY id;

SELECT '' as end_tournament_predictions_section;

-- ==========================================
-- SECTION 6: TOURNAMENT TEAMS BACKUP
-- ==========================================

SELECT '=== TOURNAMENT TEAMS BACKUP DATA ===' as section_header;
SELECT 'Copy all rows below and save as tournament_teams_backup.sql' as instruction;
SELECT '' as separator;

SELECT 'INSERT INTO tournament_team (id, name, country_code, created_at) VALUES (' ||
       id || ', ' ||
       '''' || REPLACE(name, '''', '''''') || ''', ' ||
       COALESCE('''' || country_code || '''', 'NULL') || ', ' ||
       '''' || created_at || '''' ||
       ');' as backup_sql
FROM tournament_team
ORDER BY id;

SELECT '' as end_tournament_teams_section;

-- ==========================================
-- BACKUP SUMMARY
-- ==========================================

SELECT '=== BACKUP SUMMARY ===' as section_header;
SELECT 
    'Database Backup Summary - ' || NOW() as backup_info,
    (SELECT COUNT(*) FROM "user") as users_count,
    (SELECT COUNT(*) FROM game) as games_count,
    (SELECT COUNT(*) FROM prediction) as predictions_count,
    (SELECT COUNT(*) FROM tournament_team) as tournament_teams_count,
    (SELECT COUNT(*) FROM tournament_config) as tournament_configs_count,
    (SELECT COUNT(*) FROM tournament_prediction) as tournament_predictions_count;

-- ==========================================
-- COMPLETE BACKUP (ALL IN ONE)
-- ==========================================

SELECT '=== COMPLETE DATABASE BACKUP ===' as section_header;
SELECT 'Copy everything below and save as complete_backup.sql' as instruction;
SELECT '-- Volleyball Prediction Game Database Backup Generated: ' || NOW() as header;
SELECT '-- Disable foreign key checks during restore' as restore_instruction_1;
SELECT 'SET session_replication_role = replica;' as restore_instruction_2;
SELECT '' as separator_1;

-- All users data
SELECT '-- Users Data' as users_header;
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
ORDER BY id;

-- All games data
SELECT '' as separator_2;
SELECT '-- Games Data' as games_header;
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
ORDER BY id;

-- All tournament teams data
SELECT '' as separator_3;
SELECT '-- Tournament Teams Data' as tournament_teams_header;
SELECT 'INSERT INTO tournament_team (id, name, country_code, created_at) VALUES (' ||
       id || ', ' ||
       '''' || REPLACE(name, '''', '''''') || ''', ' ||
       COALESCE('''' || country_code || '''', 'NULL') || ', ' ||
       '''' || created_at || '''' ||
       ');' as backup_sql
FROM tournament_team
ORDER BY id;

-- All tournament config data
SELECT '' as separator_4;
SELECT '-- Tournament Config Data' as tournament_config_header;
SELECT 'INSERT INTO tournament_config (id, prediction_deadline, first_place_result, second_place_result, third_place_result, is_finalized) VALUES (' ||
       id || ', ' ||
       '''' || prediction_deadline || ''', ' ||
       COALESCE('''' || REPLACE(first_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
       COALESCE('''' || REPLACE(second_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
       COALESCE('''' || REPLACE(third_place_result, '''', '''''') || '''', 'NULL') || ', ' ||
       COALESCE(is_finalized::text, 'false') ||
       ');' as backup_sql
FROM tournament_config
ORDER BY id;

-- All predictions data
SELECT '' as separator_5;
SELECT '-- Predictions Data' as predictions_header;
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
ORDER BY id;

-- All tournament predictions data
SELECT '' as separator_6;
SELECT '-- Tournament Predictions Data' as tournament_predictions_header;
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
ORDER BY id;

-- Restore instructions
SELECT '' as separator_7;
SELECT '-- Re-enable foreign key checks' as restore_instruction_3;
SELECT 'SET session_replication_role = DEFAULT;' as restore_instruction_4;
SELECT '-- Update sequences to prevent ID conflicts' as restore_instruction_5;
SELECT 'SELECT setval(''user_id_seq'', (SELECT MAX(id) FROM "user"));' as sequence_update_1;
SELECT 'SELECT setval(''game_id_seq'', (SELECT MAX(id) FROM game));' as sequence_update_2;
SELECT 'SELECT setval(''prediction_id_seq'', (SELECT MAX(id) FROM prediction));' as sequence_update_3;
SELECT 'SELECT setval(''tournament_team_id_seq'', (SELECT MAX(id) FROM tournament_team));' as sequence_update_4;
SELECT 'SELECT setval(''tournament_config_id_seq'', (SELECT MAX(id) FROM tournament_config));' as sequence_update_5;
SELECT 'SELECT setval(''tournament_prediction_id_seq'', (SELECT MAX(id) FROM tournament_prediction));' as sequence_update_6;
SELECT '-- Backup completed successfully!' as final_message;