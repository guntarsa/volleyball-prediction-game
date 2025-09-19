# Volleyball Prediction Game - Complete Project Context

## Project Overview
A comprehensive Flask-based web application for predicting volleyball match results during the Men's World Championship 2025. Features user authentication, advanced scoring systems, leaderboards, tournament predictions, and AI-powered personalized user messages.

## 🏗️ Technical Architecture

### Core Technology Stack
- **Backend**: Python Flask 3.0.0 with SQLAlchemy ORM
- **Database**: PostgreSQL (production) / SQLite (development)
- **Authentication**: Flask-Login with password hashing
- **Frontend**: Bootstrap 5 + Jinja2 templates + jQuery
- **Timezone**: Europe/Riga (pytz)
- **AI Integration**: Google Gemini API for personalized messages
- **Deployment**: Render.com with gunicorn

### Key Dependencies
```
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
gunicorn==21.2.0
psycopg[binary]==3.2.3
pytz==2024.1
google-generativeai
```

### File Structure
```
volleyball-prediction-game/
├── app.py                          # Main Flask application (2500+ lines)
├── requirements.txt                # Python dependencies
├── render.yaml                     # Render.com deployment config
├── run.py                          # Local development server
├── templates/                      # Jinja2 HTML templates
│   ├── base.html                   # Base template with navigation
│   ├── index.html                  # Home page with scoring explanation
│   ├── predictions.html            # Main prediction interface
│   ├── tournament_predictions.html # Tournament winner predictions
│   ├── leaderboard.html           # Rankings and statistics
│   ├── admin.html                 # Administrative panel
│   ├── user_profile.html          # Individual user stats
│   ├── match_detail.html          # Detailed match view
│   └── all_predictions.html       # All predictions overview
├── *.sql                          # Database scripts (backup/migration)
├── *.py                           # Utility scripts (migration/fixes)
└── *.md                           # Documentation files
```

## 📊 Database Schema

### Core Models
1. **User** (`users` table)
   - Authentication: id, name, email, password_hash
   - Flags: is_admin, password_change_required
   - Statistics methods: get_total_score(), get_accuracy(), etc.

2. **Game** (`games` table)
   - Match details: team1, team2, date, time, round
   - Results: team1_score, team2_score, finished
   - Configuration: prediction_deadline (default: 30min before)

3. **Prediction** (`predictions` table)
   - User predictions: user_id, game_id, team1_score, team2_score
   - Calculated: points (0-6), created_at, updated_at
   - Constraint: unique(user_id, game_id)

4. **TournamentPrediction** (`tournament_predictions` table)
   - Tournament winners: first_place, second_place, third_place
   - Scoring: total_points calculated from results
   - Constraint: unique(user_id)

5. **TournamentConfig** (`tournament_config` table)
   - Settings: results_available, actual winners
   - Results: actual_first, actual_second, actual_third

6. **AIMessageGenerator Support Tables**
   - **PlayerMessage**: Cached AI messages with expiration
   - **DailyApiUsage**: API rate limiting tracking

### Relationships
- User → Predictions (1:many)
- User → TournamentPrediction (1:1)
- Game → Predictions (1:many)

## 🎯 Scoring Systems

### Match Predictions (6/4/2/1/0 points)
```python
def calculate_points(prediction, game):
    if exact_score_match: return 6     # Perfect prediction
    if correct_winner_off_by_1: return 4  # Close prediction
    if correct_winner: return 2           # Winner correct
    if correct_total_sets: return 1       # Total sets correct
    return 0                              # Completely wrong
```

### Tournament Predictions (30/15/+5 points)
```python
def calculate_tournament_points():
    points = 0
    if correct_first_place: points += 30
    if any_correct_medalist: points += 15 per medalist
    if exact_position_2nd_or_3rd: points += 5 per exact
    # Maximum possible: 30 + 15 + 15 + 5 + 5 = 70 points
```

### Volleyball Score Validation
- Winner must have exactly 3 sets
- Loser must have 0, 1, or 2 sets
- Valid formats: 3-0, 3-1, 3-2
- Invalid: 3-3, 4-2, 2-1, etc.

## 🔧 Key Features & Routes

### Public Routes
- `/` - Home page with game explanation
- `/register` - User registration
- `/login` - User authentication
- `/logout` - Session termination

### User Routes
- `/predictions` - Main prediction interface with filtering
- `/leaderboard` - Rankings and AI-powered user messages
- `/tournament-predictions` - Tournament winner predictions
- `/user/<id>` - Individual user profiles
- `/match/<id>` - Detailed match view with all predictions
- `/change-password` - Password change functionality

### Admin Routes
- `/admin` - Main administrative panel
- `/upload_games` - CSV game import
- `/upload_tournament_teams` - Team management
- `/update_result` - Match result entry
- `/admin/manage_prediction` - Prediction override (post-deadline)
- `/admin/recalculate_points` - Point recalculation tools
- `/admin/tournament-config` - Tournament settings
- `/admin/tournament-results` - Tournament result entry

### API Routes
- `/api/user_message` - Asynchronous AI message loading
- `/save_prediction_ajax` - Mobile-optimized prediction saving
- `/get_prediction/<game_id>` - Fetch existing predictions

## 🤖 AI Integration

### Google Gemini API Integration
```python
class AIMessageGenerator:
    def __init__(self):
        self.daily_limit = 100
        self.cache_duration_hours = 24

    def get_or_create_message(self, user_id):
        # Check cache first
        # Generate new message if needed
        # Use fallback templates if API fails
```

### AI Message Features
- **Personalized Content**: References specific games, scores, ranking changes
- **Context-Aware**: Uses detailed user performance analysis
- **Cached**: 24-hour cache to reduce API calls
- **Fallback System**: Template-based messages if AI unavailable
- **Rate Limited**: 100 API calls per day
- **Asynchronous Loading**: Prevents page hanging (recent fix)

