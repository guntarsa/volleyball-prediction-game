-- Test Script for New Leaderboard Columns
-- This script shows what the new leaderboard columns will display
-- Run this in pgAdmin to preview the changes

-- ==========================================
-- TEST NEW LEADERBOARD COLUMNS
-- ==========================================

SELECT '=== NEW LEADERBOARD PREVIEW ===' as test_header;

-- Simulate the leaderboard with new columns
SELECT 
    u.name as player_name,
    -- Total Score (unchanged)
    COALESCE(SUM(p.points), 0) as total_score,
    
    -- NEW COLUMN: All Predictions (all filled out, regardless of deadline)
    COUNT(CASE 
        WHEN p.team1_score IS NOT NULL 
         AND p.team2_score IS NOT NULL
        THEN 1 
    END) as all_predictions_filled,
    
    -- Finished Games (only finished games)
    COUNT(CASE 
        WHEN p.team1_score IS NOT NULL 
         AND g.is_finished = true 
         AND p.points IS NOT NULL 
        THEN 1 
    END) as finished_games,
    
    -- Correct predictions (2+ points from finished games)
    COUNT(CASE 
        WHEN p.points >= 2 
         AND g.is_finished = true 
        THEN 1 
    END) as correct_predictions,
    
    -- Accuracy (based on finished games only)
    CASE 
        WHEN COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished = true AND p.points IS NOT NULL THEN 1 END) > 0 THEN
            ROUND(
                COUNT(CASE WHEN p.points >= 2 AND g.is_finished = true THEN 1 END) * 100.0 / 
                COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished = true AND p.points IS NOT NULL THEN 1 END), 
                1
            )
        ELSE 0
    END as accuracy_percentage

FROM "user" u
LEFT JOIN prediction p ON u.id = p.user_id
LEFT JOIN game g ON p.game_id = g.id
GROUP BY u.id, u.name
ORDER BY total_score DESC, accuracy_percentage DESC;

-- Show what the differences mean
SELECT '' as separator;
SELECT '=== COLUMN EXPLANATIONS ===' as explanations_header;

SELECT 
    'All Predictions' as column_name,
    'All predictions filled out by user (regardless of deadline status)' as description,
    'Shows total user participation and engagement' as purpose;

SELECT 
    'Finished Games' as column_name,
    'Predictions for games with actual results and calculated points' as description,
    'Shows predictions that can be evaluated for accuracy' as purpose;

SELECT 
    'Correct' as column_name,
    'Predictions earning 2+ points (truly successful predictions)' as description,
    'Excludes partial correct (1 point) as "incorrect"' as purpose;

SELECT 
    'Accuracy' as column_name,
    'Percentage based only on finished games with 2+ point threshold' as description,
    'More meaningful accuracy metric' as purpose;

-- Show detailed breakdown for users to understand the difference
SELECT '' as separator;
SELECT '=== DETAILED BREAKDOWN EXAMPLE ===' as breakdown_header;

SELECT 
    u.name as user_name,
    p.id as prediction_id,
    g.team1 || ' vs ' || g.team2 as game,
    p.team1_score || '-' || p.team2_score as prediction,
    g.is_finished,
    CASE WHEN g.is_finished THEN g.team1_score || '-' || g.team2_score ELSE 'Not finished' END as actual_result,
    COALESCE(p.points, 0) as points,
    -- Show how each prediction is categorized
    CASE 
        WHEN p.team1_score IS NOT NULL AND p.team2_score IS NOT NULL
        THEN '✓ Counts in "All Predictions"'
        ELSE '✗ Does not count (prediction not filled out)'
    END as all_predictions_status,
    CASE 
        WHEN p.team1_score IS NOT NULL AND g.is_finished = true AND p.points IS NOT NULL 
        THEN '✓ Counts in "Finished Games"'
        ELSE '✗ Does not count (not finished or no points)'
    END as finished_games_status,
    CASE 
        WHEN p.points >= 2 AND g.is_finished = true 
        THEN '✓ Counts as "Correct"'
        WHEN p.points = 1 AND g.is_finished = true
        THEN '✗ Partial correct (not counted as correct)'
        WHEN p.points = 0 AND g.is_finished = true
        THEN '✗ Wrong prediction'
        ELSE '✗ Not evaluated yet'
    END as correct_status
FROM "user" u
LEFT JOIN prediction p ON u.id = p.user_id
LEFT JOIN game g ON p.game_id = g.id
WHERE p.id IS NOT NULL
ORDER BY u.name, p.id
LIMIT 15;

SELECT '' as separator;
SELECT 'The new leaderboard will show a clearer picture of user participation and true accuracy!' as summary;