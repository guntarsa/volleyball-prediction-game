-- PostgreSQL Manual Predictions Import Script
-- NO FILE PERMISSIONS REQUIRED
-- Use this when you can't use COPY TO/FROM file commands

-- ==========================================
-- MANUAL CSV IMPORT FOR PREDICTIONS
-- ==========================================

-- INSTRUCTIONS:
-- 1. Replace the sample data below with your actual prediction data
-- 2. Follow the CSV format: user_name, team1, team2, team1_score, team2_score
-- 3. Run this script in pgAdmin

-- ==========================================
-- PREPARATION
-- ==========================================

-- Create a temporary table to hold CSV data
DROP TABLE IF EXISTS temp_predictions_import;
CREATE TEMPORARY TABLE temp_predictions_import (
    user_identifier TEXT,
    team1 TEXT,
    team2 TEXT,
    team1_score INTEGER,
    team2_score INTEGER,
    additional_info TEXT
);

-- Show current prediction count before import
SELECT 'CURRENT PREDICTIONS COUNT BEFORE IMPORT:' as status;
SELECT COUNT(*) as current_predictions FROM prediction;

-- ==========================================
-- MANUAL DATA ENTRY
-- ==========================================

-- REPLACE THE SAMPLE DATA BELOW WITH YOUR ACTUAL DATA
-- Format: user_name, team1, team2, team1_score, team2_score, round_info
INSERT INTO temp_predictions_import (user_identifier, team1, team2, team1_score, team2_score, additional_info) VALUES
-- Sample data - REPLACE WITH YOUR ACTUAL DATA:
('admin@example.com', 'Brazil', 'Italy', 3, 1, 'Quarter Final 1'),
('user@example.com', 'Brazil', 'Italy', 3, 2, 'Quarter Final 1'),
('john@example.com', 'USA', 'Poland', 3, 0, 'Quarter Final 2'),
('admin@example.com', 'USA', 'Poland', 3, 2, 'Quarter Final 2'),
('user@example.com', 'Serbia', 'Turkey', 3, 1, 'Quarter Final 3');

-- ADD MORE ROWS ABOVE AS NEEDED
-- Copy this format: ('user_email_or_name', 'team1', 'team2', score1, score2, 'round_info'),

-- ==========================================
-- ALTERNATIVE: BATCH INSERT TEMPLATE
-- ==========================================

-- If you have many predictions, use this template:
-- Uncomment and modify the section below:

/*
-- BATCH 1: Quarter Finals
INSERT INTO temp_predictions_import (user_identifier, team1, team2, team1_score, team2_score, additional_info) VALUES
('user1@example.com', 'Brazil', 'Italy', 3, 1, 'QF1'),
('user1@example.com', 'USA', 'Poland', 3, 2, 'QF2'),
('user1@example.com', 'Serbia', 'Turkey', 3, 0, 'QF3'),
('user1@example.com', 'France', 'Japan', 3, 1, 'QF4');

-- BATCH 2: Semi Finals  
INSERT INTO temp_predictions_import (user_identifier, team1, team2, team1_score, team2_score, additional_info) VALUES
('user2@example.com', 'Brazil', 'USA', 3, 2, 'SF1'),
('user2@example.com', 'Serbia', 'France', 3, 1, 'SF2');

-- Continue with more batches...
*/

-- ==========================================
-- DATA PROCESSING
-- ==========================================

-- Check what data was imported
SELECT 'IMPORTED DATA PREVIEW:' as status;
SELECT * FROM temp_predictions_import ORDER BY user_identifier;

-- Validate imported data
SELECT 'DATA VALIDATION:' as status;
SELECT 
    COUNT(*) as total_rows,
    COUNT(CASE WHEN user_identifier IS NOT NULL THEN 1 END) as rows_with_user,
    COUNT(CASE WHEN team1_score IS NOT NULL AND team2_score IS NOT NULL THEN 1 END) as rows_with_scores,
    COUNT(CASE WHEN team1_score = 3 OR team2_score = 3 THEN 1 END) as valid_volleyball_scores
FROM temp_predictions_import;

-- Create staging table with resolved IDs
DROP TABLE IF EXISTS temp_predictions_staged;
CREATE TEMPORARY TABLE temp_predictions_staged AS
WITH resolved_data AS (
    SELECT 
        ti.*,
        -- Resolve user_id (by name or email)
        COALESCE(
            (SELECT u.id FROM "user" u WHERE u.email = ti.user_identifier LIMIT 1),
            (SELECT u.id FROM "user" u WHERE u.name = ti.user_identifier LIMIT 1)
        ) as resolved_user_id,
        
        -- Resolve game_id (by team names)
        (SELECT g.id FROM game g 
         WHERE g.team1 = ti.team1 AND g.team2 = ti.team2 
         LIMIT 1) as resolved_game_id
    FROM temp_predictions_import ti
)
SELECT 
    resolved_user_id as user_id,
    resolved_game_id as game_id,
    team1_score,
    team2_score,
    -- Determine predicted winner
    CASE 
        WHEN team1_score > team2_score THEN team1
        WHEN team2_score > team1_score THEN team2
        ELSE NULL
    END as predicted_winner
