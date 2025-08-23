-- PostgreSQL Database Restore Script for Volleyball Prediction Game
-- Run this script in pgAdmin to restore data from backup
-- IMPORTANT: Make sure you have a backup file ready to restore from

-- ==========================================
-- DATABASE RESTORE SCRIPT
-- ==========================================

-- WARNING: This will delete all existing data!
-- Uncomment the TRUNCATE statements below only if you want to clear all data first

/*
-- DANGER ZONE: Uncomment these lines to clear all existing data
TRUNCATE TABLE prediction RESTART IDENTITY CASCADE;
TRUNCATE TABLE tournament_prediction RESTART IDENTITY CASCADE;
TRUNCATE TABLE game RESTART IDENTITY CASCADE;
TRUNCATE TABLE "user" RESTART IDENTITY CASCADE;
TRUNCATE TABLE tournament_config RESTART IDENTITY CASCADE;
TRUNCATE TABLE tournament_team RESTART IDENTITY CASCADE;
*/

-- Check current data before restore
SELECT 'CURRENT DATABASE STATE BEFORE RESTORE:' as status;
SELECT 
    'Current Data Count' as info,
    (SELECT COUNT(*) FROM "user") as users,
    (SELECT COUNT(*) FROM game) as games,
    (SELECT COUNT(*) FROM prediction) as predictions,
    (SELECT COUNT(*) FROM tournament_team) as tournament_teams,
    (SELECT COUNT(*) FROM tournament_config) as configs,
    (SELECT COUNT(*) FROM tournament_prediction) as tournament_predictions;

-- Disable foreign key checks during restore
SET session_replication_role = replica;

-- ==========================================
-- MANUAL RESTORE INSTRUCTIONS
-- ==========================================

/*
INSTRUCTIONS FOR MANUAL RESTORE:

1. If you have a backup file from backup_database.sql:
   - Copy the content from /tmp/full_database_backup.sql
   - Paste it below this comment block and execute

2. If you have individual table backups:
   - Execute the INSERT statements from each backup file in this order:
   a) Users first (users_backup.sql)
   b) Games second (games_backup.sql)  
   c) Tournament Teams (tournament_teams_backup.sql)
   d) Tournament Config (tournament_config_backup.sql)
   e) Predictions (predictions_backup.sql)
   f) Tournament Predictions (tournament_predictions_backup.sql)

3. After restore, run the sequence updates at the bottom of this file
*/

-- ==========================================
-- SAMPLE RESTORE DATA (REPLACE WITH YOUR BACKUP)
-- ==========================================

-- Example: If you want to restore sample data, uncomment below:
/*
-- Sample Users (replace with your actual backup data)
INSERT INTO "user" (id, name, email, password_hash, is_admin, is_verified, password_reset_required, created_at) VALUES 
(1, 'Admin User', 'admin@example.com', 'your_password_hash_here', true, true, false, '2024-01-01 00:00:00'),
(2, 'Test User', 'user@example.com', 'your_password_hash_here', false, true, false, '2024-01-01 00:00:00');

-- Sample Games (replace with your actual backup data)
INSERT INTO game (id, team1, team2, game_date, prediction_deadline, round_name, team1_score, team2_score, is_finished) VALUES 
(1, 'Brazil', 'Italy', '2024-12-01 14:00:00', '2024-12-01 13:30:00', 'Quarter Final 1', NULL, NULL, false);

-- Add more INSERT statements from your backup here...
*/

-- ==========================================
-- POST-RESTORE CLEANUP
-- ==========================================

-- Re-enable foreign key checks
SET session_replication_role = DEFAULT;

-- Update sequences to prevent ID conflicts
-- This ensures new records will have proper IDs
SELECT 'Updating sequences...' as status;

DO $$
BEGIN
    -- Update user sequence
    IF (SELECT COUNT(*) FROM "user") > 0 THEN
        PERFORM setval('user_id_seq', (SELECT MAX(id) FROM "user"));
    END IF;
    
    -- Update game sequence
    IF (SELECT COUNT(*) FROM game) > 0 THEN
        PERFORM setval('game_id_seq', (SELECT MAX(id) FROM game));
    END IF;
    
    -- Update prediction sequence
    IF (SELECT COUNT(*) FROM prediction) > 0 THEN
        PERFORM setval('prediction_id_seq', (SELECT MAX(id) FROM prediction));
    END IF;
    
    -- Update tournament_team sequence
    IF (SELECT COUNT(*) FROM tournament_team) > 0 THEN
        PERFORM setval('tournament_team_id_seq', (SELECT MAX(id) FROM tournament_team));
    END IF;
    
    -- Update tournament_config sequence
    IF (SELECT COUNT(*) FROM tournament_config) > 0 THEN
        PERFORM setval('tournament_config_id_seq', (SELECT MAX(id) FROM tournament_config));
    END IF;
    
    -- Update tournament_prediction sequence
    IF (SELECT COUNT(*) FROM tournament_prediction) > 0 THEN
        PERFORM setval('tournament_prediction_id_seq', (SELECT MAX(id) FROM tournament_prediction));
    END IF;
END $$;

-- ==========================================
-- VALIDATION QUERIES
-- ==========================================

-- Verify restore was successful
SELECT 'RESTORE VALIDATION:' as status;

-- Check data counts
SELECT 
    'Final Data Count' as validation_type,
    (SELECT COUNT(*) FROM "user") as users,
    (SELECT COUNT(*) FROM game) as games,
    (SELECT COUNT(*) FROM prediction) as predictions,
    (SELECT COUNT(*) FROM tournament_team) as tournament_teams,
    (SELECT COUNT(*) FROM tournament_config) as configs,
    (SELECT COUNT(*) FROM tournament_prediction) as tournament_predictions;

-- Check for any orphaned records
SELECT 'Checking for data integrity issues...' as status;

-- Check for predictions without valid users or games
SELECT 
    'Orphaned Predictions' as issue_type,
    COUNT(*) as count
FROM prediction p
LEFT JOIN "user" u ON p.user_id = u.id
LEFT JOIN game g ON p.game_id = g.id
WHERE u.id IS NULL OR g.id IS NULL;

-- Check for tournament predictions without valid users
SELECT 
    'Orphaned Tournament Predictions' as issue_type,
    COUNT(*) as count
FROM tournament_prediction tp
LEFT JOIN "user" u ON tp.user_id = u.id
WHERE u.id IS NULL;

-- Show sample of restored data
SELECT 'Sample restored users:' as info;
SELECT id, name, email, is_admin, created_at FROM "user" LIMIT 5;

SELECT 'Sample restored games:' as info;
SELECT id, team1, team2, round_name, game_date, is_finished FROM game LIMIT 5;

SELECT 'Sample restored predictions:' as info;
SELECT p.id, u.name as user_name, g.team1 || ' vs ' || g.team2 as game, 
       p.team1_score, p.team2_score, p.points 
FROM prediction p 
JOIN "user" u ON p.user_id = u.id 
JOIN game g ON p.game_id = g.id 
LIMIT 5;

SELECT 'Restore process completed!' as status;
SELECT 'Remember to test the application to ensure everything is working properly.' as reminder;