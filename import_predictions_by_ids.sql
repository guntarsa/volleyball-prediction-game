-- PostgreSQL Manual Predictions Import Script - By User ID and Game ID
-- NO FILE PERMISSIONS REQUIRED
-- Format: user_id, game_id, team1_score, team2_score
-- Automatically calculates points for finished games

-- ==========================================
-- MANUAL CSV IMPORT FOR PREDICTIONS BY IDS
-- ==========================================

-- INSTRUCTIONS:
-- 1. Replace the sample data below with your actual prediction data
-- 2. Use format: user_id, game_id, team1_score, team2_score
-- 3. Points will be automatically calculated if games are finished
-- 4. Run this script in pgAdmin

-- ==========================================
-- PREPARATION
-- ==========================================

-- Create a temporary table to hold CSV data
DROP TABLE IF EXISTS temp_predictions_import;
CREATE TEMPORARY TABLE temp_predictions_import (
    user_id INTEGER,
    game_id INTEGER,
    team1_score INTEGER,
    team2_score INTEGER
);

-- Show current prediction count before import
SELECT 'CURRENT PREDICTIONS COUNT BEFORE IMPORT:' as status;
SELECT COUNT(*) as current_predictions FROM prediction;

-- Show current users and games for reference
SELECT 'AVAILABLE USERS FOR REFERENCE:' as info;
SELECT id as user_id, name, email FROM "user" ORDER BY id;

SELECT 'AVAILABLE GAMES FOR REFERENCE:' as info;
SELECT 
    id as game_id, 
    team1 || ' vs ' || team2 as matchup, 
    round_name,
    game_date,
    is_finished,
    CASE WHEN is_finished THEN team1_score || '-' || team2_score ELSE 'Not finished' END as actual_result
FROM game 
ORDER BY id;

-- ==========================================
-- MANUAL DATA ENTRY
-- ==========================================

-- REPLACE THE SAMPLE DATA BELOW WITH YOUR ACTUAL DATA
-- Format: (user_id, game_id, team1_score, team2_score)
INSERT INTO temp_predictions_import (user_id, game_id, team1_score, team2_score) VALUES
-- Sample data - REPLACE WITH YOUR ACTUAL DATA:
(1, 1, 3, 1),  -- User ID 1, Game ID 1, prediction 3-1
(1, 2, 3, 2),  -- User ID 1, Game ID 2, prediction 3-2
(2, 1, 3, 0),  -- User ID 2, Game ID 1, prediction 3-0
(2, 2, 3, 1),  -- User ID 2, Game ID 2, prediction 3-1
(3, 1, 3, 2),  -- User ID 3, Game ID 1, prediction 3-2
(3, 2, 3, 0);  -- User ID 3, Game ID 2, prediction 3-0

-- ADD MORE ROWS ABOVE AS NEEDED
-- Copy this format: (user_id, game_id, team1_score, team2_score),

-- ==========================================
-- ALTERNATIVE: LARGE BATCH INSERT TEMPLATE
-- ==========================================

-- If you have many predictions, use this template:
-- Uncomment and modify the section below:

/*
-- BATCH 1: Game 1 predictions
INSERT INTO temp_predictions_import (user_id, game_id, team1_score, team2_score) VALUES
(1, 1, 3, 1),
(2, 1, 3, 2),
(3, 1, 3, 0),
(4, 1, 3, 1),
(5, 1, 3, 2);

-- BATCH 2: Game 2 predictions  
INSERT INTO temp_predictions_import (user_id, game_id, team1_score, team2_score) VALUES
(1, 2, 3, 2),
(2, 2, 3, 1),
(3, 2, 3, 0),
(4, 2, 3, 2),
(5, 2, 3, 1);

-- BATCH 3: Game 3 predictions
INSERT INTO temp_predictions_import (user_id, game_id, team1_score, team2_score) VALUES
(1, 3, 3, 1),
(2, 3, 3, 0),
(3, 3, 3, 2),
(4, 3, 3, 1),
(5, 3, 3, 0);

-- Continue with more batches...
*/

-- ==========================================
-- DATA VALIDATION
-- ==========================================

-- Check what data was imported
SELECT 'IMPORTED DATA PREVIEW:' as status;
SELECT 
    ti.*,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game_matchup,
    g.round_name,
    g.is_finished,
    CASE WHEN g.is_finished THEN g.team1_score || '-' || g.team2_score ELSE 'Not finished' END as actual_result
FROM temp_predictions_import ti
LEFT JOIN "user" u ON ti.user_id = u.id
LEFT JOIN game g ON ti.game_id = g.id
ORDER BY ti.user_id, ti.game_id;

