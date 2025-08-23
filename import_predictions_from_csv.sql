-- PostgreSQL Script to Import Predictions from CSV
-- Run this script in pgAdmin to import predictions from CSV file
-- Make sure your CSV file is accessible to PostgreSQL

-- ==========================================
-- CSV IMPORT SCRIPT FOR PREDICTIONS
-- ==========================================

-- Expected CSV format:
-- user_name,team1,team2,team1_score,team2_score,game_date,round_name
-- OR
-- user_id,game_id,team1_score,team2_score
-- OR  
-- user_email,team1,team2,team1_score,team2_score,prediction_date

-- ==========================================
-- PREPARATION STEPS
-- ==========================================

-- Create a temporary table to import CSV data
DROP TABLE IF EXISTS temp_predictions_import;
CREATE TEMPORARY TABLE temp_predictions_import (
    user_identifier TEXT,          -- Can be name, email, or ID
    game_identifier_1 TEXT,        -- team1 OR game_id
    game_identifier_2 TEXT,        -- team2 OR NULL if using game_id
    team1_score INTEGER,
    team2_score INTEGER,
    additional_info TEXT,          -- game_date, round_name, or other info
    extra_field TEXT               -- for flexible CSV formats
);

-- Show current prediction count before import
SELECT 'CURRENT PREDICTIONS COUNT BEFORE IMPORT:' as status;
SELECT COUNT(*) as current_predictions FROM prediction;

-- ==========================================
-- CSV IMPORT METHODS
-- ==========================================

-- METHOD 1: Import from CSV file (requires file system access)
-- For Windows: Place your CSV file in C:\temp\ or update the path below
-- Uncomment and modify the path to your CSV file:
/*
COPY temp_predictions_import(user_identifier, game_identifier_1, game_identifier_2, team1_score, team2_score, additional_info)
FROM 'C:\temp\predictions.csv' 
DELIMITER ',' 
CSV HEADER;
*/

-- METHOD 2: Manual data entry (if you can't use COPY)
-- Uncomment and add your data:
/*
INSERT INTO temp_predictions_import (user_identifier, game_identifier_1, game_identifier_2, team1_score, team2_score, additional_info) VALUES
('john@example.com', 'Brazil', 'Italy', 3, 1, 'Quarter Final 1'),
('admin@example.com', 'USA', 'Poland', 3, 2, 'Quarter Final 2'),
('user@example.com', 'Serbia', 'Turkey', 3, 0, 'Quarter Final 3');
-- Add more rows as needed
*/

-- METHOD 3: Import with game_id and user_id (if you have IDs)
/*
INSERT INTO temp_predictions_import (user_identifier, game_identifier_1, game_identifier_2, team1_score, team2_score) VALUES
('1', '1', NULL, 3, 1),  -- user_id=1, game_id=1
('2', '1', NULL, 3, 2),  -- user_id=2, game_id=1  
('1', '2', NULL, 3, 0);  -- user_id=1, game_id=2
*/

-- ==========================================
-- DATA PROCESSING AND VALIDATION
-- ==========================================

-- Check what data was imported
SELECT 'IMPORTED DATA PREVIEW:' as status;
SELECT * FROM temp_predictions_import LIMIT 10;

-- Validate imported data
SELECT 'DATA VALIDATION:' as status;
SELECT 
    COUNT(*) as total_rows,
    COUNT(CASE WHEN user_identifier IS NOT NULL THEN 1 END) as rows_with_user,
    COUNT(CASE WHEN team1_score IS NOT NULL AND team2_score IS NOT NULL THEN 1 END) as rows_with_scores,
    COUNT(CASE WHEN team1_score = 3 OR team2_score = 3 THEN 1 END) as valid_volleyball_scores
FROM temp_predictions_import;

-- ==========================================
-- PREDICTION IMPORT LOGIC
-- ==========================================

-- Create a staging table with resolved IDs
DROP TABLE IF EXISTS temp_predictions_staged;
CREATE TEMPORARY TABLE temp_predictions_staged AS
WITH resolved_data AS (
    SELECT 
        ti.*,
        -- Resolve user_id
        CASE 
            WHEN ti.user_identifier ~ '^\d+$' THEN ti.user_identifier::integer
            ELSE (
                SELECT u.id 
                FROM "user" u 
                WHERE u.name = ti.user_identifier 
                   OR u.email = ti.user_identifier 
                LIMIT 1
            )
        END as resolved_user_id,
        
        -- Resolve game_id  
        CASE 
            WHEN ti.game_identifier_1 ~ '^\d+$' AND ti.game_identifier_2 IS NULL THEN 
                ti.game_identifier_1::integer
            ELSE (
                SELECT g.id 
                FROM game g 
                WHERE g.team1 = ti.game_identifier_1 
                  AND g.team2 = ti.game_identifier_2
                LIMIT 1
            )
        END as resolved_game_id
    FROM temp_predictions_import ti
)
SELECT 
    resolved_user_id as user_id,
    resolved_game_id as game_id,
    team1_score,
    team2_score,
    -- Determine predicted winner
    CASE 
        WHEN team1_score > team2_score THEN (SELECT team1 FROM game WHERE id = resolved_game_id)
        WHEN team2_score > team1_score THEN (SELECT team2 FROM game WHERE id = resolved_game_id)
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
    g.team1 || ' vs ' || g.team2 as game_matchup
FROM temp_predictions_staged s
LEFT JOIN "user" u ON s.user_id = u.id
LEFT JOIN game g ON s.game_id = g.id
ORDER BY s.user_id, s.game_id;

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

-- Option 1: Insert new predictions (skip conflicts)
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

-- Option 2: Update existing predictions (uncomment if you want to overwrite)
/*
UPDATE prediction p
SET 
    team1_score = s.team1_score,
    team2_score = s.team2_score,
    predicted_winner = s.predicted_winner,
    points = CASE 
        WHEN g.is_finished THEN 
            CASE
                WHEN s.team1_score = g.team1_score AND s.team2_score = g.team2_score THEN 6
                WHEN (s.team1_score > s.team2_score AND g.team1_score > g.team2_score AND 
                      (s.team1_score = g.team1_score OR s.team2_score = g.team2_score)) OR
                     (s.team2_score > s.team1_score AND g.team2_score > g.team1_score AND 
                      (s.team1_score = g.team1_score OR s.team2_score = g.team2_score)) THEN 4
                WHEN (s.team1_score > s.team2_score AND g.team1_score > g.team2_score) OR
                     (s.team2_score > s.team1_score AND g.team2_score > g.team1_score) THEN 2
                WHEN s.team1_score = g.team1_score OR s.team2_score = g.team2_score THEN 1
                ELSE 0
            END
        ELSE NULL
    END
FROM temp_predictions_staged s
JOIN game g ON s.game_id = g.id
WHERE p.user_id = s.user_id AND p.game_id = s.game_id;
*/

-- ==========================================
-- POST-IMPORT VALIDATION
-- ==========================================

-- Show results
SELECT 'IMPORT COMPLETED! RESULTS:' as status;

SELECT 
    'Import Summary' as info,
    (SELECT COUNT(*) FROM temp_predictions_staged) as staged_predictions,
    (SELECT COUNT(*) FROM prediction) as total_predictions_after,
    (SELECT COUNT(*) FROM prediction) - (
        SELECT COUNT(*) FROM prediction WHERE created_at < NOW() - INTERVAL '1 minute'
    ) as newly_imported_predictions;

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

-- Cleanup temporary tables
DROP TABLE IF EXISTS temp_predictions_import;
DROP TABLE IF EXISTS temp_predictions_staged;

SELECT 'Import process completed successfully!' as final_status;