### Performance Context Generation
```python
def get_detailed_context_for_ai(user_id):
    return {
        'user_performance': get_user_analysis(user_id),
        'recent_games': get_latest_game_results(user_id),
        'specific_details': [list of achievements/failures]
    }
```

## 🔍 Advanced Features

### Filtering System (Predictions Page)
- **Default Filter**: Shows today and tomorrow's games
- **Quick Filters**: Today & Tomorrow, Upcoming, Finished, All Games
- **Advanced Filters**: Specific date, tournament round
- **Dynamic UI**: Expandable/collapsible date sections

### Mobile Optimization
- **Responsive Design**: Bootstrap-based mobile-first approach
- **AJAX Forms**: Prevents page reloads on mobile devices
- **Touch-Friendly**: Large buttons and touch targets
- **Mobile-Specific**: Separate mobile and desktop layouts

### Admin Prediction Override
```python
@app.route('/admin/manage_prediction', methods=['POST'])
def admin_manage_prediction():
    # Allows admins to input predictions for users after deadlines
    # Maintains audit trail
    # Validates all input data
```

### Country Flag Integration
```python
TEAM_COUNTRY_MAPPING = {
    'Brazil': 'br', 'Italy': 'it', 'USA': 'us',
    # ... 32 countries for World Championship 2025
}
```

## 📈 Statistics & Analytics

### User Statistics Methods
```python
class User:
    def get_total_score(self):          # Total points across all predictions
    def get_accuracy_percentage(self):   # Based on 2+ point predictions only
    def get_total_predictions(self):     # Count of finished game predictions
    def get_correct_predictions(self):   # Count of 2+ point predictions
    def get_all_predictions_filled(self): # Count of all user predictions
```

### Leaderboard Features
- **Multi-Column Display**: Total score, accuracy, prediction counts
- **Responsive Tables**: Desktop table + mobile cards
- **Performance Highlights**: Crown icons, leader badges
- **Statistics Cards**: Highest score, best accuracy, total players

## 🛠️ Development & Maintenance

### Recent Major Fixes
1. **Async AI Loading**: Fixed leaderboard hanging when AI API is slow
2. **Tournament Scoring**: Overhauled from 50/25/25 to 30/15/+5 system
3. **Accuracy Calculation**: Changed to count only 2+ points as "correct"
4. **Mobile AJAX**: Improved mobile form submission experience
5. **Prediction Filtering**: Comprehensive filtering system implementation

### Database Management Scripts
- `backup_database.sql` - PostgreSQL backup procedures
- `fix_points_calculation.sql` - Point recalculation after rule changes
- `import_predictions_by_ids.sql` - Bulk prediction import with validation
- `test_leaderboard_accuracy.sql` - Testing scripts for accuracy changes

### Common Issues & Solutions
- **Timezone Handling**: All dates converted to Europe/Riga timezone
- **Score Validation**: Strict volleyball format enforcement
- **Cascade Deletes**: Careful relationship management to preserve data
- **Mobile Performance**: AJAX forms to prevent page reloads
- **API Rate Limiting**: Google Gemini API usage tracking

### Environment Configuration
```python
# Production (Render.com)
DATABASE_URL = postgresql://...
SECRET_KEY = random_secure_key
GEMINI_API_KEY = google_api_key

# Development
DATABASE_URL = sqlite:///local.db (fallback)
```

## 🚀 Deployment & Operations

### Render.com Configuration
```yaml
# render.yaml
services:
  - type: web
    name: volleyball-prediction-game
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: DATABASE_URL
        fromDatabase: postgresql
```

### Performance Considerations
- **Database Queries**: Optimized with proper joins and indexing
- **Caching**: AI messages cached for 24 hours
- **Async Loading**: Non-blocking AI message generation
- **Responsive Design**: Efficient mobile/desktop rendering

### Monitoring & Alerts
- **Error Logging**: Comprehensive error tracking for AI failures
- **API Usage**: Daily Gemini API call monitoring
- **Database Health**: Connection pooling and query optimization

## 🎮 User Experience

### Game Flow
1. **Registration**: Simple email-based registration
2. **Prediction Making**: Intuitive score input with validation
3. **Tournament Predictions**: Select 1st, 2nd, 3rd place finishers
4. **Leaderboard Viewing**: Real-time rankings with AI insights
5. **Profile Tracking**: Detailed personal statistics

### Admin Workflow
1. **Game Management**: CSV import or manual game creation
2. **Result Entry**: Update match results when games finish
3. **User Management**: Password resets, prediction overrides
4. **Tournament Setup**: Configure tournament and enter final results

## 📝 Code Quality & Standards

### Key Programming Patterns
- **Flask Application Factory**: Centralized app configuration
- **SQLAlchemy ORM**: Database abstraction and relationships
- **Template Inheritance**: DRY principle with base.html
- **Error Handling**: Comprehensive try/catch with logging
- **Input Validation**: Server-side and client-side validation

### Security Features
- **Password Hashing**: Werkzeug secure password handling
- **Session Management**: Flask-Login secure sessions
- **Input Sanitization**: Form validation and SQL injection prevention
- **Admin Access Control**: Role-based permissions

### Testing & Validation
- **SQL Test Scripts**: Database change validation
- **Score Calculation Tests**: Edge case validation
- **Mobile Testing**: Cross-device compatibility
- **Performance Testing**: Load testing for concurrent users

This context document serves as a comprehensive reference for understanding, maintaining, and extending the volleyball prediction game application. The codebase represents a mature, production-ready web application with advanced features, robust error handling, and user-friendly interfaces.