-- Validate imported data
SELECT 'DATA VALIDATION SUMMARY:' as status;
SELECT 
    COUNT(*) as total_rows,
    COUNT(CASE WHEN user_id IS NOT NULL THEN 1 END) as rows_with_user_id,
    COUNT(CASE WHEN game_id IS NOT NULL THEN 1 END) as rows_with_game_id,
    COUNT(CASE WHEN team1_score IS NOT NULL AND team2_score IS NOT NULL THEN 1 END) as rows_with_scores,
    COUNT(CASE WHEN team1_score = 3 OR team2_score = 3 THEN 1 END) as valid_volleyball_scores,
    COUNT(CASE WHEN EXISTS(SELECT 1 FROM "user" u WHERE u.id = ti.user_id) THEN 1 END) as valid_users,
    COUNT(CASE WHEN EXISTS(SELECT 1 FROM game g WHERE g.id = ti.game_id) THEN 1 END) as valid_games
FROM temp_predictions_import ti;

-- Check for invalid user IDs
SELECT 'INVALID USER IDS:' as validation_issue;
SELECT DISTINCT ti.user_id
FROM temp_predictions_import ti
WHERE NOT EXISTS (SELECT 1 FROM "user" u WHERE u.id = ti.user_id);

-- Check for invalid game IDs  
SELECT 'INVALID GAME IDS:' as validation_issue;
SELECT DISTINCT ti.game_id
FROM temp_predictions_import ti
WHERE NOT EXISTS (SELECT 1 FROM game g WHERE g.id = ti.game_id);

-- Check for invalid volleyball scores
SELECT 'INVALID VOLLEYBALL SCORES:' as validation_issue;
SELECT ti.*, 'Invalid: Winner must have 3 sets, loser 0-2 sets' as issue
FROM temp_predictions_import ti
WHERE NOT (
    (ti.team1_score = 3 AND ti.team2_score BETWEEN 0 AND 2) OR
    (ti.team2_score = 3 AND ti.team1_score BETWEEN 0 AND 2)
);

-- ==========================================
-- STAGING WITH POINT CALCULATION
-- ==========================================

-- Create staging table with calculated points
DROP TABLE IF EXISTS temp_predictions_staged;
CREATE TEMPORARY TABLE temp_predictions_staged AS
SELECT 
    ti.user_id,
    ti.game_id,
    ti.team1_score,
    ti.team2_score,
    -- Determine predicted winner
    CASE 
        WHEN ti.team1_score > ti.team2_score THEN g.team1
        WHEN ti.team2_score > ti.team1_score THEN g.team2
        ELSE NULL
    END as predicted_winner,
    -- Calculate points if game is finished
    CASE 
        WHEN g.is_finished AND g.team1_score IS NOT NULL AND g.team2_score IS NOT NULL THEN 
            CASE
                -- Perfect prediction (6 points) - exact score match
                WHEN ti.team1_score = g.team1_score AND ti.team2_score = g.team2_score THEN 6
                
                -- Correct winner and one correct score (4 points)  
                WHEN (ti.team1_score > ti.team2_score AND g.team1_score > g.team2_score AND 
                      (ti.team1_score = g.team1_score OR ti.team2_score = g.team2_score)) OR
                     (ti.team2_score > ti.team1_score AND g.team2_score > g.team1_score AND 
                      (ti.team1_score = g.team1_score OR ti.team2_score = g.team2_score)) THEN 4
                
                -- Correct winner only (2 points)
                WHEN (ti.team1_score > ti.team2_score AND g.team1_score > g.team2_score) OR
                     (ti.team2_score > ti.team1_score AND g.team2_score > g.team1_score) THEN 2
                
                -- One correct individual score but wrong winner (1 point)
                WHEN ti.team1_score = g.team1_score OR ti.team2_score = g.team2_score THEN 1
                
                -- Correct total number of sets (1 point) - NEW RULE
                WHEN (ti.team1_score + ti.team2_score) = (g.team1_score + g.team2_score) THEN 1
                
                -- Wrong prediction (0 points)
                ELSE 0
            END
        ELSE NULL  -- Game not finished yet
    END as calculated_points,
    g.is_finished,
    g.team1_score as actual_team1_score,
    g.team2_score as actual_team2_score
FROM temp_predictions_import ti
JOIN "user" u ON ti.user_id = u.id
JOIN game g ON ti.game_id = g.id
WHERE (ti.team1_score = 3 AND ti.team2_score BETWEEN 0 AND 2) OR
      (ti.team2_score = 3 AND ti.team1_score BETWEEN 0 AND 2);

-- Show staged data with point calculations
SELECT 'STAGED PREDICTIONS WITH CALCULATED POINTS:' as status;
SELECT 
    s.*,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game_matchup,
    g.round_name,
    CASE 
        WHEN s.is_finished THEN 
            'Actual: ' || s.actual_team1_score || '-' || s.actual_team2_score
        ELSE 'Game not finished'
    END as actual_result_info,
    CASE 
        WHEN s.calculated_points IS NOT NULL THEN 
            s.calculated_points || ' points'
        ELSE 'Points pending (game not finished)'
    END as points_info
