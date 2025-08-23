-- PostgreSQL Script to Fix Points Calculation
-- Corrects predictions that should have 1 point for guessing correct total sets
-- Run this script in pgAdmin to recalculate all prediction points

-- ==========================================
-- POINTS CALCULATION FIX SCRIPT
-- ==========================================

-- VOLLEYBALL SCORING SYSTEM (CORRECTED):
-- 6 points: Perfect prediction (exact score match)
-- 4 points: Correct winner + one correct individual score
-- 2 points: Correct winner only  
-- 1 point: One correct individual score OR correct total number of sets
-- 0 points: Completely wrong prediction

-- ==========================================
-- ANALYSIS OF CURRENT ISSUES
-- ==========================================

-- Show current predictions with 0 points that might deserve 1 point
SELECT 'CURRENT 0-POINT PREDICTIONS ANALYSIS:' as analysis_header;

SELECT 
    p.id as prediction_id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game,
    p.team1_score || '-' || p.team2_score as prediction,
    g.team1_score || '-' || g.team2_score as actual_result,
    p.predicted_winner,
    g.team1 as actual_winner_team1,
    g.team2 as actual_winner_team2,
    (p.team1_score + p.team2_score) as predicted_total_sets,
    (g.team1_score + g.team2_score) as actual_total_sets,
    p.points as current_points,
    -- Check what they got right
    CASE WHEN p.team1_score = g.team1_score THEN 'Team1 score ✓' ELSE 'Team1 score ✗' END as team1_check,
    CASE WHEN p.team2_score = g.team2_score THEN 'Team2 score ✓' ELSE 'Team2 score ✗' END as team2_check,
    CASE WHEN (p.team1_score + p.team2_score) = (g.team1_score + g.team2_score) THEN 'Total sets ✓' ELSE 'Total sets ✗' END as total_sets_check,
    CASE 
        WHEN (p.team1_score > p.team2_score AND g.team1_score > g.team2_score) OR
             (p.team2_score > p.team1_score AND g.team2_score > g.team1_score) 
        THEN 'Winner ✓' 
        ELSE 'Winner ✗' 
    END as winner_check
FROM prediction p
JOIN "user" u ON p.user_id = u.id
JOIN game g ON p.game_id = g.id
WHERE g.is_finished = true 
  AND p.points = 0
  AND g.team1_score IS NOT NULL 
  AND g.team2_score IS NOT NULL
  AND p.team1_score IS NOT NULL 
  AND p.team2_score IS NOT NULL
ORDER BY p.id;

-- Show predictions that should get 1 point for correct total sets
SELECT 'PREDICTIONS THAT SHOULD GET 1 POINT FOR CORRECT TOTAL SETS:' as fix_candidates;

SELECT 
    p.id as prediction_id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game,
    p.team1_score || '-' || p.team2_score as prediction,
    g.team1_score || '-' || g.team2_score as actual_result,
    (p.team1_score + p.team2_score) as predicted_total_sets,
    (g.team1_score + g.team2_score) as actual_total_sets,
    p.points as current_points,
    'Should be 1 point' as should_be
FROM prediction p
JOIN "user" u ON p.user_id = u.id
JOIN game g ON p.game_id = g.id
WHERE g.is_finished = true 
  AND p.points = 0
  AND g.team1_score IS NOT NULL 
  AND g.team2_score IS NOT NULL
  AND p.team1_score IS NOT NULL 
  AND p.team2_score IS NOT NULL
  -- Correct total sets but wrong everything else
  AND (p.team1_score + p.team2_score) = (g.team1_score + g.team2_score)
  -- But wrong individual scores and wrong winner
  AND p.team1_score != g.team1_score
  AND p.team2_score != g.team2_score
  AND NOT (
    (p.team1_score > p.team2_score AND g.team1_score > g.team2_score) OR
    (p.team2_score > p.team1_score AND g.team2_score > g.team1_score)
  )
ORDER BY p.id;

-- ==========================================
-- CORRECTED POINTS CALCULATION FUNCTION
-- ==========================================

-- Create a function to calculate points correctly
CREATE OR REPLACE FUNCTION calculate_prediction_points(
    pred_team1_score INTEGER,
    pred_team2_score INTEGER,
    actual_team1_score INTEGER,
    actual_team2_score INTEGER
) RETURNS INTEGER AS $$
BEGIN
    -- Return NULL if any score is NULL
    IF pred_team1_score IS NULL OR pred_team2_score IS NULL OR 
       actual_team1_score IS NULL OR actual_team2_score IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- Perfect prediction (6 points)
    IF pred_team1_score = actual_team1_score AND pred_team2_score = actual_team2_score THEN
        RETURN 6;
    END IF;
    
    -- Correct winner and one correct individual score (4 points)
    IF ((pred_team1_score > pred_team2_score AND actual_team1_score > actual_team2_score) OR
        (pred_team2_score > pred_team1_score AND actual_team2_score > actual_team1_score)) AND
       (pred_team1_score = actual_team1_score OR pred_team2_score = actual_team2_score) THEN
        RETURN 4;
    END IF;
    
    -- Correct winner only (2 points)
    IF (pred_team1_score > pred_team2_score AND actual_team1_score > actual_team2_score) OR
       (pred_team2_score > pred_team1_score AND actual_team2_score > actual_team1_score) THEN
        RETURN 2;
    END IF;
    
    -- One correct individual score (1 point)
    IF pred_team1_score = actual_team1_score OR pred_team2_score = actual_team2_score THEN
        RETURN 1;
    END IF;
    
    -- Correct total number of sets (1 point) - NEW RULE
    IF (pred_team1_score + pred_team2_score) = (actual_team1_score + actual_team2_score) THEN
        RETURN 1;
    END IF;
    
    -- Wrong prediction (0 points)
    RETURN 0;
