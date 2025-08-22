import os
import csv
from datetime import datetime, timezone
import pytz
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

# Riga timezone
RIGA_TZ = pytz.timezone('Europe/Riga')

def get_riga_time():
    """Get current time in Riga timezone"""
    return datetime.now(RIGA_TZ)

def to_riga_time(dt):
    """Convert datetime to Riga timezone"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive datetimes are in Riga timezone
        return RIGA_TZ.localize(dt)
    return dt.astimezone(RIGA_TZ)

app = Flask(__name__)

# Team name to country code mapping for flags
TEAM_COUNTRY_MAPPING = {
    'USA': 'us',
    'Brazil': 'br',
    'Poland': 'pl', 
    'Italy': 'it',
    'Serbia': 'rs',
    'Turkey': 'tr',
    'Japan': 'jp',
    'China': 'cn',
    'Netherlands': 'nl',
    'Dominican Republic': 'do',
    'France': 'fr',
    'Germany': 'de',
    'Thailand': 'th',
    'Belgium': 'be',
    'Canada': 'ca',
    'Bulgaria': 'bg',
    'Argentina': 'ar',
    'Slovenia': 'si',
    'Slovakia': 'sk',
    'Czech Republic': 'cz',
    'Puerto Rico': 'pr',
    'Ukraine': 'ua',
    'Egypt': 'eg',
    'Cameroon': 'cm',
    'Mexico': 'mx',
    'Kenya': 'ke',
    'Spain': 'es',
    'Kazakhstan': 'kz',
    'Vietnam': 'vn'
}

def get_country_code(team_name):
    """Get country code for team name, return None if not found"""
    return TEAM_COUNTRY_MAPPING.get(team_name)

def format_team_with_flag(team_name, flag_class='team-flag'):
    """Format team name with flag HTML if country code exists"""
    country_code = get_country_code(team_name)
    if country_code:
        return f'<span class="team-with-flag"><span class="fi fi-{country_code} {flag_class}"></span>{team_name}</span>'
    return team_name

# Template filters for Riga timezone
@app.template_filter('riga_datetime')
def riga_datetime_filter(dt, format='%Y-%m-%d %H:%M'):
    """Convert datetime to Riga timezone and format it"""
    if dt is None:
        return ''
    riga_dt = to_riga_time(dt)
    return riga_dt.strftime(format)

@app.template_filter('riga_date')
def riga_date_filter(dt):
    """Convert datetime to Riga timezone date"""
    if dt is None:
        return ''
    riga_dt = to_riga_time(dt)
    return riga_dt.strftime('%Y-%m-%d')

@app.template_filter('riga_time')
def riga_time_filter(dt):
    """Convert datetime to Riga timezone time"""
    if dt is None:
        return ''
    riga_dt = to_riga_time(dt)
    return riga_dt.strftime('%H:%M')

# Register template functions
app.jinja_env.globals['get_country_code'] = get_country_code
app.jinja_env.globals['format_team_with_flag'] = format_team_with_flag
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'winamount-could-be-huge-default-key-change-in-production')
# Handle PostgreSQL URL format for Render.com
database_url = os.environ.get('DATABASE_URL', 'sqlite:///volleyball_predictions.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# Use psycopg3 for PostgreSQL connections
if database_url.startswith('postgresql://'):
    # Replace postgresql:// with postgresql+psycopg:// for psycopg3
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['WTF_CSRF_ENABLED'] = True

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=True)  # Set to True for simplicity
    password_reset_required = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    predictions = db.relationship('Prediction', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_total_score(self):
        match_points = sum([p.points for p in self.predictions if p.points is not None])
        tournament_points = self.tournament_prediction.points_earned if self.tournament_prediction else 0
        return match_points + tournament_points
    
    def get_total_predictions(self):
        return len([p for p in self.predictions if p.team1_score is not None])
    
    def get_correct_predictions(self):
        return len([p for p in self.predictions if p.points and p.points > 0])

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team1 = db.Column(db.String(100), nullable=False)
    team2 = db.Column(db.String(100), nullable=False)
    game_date = db.Column(db.DateTime, nullable=False)
    prediction_deadline = db.Column(db.DateTime, nullable=False)
    round_name = db.Column(db.String(100), nullable=False)
    team1_score = db.Column(db.Integer, nullable=True)
    team2_score = db.Column(db.Integer, nullable=True)
    is_finished = db.Column(db.Boolean, default=False)
    predictions = db.relationship('Prediction', backref='game', lazy=True, cascade='all, delete-orphan')
    
    def is_prediction_open(self):
        current_time = get_riga_time()
        deadline = to_riga_time(self.prediction_deadline)
        return current_time < deadline
    
    def are_predictions_visible(self):
        current_time = get_riga_time()
        deadline = to_riga_time(self.prediction_deadline)
        return current_time >= deadline
    
    def get_winner(self):
        if self.team1_score is not None and self.team2_score is not None:
            return self.team1 if self.team1_score > self.team2_score else self.team2
        return None

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    team1_score = db.Column(db.Integer, nullable=True)
    team2_score = db.Column(db.Integer, nullable=True)
    predicted_winner = db.Column(db.String(100), nullable=True)
    points = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'game_id'),)

class TournamentPrediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    first_place = db.Column(db.String(100), nullable=True)  # Winner prediction
    second_place = db.Column(db.String(100), nullable=True)  # Runner-up prediction  
    third_place = db.Column(db.String(100), nullable=True)  # Bronze medal prediction
    points_earned = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('tournament_prediction', uselist=False))
    
    __table_args__ = (db.UniqueConstraint('user_id'),)

class TournamentTeam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    country_code = db.Column(db.String(2), nullable=True)  # ISO country code for flag
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_country_code(self):
        """Get country code, fallback to mapping if not set"""
        return self.country_code or get_country_code(self.name)

class TournamentConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prediction_deadline = db.Column(db.DateTime, nullable=False)
    first_place_result = db.Column(db.String(100), nullable=True)
    second_place_result = db.Column(db.String(100), nullable=True)  
    third_place_result = db.Column(db.String(100), nullable=True)
    is_finalized = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_prediction_open(self):
        current_time = get_riga_time()
        deadline = to_riga_time(self.prediction_deadline)
        return current_time < deadline
    
    def are_results_available(self):
        return self.is_finalized and all([self.first_place_result, self.second_place_result, self.third_place_result])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def check_password_reset():
    # Skip password reset check for certain routes
    exempt_routes = ['login', 'logout', 'register', 'change_password', 'static']
    
    if (current_user.is_authenticated and 
        current_user.password_reset_required and 
        request.endpoint not in exempt_routes):
        return redirect(url_for('change_password'))

def calculate_points(prediction, game):
    """Calculate points based on the scoring system"""
    if not game.is_finished or prediction.team1_score is None or prediction.team2_score is None:
        return None
    
    predicted_winner = prediction.team1_score > prediction.team2_score
    actual_winner = game.team1_score > game.team2_score
    
    # Check if winner prediction is correct
    winner_correct = predicted_winner == actual_winner
    
    # Check if exact score is correct
    exact_score = (prediction.team1_score == game.team1_score and 
                  prediction.team2_score == game.team2_score)
    
    # Check if total sets are correct
    total_sets_correct = (prediction.team1_score + prediction.team2_score == 
                         game.team1_score + game.team2_score)
    
    # Check if missed result by 1 set
    score_diff = abs((prediction.team1_score - prediction.team2_score) - 
                    (game.team1_score - game.team2_score))
    missed_by_one = score_diff == 1
    
    # Scoring logic
    if exact_score:
        return 6  # Perfect prediction
    elif winner_correct and missed_by_one:
        return 4  # Correct winner, missed by 1 set
    elif winner_correct:
        return 2  # Just correct winner
    elif total_sets_correct:
        return 1  # Wrong winner but correct total sets
    else:
        return 0  # Completely wrong

def calculate_tournament_points(prediction, tournament_config):
    """Calculate points for tournament predictions"""
    if not tournament_config.are_results_available():
        return 0
    
    points = 0
    
    # Check first place (winner) - 50 points
    if prediction.first_place == tournament_config.first_place_result:
        points += 50
    
    # Get user's predictions as a list
    user_predictions = [prediction.first_place, prediction.second_place, prediction.third_place]
    
    # Check if user mentioned actual 2nd place anywhere in their predictions - 25 points
    if tournament_config.second_place_result in user_predictions:
        points += 25
    
    # Check if user mentioned actual 3rd place anywhere in their predictions - 25 points  
    if tournament_config.third_place_result in user_predictions:
        points += 25
    
    return points

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not all([name, email, password, confirm_password]):
            flash('All fields are required.', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(name=name).first():
            flash('Username already taken.', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(name=name, email=email)
        user.set_password(password)
        
        # Make first user admin
        if User.query.count() == 0:
            user.is_admin = True
            flash('Welcome! You are now the admin of this prediction game.', 'success')
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash(f'Welcome {name}! You are now registered and logged in.', 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.name}!', 'success')
            
            # Redirect to next page or index
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/predictions')
@login_required
def predictions():
    # Get all games (both upcoming and finished) sorted by game time, earliest first
    games = Game.query.order_by(Game.game_date.asc()).all()
    return render_template('predictions.html', games=games)

@app.route('/leaderboard')
@login_required
def leaderboard():
    users = User.query.all()
    user_stats = []
    for user in users:
        stats = {
            'id': user.id,
            'name': user.name,
            'total_score': user.get_total_score(),
            'total_predictions': user.get_total_predictions(),
            'correct_predictions': user.get_correct_predictions(),
            'accuracy': round((user.get_correct_predictions() / max(user.get_total_predictions(), 1)) * 100, 1)
        }
        user_stats.append(stats)
    
    user_stats.sort(key=lambda x: x['total_score'], reverse=True)
    return render_template('leaderboard.html', users=user_stats)

# Removed add_user route - users now register themselves

@app.route('/make_prediction', methods=['POST'])
@login_required
def make_prediction():
    game_id = request.form.get('game_id')
    team1_score = request.form.get('team1_score')
    team2_score = request.form.get('team2_score')
    
    if not all([game_id, team1_score, team2_score]):
        flash('Please fill in all fields', 'error')
        return redirect(url_for('predictions', anchor=f'game_{game_id}'))
    
    try:
        # Convert all form data to appropriate types
        game_id = int(game_id)
        team1_score = int(team1_score)
        team2_score = int(team2_score)
        
        if team1_score < 0 or team2_score < 0:
            raise ValueError("Scores cannot be negative")
        
        # Volleyball scoring validation: one team must win 3 sets, other 0-2
        if not ((team1_score == 3 and team2_score in [0, 1, 2]) or 
                (team2_score == 3 and team1_score in [0, 1, 2])):
            raise ValueError("Invalid volleyball score")
            
    except ValueError as e:
        if "Invalid volleyball score" in str(e):
            flash('Invalid volleyball score. Winner must have 3 sets, loser 0-2 sets.', 'error')
        else:
            flash('Please enter valid values', 'error')
        return redirect(url_for('predictions', anchor=f'game_{game_id}'))
    
    game = Game.query.get(game_id)
    if not game:
        flash('Game not found', 'error')
        return redirect(url_for('predictions'))
    
    # Check prediction deadline - using Riga timezone
    current_time = get_riga_time()
    deadline = to_riga_time(game.prediction_deadline)
    
    if current_time >= deadline:
        flash('Prediction deadline has passed for this game', 'error')
        return redirect(url_for('predictions', anchor=f'game_{game_id}'))
    
    # Check if prediction already exists
    existing = Prediction.query.filter_by(user_id=current_user.id, game_id=game_id).first()
    if existing:
        existing.team1_score = team1_score
        existing.team2_score = team2_score
        existing.predicted_winner = game.team1 if team1_score > team2_score else game.team2
    else:
        predicted_winner = game.team1 if team1_score > team2_score else game.team2
        prediction = Prediction(
            user_id=current_user.id,
            game_id=game_id,
            team1_score=team1_score,
            team2_score=team2_score,
            predicted_winner=predicted_winner
        )
        db.session.add(prediction)
    
    db.session.commit()
    flash('Prediction saved!', 'success')
    return redirect(url_for('predictions', anchor=f'game_{game_id}'))

@app.route('/admin')
@login_required
@admin_required
def admin():
    games = Game.query.order_by(Game.game_date).all()
    users = User.query.order_by(User.created_at).all()
    tournament_config = TournamentConfig.query.first()
    tournament_predictions = TournamentPrediction.query.join(User).all()
    tournament_teams = TournamentTeam.query.order_by(TournamentTeam.name).all()
    
    # Get all teams for tournament results (use tournament teams if available, otherwise game teams)
    if tournament_teams:
        teams = [team.name for team in tournament_teams]
    else:
        teams = set()
        for game in games:
            teams.add(game.team1)
            teams.add(game.team2)
        teams = sorted(list(teams))
    
    return render_template('admin.html', 
                         games=games, 
                         users=users, 
                         tournament_config=tournament_config,
                         tournament_predictions=tournament_predictions,
                         tournament_teams=tournament_teams,
                         teams=teams)

@app.route('/upload_games', methods=['POST'])
@login_required
@admin_required
def upload_games():
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('admin'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin'))
    
    if file and file.filename.lower().endswith('.csv'):
        try:
            # Read CSV content
            content = file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(content)
            
            games_added = 0
            for row in reader:
                # Expected CSV columns: team1, team2, date, time, round, prediction_deadline
                try:
                    # Handle different date/time formats
                    if 'time' in row and row['time']:
                        # Separate date and time columns
                        game_date = datetime.strptime(f"{row['date']} {row['time']}", "%Y-%m-%d %H:%M")
                    else:
                        # Single datetime column
                        game_date = datetime.strptime(row['date'], "%Y-%m-%d %H:%M")
                except ValueError:
                    try:
                        # Try with comma between date and time
                        game_date = datetime.strptime(f"{row['date']},{row['time']}", "%Y-%m-%d,%H:%M")
                    except ValueError:
                        flash(f'Invalid date/time format in row: {row}', 'error')
                        continue
                
                # Parse prediction deadline
                if 'prediction_deadline' in row and row['prediction_deadline']:
                    try:
                        prediction_deadline = datetime.strptime(row['prediction_deadline'], "%Y-%m-%d %H:%M")
                    except ValueError:
                        try:
                            # Try with comma format
                            prediction_deadline = datetime.strptime(row['prediction_deadline'], "%Y-%m-%d,%H:%M")
                        except ValueError:
                            flash(f'Invalid prediction deadline format: {row["prediction_deadline"]}', 'error')
                            # Default: 30 minutes before game start
                            from datetime import timedelta
                            prediction_deadline = game_date - timedelta(minutes=30)
                else:
                    # Default: 30 minutes before game start
                    from datetime import timedelta
                    prediction_deadline = game_date - timedelta(minutes=30)
                
                # Check if game already exists
                existing = Game.query.filter_by(
                    team1=row['team1'],
                    team2=row['team2'],
                    game_date=game_date
                ).first()
                
                if not existing:
                    game = Game(
                        team1=row['team1'],
                        team2=row['team2'],
                        game_date=game_date,
                        prediction_deadline=prediction_deadline,
                        round_name=row['round']
                    )
                    db.session.add(game)
                    games_added += 1
            
            db.session.commit()
            flash(f'Successfully imported {games_added} games', 'success')
            
        except Exception as e:
            flash(f'Error importing CSV: {str(e)}', 'error')
    else:
        flash('Please upload a CSV file', 'error')
    
    return redirect(url_for('admin'))

@app.route('/upload_tournament_teams', methods=['POST'])
@login_required
@admin_required
def upload_tournament_teams():
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('admin'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin'))
    
    if file and file.filename.lower().endswith('.csv'):
        try:
            # Read CSV content
            content = file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(content)
            
            teams_added = 0
            for row in reader:
                # Expected CSV columns: team_name/name/team, country_code (optional)
                team_name = row.get('team_name') or row.get('name') or row.get('team')
                if not team_name:
                    continue
                
                team_name = team_name.strip()
                if not team_name:
                    continue
                
                # Get country code from CSV or mapping
                country_code = row.get('country_code', '').strip().lower()
                if not country_code:
                    country_code = get_country_code(team_name)
                
                # Check if team already exists
                existing = TournamentTeam.query.filter_by(name=team_name).first()
                
                if not existing:
                    team = TournamentTeam(name=team_name, country_code=country_code)
                    db.session.add(team)
                    teams_added += 1
                elif country_code and not existing.country_code:
                    # Update existing team with country code if missing
                    existing.country_code = country_code
                    db.session.add(existing)
            
            db.session.commit()
            flash(f'Successfully imported {teams_added} tournament teams', 'success')
            
        except Exception as e:
            flash(f'Error importing CSV: {str(e)}', 'error')
    else:
        flash('Please upload a CSV file', 'error')
    
    return redirect(url_for('admin'))

@app.route('/delete_tournament_team/<int:team_id>', methods=['POST'])
@login_required
@admin_required
def delete_tournament_team(team_id):
    team = TournamentTeam.query.get(team_id)
    if not team:
        flash('Team not found', 'error')
        return redirect(url_for('admin'))
    
    # Check if team is used in any tournament predictions
    predictions_count = TournamentPrediction.query.filter(
        (TournamentPrediction.first_place == team.name) |
        (TournamentPrediction.second_place == team.name) |
        (TournamentPrediction.third_place == team.name)
    ).count()
    
    if predictions_count > 0:
        flash(f'Cannot delete team: {predictions_count} tournament predictions reference this team', 'error')
        return redirect(url_for('admin'))
    
    # Delete the team
    db.session.delete(team)
    db.session.commit()
    
    flash(f'Tournament team "{team.name}" has been deleted', 'success')
    return redirect(url_for('admin'))

@app.route('/update_result', methods=['POST'])
@login_required
@admin_required
def update_result():
    game_id = request.form.get('game_id')
    team1_score = request.form.get('team1_score')
    team2_score = request.form.get('team2_score')
    
    if not all([game_id, team1_score, team2_score]):
        flash('Please fill in all fields', 'error')
        return redirect(url_for('admin'))
    
    try:
        team1_score = int(team1_score)
        team2_score = int(team2_score)
        if team1_score < 0 or team2_score < 0:
            raise ValueError("Scores cannot be negative")
        
        # Volleyball scoring validation: one team must win 3 sets, other 0-2
        if not ((team1_score == 3 and team2_score in [0, 1, 2]) or 
                (team2_score == 3 and team1_score in [0, 1, 2])):
            raise ValueError("Invalid volleyball score")
            
    except ValueError as e:
        if "Invalid volleyball score" in str(e):
            flash('Invalid volleyball score. Winner must have 3 sets, loser 0-2 sets.', 'error')
        else:
            flash('Please enter valid scores', 'error')
        return redirect(url_for('admin'))
    
    game = Game.query.get(game_id)
    if game:
        game.team1_score = team1_score
        game.team2_score = team2_score
        game.is_finished = True
        
        # Recalculate points for all predictions of this game
        predictions = Prediction.query.filter_by(game_id=game_id).all()
        for prediction in predictions:
            prediction.points = calculate_points(prediction, game)
        
        db.session.commit()
        flash('Game result updated and points recalculated!', 'success')
    else:
        flash('Game not found', 'error')
    
    return redirect(url_for('admin'))

@app.route('/delete_game/<int:game_id>', methods=['POST'])
@login_required
@admin_required
def delete_game(game_id):
    game = Game.query.get(game_id)
    if not game:
        flash('Game not found', 'error')
        return redirect(url_for('admin'))
    
    # Count predictions before deletion
    prediction_count = Prediction.query.filter_by(game_id=game_id).count()
    
    # Delete the game - predictions will be automatically deleted due to cascade='all, delete-orphan'
    db.session.delete(game)
    db.session.commit()
    
    if prediction_count > 0:
        flash(f'Game "{game.team1} vs {game.team2}" and {prediction_count} related predictions have been deleted', 'success')
    else:
        flash(f'Game "{game.team1} vs {game.team2}" has been deleted', 'success')
    return redirect(url_for('admin'))

@app.route('/bulk_delete_games', methods=['POST'])
@login_required
@admin_required
def bulk_delete_games():
    try:
        game_ids = request.form.getlist('game_ids')
        print(f"Bulk delete request received for game IDs: {game_ids}")  # Debug log
        
        if not game_ids:
            flash('No games selected for deletion', 'error')
            return redirect(url_for('admin'))
        
        deleted_count = 0
        errors = []
        
        for game_id in game_ids:
            try:
                game = Game.query.get(int(game_id))
                if not game:
                    errors.append(f"Game {game_id} not found")
                    continue
                    
                # Delete the game - predictions will be automatically deleted due to cascade='all, delete-orphan'
                db.session.delete(game)
                deleted_count += 1
                print(f"Marked game {game_id} for deletion")  # Debug log
                
            except Exception as e:
                error_msg = f"Error processing game {game_id}: {str(e)}"
                errors.append(error_msg)
                print(error_msg)  # Debug log
                continue
        
        if deleted_count > 0:
            db.session.commit()
            print(f"Database commit completed. Deleted: {deleted_count}")  # Debug log
        
        if deleted_count > 0:
            flash(f'Successfully deleted {deleted_count} games', 'success')
        
        
        if errors:
            flash(f'Errors occurred: {"; ".join(errors)}', 'error')
        
        if deleted_count == 0:
            flash('No games were deleted', 'info')
            
    except Exception as e:
        db.session.rollback()
        error_msg = f"Bulk delete failed: {str(e)}"
        print(error_msg)  # Debug log
        flash(error_msg, 'error')
    
    return redirect(url_for('admin'))

@app.route('/admin/reset-user-password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_user_password(user_id):
    user = User.query.get(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin'))
    
    if user.is_admin:
        flash('Cannot reset admin password', 'error')
        return redirect(url_for('admin'))
    
    # Set password reset flag
    user.password_reset_required = True
    db.session.commit()
    
    flash(f'Password reset initiated for {user.name}. They will be prompted to change their password on next login.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/tournament-config', methods=['POST'])
@login_required
@admin_required
def set_tournament_config():
    deadline_str = request.form.get('prediction_deadline')
    
    if not deadline_str:
        flash('Please provide a prediction deadline.', 'error')
        return redirect(url_for('admin'))
    
    try:
        deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid date format.', 'error')
        return redirect(url_for('admin'))
    
    # Create or update tournament config
    tournament_config = TournamentConfig.query.first()
    if tournament_config:
        tournament_config.prediction_deadline = deadline
    else:
        tournament_config = TournamentConfig(prediction_deadline=deadline)
        db.session.add(tournament_config)
    
    db.session.commit()
    flash('Tournament prediction deadline set successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/tournament-results', methods=['POST'])
@login_required
@admin_required
def set_tournament_results():
    first_place = request.form.get('first_place_result')
    second_place = request.form.get('second_place_result')
    third_place = request.form.get('third_place_result')
    
    if not all([first_place, second_place, third_place]):
        flash('Please select all three positions.', 'error')
        return redirect(url_for('admin'))
    
    if len(set([first_place, second_place, third_place])) != 3:
        flash('Please select different teams for each position.', 'error')
        return redirect(url_for('admin'))
    
    tournament_config = TournamentConfig.query.first()
    if not tournament_config:
        flash('Tournament configuration not found. Please set deadline first.', 'error')
        return redirect(url_for('admin'))
    
    # Update results
    tournament_config.first_place_result = first_place
    tournament_config.second_place_result = second_place
    tournament_config.third_place_result = third_place
    tournament_config.is_finalized = True
    
    # Recalculate points for all tournament predictions
    predictions = TournamentPrediction.query.all()
    for prediction in predictions:
        prediction.points_earned = calculate_tournament_points(prediction, tournament_config)
    
    db.session.commit()
    flash(f'Tournament results finalized! Points calculated for {len(predictions)} predictions.', 'success')
    return redirect(url_for('admin'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if not current_user.password_reset_required:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not new_password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('change_password.html', force_change=True)
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('change_password.html', force_change=True)
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('change_password.html', force_change=True)
        
        # Update password and clear reset flag
        current_user.set_password(new_password)
        current_user.password_reset_required = False
        db.session.commit()
        
        flash('Password changed successfully! You can now access all features.', 'success')
        return redirect(url_for('index'))
    
    return render_template('change_password.html', force_change=True)

@app.route('/tournament-predictions', methods=['GET', 'POST'])
@login_required
def tournament_predictions():
    # Get or create tournament config
    tournament_config = TournamentConfig.query.first()
    if not tournament_config:
        flash('Tournament predictions are not yet available. Please contact admin.', 'warning')
        return redirect(url_for('index'))
    
    # Get tournament teams (if available) or fallback to game teams
    tournament_teams = TournamentTeam.query.order_by(TournamentTeam.name).all()
    if tournament_teams:
        teams = [team.name for team in tournament_teams]
    else:
        # Fallback to teams from games
        teams = set()
        games = Game.query.all()
        for game in games:
            teams.add(game.team1)
            teams.add(game.team2)
        teams = sorted(list(teams))
    
    # Check if we have teams available
    if not teams:
        flash('No tournament teams available. Please contact admin to upload team list.', 'warning')
        return redirect(url_for('index'))
    
    # Get user's existing prediction
    user_prediction = TournamentPrediction.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        if not tournament_config.is_prediction_open():
            flash('Tournament prediction deadline has passed.', 'error')
            return redirect(url_for('tournament_predictions'))
        
        first_place = request.form.get('first_place')
        second_place = request.form.get('second_place')
        third_place = request.form.get('third_place')
        
        # Validation
        if not all([first_place, second_place, third_place]):
            flash('Please select all three positions.', 'error')
            return render_template('tournament_predictions.html', 
                                 tournament_config=tournament_config, 
                                 teams=teams, 
                                 user_prediction=user_prediction)
        
        # Check for duplicate selections
        if len(set([first_place, second_place, third_place])) != 3:
            flash('Please select different teams for each position.', 'error')
            return render_template('tournament_predictions.html', 
                                 tournament_config=tournament_config, 
                                 teams=teams, 
                                 user_prediction=user_prediction)
        
        # Create or update prediction
        if user_prediction:
            user_prediction.first_place = first_place
            user_prediction.second_place = second_place
            user_prediction.third_place = third_place
            user_prediction.updated_at = datetime.utcnow()
        else:
            user_prediction = TournamentPrediction(
                user_id=current_user.id,
                first_place=first_place,
                second_place=second_place,
                third_place=third_place
            )
            db.session.add(user_prediction)
        
        db.session.commit()
        flash('Tournament prediction saved successfully!', 'success')
        return redirect(url_for('tournament_predictions'))
    
    return render_template('tournament_predictions.html', 
                         tournament_config=tournament_config, 
                         teams=teams, 
                         user_prediction=user_prediction)

@app.route('/get_prediction/<int:game_id>')
@login_required
def get_prediction(game_id):
    prediction = Prediction.query.filter_by(user_id=current_user.id, game_id=game_id).first()
    if prediction:
        return jsonify({
            'team1_score': prediction.team1_score,
            'team2_score': prediction.team2_score
        })
    return jsonify({'team1_score': '', 'team2_score': ''})

@app.route('/save_prediction_ajax', methods=['POST'])
@login_required
def save_prediction_ajax():
    try:
        data = request.get_json()
        game_id = data.get('game_id')
        team1_score = data.get('team1_score')
        team2_score = data.get('team2_score')
        
        if not all([game_id, team1_score is not None, team2_score is not None]):
            return jsonify({'success': False, 'error': 'Please fill in all fields'}), 400
        
        # Convert to integers
        game_id = int(game_id)
        team1_score = int(team1_score)
        team2_score = int(team2_score)
        
        if team1_score < 0 or team2_score < 0:
            return jsonify({'success': False, 'error': 'Scores cannot be negative'}), 400
        
        # Volleyball scoring validation: one team must win 3 sets, other 0-2
        if not ((team1_score == 3 and team2_score in [0, 1, 2]) or 
                (team2_score == 3 and team1_score in [0, 1, 2])):
            return jsonify({'success': False, 'error': 'Invalid volleyball score. Winner must have 3 sets, loser 0-2 sets.'}), 400
        
        game = Game.query.get(game_id)
        if not game:
            return jsonify({'success': False, 'error': 'Game not found'}), 404
        
        # Check prediction deadline - using Riga timezone
        current_time = get_riga_time()
        deadline = to_riga_time(game.prediction_deadline)
        
        if current_time >= deadline:
            return jsonify({'success': False, 'error': 'Prediction deadline has passed for this game'}), 400
        
        # Check if prediction already exists
        existing = Prediction.query.filter_by(user_id=current_user.id, game_id=game_id).first()
        is_update = bool(existing)
        
        if existing:
            existing.team1_score = team1_score
            existing.team2_score = team2_score
            existing.predicted_winner = game.team1 if team1_score > team2_score else game.team2
        else:
            predicted_winner = game.team1 if team1_score > team2_score else game.team2
            prediction = Prediction(
                user_id=current_user.id,
                game_id=game_id,
                team1_score=team1_score,
                team2_score=team2_score,
                predicted_winner=predicted_winner
            )
            db.session.add(prediction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Prediction updated!' if is_update else 'Prediction saved!',
            'is_update': is_update,
            'team1_score': team1_score,
            'team2_score': team2_score
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'error': 'Please enter valid values'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': 'An error occurred while saving your prediction'}), 500

@app.route('/game_predictions/<int:game_id>')
@login_required
def game_predictions(game_id):
    game = Game.query.get_or_404(game_id)
    
    # Only show predictions if deadline has passed
    if not game.are_predictions_visible():
        return jsonify({'error': 'Predictions not yet visible'}), 403
    
    predictions = Prediction.query.filter_by(game_id=game_id).join(User).all()
    predictions_data = []
    for pred in predictions:
        predictions_data.append({
            'user_name': pred.user.name,
            'team1_score': pred.team1_score,
            'team2_score': pred.team2_score,
            'predicted_winner': pred.predicted_winner,
            'points': pred.points
        })
    
    return jsonify({
        'game': {
            'team1': game.team1,
            'team2': game.team2,
            'round_name': game.round_name
        },
        'predictions': predictions_data
    })

@app.route('/user/<int:user_id>')
@login_required
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    
    # Get all predictions for games with passed deadline, ordered by game date
    # Filter in Python to handle Riga timezone properly
    all_predictions = (Prediction.query
                      .join(Game)
                      .filter(Prediction.user_id == user_id)
                      .order_by(Game.game_date.desc())
                      .all())
    
    current_time = get_riga_time()
    predictions = []
    for pred in all_predictions:
        deadline = to_riga_time(pred.game.prediction_deadline)
        if current_time >= deadline:
            predictions.append(pred)
    
    # Calculate user stats
    total_predictions = len([p for p in predictions if p.team1_score is not None])
    correct_predictions = len([p for p in predictions if p.points and p.points > 0])
    total_points = sum([p.points for p in predictions if p.points is not None])
    accuracy = round((correct_predictions / max(total_predictions, 1)) * 100, 1)
    
    # Add tournament points if available
    tournament_points = user.tournament_prediction.points_earned if user.tournament_prediction else 0
    total_score = total_points + tournament_points
    
    return render_template('user_profile.html', 
                         user=user, 
                         predictions=predictions,
                         stats={
                             'total_predictions': total_predictions,
                             'correct_predictions': correct_predictions,
                             'total_points': total_points,
                             'tournament_points': tournament_points,
                             'total_score': total_score,
                             'accuracy': accuracy
                         })

@app.route('/match/<int:game_id>')
@login_required
def match_detail(game_id):
    game = Game.query.get_or_404(game_id)
    
    # Only show if prediction deadline has passed - using Riga timezone
    current_time = get_riga_time()
    deadline = to_riga_time(game.prediction_deadline)
    if current_time < deadline:
        flash('Match predictions are not yet visible.', 'warning')
        return redirect(url_for('predictions'))
    
    # Get all predictions for this game
    predictions = (Prediction.query
                  .filter_by(game_id=game_id)
                  .join(User)
                  .order_by(User.name)
                  .all())
    
    # Calculate some stats
    total_predictions = len([p for p in predictions if p.team1_score is not None])
    if game.is_finished:
        correct_predictions = len([p for p in predictions if p.points and p.points > 0])
        perfect_predictions = len([p for p in predictions if p.points == 6])
    else:
        correct_predictions = 0
        perfect_predictions = 0
    
    return render_template('match_detail.html',
                         game=game,
                         predictions=predictions,
                         stats={
                             'total_predictions': total_predictions,
                             'correct_predictions': correct_predictions,
                             'perfect_predictions': perfect_predictions
                         })

@app.route('/all_predictions')
@login_required
def all_predictions():
    # Get filter parameters
    selected_date = request.args.get('date')
    selected_pool = request.args.get('pool')
    
    # Base query: only games where deadline has passed - using Riga timezone
    current_time = get_riga_time()
    # Get all games and filter in Python to handle Riga timezone properly
    all_games = Game.query.all()
    games_with_passed_deadlines = []
    
    for game in all_games:
        deadline = to_riga_time(game.prediction_deadline)
        if current_time >= deadline:
            games_with_passed_deadlines.append(game.id)
    
    # Now query with the filtered game IDs
    games_query = Game.query.filter(Game.id.in_(games_with_passed_deadlines)) if games_with_passed_deadlines else Game.query.filter(False)
    
    # Apply date filter if provided
    if selected_date:
        try:
            filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            games_query = games_query.filter(db.func.date(Game.game_date) == filter_date)
        except ValueError:
            flash('Invalid date format', 'error')
    
    # Apply pool filter if provided
    if selected_pool:
        games_query = games_query.filter(Game.round_name.ilike(f'%{selected_pool}%'))
    
    # Order by game date (most recent first)
    games = games_query.order_by(Game.game_date.desc()).all()
    
    # Get all predictions for these games
    games_with_predictions = []
    for game in games:
        predictions = Prediction.query.filter_by(game_id=game.id).join(User).all()
        predictions_data = []
        for pred in predictions:
            predictions_data.append({
                'user_name': pred.user.name,
                'team1_score': pred.team1_score,
                'team2_score': pred.team2_score,
                'predicted_winner': pred.predicted_winner,
                'points': pred.points
            })
        
        games_with_predictions.append({
            'game': game,
            'predictions': predictions_data,
            'total_predictions': len(predictions_data)
        })
    
    # Get unique dates and pools for filtering - use games with passed deadlines
    filtered_games = [game for game in all_games if game.id in games_with_passed_deadlines] if games_with_passed_deadlines else []
    unique_dates = sorted(list(set(game.game_date.date() for game in filtered_games)), reverse=True) if filtered_games else []
    unique_pools = sorted(list(set(game.round_name for game in filtered_games))) if filtered_games else []
    
    return render_template('all_predictions.html', 
                         games_with_predictions=games_with_predictions,
                         unique_dates=unique_dates,
                         unique_pools=unique_pools,
                         selected_date=selected_date,
                         selected_pool=selected_pool)

# Initialize database
with app.app_context():
    try:
        # Create all tables (this will only create missing tables)
        db.create_all()
        print("Database tables initialized successfully")
        
        # Check if we need to add the password_reset_required column
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'user' in existing_tables:
            user_columns = [col['name'] for col in inspector.get_columns('user')]
            if 'password_reset_required' not in user_columns:
                print("Adding password_reset_required column to existing User table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE "user" ADD COLUMN password_reset_required BOOLEAN DEFAULT FALSE'))
                    conn.commit()
                print("password_reset_required column added successfully")
        
        # Check if we need to add the country_code column to tournament_team table
        if 'tournament_team' in existing_tables:
            team_columns = [col['name'] for col in inspector.get_columns('tournament_team')]
            if 'country_code' not in team_columns:
                print("Adding country_code column to existing TournamentTeam table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE tournament_team ADD COLUMN country_code VARCHAR(2)'))
                    conn.commit()
                print("country_code column added successfully")
                
                # Update existing teams with country codes
                teams_to_update = [
                    ('Brazil', 'br'), ('USA', 'us'), ('Poland', 'pl'), ('Italy', 'it'),
                    ('Serbia', 'rs'), ('Turkey', 'tr'), ('Japan', 'jp'), ('China', 'cn'),
                    ('Netherlands', 'nl'), ('Dominican Republic', 'do'), ('France', 'fr'),
                    ('Germany', 'de'), ('Thailand', 'th'), ('Belgium', 'be'), ('Canada', 'ca'),
                    ('Bulgaria', 'bg'), ('Argentina', 'ar'), ('Slovenia', 'si'),
                    ('Czech Republic', 'cz'), ('Puerto Rico', 'pr'), ('Ukraine', 'ua'),
                    ('Russia', 'ru'), ('South Korea', 'kr'), ('Croatia', 'hr')
                ]
                
                with db.engine.connect() as conn:
                    for team_name, country_code in teams_to_update:
                        try:
                            conn.execute(
                                db.text('UPDATE tournament_team SET country_code = :code WHERE name = :name'),
                                {'code': country_code, 'name': team_name}
                            )
                        except:
                            pass  # Continue if team doesn't exist
                    conn.commit()
                print("Updated country codes for existing teams")
            
    except Exception as e:
        print(f"Database initialization error: {e}")
        # Continue anyway - the app might still work with existing tables

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)