FROM temp_predictions_staged s
LEFT JOIN "user" u ON s.user_id = u.id
LEFT JOIN game g ON s.game_id = g.id
ORDER BY s.user_id, s.game_id;

-- Check for conflicts with existing predictions
SELECT 'CHECKING FOR CONFLICTS WITH EXISTING PREDICTIONS:' as status;
SELECT 
    s.user_id,
    s.game_id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game_matchup,
    'CONFLICT: Prediction already exists' as issue,
    p.team1_score || '-' || p.team2_score as existing_prediction
FROM temp_predictions_staged s
JOIN "user" u ON s.user_id = u.id
JOIN game g ON s.game_id = g.id
JOIN prediction p ON p.user_id = s.user_id AND p.game_id = s.game_id;

-- ==========================================
-- IMPORT EXECUTION
-- ==========================================

-- Show what will be imported
SELECT 'PREDICTIONS TO BE IMPORTED:' as status;
SELECT 
    COUNT(*) as total_to_import,
    COUNT(CASE WHEN calculated_points IS NOT NULL THEN 1 END) as predictions_with_points,
    COUNT(CASE WHEN NOT is_finished THEN 1 END) as predictions_pending_scoring
FROM temp_predictions_staged;

-- Insert new predictions (skip conflicts)
WITH import_results AS (
    INSERT INTO prediction (user_id, game_id, team1_score, team2_score, predicted_winner, points, created_at)
    SELECT 
        s.user_id,
        s.game_id,
        s.team1_score,
        s.team2_score,
        s.predicted_winner,
        s.calculated_points,
        NOW()
    FROM temp_predictions_staged s
    WHERE NOT EXISTS (
        SELECT 1 FROM prediction p 
        WHERE p.user_id = s.user_id AND p.game_id = s.game_id
    )
    RETURNING user_id, game_id, team1_score, team2_score, points
)
SELECT 'IMPORT EXECUTED' as status, COUNT(*) as imported_count FROM import_results;

-- ==========================================
-- IMPORT RESULTS AND SUMMARY
-- ==========================================

-- Show import results
SELECT 'IMPORT COMPLETED! RESULTS SUMMARY:' as status;
SELECT 
    'Import Summary' as metric,
    (SELECT COUNT(*) FROM temp_predictions_staged) as staged_predictions,
    (SELECT COUNT(*) FROM prediction WHERE created_at >= NOW() - INTERVAL '2 minutes') as newly_imported,
    (SELECT COUNT(*) FROM prediction) as total_predictions_after_import;

-- Show detailed results for finished games
SELECT 'IMPORTED PREDICTIONS WITH CALCULATED POINTS:' as status;
SELECT 
    p.id as prediction_id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game,
    p.team1_score || '-' || p.team2_score as prediction,
    g.team1_score || '-' || g.team2_score as actual_result,
    p.predicted_winner,
    CASE 
        WHEN p.points = 6 THEN p.points || ' points (PERFECT!)'
        WHEN p.points = 4 THEN p.points || ' points (Winner + 1 score)'
        WHEN p.points = 2 THEN p.points || ' points (Winner only)'
        WHEN p.points = 1 THEN p.points || ' points (1 score only)'
        WHEN p.points = 0 THEN p.points || ' points (Wrong)'
        ELSE 'Points pending'
    END as points_breakdown,
    p.created_at
FROM prediction p
JOIN "user" u ON p.user_id = u.id
JOIN game g ON p.game_id = g.id
WHERE p.created_at >= NOW() - INTERVAL '2 minutes'
ORDER BY p.points DESC, p.created_at DESC;

-- Show user totals after import
SELECT 'USER SCORE TOTALS AFTER IMPORT:' as status;
SELECT 
    u.name as user_name,
    COUNT(p.id) as total_predictions,
    COUNT(CASE WHEN p.points IS NOT NULL THEN 1 END) as scored_predictions,
    COALESCE(SUM(p.points), 0) as total_points,
    COALESCE(ROUND(AVG(p.points), 2), 0) as avg_points_per_prediction
FROM "user" u
LEFT JOIN prediction p ON u.id = p.user_id
GROUP BY u.id, u.name
HAVING COUNT(p.id) > 0
ORDER BY total_points DESC;

-- Cleanup temporary tables
DROP TABLE IF EXISTS temp_predictions_import;
DROP TABLE IF EXISTS temp_predictions_staged;

SELECT 'IMPORT PROCESS COMPLETED SUCCESSFULLY!' as final_status;
SELECT 'Points have been automatically calculated for all finished games.' as note;