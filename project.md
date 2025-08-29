# Volleyball Prediction Game - Project Summary

## Overview
A Flask-based web application for predicting volleyball match results and tournament outcomes, featuring user authentication, leaderboards, admin functionality, and comprehensive scoring systems.

## Tech Stack
- **Backend**: Python Flask with SQLAlchemy ORM
- **Database**: PostgreSQL with psycopg3 driver
- **Authentication**: Flask-Login
- **Frontend**: Bootstrap 5 with Jinja2 templates
- **Timezone**: pytz (Europe/Riga)
- **Deployment**: Render.com

## Core Features

### User Management
- User registration and authentication
- Admin users with special privileges
- Password change functionality
- User profiles with prediction statistics

### Match Predictions
- Volleyball score validation (3-0, 3-1, 3-2 format)
- Prediction deadlines (default: 30 minutes before match)
- Mobile-responsive prediction interface
- Real-time form validation
- AJAX submission for mobile devices

### Tournament Predictions
- Predict 1st, 2nd, and 3rd place finishers
- Validation to prevent duplicate team selections
- Results display with point breakdown

### Scoring Systems

#### Match Predictions (6/4/2/1/0 points)
- **6 points**: Perfect prediction (exact score)
- **4 points**: Correct winner, off by 1 set
- **2 points**: Correct winner only
- **1 point**: Correct total sets, wrong winner
- **0 points**: Completely wrong

#### Tournament Predictions (NEW SYSTEM)
- **30 points**: Correct tournament winner
- **15 points**: Predicting any team that becomes a medalist
- **+5 points**: Additional bonus for exact position (2nd or 3rd place)
- **Maximum possible**: 30 + 20 + 20 = 70 points

### Leaderboard & Statistics
- Total score ranking
- Accuracy percentage (based on finished games only, 2+ points considered "correct")
- All predictions count vs finished games count
- Best accuracy and highest score highlights
- Mobile-responsive cards and desktop table views

### Filtering & Navigation
- **Predictions Page**: Default filter shows today/tomorrow games
- Quick filters: Today & Tomorrow, Upcoming, Finished, All Games
- Advanced filters: Specific date, tournament round
- Expandable/collapsible date sections

### Admin Features
- Game management (create, edit, delete)
- Team management with country flag support
- Prediction override (input predictions for users after deadline)
- Tournament configuration and results management
- CSV game import functionality
- Database backup/restore tools

## Database Schema

### Key Models
- **User**: Authentication, statistics, admin flags
- **Game**: Match details, scores, deadlines, rounds
- **Prediction**: User predictions with calculated points
- **TournamentPrediction**: Tournament winner/medalist predictions
- **TournamentConfig**: Tournament settings and results
- **Team**: Team names with country codes for flags

### Important Relationships
- User -> Predictions (one-to-many)
- User -> TournamentPrediction (one-to-one)
- Game -> Predictions (one-to-many)

## Recent Major Updates

### 1. Tournament Scoring System Overhaul
- **Changed from**: 50/25/25 point system
- **Changed to**: 30/15/+5 point system
- Updated calculation logic in `calculate_tournament_points()`
- Updated all template displays and descriptions

### 2. Predictions Page Filtering
- Implemented default today/tomorrow filter
- Added comprehensive filtering system
- Replaced old date navigation with modern filter interface
- Fixed JavaScript functions and template syntax

### 3. Leaderboard Enhancements
- Added "All Predictions" vs "Finished Games" columns
- Changed accuracy calculation to count only 2+ points as "correct"
- Updated to show only finished games in accuracy percentage
- Mobile-responsive leaderboard cards

### 4. Points Calculation Fixes
- Added 1-point rule for correct total sets prediction
- Comprehensive recalculation scripts
- Volleyball score validation improvements

### 5. Admin Prediction Override
- Allows admins to input predictions for any user after deadlines
- Maintains audit trail and data integrity
- Integrated into admin panel interface

## File Structure

### Core Application Files
- `app.py` - Main Flask application with all routes and logic
- `requirements.txt` - Python dependencies

### Templates (`templates/`)
- `base.html` - Base template with navigation
- `index.html` - Home page with scoring system explanation
- `predictions.html` - Main prediction interface with filtering
- `tournament_predictions.html` - Tournament prediction interface
- `leaderboard.html` - Rankings and statistics display
- `admin.html` - Admin panel with all management tools
- `user_profile.html` - Individual user statistics
- `match_detail.html` - Detailed match view with all predictions

### Database Tools
- `backup_database.sql` - PostgreSQL backup script for pgAdmin
- `backup_database_no_files.sql` - Alternative backup without file permissions
- `import_predictions_by_ids.sql` - CSV import script with point calculation
- `fix_points_calculation.sql` - Point recalculation script
- `test_leaderboard_accuracy.sql` - Testing script for accuracy changes
- `test_new_leaderboard_columns.sql` - Testing script for new columns

## Key Functions

### Scoring Logic
- `calculate_points(prediction, game)` - Match prediction scoring
- `calculate_tournament_points(prediction, tournament_config)` - Tournament scoring

### User Statistics
- `get_total_predictions()` - Count finished game predictions
- `get_correct_predictions()` - Count 2+ point predictions
- `get_all_predictions_filled()` - Count all filled predictions
- `get_accuracy()` - Calculate accuracy percentage

### Validation
- Volleyball score validation (winner must have 3 sets, loser 0-2)
- Tournament prediction duplicate prevention
- Deadline enforcement

## Configuration

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Flask session encryption key

### Default Settings
- Timezone: Europe/Riga
- Prediction deadline: 30 minutes before game start
- Score validation: Volleyball format (3-0, 3-1, 3-2)

## Deployment Notes

### Database Migrations
- Created comprehensive backup/restore procedures
- Point calculation fix scripts available
- Import tools for bulk game/prediction data

### Common Issues Fixed
- `timedelta` import error in predictions route
- Jinja2 template syntax errors
- Permission issues with PostgreSQL COPY commands
- Mobile form validation and AJAX submission
- Cascade delete behavior affecting predictions

### Performance Optimizations
- Efficient database queries with proper joins
- Mobile-specific AJAX forms to avoid page reloads
- Responsive design with separate mobile/desktop layouts
- Batch database operations for imports

## Future Considerations

### Potential Enhancements
- Real-time updates with WebSocket
- Push notifications for deadline reminders
- Advanced analytics and trend tracking
- Social features (comments, prediction sharing)
- Integration with live match data APIs
- Multiple tournament support

### Maintenance Tasks
- Regular database backups
- Monitor prediction deadline accuracy
- Update team lists for new tournaments
- Performance monitoring and optimization

## Development Workflow

### Testing
- Use provided SQL test scripts for database changes
- Test mobile and desktop interfaces separately
- Validate scoring calculations with edge cases

### Database Changes
- Always create backup before schema changes
- Test point calculation changes thoroughly
- Use migration scripts for production updates

### Deployment
- Ensure environment variables are set
- Run database migrations if needed
- Test admin functionality after deployment
- Verify timezone handling in production

## Contact & Collaboration
This project supports collaborative volleyball prediction games with comprehensive admin tools, robust scoring systems, and user-friendly interfaces for both casual and competitive prediction gaming.