FROM resolved_data
WHERE resolved_user_id IS NOT NULL 
  AND resolved_game_id IS NOT NULL
  AND team1_score IS NOT NULL 
  AND team2_score IS NOT NULL
  -- Validate volleyball scores (winner must have 3, loser 0-2)
  AND ((team1_score = 3 AND team2_score BETWEEN 0 AND 2) 
       OR (team2_score = 3 AND team1_score BETWEEN 0 AND 2));

-- Show staged data for review
SELECT 'STAGED PREDICTIONS FOR IMPORT:' as status;
SELECT 
    s.*,
    u.name as user_name,
    u.email as user_email,
    g.team1 || ' vs ' || g.team2 as game_matchup,
    g.round_name
FROM temp_predictions_staged s
LEFT JOIN "user" u ON s.user_id = u.id
LEFT JOIN game g ON s.game_id = g.id
ORDER BY s.user_id, s.game_id;

-- Check for unresolved users or games
SELECT 'IMPORT ISSUES - UNRESOLVED USERS:' as issue_type;
SELECT DISTINCT ti.user_identifier 
FROM temp_predictions_import ti
WHERE NOT EXISTS (
    SELECT 1 FROM "user" u 
    WHERE u.email = ti.user_identifier OR u.name = ti.user_identifier
);

SELECT 'IMPORT ISSUES - UNRESOLVED GAMES:' as issue_type;
SELECT DISTINCT ti.team1 || ' vs ' || ti.team2 as unresolved_game
FROM temp_predictions_import ti  
WHERE NOT EXISTS (
    SELECT 1 FROM game g 
    WHERE g.team1 = ti.team1 AND g.team2 = ti.team2
);

-- Check for conflicts with existing predictions
SELECT 'CHECKING FOR CONFLICTS:' as status;
SELECT 
    s.user_id,
    s.game_id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game_matchup,
    'CONFLICT: Prediction already exists' as issue
FROM temp_predictions_staged s
JOIN "user" u ON s.user_id = u.id
JOIN game g ON s.game_id = g.id
WHERE EXISTS (
    SELECT 1 FROM prediction p 
    WHERE p.user_id = s.user_id AND p.game_id = s.game_id
);

-- ==========================================
-- IMPORT EXECUTION
-- ==========================================

-- Insert new predictions (skip conflicts)
INSERT INTO prediction (user_id, game_id, team1_score, team2_score, predicted_winner, points, created_at)
SELECT 
    s.user_id,
    s.game_id,
    s.team1_score,
    s.team2_score,
    s.predicted_winner,
    -- Calculate points if game is finished
    CASE 
        WHEN g.is_finished THEN 
            CASE
                -- Perfect prediction (6 points)
                WHEN s.team1_score = g.team1_score AND s.team2_score = g.team2_score THEN 6
                -- Correct winner and one correct score (4 points)  
                WHEN (s.team1_score > s.team2_score AND g.team1_score > g.team2_score AND 
                      (s.team1_score = g.team1_score OR s.team2_score = g.team2_score)) OR
                     (s.team2_score > s.team1_score AND g.team2_score > g.team1_score AND 
                      (s.team1_score = g.team1_score OR s.team2_score = g.team2_score)) THEN 4
                -- Correct winner only (2 points)
                WHEN (s.team1_score > s.team2_score AND g.team1_score > g.team2_score) OR
                     (s.team2_score > s.team1_score AND g.team2_score > g.team1_score) THEN 2
                -- One correct score but wrong winner (1 point)
                WHEN s.team1_score = g.team1_score OR s.team2_score = g.team2_score THEN 1
                -- Wrong prediction (0 points)
                ELSE 0
            END
        ELSE NULL
    END,
    NOW()
FROM temp_predictions_staged s
JOIN game g ON s.game_id = g.id
WHERE NOT EXISTS (
    SELECT 1 FROM prediction p 
    WHERE p.user_id = s.user_id AND p.game_id = s.game_id
);

-- Get count of imported predictions
SELECT 'IMPORT RESULTS:' as status;
SELECT 
    'Import Summary' as info,
    (SELECT COUNT(*) FROM temp_predictions_staged) as staged_predictions,
    (SELECT COUNT(*) FROM prediction WHERE created_at >= NOW() - INTERVAL '1 minute') as newly_imported,
    (SELECT COUNT(*) FROM prediction) as total_predictions_after;

-- Show sample of imported predictions
SELECT 'SAMPLE OF IMPORTED PREDICTIONS:' as status;
SELECT 
    p.id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game,
    p.team1_score || '-' || p.team2_score as prediction,
    p.predicted_winner,
    COALESCE(p.points::text, 'Not scored') as points,
    p.created_at
FROM prediction p
JOIN "user" u ON p.user_id = u.id
JOIN game g ON p.game_id = g.id
WHERE p.created_at >= NOW() - INTERVAL '1 minute'
ORDER BY p.created_at DESC
LIMIT 10;

-- Cleanup
DROP TABLE IF EXISTS temp_predictions_import;
DROP TABLE IF EXISTS temp_predictions_staged;

SELECT 'Manual import process completed successfully!' as final_status;