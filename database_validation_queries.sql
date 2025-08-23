-- PostgreSQL Database Validation Queries
-- Use these queries in pgAdmin to validate database integrity and check for issues

-- ==========================================
-- DATABASE HEALTH CHECK QUERIES
-- ==========================================

-- Overall database summary
SELECT '=== DATABASE SUMMARY ===' as section;
SELECT 
    'Table Counts' as metric,
    (SELECT COUNT(*) FROM "user") as users,
    (SELECT COUNT(*) FROM game) as games,
    (SELECT COUNT(*) FROM prediction) as predictions,
    (SELECT COUNT(*) FROM tournament_team) as tournament_teams,
    (SELECT COUNT(*) FROM tournament_config) as tournament_configs,
    (SELECT COUNT(*) FROM tournament_prediction) as tournament_predictions;

-- ==========================================
-- DATA INTEGRITY CHECKS
-- ==========================================

SELECT '=== DATA INTEGRITY CHECKS ===' as section;

-- Check for orphaned predictions (predictions without valid users or games)
SELECT 'Orphaned Predictions Check' as check_name;
SELECT 
    'Predictions with invalid user_id' as issue,
    COUNT(*) as count
FROM prediction p
LEFT JOIN "user" u ON p.user_id = u.id
WHERE u.id IS NULL;

SELECT 
    'Predictions with invalid game_id' as issue,
    COUNT(*) as count
FROM prediction p
LEFT JOIN game g ON p.game_id = g.id
WHERE g.id IS NULL;

-- Check for orphaned tournament predictions
SELECT 
    'Tournament predictions with invalid user_id' as issue,
    COUNT(*) as count
FROM tournament_prediction tp
LEFT JOIN "user" u ON tp.user_id = u.id
WHERE u.id IS NULL;

-- Check for duplicate predictions (should be 0 due to unique constraint)
SELECT 
    'Duplicate predictions (user_id, game_id)' as issue,
    COUNT(*) as count
FROM (
    SELECT user_id, game_id, COUNT(*) as duplicate_count
    FROM prediction 
    GROUP BY user_id, game_id 
    HAVING COUNT(*) > 1
) duplicates;

-- Check for invalid volleyball scores
SELECT 
    'Invalid volleyball scores' as issue,
    COUNT(*) as count
FROM prediction 
WHERE team1_score IS NOT NULL 
  AND team2_score IS NOT NULL
  AND NOT (
    (team1_score = 3 AND team2_score BETWEEN 0 AND 2) OR
    (team2_score = 3 AND team1_score BETWEEN 0 AND 2)
  );

-- ==========================================
-- BUSINESS LOGIC VALIDATION
-- ==========================================

SELECT '=== BUSINESS LOGIC VALIDATION ===' as section;

-- Check predictions with incorrect winner calculation
SELECT 'Predictions with incorrect winner' as check_name;
SELECT 
    p.id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game,
    p.team1_score || '-' || p.team2_score as prediction,
    p.predicted_winner,
    CASE 
        WHEN p.team1_score > p.team2_score THEN g.team1
        WHEN p.team2_score > p.team1_score THEN g.team2
        ELSE 'Tie (Invalid)'
    END as should_be_winner
FROM prediction p
JOIN "user" u ON p.user_id = u.id
JOIN game g ON p.game_id = g.id
WHERE p.team1_score IS NOT NULL 
  AND p.team2_score IS NOT NULL
  AND p.predicted_winner != (
    CASE 
        WHEN p.team1_score > p.team2_score THEN g.team1
        WHEN p.team2_score > p.team1_score THEN g.team2
        ELSE NULL
    END
  )
LIMIT 10;

-- Check for predictions made after deadline
SELECT 'Predictions made after deadline' as check_name;
SELECT 
    p.id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game,
    p.created_at as prediction_time,
    g.prediction_deadline,
    (p.created_at > g.prediction_deadline) as is_late
FROM prediction p
JOIN "user" u ON p.user_id = u.id
JOIN game g ON p.game_id = g.id
WHERE p.created_at > g.prediction_deadline
ORDER BY p.created_at DESC
LIMIT 10;

-- Check point calculations for finished games
SELECT 'Point calculation validation for finished games' as check_name;
SELECT 
    p.id,
    u.name as user_name,
    g.team1 || ' vs ' || g.team2 as game,
    g.team1_score || '-' || g.team2_score as actual_result,
    p.team1_score || '-' || p.team2_score as prediction,
    p.points as current_points,
    CASE
        -- Perfect prediction (6 points)
        WHEN p.team1_score = g.team1_score AND p.team2_score = g.team2_score THEN 6
        -- Correct winner and one correct score (4 points)  
        WHEN (p.team1_score > p.team2_score AND g.team1_score > g.team2_score AND 
              (p.team1_score = g.team1_score OR p.team2_score = g.team2_score)) OR
             (p.team2_score > p.team1_score AND g.team2_score > g.team1_score AND 
              (p.team1_score = g.team1_score OR p.team2_score = g.team2_score)) THEN 4
        -- Correct winner only (2 points)
        WHEN (p.team1_score > p.team2_score AND g.team1_score > g.team2_score) OR
             (p.team2_score > p.team1_score AND g.team2_score > g.team1_score) THEN 2
        -- One correct score but wrong winner (1 point)
        WHEN p.team1_score = g.team1_score OR p.team2_score = g.team2_score THEN 1
        -- Wrong prediction (0 points)
        ELSE 0
    END as calculated_points,
    (p.points != CASE
        WHEN p.team1_score = g.team1_score AND p.team2_score = g.team2_score THEN 6
        WHEN (p.team1_score > p.team2_score AND g.team1_score > g.team2_score AND 
              (p.team1_score = g.team1_score OR p.team2_score = g.team2_score)) OR
             (p.team2_score > p.team1_score AND g.team2_score > g.team1_score AND 
              (p.team1_score = g.team1_score OR p.team2_score = g.team2_score)) THEN 4
        WHEN (p.team1_score > p.team2_score AND g.team1_score > g.team2_score) OR
             (p.team2_score > p.team1_score AND g.team2_score > g.team1_score) THEN 2
        WHEN p.team1_score = g.team1_score OR p.team2_score = g.team2_score THEN 1
        ELSE 0
    END) as points_mismatch
