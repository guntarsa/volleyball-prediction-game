# Volleyball World Championship Prediction Game

A Flask web application for friends to predict outcomes of the Women's Volleyball World Championship matches and compete on a leaderboard.

## Features

- **Advanced Scoring System**: 6/4/2/1 points based on prediction accuracy
- **CSV Import**: Import games from CSV files
- **Player Management**: Add players and track their performance
- **SQLite Database**: Persistent data storage
- **Admin Interface**: Manage games and update results
- **Responsive Design**: Bootstrap-based UI for all devices
- **Render.com Ready**: Configured for easy cloud deployment

## Scoring System

- **6 points**: Perfect prediction (exact score)
- **4 points**: Correct winner, missed result by 1 set
- **2 points**: Correct winner only
- **1 point**: Wrong winner but correct total sets
- **0 points**: Completely wrong

## Local Development

### Prerequisites
- Python 3.8+
- pip

### Setup
1. Clone/download the project
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python run.py
   ```
5. Open http://localhost:5000 in your browser

## Deployment to Render.com

1. Fork/upload this project to GitHub
2. Connect your GitHub account to Render.com
3. Create new web service from your repository
4. Render will automatically detect the `render.yaml` configuration
5. The app will be deployed with PostgreSQL database

### Environment Variables
The app automatically configures itself for Render.com deployment. For local development, copy `.env.example` to `.env` and modify as needed.

## File Structure

```
volleyball-prediction-game/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── render.yaml            # Render.com deployment config
├── run.py                 # Local development server
├── sample_games.csv       # Example CSV format
├── templates/             # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── predictions.html
│   ├── leaderboard.html
│   └── admin.html
├── uploads/               # CSV upload directory
└── README.md
```

## CSV Import Format

Create a CSV file with the following columns:

```csv
team1,team2,date,time,round
Brazil,Italy,2024-09-15,14:00,Quarter Final 1
USA,Poland,2024-09-15,17:00,Quarter Final 2
```

- **date**: YYYY-MM-DD format
- **time**: HH:MM format (24-hour)
- **round**: Tournament round name

## Usage

1. **Add Players**: Go to Leaderboard → Add your name
2. **Import Games**: Admin → Upload CSV with tournament schedule
3. **Make Predictions**: Predictions → Select user and predict scores
4. **Update Results**: Admin → Update game results when matches finish
5. **View Standings**: Leaderboard shows rankings and statistics

## Database Models

- **User**: Player information and statistics
- **Game**: Match details and results
- **Prediction**: User predictions with calculated points

## Admin Functions

- Import games from CSV
- Update match results
- View all games and their status
- Automatic point calculation when results are updated

## Technology Stack

- **Backend**: Python Flask, SQLAlchemy
- **Database**: SQLite (local), PostgreSQL (Render.com)
- **Frontend**: Bootstrap 5, JavaScript
- **Deployment**: Render.com with gunicorn

Have fun predicting the matches with your friends! 🏐