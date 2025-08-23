-- Test Script for New Leaderboard Accuracy Calculation
-- This script shows the difference between old and new accuracy calculations
-- Run this in pgAdmin to verify the changes

-- ==========================================
-- TEST LEADERBOARD ACCURACY CHANGES
-- ==========================================

SELECT '=== COMPARISON: OLD vs NEW ACCURACY CALCULATION ===' as test_header;

-- Show predictions breakdown for each user
SELECT 'DETAILED PREDICTION BREAKDOWN BY USER:' as section_header;

SELECT 
    u.name as user_name,
    COUNT(p.id) as all_predictions,
    COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished THEN 1 END) as finished_game_predictions,
    COUNT(CASE WHEN p.points = 6 THEN 1 END) as perfect_6pts,
    COUNT(CASE WHEN p.points = 4 THEN 1 END) as winner_plus_score_4pts,
    COUNT(CASE WHEN p.points = 2 THEN 1 END) as winner_only_2pts,
    COUNT(CASE WHEN p.points = 1 THEN 1 END) as partial_1pt,
    COUNT(CASE WHEN p.points = 0 THEN 1 END) as wrong_0pts,
    -- OLD METHOD: Count 1+ points as correct
    COUNT(CASE WHEN p.points > 0 AND g.is_finished THEN 1 END) as old_correct_count,
    -- NEW METHOD: Count 2+ points as correct (finished games only)
    COUNT(CASE WHEN p.points >= 2 AND g.is_finished THEN 1 END) as new_correct_count,
    -- OLD ACCURACY: Based on all predictions with 1+ points
    CASE 
        WHEN COUNT(CASE WHEN p.team1_score IS NOT NULL THEN 1 END) > 0 THEN
            ROUND(COUNT(CASE WHEN p.points > 0 THEN 1 END) * 100.0 / COUNT(CASE WHEN p.team1_score IS NOT NULL THEN 1 END), 1)
        ELSE 0
    END as old_accuracy_all_predictions,
    -- NEW ACCURACY: Based on finished games with 2+ points
    CASE 
        WHEN COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished THEN 1 END) > 0 THEN
            ROUND(COUNT(CASE WHEN p.points >= 2 AND g.is_finished THEN 1 END) * 100.0 / COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished THEN 1 END), 1)
        ELSE 0
    END as new_accuracy_finished_only
FROM "user" u
LEFT JOIN prediction p ON u.id = p.user_id
LEFT JOIN game g ON p.game_id = g.id
GROUP BY u.id, u.name
HAVING COUNT(p.id) > 0
ORDER BY new_accuracy_finished_only DESC, u.name;

-- Show what the difference means
SELECT '' as separator;
SELECT '=== EXPLANATION OF CHANGES ===' as explanation_header;

SELECT 'OLD SYSTEM:' as system_type,
       '- Counts predictions with 1+ points as "correct"' as rule1,
       '- Includes unfinished games in total count' as rule2,
       '- 1-point predictions (partial correct) counted as success' as rule3;

SELECT 'NEW SYSTEM:' as system_type,
       '- Only counts predictions with 2+ points as "correct"' as rule1,
       '- Only includes finished games in calculations' as rule2,
       '- 1-point predictions (partial) NOT counted as success' as rule3;

-- Show impact on specific users
SELECT '' as separator;
SELECT 'USERS MOST AFFECTED BY THE CHANGE:' as impact_header;

SELECT 
    u.name as user_name,
    COUNT(CASE WHEN p.points = 1 AND g.is_finished THEN 1 END) as one_point_predictions,
    COUNT(CASE WHEN p.team1_score IS NOT NULL AND NOT g.is_finished THEN 1 END) as unfinished_predictions,
    -- OLD vs NEW accuracy
    CASE 
        WHEN COUNT(CASE WHEN p.team1_score IS NOT NULL THEN 1 END) > 0 THEN
            ROUND(COUNT(CASE WHEN p.points > 0 THEN 1 END) * 100.0 / COUNT(CASE WHEN p.team1_score IS NOT NULL THEN 1 END), 1)
        ELSE 0
    END as old_accuracy,
    CASE 
        WHEN COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished THEN 1 END) > 0 THEN
            ROUND(COUNT(CASE WHEN p.points >= 2 AND g.is_finished THEN 1 END) * 100.0 / COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished THEN 1 END), 1)
        ELSE 0
    END as new_accuracy,
    -- Difference
    CASE 
        WHEN COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished THEN 1 END) > 0 THEN
            ROUND(COUNT(CASE WHEN p.points >= 2 AND g.is_finished THEN 1 END) * 100.0 / COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished THEN 1 END), 1) -
            ROUND(COUNT(CASE WHEN p.points > 0 THEN 1 END) * 100.0 / COUNT(CASE WHEN p.team1_score IS NOT NULL THEN 1 END), 1)
        ELSE 0
    END as accuracy_change
FROM "user" u
LEFT JOIN prediction p ON u.id = p.user_id
LEFT JOIN game g ON p.game_id = g.id
GROUP BY u.id, u.name
HAVING COUNT(p.id) > 0
ORDER BY ABS(CASE 
    WHEN COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished THEN 1 END) > 0 THEN
        ROUND(COUNT(CASE WHEN p.points >= 2 AND g.is_finished THEN 1 END) * 100.0 / COUNT(CASE WHEN p.team1_score IS NOT NULL AND g.is_finished THEN 1 END), 1) -
        ROUND(COUNT(CASE WHEN p.points > 0 THEN 1 END) * 100.0 / COUNT(CASE WHEN p.team1_score IS NOT NULL THEN 1 END), 1)
    ELSE 0
END) DESC;

-- Show what constitutes "correct" predictions now
SELECT '' as separator;
SELECT 'WHAT COUNTS AS "CORRECT" NOW:' as correct_definition_header;

SELECT 
    p.id as prediction_id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game,
    p.team1_score || '-' || p.team2_score as prediction,
    g.team1_score || '-' || g.team2_score as actual_result,
    p.points,
    CASE 
        WHEN p.points >= 2 THEN 'CORRECT (2+ points)'
        WHEN p.points = 1 THEN 'INCORRECT (only 1 point - partial)'
        WHEN p.points = 0 THEN 'INCORRECT (0 points - wrong)'
        ELSE 'NOT SCORED (game not finished)'
    END as new_classification,
    CASE 
        WHEN p.points > 0 THEN 'Was CORRECT in old system'
        ELSE 'Was INCORRECT in old system'
    END as old_classification
FROM prediction p
JOIN "user" u ON p.user_id = u.id
JOIN game g ON p.game_id = g.id
WHERE g.is_finished = true
  AND p.team1_score IS NOT NULL
  AND p.points IS NOT NULL
ORDER BY u.name, p.points DESC
LIMIT 20;

SELECT '' as separator;
SELECT 'SUMMARY: The new accuracy calculation is more strict and only counts truly successful predictions (2+ points) from finished games.' as summary;