FROM prediction p
JOIN "user" u ON p.user_id = u.id
JOIN game g ON p.game_id = g.id
WHERE g.is_finished = true
  AND p.team1_score IS NOT NULL 
  AND p.team2_score IS NOT NULL
  AND g.team1_score IS NOT NULL
  AND g.team2_score IS NOT NULL
ORDER BY points_mismatch DESC, p.id
LIMIT 10;

-- ==========================================
-- PERFORMANCE AND STATISTICS
-- ==========================================

SELECT '=== STATISTICS ===' as section;

-- User participation statistics
SELECT 'User Participation' as metric;
SELECT 
    u.name as user_name,
    u.is_admin,
    COUNT(p.id) as total_predictions,
    COUNT(CASE WHEN p.points IS NOT NULL THEN 1 END) as scored_predictions,
    COALESCE(SUM(p.points), 0) as total_points,
    COALESCE(ROUND(AVG(p.points), 2), 0) as avg_points_per_prediction
FROM "user" u
LEFT JOIN prediction p ON u.id = p.user_id
GROUP BY u.id, u.name, u.is_admin
ORDER BY total_points DESC;

-- Game statistics
SELECT 'Game Statistics' as metric;
SELECT 
    CASE 
        WHEN is_finished THEN 'Finished'
        WHEN NOW() > prediction_deadline THEN 'Deadline Passed'
        ELSE 'Open for Predictions'
    END as game_status,
    COUNT(*) as game_count,
    COUNT(DISTINCT p.user_id) as unique_predictors,
    COUNT(p.id) as total_predictions
FROM game g
LEFT JOIN prediction p ON g.id = p.game_id
GROUP BY 
    CASE 
        WHEN is_finished THEN 'Finished'
        WHEN NOW() > prediction_deadline THEN 'Deadline Passed'
        ELSE 'Open for Predictions'
    END
ORDER BY game_count DESC;

-- Prediction accuracy by user
SELECT 'Top Performers (by accuracy)' as metric;
SELECT 
    u.name as user_name,
    COUNT(p.id) as total_predictions,
    COUNT(CASE WHEN p.points > 0 THEN 1 END) as successful_predictions,
    ROUND(
        COUNT(CASE WHEN p.points > 0 THEN 1 END) * 100.0 / NULLIF(COUNT(p.id), 0), 
        1
    ) as accuracy_percentage,
    SUM(p.points) as total_points
FROM "user" u
JOIN prediction p ON u.id = p.user_id
JOIN game g ON p.game_id = g.id
WHERE g.is_finished = true AND p.points IS NOT NULL
GROUP BY u.id, u.name
HAVING COUNT(p.id) >= 3  -- Only users with at least 3 predictions
ORDER BY accuracy_percentage DESC, total_points DESC
LIMIT 10;

-- ==========================================
-- MAINTENANCE QUERIES
-- ==========================================

SELECT '=== MAINTENANCE SUGGESTIONS ===' as section;

-- Games without any predictions
SELECT 'Games without predictions' as maintenance_item;
SELECT 
    g.id,
    g.team1 || ' vs ' || g.team2 as game,
    g.game_date,
    g.prediction_deadline,
    g.is_finished
FROM game g
LEFT JOIN prediction p ON g.id = p.game_id
WHERE p.id IS NULL
ORDER BY g.game_date;

-- Users without any predictions
SELECT 'Users without predictions' as maintenance_item;
SELECT 
    u.id,
    u.name,
    u.email,
    u.created_at,
    u.is_admin
FROM "user" u
LEFT JOIN prediction p ON u.id = p.user_id
WHERE p.id IS NULL
ORDER BY u.created_at;

-- Check database constraints
SELECT 'Database Constraints Status' as maintenance_item;
SELECT 
    conname as constraint_name,
    contype as constraint_type,
    pg_get_constraintdef(oid) as definition
FROM pg_constraint 
WHERE conrelid IN (
    SELECT oid FROM pg_class WHERE relname IN ('user', 'game', 'prediction', 'tournament_prediction', 'tournament_team', 'tournament_config')
)
ORDER BY conname;

SELECT '=== VALIDATION COMPLETE ===' as section;
SELECT 'Review the results above to identify any data integrity issues.' as recommendation;