END;
$$ LANGUAGE plpgsql;

-- ==========================================
-- TEST THE NEW CALCULATION
-- ==========================================

-- Show what the new calculation would produce
SELECT 'NEW POINTS CALCULATION TEST:' as test_header;

SELECT 
    p.id as prediction_id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game,
    p.team1_score || '-' || p.team2_score as prediction,
    g.team1_score || '-' || g.team2_score as actual_result,
    p.points as current_points,
    calculate_prediction_points(p.team1_score, p.team2_score, g.team1_score, g.team2_score) as new_calculated_points,
    CASE 
        WHEN p.points != calculate_prediction_points(p.team1_score, p.team2_score, g.team1_score, g.team2_score)
        THEN 'WILL CHANGE: ' || p.points || ' → ' || calculate_prediction_points(p.team1_score, p.team2_score, g.team1_score, g.team2_score)
        ELSE 'No change'
    END as change_status
FROM prediction p
JOIN "user" u ON p.user_id = u.id
JOIN game g ON p.game_id = g.id
WHERE g.is_finished = true 
  AND g.team1_score IS NOT NULL 
  AND g.team2_score IS NOT NULL
  AND p.team1_score IS NOT NULL 
  AND p.team2_score IS NOT NULL
ORDER BY 
    CASE WHEN p.points != calculate_prediction_points(p.team1_score, p.team2_score, g.team1_score, g.team2_score) THEN 0 ELSE 1 END,
    p.id;

-- Show summary of changes
SELECT 'SUMMARY OF POINT CHANGES:' as summary_header;

SELECT 
    'Point Changes Summary' as metric,
    COUNT(*) as total_finished_predictions,
    COUNT(CASE WHEN p.points != calculate_prediction_points(p.team1_score, p.team2_score, g.team1_score, g.team2_score) THEN 1 END) as predictions_to_update,
    COUNT(CASE WHEN p.points = 0 AND calculate_prediction_points(p.team1_score, p.team2_score, g.team1_score, g.team2_score) = 1 THEN 1 END) as zero_to_one_point_changes,
    COUNT(CASE WHEN p.points < calculate_prediction_points(p.team1_score, p.team2_score, g.team1_score, g.team2_score) THEN 1 END) as point_increases,
    COUNT(CASE WHEN p.points > calculate_prediction_points(p.team1_score, p.team2_score, g.team1_score, g.team2_score) THEN 1 END) as point_decreases
FROM prediction p
JOIN game g ON p.game_id = g.id
WHERE g.is_finished = true 
  AND g.team1_score IS NOT NULL 
  AND g.team2_score IS NOT NULL
  AND p.team1_score IS NOT NULL 
  AND p.team2_score IS NOT NULL;

-- ==========================================
-- EXECUTE THE CORRECTION
-- ==========================================

-- Update all prediction points with corrected calculation
SELECT 'UPDATING PREDICTION POINTS...' as update_status;

UPDATE prediction 
SET points = calculate_prediction_points(
    prediction.team1_score, 
    prediction.team2_score, 
    game.team1_score, 
    game.team2_score
)
FROM game
WHERE prediction.game_id = game.id
  AND game.is_finished = true 
  AND game.team1_score IS NOT NULL 
  AND game.team2_score IS NOT NULL
  AND prediction.team1_score IS NOT NULL 
  AND prediction.team2_score IS NOT NULL;

-- Show how many were updated
SELECT 'POINTS UPDATE COMPLETED!' as completion_status;

-- Show final results
SELECT 'UPDATED PREDICTIONS SUMMARY:' as final_summary;

SELECT 
    COUNT(*) as total_finished_predictions,
    COUNT(CASE WHEN points = 6 THEN 1 END) as perfect_predictions_6pts,
    COUNT(CASE WHEN points = 4 THEN 1 END) as winner_plus_score_4pts,
    COUNT(CASE WHEN points = 2 THEN 1 END) as winner_only_2pts,
    COUNT(CASE WHEN points = 1 THEN 1 END) as partial_correct_1pt,
    COUNT(CASE WHEN points = 0 THEN 1 END) as wrong_predictions_0pts
FROM prediction p
JOIN game g ON p.game_id = g.id
WHERE g.is_finished = true AND p.points IS NOT NULL;

-- Show user totals after correction
SELECT 'USER TOTALS AFTER POINT CORRECTION:' as user_totals_header;

SELECT 
    u.name as user_name,
    COUNT(p.id) as total_predictions,
    COUNT(CASE WHEN p.points IS NOT NULL THEN 1 END) as scored_predictions,
    COALESCE(SUM(p.points), 0) as total_points,
    COALESCE(ROUND(AVG(p.points), 2), 0) as avg_points_per_prediction,
    COUNT(CASE WHEN p.points = 1 THEN 1 END) as one_point_predictions
FROM "user" u
LEFT JOIN prediction p ON u.id = p.user_id
GROUP BY u.id, u.name
HAVING COUNT(p.id) > 0
ORDER BY total_points DESC;

-- Clean up the function (optional - remove if you want to keep it)
-- DROP FUNCTION IF EXISTS calculate_prediction_points(INTEGER, INTEGER, INTEGER, INTEGER);

SELECT 'POINTS CORRECTION COMPLETED SUCCESSFULLY!' as final_status;
SELECT 'All predictions now correctly award 1 point for guessing the total number of sets.' as note;