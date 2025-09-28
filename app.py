import os
import csv
import hashlib
import random
import logging
from datetime import datetime, timezone, timedelta
import pytz
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

# Suppress absl logging warnings from Google AI libraries
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow warnings
import warnings
warnings.filterwarnings('ignore', message='All log messages before absl::InitializeLog')

# AI functionality imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    # Initialize absl logging to prevent warnings
    try:
        from absl import logging as absl_logging
        absl_logging.set_verbosity(absl_logging.ERROR)
    except ImportError:
        pass
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("Google Generative AI package not installed. AI messages will use fallback templates only.")

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

# Team name to country code mapping for flags - 2025 Men's World Championship
TEAM_COUNTRY_MAPPING = {
    'Algeria': 'dz',
    'Argentina': 'ar',
    'Belgium': 'be',
    'Brazil': 'br',
    'Bulgaria': 'bg',
    'Canada': 'ca',
    'Chile': 'cl',
    'China': 'cn',
    'Colombia': 'co',
    'Cuba': 'cu',
    'Czechia': 'cz',
    'Czech Republic': 'cz',
    'Egypt': 'eg',
    'Finland': 'fi',
    'France': 'fr',
    'Germany': 'de',
    'Iran': 'ir',
    'Italy': 'it',
    'Japan': 'jp',
    'Korea': 'kr',
    'Libya': 'ly',
    'Netherlands': 'nl',
    'Philippines': 'ph',
    'Poland': 'pl',
    'Portugal': 'pt',
    'Qatar': 'qa',
    'Romania': 'ro',
    'Serbia': 'rs',
    'Slovenia': 'si',
    'Tunisia': 'tn',
    'Turkey': 'tr',
    'Türkiye': 'tr',
    'Ukraine': 'ua',
    'USA': 'us'
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
        """Count only predictions for finished games"""
        return len([p for p in self.predictions 
                   if p.team1_score is not None 
                   and p.game.is_finished 
                   and p.points is not None])
    
    def get_all_predictions_filled(self):
        """Count all predictions that have been filled out (regardless of deadline)"""
        return len([p for p in self.predictions 
                   if p.team1_score is not None 
                   and p.team2_score is not None])
    
    def get_correct_predictions(self):
        """Count only predictions with 2+ points (truly correct predictions)"""
        return len([p for p in self.predictions 
                   if p.points is not None 
                   and p.points >= 2
                   and p.game.is_finished])
    
    def get_finished_predictions(self):
        """Get all predictions for finished games"""
        return [p for p in self.predictions 
                if p.game.is_finished 
                and p.team1_score is not None 
                and p.points is not None]
    
    def get_accuracy_percentage(self):
        """Calculate accuracy percentage based on finished games only"""
        finished_predictions = self.get_finished_predictions()
        if not finished_predictions:
            return 0.0
        
        correct_count = len([p for p in finished_predictions if p.points >= 2])
        return round((correct_count / len(finished_predictions)) * 100, 1)
    
    def get_prediction_breakdown(self):
        """Get detailed breakdown of prediction performance"""
        finished_predictions = self.get_finished_predictions()
        
        return {
            'total_finished': len(finished_predictions),
            'perfect_6pts': len([p for p in finished_predictions if p.points == 6]),
            'winner_plus_score_4pts': len([p for p in finished_predictions if p.points == 4]),
            'winner_only_2pts': len([p for p in finished_predictions if p.points == 2]),
            'partial_1pt': len([p for p in finished_predictions if p.points == 1]),
            'wrong_0pts': len([p for p in finished_predictions if p.points == 0]),
            'correct_predictions': len([p for p in finished_predictions if p.points >= 2]),
            'accuracy': round((len([p for p in finished_predictions if p.points >= 2]) / max(len(finished_predictions), 1)) * 100, 1)
        }

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

    # SerpApi auto-update fields
    auto_update_attempted = db.Column(db.Boolean, default=False)
    auto_update_timestamp = db.Column(db.DateTime, nullable=True)
    result_source = db.Column(db.String(50), default='manual')  # 'manual', 'auto_serpapi'
    serpapi_search_used = db.Column(db.Boolean, default=False)

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
    
    def is_default_prediction(self):
        """Check if this is a default prediction (created by recalculation system)"""
        return self.team1_score is None and self.team2_score is None and self.predicted_winner is None

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

class RecalculationConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    default_points_position = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_current_config():
        """Get current recalculation config, create if doesn't exist"""
        config = RecalculationConfig.query.first()
        if not config:
            config = RecalculationConfig(default_points_position=1)
            db.session.add(config)
            db.session.commit()
        return config

class PlayerMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    message_category = db.Column(db.String(50), nullable=True)
    performance_hash = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    api_calls_used = db.Column(db.Integer, default=1)
    last_viewed_at = db.Column(db.DateTime, nullable=True)
    latest_results_hash = db.Column(db.String(32), nullable=True)
    
    user = db.relationship('User', backref=db.backref('messages', lazy=True))

class DailyApiUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    calls_made = db.Column(db.Integer, default=0)
    daily_limit = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SerpApiUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month_year = db.Column(db.String(7), unique=True, nullable=False)  # "2025-09"
    searches_used = db.Column(db.Integer, default=0)
    monthly_limit = db.Column(db.Integer, default=250)
    last_search_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def get_current_month_usage():
        """Get current month's usage, create if doesn't exist"""
        current_month = datetime.now().strftime('%Y-%m')
        usage = SerpApiUsage.query.filter_by(month_year=current_month).first()
        if not usage:
            usage = SerpApiUsage(month_year=current_month)
            db.session.add(usage)
            db.session.commit()
        return usage

    def can_make_search(self):
        """Check if we can make another search this month"""
        return self.searches_used < self.monthly_limit

    def increment_usage(self):
        """Increment search count and update timestamp"""
        self.searches_used += 1
        self.last_search_date = datetime.utcnow()
        db.session.commit()

class LoggingConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_level = db.Column(db.String(20), default='INFO')  # DEBUG, INFO, WARNING, ERROR
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_current_log_level():
        """Get current log level, create if doesn't exist"""
        config = LoggingConfig.query.first()
        if not config:
            config = LoggingConfig(log_level='INFO')
            db.session.add(config)
            db.session.commit()
        return config.log_level

    @staticmethod
    def set_log_level(level):
        """Set current log level"""
        config = LoggingConfig.query.first()
        if not config:
            config = LoggingConfig(log_level=level)
            db.session.add(config)
        else:
            config.log_level = level
            config.updated_at = datetime.utcnow()
        db.session.commit()

        # Update Python logging level
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        logging.getLogger().setLevel(numeric_level)

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


class GameHighlight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    youtube_url = db.Column(db.String(500), nullable=False)
    youtube_video_id = db.Column(db.String(20), nullable=False)  # Extracted from URL
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    duration = db.Column(db.String(20), nullable=True)  # e.g., "PT5M30S" or "5:30"
    video_type = db.Column(db.String(50), default='highlight')  # highlight, top_moment, interview
    view_count = db.Column(db.Integer, nullable=True)
    upload_date = db.Column(db.DateTime, nullable=True)
    channel_name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)  # For manually selected top highlights
    auto_detected = db.Column(db.Boolean, default=False)  # True if found by automatic detection
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    game = db.relationship('Game', backref=db.backref('highlights', lazy=True, cascade='all, delete-orphan'))

    def get_embed_url(self):
        """Convert YouTube URL to embeddable format"""
        if 'youtube.com/watch?v=' in self.youtube_url:
            return self.youtube_url.replace('youtube.com/watch?v=', 'youtube.com/embed/')
        elif 'youtu.be/' in self.youtube_url:
            video_id = self.youtube_url.split('youtu.be/')[-1].split('?')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        return self.youtube_url

    def get_video_id(self):
        """Extract video ID from YouTube URL"""
        if 'youtube.com/watch?v=' in self.youtube_url:
            return self.youtube_url.split('youtube.com/watch?v=')[-1].split('&')[0]
        elif 'youtu.be/' in self.youtube_url:
            return self.youtube_url.split('youtu.be/')[-1].split('?')[0]
        return self.youtube_video_id

    def format_duration(self):
        """Format duration for display"""
        if not self.duration:
            return "Unknown"
        # Convert PT5M30S format to 5:30
        if self.duration.startswith('PT'):
            import re
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', self.duration)
            if match:
                hours, minutes, seconds = match.groups()
                parts = []
                if hours:
                    parts.append(f"{hours}h")
                if minutes:
                    parts.append(f"{minutes}m")
                if seconds:
                    parts.append(f"{seconds}s")
                return " ".join(parts) if parts else "0s"
        return self.duration


class FeaturedVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    youtube_url = db.Column(db.String(500), nullable=False)
    youtube_video_id = db.Column(db.String(20), nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    duration = db.Column(db.String(20), nullable=True)
    channel_name = db.Column(db.String(100), nullable=True)
    view_count = db.Column(db.Integer, nullable=True)
    upload_date = db.Column(db.DateTime, nullable=True)
    display_order = db.Column(db.Integer, default=0)  # For custom ordering
    is_active = db.Column(db.Boolean, default=True)
    auto_detected = db.Column(db.Boolean, default=False)  # True if found by automatic detection
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_embed_url(self):
        """Convert YouTube URL to embeddable format"""
        if 'youtube.com/watch?v=' in self.youtube_url:
            return self.youtube_url.replace('youtube.com/watch?v=', 'youtube.com/embed/')
        elif 'youtu.be/' in self.youtube_url:
            video_id = self.youtube_url.split('youtu.be/')[-1].split('?')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        return self.youtube_url

    def get_video_id(self):
        """Extract video ID from YouTube URL"""
        if 'youtube.com/watch?v=' in self.youtube_url:
            return self.youtube_url.split('youtube.com/watch?v=')[-1].split('&')[0]
        elif 'youtu.be/' in self.youtube_url:
            return self.youtube_url.split('youtu.be/')[-1].split('?')[0]
        return self.youtube_video_id

    def format_duration(self):
        """Format duration for display"""
        if not self.duration:
            return "Unknown"
        # Convert PT5M30S format to 5:30
        if self.duration.startswith('PT'):
            import re
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', self.duration)
            if match:
                hours, minutes, seconds = match.groups()
                parts = []
                if hours:
                    parts.append(f"{hours}h")
                if minutes:
                    parts.append(f"{minutes}m")
                if seconds:
                    parts.append(f"{seconds}s")
                return " ".join(parts) if parts else "0s"
        return self.duration


# Performance Analysis Functions
def calculate_performance_hash(user_id):
    """Calculate a hash based on user's current performance metrics"""
    try:
        user = User.query.get(user_id)
        if not user:
            return None
        
        # Get recent performance data (last 7 days of finished games)
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_predictions = db.session.query(Prediction).join(Game).filter(
            Prediction.user_id == user_id,
            Game.is_finished == True,
            Game.game_date >= recent_cutoff,
            Prediction.team1_score.isnot(None)  # Only real predictions
        ).all()
        
        # Calculate metrics
        total_score = user.get_total_score()
        total_predictions = len([p for p in user.predictions if not p.is_default_prediction()])
        correct_predictions = len([p for p in user.predictions if p.points and p.points >= 2 and not p.is_default_prediction()])
        accuracy = round((correct_predictions / total_predictions * 100) if total_predictions > 0 else 0)
        
        # Recent performance
        recent_correct = len([p for p in recent_predictions if p.points and p.points >= 2])
        recent_total = len(recent_predictions)
        recent_accuracy = round((recent_correct / recent_total * 100) if recent_total > 0 else 0)
        recent_points = sum([p.points or 0 for p in recent_predictions])
        
        # Create hash string
        hash_data = f"{total_score}_{total_predictions}_{accuracy}_{recent_accuracy}_{recent_points}_{recent_total}"
        return hashlib.md5(hash_data.encode()).hexdigest()
        
    except Exception as e:
        logging.error(f"Error calculating performance hash for user {user_id}: {str(e)}")
        db.session.rollback()
        return None

def calculate_latest_results_hash(user_id):
    """Calculate hash based on latest game results user hasn't seen"""
    try:
        # Get latest finished games (recent games that have results)
        latest_games = Game.query.filter(
            Game.is_finished == True,
            Game.team1_score.isnot(None),
            Game.team2_score.isnot(None)
        ).order_by(Game.game_date.desc()).limit(5).all()
        
        # Include user's predictions for these games
        user_predictions = {}
        if latest_games:
            game_ids = [g.id for g in latest_games]
            predictions = Prediction.query.filter(
                Prediction.user_id == user_id,
                Prediction.game_id.in_(game_ids)
            ).all()
            user_predictions = {p.game_id: p for p in predictions}
        
        # Create hash from game results and user predictions
        hash_data = ""
        for game in latest_games:
            pred = user_predictions.get(game.id)
            pred_info = f"{pred.team1_score}-{pred.team2_score}" if pred and pred.team1_score is not None else "none"
            points = pred.points if pred else 0
            hash_data += f"{game.id}_{game.team1_score}_{game.team2_score}_{pred_info}_{points}_"
        
        return hashlib.md5(hash_data.encode()).hexdigest() if hash_data else None
        
    except Exception as e:
        logging.error(f"Error calculating latest results hash for user {user_id}: {str(e)}")
        db.session.rollback()
        return None

def get_latest_results_summary(user_id):
    """Get detailed summary of latest results user participated in"""
    try:
        # First try to get games from last 24 hours
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_games = db.session.query(Game).join(Prediction).filter(
            Game.is_finished == True,
            Game.team1_score.isnot(None),
            Game.team2_score.isnot(None),
            Game.game_date >= recent_cutoff,
            Prediction.user_id == user_id
        ).order_by(Game.game_date.desc()).limit(3).all()
        
        # If we have recent games, use them
        if recent_games:
            results = []
            for game in recent_games:
                prediction = Prediction.query.filter_by(user_id=user_id, game_id=game.id).first()
                if prediction:
                    correct = prediction.points and prediction.points >= 2
                    results.append({
                        'game': game,
                        'prediction': prediction,
                        'correct': correct,
                        'points': prediction.points or 0,
                        'is_recent': True
                    })
            return results
        
        # Otherwise get the most recent completed games (up to last 7 days)
        week_cutoff = datetime.utcnow() - timedelta(days=7)
        latest_games = db.session.query(Game).join(Prediction).filter(
            Game.is_finished == True,
            Game.team1_score.isnot(None),
            Game.team2_score.isnot(None),
            Game.game_date >= week_cutoff,
            Prediction.user_id == user_id
        ).order_by(Game.game_date.desc()).limit(2).all()
        
        if not latest_games:
            # Last resort - get any completed game
            last_game = db.session.query(Game).join(Prediction).filter(
                Game.is_finished == True,
                Game.team1_score.isnot(None),
                Game.team2_score.isnot(None),
                Prediction.user_id == user_id
            ).order_by(Game.game_date.desc()).first()
            
            if last_game:
                prediction = Prediction.query.filter_by(user_id=user_id, game_id=last_game.id).first()
                if prediction:
                    return [{
                        'game': last_game,
                        'prediction': prediction,
                        'correct': prediction.points and prediction.points >= 2,
                        'points': prediction.points or 0,
                        'is_latest': True
                    }]
            return None
        
        results = []
        for game in latest_games:
            prediction = Prediction.query.filter_by(user_id=user_id, game_id=game.id).first()
            if prediction:
                correct = prediction.points and prediction.points >= 2
                results.append({
                    'game': game,
                    'prediction': prediction,
                    'correct': correct,
                    'points': prediction.points or 0,
                    'is_recent': False
                })
        
        return results
        
    except Exception as e:
        logging.error(f"Error getting latest results summary for user {user_id}: {str(e)}")
        db.session.rollback()
        return None

def get_detailed_context_for_ai(user_id):
    """Get very detailed context for AI message generation"""
    analysis = analyze_user_performance(user_id)
    if not analysis:
        return None
    
    user = User.query.get(user_id)
    latest_results = get_latest_results_summary(user_id)
    
    context = {
        'user': user,
        'analysis': analysis,
        'latest_results': latest_results,
        'specific_details': []
    }
    
    # Add specific performance insights
    if analysis['recent_accuracy'] > analysis['accuracy'] + 15:
        context['specific_details'].append(f"Hot streak: Recent {analysis['recent_accuracy']}% vs overall {analysis['accuracy']}%")
    elif analysis['recent_accuracy'] < analysis['accuracy'] - 15:
        context['specific_details'].append(f"Rough patch: Recent {analysis['recent_accuracy']}% vs overall {analysis['accuracy']}%")
    
    # Add ranking context
    if analysis['rank'] <= 3:
        context['specific_details'].append(f"Elite position: #{analysis['rank']} out of {analysis['total_players']} players")
    elif analysis['rank'] <= analysis['total_players'] // 2:
        context['specific_details'].append(f"Upper half: #{analysis['rank']} out of {analysis['total_players']} players")
    else:
        context['specific_details'].append(f"Room to climb: #{analysis['rank']} out of {analysis['total_players']} players")
    
    # Add latest game details if available
    if latest_results:
        for result in latest_results[:2]:  # Only first 2 games
            game = result['game']
            pred = result['prediction']
            actual_score = f"{game.team1_score}-{game.team2_score}"
            
            if pred.team1_score is not None:
                pred_score = f"{pred.team1_score}-{pred.team2_score}"
                if result['correct']:
                    context['specific_details'].append(f"Nailed {game.team1} vs {game.team2}: predicted {pred_score}, actual {actual_score} ({result['points']}pts)")
                else:
                    context['specific_details'].append(f"Missed {game.team1} vs {game.team2}: predicted {pred_score}, actual {actual_score} ({result['points']}pts)")
            else:
                context['specific_details'].append(f"No prediction for {game.team1} vs {game.team2}: {actual_score} ({result['points']}pts default)")
    
    return context

def analyze_user_performance(user_id):
    """Analyze user performance and return category and metrics"""
    user = User.query.get(user_id)
    if not user:
        return None
    
    # Get all users for ranking comparison
    all_users = User.query.all()
    user_scores = [(u.get_total_score(), u.id) for u in all_users]
    user_scores.sort(reverse=True)
    user_rank = next((i + 1 for i, (score, uid) in enumerate(user_scores) if uid == user_id), len(user_scores))
    
    # Calculate metrics
    total_score = user.get_total_score()
    total_predictions = len([p for p in user.predictions if not p.is_default_prediction()])
    correct_predictions = len([p for p in user.predictions if p.points and p.points >= 2 and not p.is_default_prediction()])
    accuracy = round((correct_predictions / total_predictions * 100) if total_predictions > 0 else 0)
    
    # Recent performance (last 5 games)
    recent_predictions = db.session.query(Prediction).join(Game).filter(
        Prediction.user_id == user_id,
        Game.is_finished == True,
        Prediction.team1_score.isnot(None)  # Only real predictions
    ).order_by(Game.game_date.desc()).limit(5).all()
    
    recent_correct = len([p for p in recent_predictions if p.points and p.points >= 2])
    recent_total = len(recent_predictions)
    recent_accuracy = round((recent_correct / recent_total * 100) if recent_total > 0 else 0)
    
    # Determine performance category
    category = "newcomer"
    if total_predictions >= 5:
        if user_rank == 1:
            category = "champion"
        elif user_rank <= 3:
            category = "top_performer"
        elif accuracy >= 70:
            category = "accuracy_master"
        elif accuracy >= 50:
            category = "solid_predictor"
        elif recent_accuracy > accuracy and recent_total >= 3:
            category = "improving"
        elif recent_accuracy < accuracy - 10 and recent_total >= 3:
            category = "struggling"
        else:
            category = "average"
    
    return {
        'category': category,
        'total_score': total_score,
        'rank': user_rank,
        'total_players': len(all_users),
        'accuracy': accuracy,
        'recent_accuracy': recent_accuracy,
        'total_predictions': total_predictions,
        'recent_total': recent_total,
        'correct_predictions': correct_predictions,
        'recent_correct': recent_correct
    }

class AIMessageGenerator:
    """Generate AI-powered inspirational messages for players"""
    
    def __init__(self):
        self.daily_limit = 100
        self.cache_duration_hours = 24
        
        # Fallback templates by category (20-30 words each)
        self.fallback_templates = {
            'champion': [
                "🏆 Champion leading with {total_score} points! Your {accuracy}% accuracy dominates the competition. Outstanding work!",
                "👑 Top of the leaderboard! {correct_predictions} correct predictions show your volleyball expertise. Keep winning!",
                "🌟 Prediction champion! Your consistency at {accuracy}% accuracy keeps you ahead. Stay strong!"
            ],
            'top_performer': [
                "🥇 Rank #{rank} with {accuracy}% accuracy! Your top 3 position shows real prediction skills. Great job!",
                "🚀 Top 3 performance with {total_score} points! Your dedication to accurate predictions is paying off beautifully.",
                "⭐ Excellent #{rank} position! Your {correct_predictions} correct predictions keep you in contention. Amazing work!"
            ],
            'accuracy_master': [
                "🎯 Incredible {accuracy}% accuracy! Your precision with {correct_predictions} correct predictions is truly remarkable. Keep it up!",
                "🔥 {accuracy}% success rate - you're on fire! Your prediction skills are top tier. Fantastic work!",
                "💯 Amazing {accuracy}% accuracy! Your volleyball knowledge shines through every prediction. Well done!"
            ],
            'solid_predictor': [
                "👍 Solid {accuracy}% accuracy! Your {correct_predictions} correct predictions show consistent improvement. Keep building!",
                "📈 {total_score} points and climbing! Your steady approach to predictions is working well. Great progress!",
                "💪 Strong {accuracy}% accuracy! Your {correct_predictions} correct calls demonstrate good volleyball instincts. Keep going!"
            ],
            'improving': [
                "📈 Love the upward trend! Recent {recent_accuracy}% vs {accuracy}% overall shows real improvement. Keep growing!",
                "🌱 Great progress! Your recent predictions are much stronger. This improvement trend looks fantastic!",
                "🔥 You're heating up! Recent form shows {recent_accuracy}% accuracy. This momentum is excellent!"
            ],
            'struggling': [
                "💪 Tough stretch, but your {total_predictions} predictions show dedication. Champions bounce back - keep pushing!",
                "🌟 Every expert faces challenges! Your {correct_predictions} correct predictions prove you've got this. Stay confident!",
                "🎯 Difficult period, but your commitment shines through. Trust your instincts and keep making predictions!"
            ],
            'average': [
                "⚡ Solid position with {total_score} points! Your {accuracy}% accuracy has room to climb higher. Keep going!",
                "🎲 {total_predictions} predictions show real commitment! Your volleyball knowledge can take you further up the rankings.",
                "🌊 Steady progress with {accuracy}% accuracy! Every prediction brings you closer to the top. Keep predicting!"
            ],
            'newcomer': [
                "🎉 Welcome to predictions! Every expert started somewhere. Your volleyball journey begins with each new prediction!",
                "🌱 Fresh start, bright future! Each prediction teaches you more. Build your legacy one game at a time!",
                "🚀 New player energy! Jump in and start climbing the leaderboard. Your prediction adventure starts now!"
            ]
        }
    
    def get_or_create_message(self, user_id):
        """Get cached message or generate new one for user"""
        try:
            # Calculate current performance and results hashes
            perf_hash = calculate_performance_hash(user_id)
            results_hash = calculate_latest_results_hash(user_id)
            
            if not perf_hash:
                return self._get_fallback_message(user_id)
            
            # Check for existing cached message
            cached_message = PlayerMessage.query.filter_by(
                user_id=user_id
            ).filter(PlayerMessage.expires_at > datetime.utcnow()).first()
            
            # Check if we need new message due to new results or performance change
            need_new_message = (
                not cached_message or
                cached_message.performance_hash != perf_hash or
                (results_hash and cached_message.latest_results_hash != results_hash) or
                not cached_message.last_viewed_at or
                (datetime.utcnow() - cached_message.created_at).total_seconds() > 3600  # 1 hour
            )
            
            if cached_message and not need_new_message:
                return {
                    'text': cached_message.message_text,
                    'category': cached_message.message_category,
                    'cached': True,
                    'message_id': cached_message.id
                }
            
            # Check daily API limits
            if not self._can_make_api_call():
                return self._get_fallback_message(user_id)
            
            # Generate new message
            if GEMINI_AVAILABLE:
                try:
                    message_data = self._generate_gemini_message(user_id)
                    if message_data:
                        # Cache the message
                        self._cache_message(user_id, message_data, perf_hash, results_hash)
                        return message_data
                except Exception as e:
                    logging.error(f"Error generating Gemini message for user {user_id}: {str(e)}")
                    db.session.rollback()  # Rollback any failed transaction
            
            # Fallback to template
            return self._get_fallback_message(user_id)
            
        except Exception as e:
            logging.error(f"Database error in get_or_create_message for user {user_id}: {str(e)}")
            db.session.rollback()  # Rollback any failed transaction
            # Return a safe fallback message
            return {'text': '🎯 Ready for your next prediction!', 'category': 'general', 'cached': False}
    
    def mark_message_viewed(self, user_id):
        """Mark the current message as viewed by the user"""
        try:
            cached_message = PlayerMessage.query.filter_by(
                user_id=user_id
            ).filter(PlayerMessage.expires_at > datetime.utcnow()).first()
            
            if cached_message:
                cached_message.last_viewed_at = datetime.utcnow()
                db.session.commit()
        except Exception as e:
            logging.error(f"Error marking message viewed for user {user_id}: {str(e)}")
            db.session.rollback()
    
    def _can_make_api_call(self):
        """Check if we can make another API call today"""
        try:
            today = datetime.utcnow().date()
            usage = DailyApiUsage.query.filter_by(date=today).first()
            
            if not usage:
                # Create new usage record
                usage = DailyApiUsage(date=today, calls_made=0)
                db.session.add(usage)
                db.session.commit()
            
            return usage.calls_made < self.daily_limit
        except Exception as e:
            logging.error(f"Error checking API usage: {str(e)}")
            db.session.rollback()
            # Default to not allowing API calls if we can't check
            return False
    
    def _increment_api_usage(self):
        """Increment daily API usage counter"""
        try:
            today = datetime.utcnow().date()
            usage = DailyApiUsage.query.filter_by(date=today).first()
            
            if not usage:
                usage = DailyApiUsage(date=today, calls_made=1)
                db.session.add(usage)
            else:
                usage.calls_made += 1
            
            db.session.commit()
        except Exception as e:
            logging.error(f"Error incrementing API usage: {str(e)}")
            db.session.rollback()
    
    def _generate_gemini_message(self, user_id):
        """Generate message using Gemini API with detailed context"""
        # Get comprehensive context
        context = get_detailed_context_for_ai(user_id)
        if not context:
            return None
        
        user = context['user']
        analysis = context['analysis']
        specific_details = context['specific_details']
        
        # Build detailed context string
        details_text = "\n".join(specific_details) if specific_details else "No recent specific events"
        
        # Create highly detailed prompt for Gemini
        prompt = f"""You are generating a personalized update message for {user.name} in a volleyball prediction competition.

CURRENT SITUATION:
- Player: {user.name}
- Current Rank: #{analysis['rank']} out of {analysis['total_players']} players
- Total Points: {analysis['total_score']}
- Overall Accuracy: {analysis['accuracy']}% ({analysis['correct_predictions']} correct out of {analysis['total_predictions']} predictions)
- Recent Form: {analysis['recent_accuracy']}% accuracy in last {analysis['recent_total']} games
- Performance Category: {analysis['category']}

SPECIFIC RECENT EVENTS & INSIGHTS:
{details_text}

TASK: Create a highly specific, informative message (20-30 words) that:

1. REFERENCES SPECIFIC DETAILS from the context above (actual game results, scores, ranking changes, etc.)
2. Uses CONCRETE NUMBERS and FACTS, not generic phrases
3. Mentions actual TEAM NAMES, SCORES, or SPECIFIC ACHIEVEMENTS when available
4. Shows you understand their exact situation
5. Provides actionable insight or celebrates specific success

EXAMPLES OF GOOD SPECIFIC MESSAGES:
- "🎯 Nailed Brazil vs Italy 3-1! Your recent 85% accuracy jumped you to #3. Keep targeting upsets!"
- "📈 Climbed from #8 to #5 after Argentina prediction! Your 6-point Poland game was clutch. Momentum building!"
- "🔥 Perfect Serbia 3-0 call earned 6pts! You're #2 with 89% accuracy. One win from the lead!"

EXAMPLES OF BAD GENERIC MESSAGES:
- "Great job! Keep up the good work!" (too vague)
- "Your accuracy is improving!" (no specifics)
- "You're doing well in the competition!" (generic)

Requirements:
- 20-30 words exactly
- Include 1-2 relevant emojis  
- Reference specific recent games/results when available
- Use actual team names and scores from the context
- Be conversational and excited about their specific achievements

Generate the message now:"""

        try:
            # Configure Gemini API
            genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
            
            # Create model
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Generate content
            response = model.generate_content(prompt)
            
            message_text = response.text.strip().replace('"', '').replace("'", '')
            
            # Ensure message is within word limit
            words = message_text.split()
            if len(words) > 30:
                message_text = ' '.join(words[:30]) + '...'
            elif len(words) < 15:
                # If too short, try fallback
                return self._get_fallback_message(user_id)
            
            # Increment API usage
            self._increment_api_usage()
            
            return {
                'text': message_text,
                'category': analysis['category'],
                'cached': False
            }
            
        except Exception as e:
            logging.error(f"Gemini API error: {str(e)}")
            return None
    
    def _get_fallback_message(self, user_id):
        """Generate message using fallback templates with specific context"""
        context = get_detailed_context_for_ai(user_id)
        if not context:
            return {'text': '🎯 Ready to make some winning predictions!', 'category': 'general', 'cached': False}
        
        user = context['user']
        analysis = context['analysis']
        latest_results = context['latest_results']
        category = analysis['category']
        templates = self.fallback_templates.get(category, self.fallback_templates['average'])
        
        # Add specific context for templates
        format_data = {
            'name': user.name,
            'total_score': analysis['total_score'],
            'rank': analysis['rank'],
            'total_players': analysis['total_players'],
            'accuracy': analysis['accuracy'],
            'recent_accuracy': analysis['recent_accuracy'],
            'correct_predictions': analysis['correct_predictions'],
            'total_predictions': analysis['total_predictions'],
            'recent_total': analysis['recent_total']
        }
        
        # Add latest game context if available
        if latest_results and len(latest_results) > 0:
            latest = latest_results[0]
            game = latest['game']
            if latest['correct']:
                format_data['latest_game'] = f"nailed {game.team1} vs {game.team2}"
                format_data['latest_points'] = latest['points']
            else:
                format_data['latest_game'] = f"missed {game.team1} vs {game.team2}"
                format_data['latest_points'] = latest['points']
        else:
            format_data['latest_game'] = "ready for next match"
            format_data['latest_points'] = 0
        
        # Select template based on context
        if latest_results and latest_results[0]['correct']:
            # Positive recent result templates
            specific_templates = {
                'champion': "🏆 {latest_game} keeps you at #{rank}! {accuracy}% accuracy dominates with {total_score} points. Unstoppable!",
                'top_performer': "🥇 {latest_game} for {latest_points}pts! Rank #{rank} with {accuracy}% accuracy. Top tier performance!",
                'accuracy_master': "🎯 {latest_game} showcases your {accuracy}% precision! {correct_predictions} correct predictions prove your skills!",
                'solid_predictor': "👍 {latest_game} adds to your {total_score} points! {accuracy}% accuracy shows consistent improvement!",
                'improving': "📈 {latest_game} boosts recent {recent_accuracy}% vs {accuracy}% overall! Momentum building perfectly!",
                'struggling': "💪 {latest_game} for {latest_points}pts breaks the slide! Your dedication shows - keep pushing forward!",
                'average': "⚡ {latest_game} earns {latest_points}pts! Rank #{rank} with room to climb higher. Keep predicting!",
                'newcomer': "🎉 {latest_game} in early games! Great start building your prediction skills. Promising beginning!"
            }
            template = specific_templates.get(category, templates[0])
        else:
            # Use regular templates
            template = random.choice(templates)
        
        # Format with specific data
        try:
            message = template.format(**format_data)
        except KeyError:
            # Fallback if formatting fails
            template = random.choice(templates)
            message = template.format(**format_data)
        
        return {
            'text': message,
            'category': category,
            'cached': False
        }
    
    def _cache_message(self, user_id, message_data, perf_hash, results_hash=None):
        """Cache generated message in database"""
        try:
            expires_at = datetime.utcnow() + timedelta(hours=self.cache_duration_hours)
            
            # Remove old messages for this user
            PlayerMessage.query.filter_by(user_id=user_id).delete()
            
            # Create new cached message
            cached_message = PlayerMessage(
                user_id=user_id,
                message_text=message_data['text'],
                message_category=message_data['category'],
                performance_hash=perf_hash,
                latest_results_hash=results_hash,
                expires_at=expires_at,
                api_calls_used=1 if not message_data.get('cached', False) else 0
            )
            
            db.session.add(cached_message)
            db.session.commit()
        except Exception as e:
            logging.error(f"Error caching message for user {user_id}: {str(e)}")
            db.session.rollback()

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

def recalculate_all_points_with_defaults(n_position):
    """
    Recalculate all points with default points for non-predictions
    n_position: Nth worst position for default points (1 = worst, 2 = 2nd worst, etc.)
    """
    try:
        # Get all finished games
        finished_games = Game.query.filter(
            Game.is_finished == True,
            Game.team1_score.isnot(None),
            Game.team2_score.isnot(None)
        ).all()
        
        if not finished_games:
            return {"success": False, "error": "No finished games found"}
        
        # Get all users
        all_users = User.query.all()
        if not all_users:
            return {"success": False, "error": "No users found"}
        
        total_games = len(finished_games)
        processed_games = 0
        total_predictions_created = 0
        total_points_updated = 0
        
        for game in finished_games:
            # Get ALL predictions for this game
            all_predictions = Prediction.query.filter_by(game_id=game.id).all()
            
            # Separate real predictions (with actual scores) from default predictions (None scores)
            real_predictions = [p for p in all_predictions if not p.is_default_prediction()]
            default_predictions = [p for p in all_predictions if p.is_default_prediction()]
            
            # Recalculate points for REAL predictions only
            real_points = []
            for prediction in real_predictions:
                old_points = prediction.points
                new_points = calculate_points(prediction, game)
                prediction.points = new_points
                if old_points != new_points:
                    total_points_updated += 1
                if new_points is not None:
                    real_points.append(new_points)
            
            # Sort REAL points to find Nth worst (ascending order)
            real_points.sort()
            
            # Determine default points for non-predictors based on REAL predictions only
            if len(real_points) >= n_position:
                default_points = real_points[n_position - 1]  # n_position-1 because 0-indexed
            elif len(real_points) > 0:
                # If not enough real predictions exist, use the worst available
                default_points = real_points[0]
            else:
                # No real predictions exist for this game, default to 0
                default_points = 0
            
            # Update existing default predictions with new default points
            for prediction in default_predictions:
                if prediction.points != default_points:
                    prediction.points = default_points
                    total_points_updated += 1
            
            # Find users who don't have ANY prediction (real or default) for this game
            existing_user_ids = {p.user_id for p in all_predictions}
            non_predictors = [user for user in all_users if user.id not in existing_user_ids]
            
            # Create NEW default predictions for users who have none
            for user in non_predictors:
                new_prediction = Prediction(
                    user_id=user.id,
                    game_id=game.id,
                    team1_score=None,  # No actual prediction made
                    team2_score=None,  # No actual prediction made
                    predicted_winner=None,
                    points=default_points
                )
                db.session.add(new_prediction)
                total_predictions_created += 1
            
            processed_games += 1
        
        # Commit all changes
        db.session.commit()
        
        return {
            "success": True,
            "message": f"Recalculation completed successfully!",
            "details": {
                "games_processed": processed_games,
                "predictions_created": total_predictions_created,
                "points_updated": total_points_updated,
                "n_position": n_position
            }
        }
        
    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": f"Error during recalculation: {str(e)}"}

def calculate_tournament_points(prediction, tournament_config):
    """Calculate points for tournament predictions"""
    if not tournament_config.are_results_available():
        return 0

    points = 0

    # Get user's predictions as a list
    user_predictions = [prediction.first_place, prediction.second_place, prediction.third_place]

    # Check if user mentioned actual 1st place anywhere in their predictions - 15 points
    if tournament_config.first_place_result in user_predictions:
        points += 15
        # Additional 15 points if predicted in exact 1st place (total 30 points)
        if prediction.first_place == tournament_config.first_place_result:
            points += 15

    # Check if user mentioned actual 2nd place anywhere in their predictions - 15 points
    if tournament_config.second_place_result in user_predictions:
        points += 15
        # Additional 5 points if predicted in exact 2nd place
        if prediction.second_place == tournament_config.second_place_result:
            points += 5

    # Check if user mentioned actual 3rd place anywhere in their predictions - 15 points
    if tournament_config.third_place_result in user_predictions:
        points += 15
        # Additional 5 points if predicted in exact 3rd place
        if prediction.third_place == tournament_config.third_place_result:
            points += 5

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
    # Get filter parameters
    selected_date = request.args.get('date')
    selected_round = request.args.get('round')
    
    # Smart default filter: today/tomorrow if games exist, otherwise upcoming
    show_filter = request.args.get('filter')
    if not show_filter:
        # Check if there are games today or tomorrow
        current_date = get_riga_time().date()
        tomorrow_date = current_date + timedelta(days=1)
        today_tomorrow_games = Game.query.filter(
            db.func.date(Game.game_date) >= current_date,
            db.func.date(Game.game_date) <= tomorrow_date
        ).count()
        
        show_filter = 'today_tomorrow' if today_tomorrow_games > 0 else 'upcoming'
    
    # Base query
    games_query = Game.query
    
    # Apply filters
    if show_filter == 'today_tomorrow':
        # Default filter: show games for today and tomorrow only
        current_date = get_riga_time().date()
        tomorrow_date = current_date + timedelta(days=1)
        games_query = games_query.filter(
            db.func.date(Game.game_date) >= current_date,
            db.func.date(Game.game_date) <= tomorrow_date
        )
    elif show_filter == 'all':
        # Show all games
        pass  # No additional filtering
    elif show_filter == 'upcoming':
        # Show only upcoming games (not finished)
        games_query = games_query.filter(Game.is_finished == False)
    elif show_filter == 'finished':
        # Show only finished games
        games_query = games_query.filter(Game.is_finished == True)
    
    # Apply date filter if provided
    if selected_date:
        try:
            filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            games_query = games_query.filter(db.func.date(Game.game_date) == filter_date)
        except ValueError:
            flash('Invalid date format', 'error')
    
    # Apply round filter if provided
    if selected_round:
        games_query = games_query.filter(Game.round_name.ilike(f'%{selected_round}%'))
    
    # Get filtered games sorted by game time, earliest first
    games = games_query.order_by(Game.game_date.asc()).all()
    
    # Get unique dates and rounds for filter dropdowns
    all_games = Game.query.all()
    unique_dates = sorted(list(set(game.game_date.date() for game in all_games)))
    unique_rounds = sorted(list(set(game.round_name for game in all_games)))
    
    return render_template('predictions.html', 
                         games=games,
                         unique_dates=unique_dates,
                         unique_rounds=unique_rounds,
                         show_filter=show_filter,
                         selected_date=selected_date,
                         selected_round=selected_round)

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
            'all_predictions_filled': user.get_all_predictions_filled(),
            'total_predictions': user.get_total_predictions(),
            'correct_predictions': user.get_correct_predictions(),
            'accuracy': user.get_accuracy_percentage()
        }
        user_stats.append(stats)

    user_stats.sort(key=lambda x: x['total_score'], reverse=True)
    return render_template('leaderboard.html', users=user_stats)

@app.route('/race-chart')
@login_required
def race_chart():
    """Display cumulative points race chart"""
    users = User.query.all()
    games = Game.query.filter_by(is_finished=True).order_by(Game.game_date).all()

    logging.info(f"Race chart page: {len(users)} users, {len(games)} finished games")

    return render_template('race_chart.html', users=users, games=games)

@app.route('/api/race-chart-data')
@login_required
def get_race_chart_data():
    """API endpoint to get cumulative points data for race chart"""
    try:
        logging.info("Race chart data request received")
        # Get query parameters for filtering
        selected_user_ids = request.args.getlist('users[]')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        logging.info(f"Filters - Users: {selected_user_ids}, Start: {start_date}, End: {end_date}")

        # Get all finished games ordered by date
        games_query = Game.query.filter_by(is_finished=True).order_by(Game.game_date)
        logging.info("Initial games query created")

        # Apply date filtering if provided
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                games_query = games_query.filter(Game.game_date >= start_dt)
            except ValueError:
                pass

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                games_query = games_query.filter(Game.game_date < end_dt)
            except ValueError:
                pass

        games = games_query.all()
        logging.info(f"Found {len(games)} finished games")

        # If no finished games, return empty data structure
        if not games:
            logging.warning("No finished games found, returning empty chart data")
            return jsonify({
                'success': True,
                'data': {
                    'games': [],
                    'players': []
                }
            })

        # Get users to include in chart
        if selected_user_ids:
            try:
                user_ids = [int(uid) for uid in selected_user_ids]
                users = User.query.filter(User.id.in_(user_ids)).all()
                logging.info(f"Selected {len(users)} specific users")
            except ValueError as e:
                logging.error(f"Error parsing user IDs: {e}")
                users = User.query.all()
        else:
            users = User.query.all()
            logging.info(f"Using all {len(users)} users")

        # Build cumulative data
        chart_data = {
            'games': [],
            'players': []
        }

        # Game labels and dates
        for i, game in enumerate(games):
            try:
                game_label = f"{game.team1} vs {game.team2}"
                chart_data['games'].append({
                    'id': game.id,
                    'label': game_label,
                    'date': game.game_date.strftime('%Y-%m-%d %H:%M'),
                    'round': game.round_name
                })
            except Exception as e:
                logging.error(f"Error processing game {i}: {e}")

        logging.info(f"Processed {len(chart_data['games'])} games for chart")

        # Player data with cumulative points
        colors = [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
            '#FF9F40', '#C9CBCF', '#E74C3C', '#2ECC71', '#F39C12',
            '#9B59B6', '#1ABC9C', '#34495E', '#E67E22', '#95A5A6'
        ]

        # Sort users by total score for better color assignment
        try:
            users_sorted = sorted(users, key=lambda u: u.get_total_score(), reverse=True)
            logging.info(f"Sorted {len(users_sorted)} users by score")
        except Exception as e:
            logging.error(f"Error sorting users: {e}")
            users_sorted = users

        # First, calculate cumulative points for all users for each game
        users_cumulative_data = []
        for user in users_sorted:
            try:
                cumulative_points = 0
                tournament_points = user.tournament_prediction.points_earned if user.tournament_prediction else 0
                points_data = []

                # Calculate cumulative points for each game
                for game in games:
                    # Find user's prediction for this game
                    prediction = next((p for p in user.predictions if p.game_id == game.id), None)

                    if prediction and prediction.points is not None:
                        cumulative_points += prediction.points

                    points_data.append(cumulative_points)

                users_cumulative_data.append({
                    'user': user,
                    'points_data': points_data,
                    'tournament_points': tournament_points,
                    'total_score': user.get_total_score()
                })

            except Exception as e:
                logging.error(f"Error processing user {user.name}: {e}")

        # Now calculate positions for each game
        for i, user_data in enumerate(users_cumulative_data):
            try:
                user = user_data['user']
                position_data = []

                # Calculate position for each game
                for game_index in range(len(games)):
                    # Get all users' scores at this point
                    scores_at_game = [(ud['points_data'][game_index], idx) for idx, ud in enumerate(users_cumulative_data)]
                    # Sort by score (descending) to get rankings
                    scores_at_game.sort(key=lambda x: x[0], reverse=True)

                    # Find this user's position
                    user_position = next(pos + 1 for pos, (score, idx) in enumerate(scores_at_game) if idx == i)
                    position_data.append(user_position)

                player_data = {
                    'name': user.name,
                    'id': user.id,
                    'color': colors[i % len(colors)],
                    'data': position_data,  # Now contains positions instead of points
                    'points_data': user_data['points_data'],  # Keep points for tooltips
                    'tournament_points': user_data['tournament_points'],
                    'total_score': user_data['total_score'],
                    'final_position': i + 1
                }

                chart_data['players'].append(player_data)

            except Exception as e:
                logging.error(f"Error processing user {user.name}: {e}")

        logging.info(f"Successfully processed {len(chart_data['players'])} players with position data")

        return jsonify({'success': True, 'data': chart_data})

    except Exception as e:
        logging.error(f"Error getting race chart data: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to load chart data'})

@app.route('/api/user_message')
@login_required
def get_user_message():
    """API endpoint to get AI-generated message for current user asynchronously"""
    try:
        ai_generator = AIMessageGenerator()
        current_user_message = ai_generator.get_or_create_message(current_user.id)
        # Mark message as viewed when user requests it
        ai_generator.mark_message_viewed(current_user.id)
        return jsonify({'success': True, 'message': current_user_message})
    except Exception as e:
        logging.error(f"Error getting AI message for current user {current_user.id}: {str(e)}")
        fallback_message = {'text': '🎯 Keep making those predictions!', 'category': 'general', 'cached': False}
        return jsonify({'success': True, 'message': fallback_message})

@app.route('/highlights')
@login_required
def highlights():
    """Display volleyball highlights from the latest games"""
    try:
        # Get the 2 most recent completed games
        recent_games = Game.query.filter(
            Game.is_finished == True,
            Game.team1_score.isnot(None),
            Game.team2_score.isnot(None)
        ).order_by(Game.game_date.desc()).limit(2).all()

        games_with_highlights = []

        for game in recent_games:
            # Get existing highlights for this game
            existing_highlights = GameHighlight.query.filter_by(
                game_id=game.id,
                is_active=True
            ).order_by(
                GameHighlight.is_featured.desc(),
                GameHighlight.view_count.desc()
            ).limit(5).all()

            # If no highlights exist, try to search for some
            if not existing_highlights:
                from youtube_service import search_game_highlights
                videos = search_game_highlights(game.id)

                # Save the best videos as highlights
                for video in videos[:3]:  # Save top 3
                    try:
                        highlight = GameHighlight(
                            game_id=game.id,
                            youtube_url=video['youtube_url'],
                            youtube_video_id=video['video_id'],
                            title=video['title'],
                            description=video['description'][:500] if video['description'] else '',
                            thumbnail_url=video['thumbnail_url'],
                            duration=video.get('duration', ''),
                            channel_name=video['channel_name'],
                            view_count=video.get('view_count', 0),
                            upload_date=video['upload_date'],
                            auto_detected=True
                        )
                        db.session.add(highlight)
                        existing_highlights.append(highlight)
                    except Exception as e:
                        logging.error(f"Error saving highlight: {e}")
                        continue

                try:
                    db.session.commit()
                except Exception as e:
                    logging.error(f"Error committing highlights: {e}")
                    db.session.rollback()

            games_with_highlights.append({
                'game': game,
                'highlights': existing_highlights[:5]  # Limit to 5 highlights per game
            })

        # Get featured videos from database (admin-managed)
        featured_videos = FeaturedVideo.query.filter_by(is_active=True).order_by(
            FeaturedVideo.display_order.asc(),
            FeaturedVideo.created_at.desc()
        ).limit(6).all()

        # Convert to format expected by template
        featured_videos_data = []
        for video in featured_videos:
            featured_videos_data.append({
                'title': video.title,
                'youtube_url': video.youtube_url,
                'thumbnail_url': video.thumbnail_url,
                'channel_name': video.channel_name,
                'upload_date': video.upload_date,
                'view_count': video.view_count,
                'duration': video.format_duration()
            })

        return render_template('highlights.html',
                             games_with_highlights=games_with_highlights,
                             featured_videos=featured_videos_data)

    except Exception as e:
        logging.error(f"Error loading highlights page: {e}")
        flash('Error loading highlights. Please try again later.', 'error')
        return redirect(url_for('index'))

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
    # Get unfinished games (nearest first) and finished games (latest first)
    unfinished_games = Game.query.filter_by(is_finished=False).order_by(Game.game_date.asc()).all()
    finished_games = Game.query.filter_by(is_finished=True).order_by(Game.game_date.desc()).all()

    # Combine lists: unfinished games first, then finished games
    games = unfinished_games + finished_games
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
    
    # Get recalculation config
    recalculation_config = RecalculationConfig.get_current_config()
    
    return render_template('admin.html', 
                         games=games, 
                         users=users, 
                         tournament_config=tournament_config,
                         tournament_predictions=tournament_predictions,
                         tournament_teams=tournament_teams,
                         teams=teams,
                         recalculation_config=recalculation_config)

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
                            prediction_deadline = game_date - timedelta(minutes=30)
                else:
                    # Default: 30 minutes before game start
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
        logging.debug(f"Bulk delete request received for game IDs: {game_ids}")
        
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
                logging.debug(f"Marked game {game_id} for deletion")
                
            except Exception as e:
                error_msg = f"Error processing game {game_id}: {str(e)}"
                errors.append(error_msg)
                logging.error(error_msg)
                continue
        
        if deleted_count > 0:
            db.session.commit()
            logging.info(f"Database commit completed. Deleted: {deleted_count}")
        
        if deleted_count > 0:
            flash(f'Successfully deleted {deleted_count} games', 'success')
        
        
        if errors:
            flash(f'Errors occurred: {"; ".join(errors)}', 'error')
        
        if deleted_count == 0:
            flash('No games were deleted', 'info')
            
    except Exception as e:
        db.session.rollback()
        error_msg = f"Bulk delete failed: {str(e)}"
        logging.error(error_msg)
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

@app.route('/tournament-predictions/all')
@login_required
def all_tournament_predictions():
    # Get tournament config to check if predictions are closed
    tournament_config = TournamentConfig.query.first()
    if not tournament_config:
        flash('Tournament predictions are not yet available. Please contact admin.', 'warning')
        return redirect(url_for('index'))
    
    # Only show all predictions if deadline has passed
    if tournament_config.is_prediction_open():
        flash('Tournament predictions are still open. All predictions will be visible after the deadline.', 'info')
        return redirect(url_for('tournament_predictions'))
    
    # Get all tournament predictions with user information, ordered by user name
    all_predictions = (TournamentPrediction.query
                      .join(User)
                      .order_by(User.name)
                      .all())
    
    # Get statistics
    total_participants = len(all_predictions)
    
    # If tournament results are available, calculate some stats
    stats = {
        'total_participants': total_participants,
        'results_available': tournament_config.are_results_available()
    }
    
    if tournament_config.are_results_available():
        # Count correct predictions for each position
        first_place_correct = len([p for p in all_predictions if p.first_place == tournament_config.first_place_result])
        second_place_mentioned = len([p for p in all_predictions if tournament_config.second_place_result in [p.first_place, p.second_place, p.third_place]])
        third_place_mentioned = len([p for p in all_predictions if tournament_config.third_place_result in [p.first_place, p.second_place, p.third_place]])
        
        stats.update({
            'first_place_correct': first_place_correct,
            'second_place_mentioned': second_place_mentioned, 
            'third_place_mentioned': third_place_mentioned,
            'average_points': sum(p.points_earned for p in all_predictions) / max(total_participants, 1)
        })
    
    return render_template('all_tournament_predictions.html',
                         tournament_config=tournament_config,
                         all_predictions=all_predictions,
                         stats=stats)

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
    all_deadline_passed_predictions = []
    for pred in all_predictions:
        deadline = to_riga_time(pred.game.prediction_deadline)
        if current_time >= deadline:
            all_deadline_passed_predictions.append(pred)
    
    # Include all predictions for detailed display (both real and default predictions)
    predictions = all_deadline_passed_predictions
    
    # Calculate user stats using the updated methods
    total_predictions = user.get_total_predictions()
    correct_predictions = user.get_correct_predictions()
    # Use all deadline-passed predictions (including default) for total points calculation
    total_points = sum([p.points for p in all_deadline_passed_predictions if p.points is not None])
    accuracy = user.get_accuracy_percentage()
    
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
    
    # Get all predictions for this game, but only show real predictions
    all_predictions = (Prediction.query
                      .filter_by(game_id=game_id)
                      .join(User)
                      .order_by(User.name)
                      .all())
    
    # Include all predictions for detailed display (both real and default predictions)
    predictions = all_predictions
    
    # Calculate some stats based on real predictions only
    real_predictions = [p for p in all_predictions if not p.is_default_prediction()]
    total_predictions = len(real_predictions)
    if game.is_finished:
        correct_predictions = len([p for p in real_predictions if p.points and p.points > 0])
        perfect_predictions = len([p for p in real_predictions if p.points == 6])
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
        all_predictions = Prediction.query.filter_by(game_id=game.id).join(User).all()
        
        # Include both real and default predictions for display, but separate them
        predictions_data = []
        for pred in all_predictions:
            predictions_data.append({
                'user_name': pred.user.name,
                'team1_score': pred.team1_score,
                'team2_score': pred.team2_score,
                'predicted_winner': pred.predicted_winner,
                'points': pred.points
            })
        
        # Count only real predictions for the summary
        real_predictions_count = len([pred for pred in all_predictions if not pred.is_default_prediction()])
        
        games_with_predictions.append({
            'game': game,
            'predictions': predictions_data,
            'total_predictions': real_predictions_count  # Still counts only real predictions
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

@app.route('/admin/manage_prediction', methods=['POST'])
@login_required
@admin_required
def admin_manage_prediction():
    user_id = request.form.get('user_id')
    game_id = request.form.get('game_id')
    team1_score = request.form.get('team1_score')
    team2_score = request.form.get('team2_score')
    
    if not all([user_id, game_id, team1_score, team2_score]):
        if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'error': 'Please fill in all fields'}), 400
        flash('Please fill in all fields', 'error')
        return redirect(url_for('admin'))
    
    try:
        # Convert all form data to appropriate types
        user_id = int(user_id)
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
        error_msg = 'Invalid volleyball score. Winner must have 3 sets, loser 0-2 sets.' if "Invalid volleyball score" in str(e) else 'Please enter valid values'
        if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('admin'))
    
    # Verify user and game exist
    user = User.query.get(user_id)
    game = Game.query.get(game_id)
    
    if not user:
        if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'error': 'User not found'}), 404
        flash('User not found', 'error')
        return redirect(url_for('admin'))

    if not game:
        if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'error': 'Game not found'}), 404
        flash('Game not found', 'error')
        return redirect(url_for('admin'))
    
    # Check if prediction already exists
    existing = Prediction.query.filter_by(user_id=user_id, game_id=game_id).first()
    
    predicted_winner = game.team1 if team1_score > team2_score else game.team2
    
    if existing:
        existing.team1_score = team1_score
        existing.team2_score = team2_score
        existing.predicted_winner = predicted_winner
        
        # Recalculate points if game is finished
        if game.is_finished:
            existing.points = calculate_points(existing, game)
        
        success_msg = f'Prediction updated for {user.name}: {game.team1} vs {game.team2}'
        action = 'updated'
    else:
        prediction = Prediction(
            user_id=user_id,
            game_id=game_id,
            team1_score=team1_score,
            team2_score=team2_score,
            predicted_winner=predicted_winner
        )

        # Calculate points if game is finished
        if game.is_finished:
            prediction.points = calculate_points(prediction, game)

        db.session.add(prediction)
        success_msg = f'Prediction created for {user.name}: {game.team1} vs {game.team2}'
        action = 'created'

    db.session.commit()

    # Return JSON response for AJAX calls
    if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
        return jsonify({'success': True, 'message': success_msg, 'action': action})

    flash(success_msg, 'success')
    return redirect(url_for('admin'))

@app.route('/admin/recalculate_points', methods=['POST'])
@login_required
@admin_required
def admin_recalculate_points():
    """Handle points recalculation with default points for non-predictors"""
    try:
        # Get the N position from form data
        n_position = request.form.get('default_points_position')
        if not n_position:
            return jsonify({"success": False, "error": "Default points position is required"})
        
        n_position = int(n_position)
        if n_position < 1:
            return jsonify({"success": False, "error": "Position must be at least 1"})
        
        # Save configuration
        config = RecalculationConfig.get_current_config()
        config.default_points_position = n_position
        config.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Perform recalculation
        result = recalculate_all_points_with_defaults(n_position)
        
        return jsonify(result)
        
    except ValueError:
        return jsonify({"success": False, "error": "Invalid position value"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Server error: {str(e)}"})

@app.route('/admin/recalculation_config', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_recalculation_config():
    """Get or update recalculation configuration"""
    if request.method == 'GET':
        config = RecalculationConfig.get_current_config()
        return jsonify({
            "success": True,
            "default_points_position": config.default_points_position
        })
    
    elif request.method == 'POST':
        try:
            n_position = int(request.form.get('default_points_position', 1))
            if n_position < 1:
                return jsonify({"success": False, "error": "Position must be at least 1"})
            
            config = RecalculationConfig.get_current_config()
            config.default_points_position = n_position
            config.updated_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({"success": True, "message": "Configuration updated successfully"})
            
        except ValueError:
            return jsonify({"success": False, "error": "Invalid position value"})
        except Exception as e:
            return jsonify({"success": False, "error": f"Server error: {str(e)}"})

@app.route('/admin/get_prediction', methods=['GET'])
@login_required
@admin_required
def admin_get_prediction():
    user_id = request.args.get('user_id')
    game_id = request.args.get('game_id')
    
    if not user_id or not game_id:
        return jsonify({'success': False, 'error': 'Missing parameters'})
    
    try:
        user_id = int(user_id)
        game_id = int(game_id)
        
        prediction = Prediction.query.filter_by(user_id=user_id, game_id=game_id).first()
        
        if prediction:
            return jsonify({
                'success': True,
                'team1_score': prediction.team1_score,
                'team2_score': prediction.team2_score,
                'points': prediction.points
            })
        else:
            return jsonify({
                'success': True,
                'team1_score': '',
                'team2_score': '',
                'points': None
            })
            
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid parameters'})


# Background scheduler for automatic result updates
def auto_update_results():
    """Background task to automatically update game results"""
    with app.app_context():
        try:
            current_time = get_riga_time()
            three_hours_ago = current_time - timedelta(hours=3)

            # Find games that started 3+ hours ago, not finished, not attempted
            pending_games = Game.query.filter(
                Game.is_finished == False,
                Game.auto_update_attempted == False,
                Game.game_date <= three_hours_ago
            ).limit(5).all()  # Limit to 5 games per run to avoid API limits

            if pending_games:
                logging.info(f"Auto-update: Found {len(pending_games)} games to check")

                # Check SerpAPI usage before proceeding
                from result_fetcher import get_monthly_usage_info
                usage_info = get_monthly_usage_info()

                if not usage_info.get('can_search', False):
                    logging.warning(f"Auto-update: Monthly SerpAPI limit reached ({usage_info.get('searches_used', 0)}/{usage_info.get('monthly_limit', 0)})")
                    return

                # Try to update each game
                successful_updates = 0
                for game in pending_games:
                    try:
                        from result_fetcher import update_game_with_result
                        success = update_game_with_result(game.id, force=False)

                        if success:
                            successful_updates += 1
                            logging.info(f"Auto-update: Successfully updated {game.team1} vs {game.team2}")
                        else:
                            logging.info(f"Auto-update: No result found for {game.team1} vs {game.team2}")

                    except Exception as e:
                        logging.error(f"Auto-update: Error updating game {game.id}: {e}")
                        continue

                if successful_updates > 0:
                    logging.info(f"Auto-update: Successfully updated {successful_updates}/{len(pending_games)} games")
            else:
                logging.debug("Auto-update: No games pending auto-update")

        except Exception as e:
            logging.error(f"Auto-update: Error in background task: {e}")


def auto_detect_highlights():
    """Background task to automatically detect and save volleyball highlights"""
    with app.app_context():
        try:
            # Check if YouTube API is available
            youtube_api_key = os.environ.get('YOUTUBE_API_KEY')
            if not youtube_api_key:
                logging.debug("YouTube API key not available - skipping highlight detection")
                return

            # Get the most recent completed games that don't have highlights yet
            # Focus on the latest games that would appear on the highlights page
            all_recent_games = db.session.query(Game).filter(
                Game.is_finished == True,
                Game.team1_score.isnot(None),
                Game.team2_score.isnot(None)
            ).order_by(Game.game_date.desc()).limit(5).all()  # Get latest 5 completed games

            # Filter to only those without highlights
            games_without_highlights = []
            for game in all_recent_games:
                existing_highlights = db.session.query(GameHighlight).filter_by(game_id=game.id).count()
                if existing_highlights == 0:
                    games_without_highlights.append(game)

                # Limit to max 2 games per run (since we show 2 on highlights page)
                if len(games_without_highlights) >= 2:
                    break

            if not games_without_highlights:
                logging.debug("Auto-highlight: No games without highlights found")
                return

            logging.info(f"Auto-highlight: Found {len(games_without_highlights)} games without highlights")

            from youtube_service import search_game_highlights

            highlights_added = 0
            for game in games_without_highlights:
                try:
                    logging.info(f"Auto-highlight: Searching highlights for {game.team1} vs {game.team2}")

                    # Search for highlights
                    videos = search_game_highlights(game.id)

                    if videos:
                        # Save the best highlights (top 3)
                        for video in videos[:3]:
                            try:
                                # Check if this video already exists for any game
                                existing = GameHighlight.query.filter_by(
                                    youtube_video_id=video['video_id']
                                ).first()

                                if existing:
                                    logging.debug(f"Video {video['video_id']} already exists, skipping")
                                    continue

                                highlight = GameHighlight(
                                    game_id=game.id,
                                    youtube_url=video['youtube_url'],
                                    youtube_video_id=video['video_id'],
                                    title=video['title'][:200],  # Truncate title if too long
                                    description=video['description'][:500] if video['description'] else '',
                                    thumbnail_url=video['thumbnail_url'],
                                    duration=video.get('duration', ''),
                                    channel_name=video['channel_name'],
                                    view_count=video.get('view_count', 0),
                                    upload_date=video['upload_date'],
                                    auto_detected=True,
                                    video_type='highlight'
                                )
                                db.session.add(highlight)
                                highlights_added += 1

                                logging.info(f"Auto-highlight: Added highlight '{video['title'][:50]}...' for {game.team1} vs {game.team2}")

                            except Exception as e:
                                logging.error(f"Auto-highlight: Error saving highlight: {e}")
                                continue

                        try:
                            db.session.commit()
                        except Exception as e:
                            logging.error(f"Auto-highlight: Error committing highlights for game {game.id}: {e}")
                            db.session.rollback()

                    else:
                        logging.info(f"Auto-highlight: No highlights found for {game.team1} vs {game.team2}")

                except Exception as e:
                    logging.error(f"Auto-highlight: Error processing game {game.id}: {e}")
                    continue

            if highlights_added > 0:
                logging.info(f"Auto-highlight: Successfully added {highlights_added} highlights")

        except Exception as e:
            logging.error(f"Auto-highlight: Error in background task: {e}")


def init_scheduler():
    """Initialize the background scheduler for automatic result updates"""
    try:
        # Only run scheduler if SerpAPI is available
        serpapi_key = os.environ.get('SERPAPI_API_KEY')
        if not serpapi_key:
            logging.info("SerpAPI key not found - automatic result updates disabled")
            return

        # Check if scheduler should run (avoid in development/debug mode)
        if os.environ.get('FLASK_ENV') == 'development':
            logging.info("Development mode detected - automatic result updates disabled")
            return

        scheduler = BackgroundScheduler()

        # Check for updates every 2 hours
        scheduler.add_job(
            func=auto_update_results,
            trigger=IntervalTrigger(hours=2),
            id='auto_update_results',
            name='Automatic volleyball result updates',
            replace_existing=True
        )

        # Check for highlights every 4 hours (offset by 1 hour from result updates)
        scheduler.add_job(
            func=auto_detect_highlights,
            trigger=IntervalTrigger(hours=4),
            id='auto_detect_highlights',
            name='Automatic volleyball highlight detection',
            replace_existing=True
        )

        scheduler.start()
        logging.info("Background scheduler started - automatic result updates (every 2 hours) and highlight detection (every 4 hours) enabled")

        # Shut down the scheduler when exiting the app
        atexit.register(lambda: scheduler.shutdown())

    except Exception as e:
        logging.error(f"Failed to initialize background scheduler: {e}")


# Initialize database
with app.app_context():
    try:
        # Create all tables (this will only create missing tables)
        db.create_all()
        logging.info("Database tables initialized successfully")
        
        # Check if we need to add the password_reset_required column
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'user' in existing_tables:
            user_columns = [col['name'] for col in inspector.get_columns('user')]
            if 'password_reset_required' not in user_columns:
                logging.info("Adding password_reset_required column to existing User table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE "user" ADD COLUMN password_reset_required BOOLEAN DEFAULT FALSE'))
                    conn.commit()
                logging.info("password_reset_required column added successfully")
        
        # Check if we need to add the country_code column to tournament_team table
        if 'tournament_team' in existing_tables:
            team_columns = [col['name'] for col in inspector.get_columns('tournament_team')]
            if 'country_code' not in team_columns:
                logging.info("Adding country_code column to existing TournamentTeam table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE tournament_team ADD COLUMN country_code VARCHAR(2)'))
                    conn.commit()
                logging.info("country_code column added successfully")
                
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
                logging.info("Updated country codes for existing teams")
        
        # Check if we need to add new columns to player_message table
        if 'player_message' in existing_tables:
            player_message_columns = [col['name'] for col in inspector.get_columns('player_message')]
            
            # Add last_viewed_at column if missing
            if 'last_viewed_at' not in player_message_columns:
                logging.info("Adding last_viewed_at column to existing PlayerMessage table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE player_message ADD COLUMN last_viewed_at TIMESTAMP'))
                    conn.commit()
                logging.info("last_viewed_at column added successfully")
            
            # Add latest_results_hash column if missing
            if 'latest_results_hash' not in player_message_columns:
                logging.info("Adding latest_results_hash column to existing PlayerMessage table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE player_message ADD COLUMN latest_results_hash VARCHAR(32)'))
                    conn.commit()
                logging.info("latest_results_hash column added successfully")

        # Check if we need to add SerpApi columns to game table
        if 'game' in existing_tables:
            game_columns = [col['name'] for col in inspector.get_columns('game')]

            # Add auto_update_attempted column if missing
            if 'auto_update_attempted' not in game_columns:
                logging.info("Adding auto_update_attempted column to existing Game table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE game ADD COLUMN auto_update_attempted BOOLEAN DEFAULT FALSE'))
                    conn.commit()
                logging.info("auto_update_attempted column added successfully")

            # Add auto_update_timestamp column if missing
            if 'auto_update_timestamp' not in game_columns:
                logging.info("Adding auto_update_timestamp column to existing Game table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE game ADD COLUMN auto_update_timestamp TIMESTAMP'))
                    conn.commit()
                logging.info("auto_update_timestamp column added successfully")

            # Add result_source column if missing
            if 'result_source' not in game_columns:
                logging.info("Adding result_source column to existing Game table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE game ADD COLUMN result_source VARCHAR(50) DEFAULT 'manual'"))
                    conn.commit()
                logging.info("result_source column added successfully")

            # Add serpapi_search_used column if missing
            if 'serpapi_search_used' not in game_columns:
                logging.info("Adding serpapi_search_used column to existing Game table...")
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE game ADD COLUMN serpapi_search_used BOOLEAN DEFAULT FALSE'))
                    conn.commit()
                logging.info("serpapi_search_used column added successfully")

        # Check if we need to create the game_highlight table
        if 'game_highlight' not in existing_tables:
            logging.info("Creating GameHighlight table...")
            # The table will be created automatically by db.create_all() above
            # But we log it for transparency
            try:
                # Verify the table was created
                db.session.execute(db.text('SELECT 1 FROM game_highlight LIMIT 1'))
                logging.info("GameHighlight table created successfully")
            except Exception:
                # Table doesn't exist yet, which is expected on first run
                logging.info("GameHighlight table will be created by db.create_all()")

        # Check if we need to create the featured_video table
        if 'featured_video' not in existing_tables:
            logging.info("Creating FeaturedVideo table...")
            # The table will be created automatically by db.create_all() above
            # But we log it for transparency
            try:
                # Verify the table was created
                db.session.execute(db.text('SELECT 1 FROM featured_video LIMIT 1'))
                logging.info("FeaturedVideo table created successfully")
            except Exception:
                # Table doesn't exist yet, which is expected on first run
                logging.info("FeaturedVideo table will be created by db.create_all()")

        # Initialize logging configuration
        try:
            current_log_level = LoggingConfig.get_current_log_level()
            numeric_level = getattr(logging, current_log_level.upper(), logging.INFO)
            logging.getLogger().setLevel(numeric_level)
            logging.info(f"Logging initialized at {current_log_level} level")
        except Exception as log_error:
            logging.warning(f"Failed to initialize logging config: {log_error}")
            # Set default log level
            logging.getLogger().setLevel(logging.INFO)

        # Initialize background scheduler for automatic result updates
        # init_scheduler()  # Disabled - run updates manually from admin page

    except Exception as e:
        logging.error(f"Database initialization error: {e}")
        # Continue anyway - the app might still work with existing tables

@app.route('/potential-points')
@login_required
def potential_points():
    """Show potential points for the earliest unfinished game with passed deadline"""

    # Find unfinished game with earliest passed deadline
    current_time = get_riga_time()

    try:
        # Debug logging for what-if analysis
        logging.debug(f"What-if analysis - Current time: {current_time}")

        all_games = Game.query.all()
        unfinished_games = Game.query.filter_by(is_finished=False).all()

        logging.debug(f"What-if analysis - Total games: {len(all_games)}")
        logging.debug(f"What-if analysis - Unfinished games: {len(unfinished_games)}")

        for game in unfinished_games:
            # Convert deadline to Riga timezone for comparison
            game_deadline = to_riga_time(game.prediction_deadline)
            deadline_passed = game_deadline < current_time
            logging.debug(f"What-if analysis - Game: {game.team1} vs {game.team2}")
            logging.debug(f"  Deadline: {game.prediction_deadline} -> {game_deadline}")
            logging.debug(f"  Deadline passed: {deadline_passed}")
            logging.debug(f"  Is finished: {game.is_finished}")

        # Convert current time to naive datetime for database comparison
        current_time_naive = current_time.replace(tzinfo=None)
        target_game = Game.query.filter(
            Game.is_finished == False,
            Game.prediction_deadline < current_time_naive
        ).order_by(Game.prediction_deadline.asc()).first()

        logging.debug(f"What-if analysis - Target game found: {target_game is not None}")
        if target_game:
            logging.debug(f"What-if analysis - Selected game: {target_game.team1} vs {target_game.team2}")
        else:
            logging.debug("What-if analysis - No qualifying games found")

    except Exception as e:
        logging.error(f"What-if analysis - Query error: {e}")
        target_game = None

    if not target_game:
        # No qualifying games found - let's provide more context
        total_games = Game.query.count()
        finished_games = Game.query.filter_by(is_finished=True).count()
        upcoming_games = Game.query.filter(
            Game.is_finished == False,
            Game.prediction_deadline >= current_time
        ).count()

        # Create a helpful message based on the situation
        if total_games == 0:
            message = "No games have been added to the system yet."
            suggestion = "Check back once games are scheduled!"
        elif upcoming_games > 0:
            message = f"All unfinished games ({upcoming_games}) still have open prediction deadlines."
            suggestion = "Make your predictions now! This analysis will be available once prediction deadlines pass."
        else:
            message = f"All {finished_games} games have been completed."
            suggestion = "The tournament may be finished, or check back when new games are added."

        return render_template('potential_points.html',
                             target_game=None,
                             scenarios=None,
                             message=message,
                             suggestion=suggestion,
                             stats={
                                 'total_games': total_games,
                                 'finished_games': finished_games,
                                 'upcoming_games': upcoming_games
                             })

    # Get all users and their current total points
    users = User.query.all()
    user_data = {}
    for user in users:
        user_data[user.id] = {
            'user': user,
            'current_total': user.get_total_score(),
            'prediction': None
        }

    # Get existing predictions for this game
    predictions = Prediction.query.filter_by(game_id=target_game.id).all()
    for prediction in predictions:
        if prediction.user_id in user_data:
            user_data[prediction.user_id]['prediction'] = prediction

    # Define all possible volleyball outcomes
    possible_outcomes = [
        {'team1_score': 3, 'team2_score': 0, 'label': f'{target_game.team1} 3-0'},
        {'team1_score': 3, 'team2_score': 1, 'label': f'{target_game.team1} 3-1'},
        {'team1_score': 3, 'team2_score': 2, 'label': f'{target_game.team1} 3-2'},
        {'team1_score': 2, 'team2_score': 3, 'label': f'{target_game.team2} 3-2'},
        {'team1_score': 1, 'team2_score': 3, 'label': f'{target_game.team2} 3-1'},
        {'team1_score': 0, 'team2_score': 3, 'label': f'{target_game.team2} 3-0'},
    ]

    # Calculate current leaderboard positions
    current_leaderboard = []
    for user_id, data in user_data.items():
        current_leaderboard.append({
            'user_id': user_id,
            'user': data['user'],
            'total_points': data['current_total']
        })

    # Sort by current total points (descending) to get current positions
    current_leaderboard.sort(key=lambda x: x['total_points'], reverse=True)

    # Create position mapping
    current_positions = {}
    for i, entry in enumerate(current_leaderboard):
        current_positions[entry['user_id']] = i + 1  # Position starts from 1

    # Calculate potential points for each scenario
    scenarios = []
    for outcome in possible_outcomes:
        scenario = {
            'label': outcome['label'],
            'team1_score': outcome['team1_score'],
            'team2_score': outcome['team2_score'],
            'user_results': []
        }

        # Create a mock finished game for point calculation
        mock_game = Game()
        mock_game.team1 = target_game.team1
        mock_game.team2 = target_game.team2
        mock_game.team1_score = outcome['team1_score']
        mock_game.team2_score = outcome['team2_score']
        mock_game.is_finished = True

        for user_id, data in user_data.items():
            if data['prediction'] and data['prediction'].team1_score is not None and data['prediction'].team2_score is not None:
                # User has a prediction - calculate points they would earn
                points_earned = calculate_points(data['prediction'], mock_game)
                if points_earned is None:
                    points_earned = 0
            else:
                # User has no prediction - gets 0 points
                points_earned = 0

            # Calculate total points after this game
            total_after_game = data['current_total'] + points_earned

            scenario['user_results'].append({
                'user_id': user_id,  # Store user_id separately for position calculations
                'user': {
                    'id': data['user'].id,
                    'name': data['user'].name,
                    'total_score': data['current_total']
                },
                'points_earned': points_earned,
                'total_after_game': total_after_game,
                'has_prediction': data['prediction'] is not None and data['prediction'].team1_score is not None
            })

        # Sort users by total points after game (descending) to get new positions
        scenario['user_results'].sort(key=lambda x: x['total_after_game'], reverse=True)

        # Calculate position changes
        for i, user_result in enumerate(scenario['user_results']):
            new_position = i + 1  # Position starts from 1
            current_position = current_positions[user_result['user_id']]
            position_change = current_position - new_position  # Positive = moved up, negative = moved down

            user_result['current_position'] = current_position
            user_result['new_position'] = new_position
            user_result['position_change'] = position_change

        # Calculate notable position changes for this scenario (with serializable data)
        notable_changes = []
        for user_result in scenario['user_results']:
            if abs(user_result['position_change']) >= 1:  # Any position change is notable
                notable_changes.append({
                    'user': {
                        'id': user_result['user']['id'],
                        'name': user_result['user']['name']
                    },
                    'current_position': user_result['current_position'],
                    'new_position': user_result['new_position'],
                    'position_change': user_result['position_change'],
                    'points_earned': user_result['points_earned']
                })

        # Sort notable changes by magnitude of change (biggest changes first)
        notable_changes.sort(key=lambda x: abs(x['position_change']), reverse=True)
        scenario['notable_changes'] = notable_changes[:8]  # Limit to top 8 changes

        scenarios.append(scenario)

    return render_template('potential_points.html',
                         target_game=target_game,
                         scenarios=scenarios,
                         message=None)

def get_point_color_class(points):
    """Return Bootstrap color class based on points earned"""
    if points == 6:
        return "bg-success text-light"
    elif points == 4:
        return "bg-primary text-light"
    elif points == 2:
        return "bg-info text-light"
    elif points == 1:
        return "bg-warning text-dark"  # Keep dark text for yellow background
    else:  # 0 points
        return "bg-danger text-light"

# Make the color function available in templates
app.jinja_env.globals.update(get_point_color_class=get_point_color_class)

# SerpApi Routes
@app.route('/admin/serpapi-usage', methods=['GET'])
@login_required
@admin_required
def get_serpapi_usage():
    """Get current month's SerpApi usage information"""
    try:
        from result_fetcher import get_monthly_usage_info
        usage_info = get_monthly_usage_info()
        return jsonify({
            'success': True,
            **usage_info
        })
    except Exception as e:
        logging.error(f"Error getting SerpApi usage: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'searches_used': 0,
            'monthly_limit': 250,
            'remaining': 250,
            'can_search': False
        })

@app.route('/admin/manual-result-search', methods=['POST'])
@login_required
@admin_required
def manual_result_search():
    """Manual SerpApi search for game result"""
    try:
        game_id = request.form.get('game_id')
        test_mode = request.form.get('test_mode') == 'true'

        if not game_id:
            return jsonify({'success': False, 'error': 'Game ID is required'})

        game_id = int(game_id)
        game = Game.query.get(game_id)
        if not game:
            return jsonify({'success': False, 'error': 'Game not found'})

        # In test mode, allow finished games; in normal mode, only unfinished
        if not test_mode and game.is_finished:
            return jsonify({'success': False, 'error': 'Game is already finished'})

        # Check monthly limit
        usage = SerpApiUsage.get_current_month_usage()
        if not usage.can_make_search():
            return jsonify({
                'success': False,
                'error': f'Monthly search limit reached ({usage.searches_used}/{usage.monthly_limit})'
            })

        if test_mode:
            # Test mode: search but don't update database
            from result_fetcher import search_game_result
            result = search_game_result(game_id)

            if result:
                # Update usage tracking since we used an API call
                usage.increment_usage()

                # Mark that this game has used SerpApi for testing
                if not game.serpapi_search_used:
                    game.serpapi_search_used = True
                    db.session.commit()

                return jsonify({
                    'success': True,
                    'test_mode': True,
                    'message': f'SerpApi test search completed for {game.team1} vs {game.team2}',
                    'result': {
                        'team1_score': result['team1_score'],
                        'team2_score': result['team2_score'],
                        'source': result['source']
                    },
                    'current_result': {
                        'team1_score': game.team1_score,
                        'team2_score': game.team2_score
                    }
                })
            else:
                # Still increment usage even if no result found
                usage.increment_usage()
                return jsonify({
                    'success': False,
                    'test_mode': True,
                    'error': 'No result found in test search. The result may not be available online yet.'
                })
        else:
            # Normal mode: search and update database
            from result_fetcher import update_game_with_result
            success = update_game_with_result(game_id, force=True)

            if success:
                # Get updated game info
                db.session.refresh(game)
                return jsonify({
                    'success': True,
                    'test_mode': False,
                    'message': f'Successfully found and updated result for {game.team1} vs {game.team2}',
                    'result': {
                        'team1_score': game.team1_score,
                        'team2_score': game.team2_score,
                        'source': game.result_source
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'test_mode': False,
                    'error': 'No result found or search failed. The game may not have finished yet, or the result may not be available online.'
                })

    except ValueError as e:
        return jsonify({'success': False, 'error': 'Invalid game ID'})
    except Exception as e:
        logging.error(f"Error in manual result search: {e}")
        return jsonify({'success': False, 'error': f'Search failed: {str(e)}'})

@app.route('/admin/check-pending-auto-updates', methods=['GET'])
@login_required
@admin_required
def check_pending_auto_updates():
    """Check which games are eligible for auto-update (3+ hours after start)"""
    try:
        current_time = get_riga_time()
        three_hours_ago = current_time - timedelta(hours=3)

        # Find games that started 3+ hours ago, not finished, not attempted
        pending_games = Game.query.filter(
            Game.is_finished == False,
            Game.auto_update_attempted == False,
            Game.game_date <= three_hours_ago
        ).order_by(Game.game_date.asc()).all()

        pending_list = []
        for game in pending_games:
            pending_list.append({
                'id': game.id,
                'team1': game.team1,
                'team2': game.team2,
                'game_date': game.game_date.strftime('%Y-%m-%d %H:%M'),
                'hours_since_start': int((current_time - to_riga_time(game.game_date)).total_seconds() / 3600)
            })

        return jsonify({
            'success': True,
            'pending_games': pending_list,
            'count': len(pending_list)
        })

    except Exception as e:
        logging.error(f"Error checking pending auto-updates: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/force-auto-update/<int:game_id>', methods=['POST'])
@login_required
@admin_required
def force_auto_update(game_id):
    """Force auto-update for a specific game"""
    try:
        game = Game.query.get(game_id)
        if not game:
            return jsonify({'success': False, 'error': 'Game not found'})

        # Check monthly limit
        usage = SerpApiUsage.get_current_month_usage()
        if not usage.can_make_search():
            return jsonify({
                'success': False,
                'error': f'Monthly search limit reached ({usage.searches_used}/{usage.monthly_limit})'
            })

        # Import and use result fetcher
        from result_fetcher import update_game_with_result
        success = update_game_with_result(game_id, force=True)

        if success:
            flash(f'Auto-update successful for {game.team1} vs {game.team2}', 'success')
            return jsonify({'success': True, 'message': 'Auto-update completed successfully'})
        else:
            return jsonify({'success': False, 'error': 'Auto-update failed - no result found'})

    except Exception as e:
        logging.error(f"Error in force auto-update: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/trigger-auto-update', methods=['POST'])
@login_required
@admin_required
def trigger_auto_update():
    """Manually trigger the automatic update process (for testing)"""
    try:
        # Run the auto-update function manually
        auto_update_results()
        return jsonify({'success': True, 'message': 'Auto-update process triggered successfully'})
    except Exception as e:
        logging.error(f"Error triggering auto-update: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/trigger-highlight-detection', methods=['POST'])
@login_required
@admin_required
def trigger_highlight_detection():
    """Manually trigger the automatic highlight detection process (for testing)"""
    try:
        # Run the highlight detection function manually
        auto_detect_highlights()
        return jsonify({'success': True, 'message': 'Highlight detection process triggered successfully'})
    except Exception as e:
        logging.error(f"Error triggering highlight detection: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/manage-highlights/<int:game_id>')
@login_required
@admin_required
def manage_highlights(game_id):
    """Manage highlights for a specific game"""
    try:
        game = Game.query.get_or_404(game_id)
        highlights = GameHighlight.query.filter_by(game_id=game_id).order_by(
            GameHighlight.is_featured.desc(),
            GameHighlight.view_count.desc()
        ).all()

        return jsonify({
            'success': True,
            'game': {
                'id': game.id,
                'team1': game.team1,
                'team2': game.team2,
                'date': game.game_date.strftime('%Y-%m-%d %H:%M'),
                'round': game.round_name
            },
            'highlights': [{
                'id': h.id,
                'title': h.title,
                'youtube_url': h.youtube_url,
                'channel_name': h.channel_name,
                'duration': h.format_duration(),
                'view_count': h.view_count,
                'is_featured': h.is_featured,
                'is_active': h.is_active,
                'auto_detected': h.auto_detected
            } for h in highlights]
        })

    except Exception as e:
        logging.error(f"Error managing highlights for game {game_id}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/add-highlight', methods=['POST'])
@login_required
@admin_required
def add_highlight():
    """Manually add a highlight video"""
    try:
        data = request.get_json()
        game_id = data.get('game_id')
        youtube_url = data.get('youtube_url')
        title = data.get('title', '')
        description = data.get('description', '')

        if not game_id or not youtube_url:
            return jsonify({'success': False, 'error': 'Game ID and YouTube URL are required'})

        game = Game.query.get(game_id)
        if not game:
            return jsonify({'success': False, 'error': 'Game not found'})

        # Extract video ID from URL
        video_id = None
        if 'youtube.com/watch?v=' in youtube_url:
            video_id = youtube_url.split('youtube.com/watch?v=')[-1].split('&')[0]
        elif 'youtu.be/' in youtube_url:
            video_id = youtube_url.split('youtu.be/')[-1].split('?')[0]

        if not video_id:
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'})

        # Check if highlight already exists
        existing = GameHighlight.query.filter_by(youtube_video_id=video_id).first()
        if existing:
            return jsonify({'success': False, 'error': 'This video is already added as a highlight'})

        # Try to get video details from YouTube API
        try:
            from youtube_service import youtube_service
            video_details = youtube_service.get_video_details(video_id)

            if video_details:
                title = video_details['title']
                description = video_details['description'][:500]
                thumbnail_url = video_details['thumbnail_url']
                duration = video_details.get('duration', '')
                channel_name = video_details['channel_name']
                view_count = video_details.get('view_count', 0)
                upload_date = video_details['upload_date']
            else:
                # Use provided data if API fails
                thumbnail_url = f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg'
                duration = ''
                channel_name = ''
                view_count = 0
                upload_date = datetime.utcnow()

        except Exception as e:
            logging.warning(f"Failed to get video details from YouTube API: {e}")
            # Use basic data
            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg'
            duration = ''
            channel_name = ''
            view_count = 0
            upload_date = datetime.utcnow()

        # Create new highlight
        highlight = GameHighlight(
            game_id=game_id,
            youtube_url=youtube_url,
            youtube_video_id=video_id,
            title=title[:200] if title else 'Manual Highlight',
            description=description[:500] if description else '',
            thumbnail_url=thumbnail_url,
            duration=duration,
            channel_name=channel_name,
            view_count=view_count,
            upload_date=upload_date,
            auto_detected=False,
            video_type='highlight'
        )

        db.session.add(highlight)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Highlight added successfully',
            'highlight': {
                'id': highlight.id,
                'title': highlight.title,
                'youtube_url': highlight.youtube_url
            }
        })

    except Exception as e:
        logging.error(f"Error adding highlight: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/toggle-highlight-featured/<int:highlight_id>', methods=['POST'])
@login_required
@admin_required
def toggle_highlight_featured(highlight_id):
    """Toggle the featured status of a highlight"""
    try:
        highlight = GameHighlight.query.get_or_404(highlight_id)
        highlight.is_featured = not highlight.is_featured
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Highlight {"featured" if highlight.is_featured else "unfeatured"} successfully',
            'is_featured': highlight.is_featured
        })

    except Exception as e:
        logging.error(f"Error toggling highlight featured status: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/toggle-highlight-active/<int:highlight_id>', methods=['POST'])
@login_required
@admin_required
def toggle_highlight_active(highlight_id):
    """Toggle the active status of a highlight"""
    try:
        highlight = GameHighlight.query.get_or_404(highlight_id)
        highlight.is_active = not highlight.is_active
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Highlight {"activated" if highlight.is_active else "deactivated"} successfully',
            'is_active': highlight.is_active
        })

    except Exception as e:
        logging.error(f"Error toggling highlight active status: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/delete-highlight/<int:highlight_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_highlight(highlight_id):
    """Delete a highlight"""
    try:
        highlight = GameHighlight.query.get_or_404(highlight_id)
        db.session.delete(highlight)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Highlight deleted successfully'
        })

    except Exception as e:
        logging.error(f"Error deleting highlight: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/featured-videos', methods=['GET'])
@login_required
@admin_required
def get_featured_videos():
    """Get all featured videos for admin management"""
    try:
        featured_videos = FeaturedVideo.query.order_by(
            FeaturedVideo.display_order.asc(),
            FeaturedVideo.created_at.desc()
        ).all()

        return jsonify({
            'success': True,
            'videos': [{
                'id': video.id,
                'title': video.title,
                'youtube_url': video.youtube_url,
                'channel_name': video.channel_name,
                'duration': video.format_duration(),
                'view_count': video.view_count,
                'display_order': video.display_order,
                'is_active': video.is_active,
                'auto_detected': video.auto_detected,
                'thumbnail_url': video.thumbnail_url
            } for video in featured_videos]
        })

    except Exception as e:
        logging.error(f"Error getting featured videos: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/add-featured-video', methods=['POST'])
@login_required
@admin_required
def add_featured_video():
    """Manually add a featured video"""
    try:
        data = request.get_json()
        youtube_url = data.get('youtube_url')
        title = data.get('title', '')
        description = data.get('description', '')
        display_order = data.get('display_order', 0)

        if not youtube_url:
            return jsonify({'success': False, 'error': 'YouTube URL is required'})

        # Extract video ID from URL
        video_id = None
        if 'youtube.com/watch?v=' in youtube_url:
            video_id = youtube_url.split('youtube.com/watch?v=')[-1].split('&')[0]
        elif 'youtu.be/' in youtube_url:
            video_id = youtube_url.split('youtu.be/')[-1].split('?')[0]

        if not video_id:
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'})

        # Check if video already exists
        existing = FeaturedVideo.query.filter_by(youtube_video_id=video_id).first()
        if existing:
            return jsonify({'success': False, 'error': 'This video is already added as a featured video'})

        # Try to get video details from YouTube API
        try:
            from youtube_service import youtube_service
            video_details = youtube_service.get_video_details(video_id)

            if video_details:
                title = video_details['title']
                description = video_details['description'][:500]
                thumbnail_url = video_details['thumbnail_url']
                duration = video_details.get('duration', '')
                channel_name = video_details['channel_name']
                view_count = video_details.get('view_count', 0)
                upload_date = video_details['upload_date']
            else:
                # Use provided data if API fails
                thumbnail_url = f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg'
                duration = ''
                channel_name = ''
                view_count = 0
                upload_date = datetime.utcnow()

        except Exception as e:
            logging.warning(f"Failed to get video details from YouTube API: {e}")
            # Use basic data
            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg'
            duration = ''
            channel_name = ''
            view_count = 0
            upload_date = datetime.utcnow()

        # Create new featured video
        featured_video = FeaturedVideo(
            youtube_url=youtube_url,
            youtube_video_id=video_id,
            title=title[:200] if title else 'Featured Video',
            description=description[:500] if description else '',
            thumbnail_url=thumbnail_url,
            duration=duration,
            channel_name=channel_name,
            view_count=view_count,
            upload_date=upload_date,
            display_order=display_order,
            auto_detected=False
        )

        db.session.add(featured_video)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Featured video added successfully',
            'video': {
                'id': featured_video.id,
                'title': featured_video.title,
                'youtube_url': featured_video.youtube_url
            }
        })

    except Exception as e:
        logging.error(f"Error adding featured video: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/update-featured-video-order', methods=['POST'])
@login_required
@admin_required
def update_featured_video_order():
    """Update display order of featured videos"""
    try:
        data = request.get_json()
        video_orders = data.get('video_orders', [])

        for item in video_orders:
            video_id = item.get('id')
            display_order = item.get('display_order', 0)

            video = FeaturedVideo.query.get(video_id)
            if video:
                video.display_order = display_order

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Featured video order updated successfully'
        })

    except Exception as e:
        logging.error(f"Error updating featured video order: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/toggle-featured-video-active/<int:video_id>', methods=['POST'])
@login_required
@admin_required
def toggle_featured_video_active(video_id):
    """Toggle the active status of a featured video"""
    try:
        video = FeaturedVideo.query.get_or_404(video_id)
        video.is_active = not video.is_active
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Featured video {"activated" if video.is_active else "deactivated"} successfully',
            'is_active': video.is_active
        })

    except Exception as e:
        logging.error(f"Error toggling featured video active status: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/delete-featured-video/<int:video_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_featured_video(video_id):
    """Delete a featured video"""
    try:
        video = FeaturedVideo.query.get_or_404(video_id)
        db.session.delete(video)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Featured video deleted successfully'
        })

    except Exception as e:
        logging.error(f"Error deleting featured video: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Logging Configuration Routes
@app.route('/admin/logging-config', methods=['GET', 'POST'])
@login_required
@admin_required
def logging_config():
    """Get or update logging configuration"""
    if request.method == 'GET':
        current_level = LoggingConfig.get_current_log_level()
        return jsonify({
            'success': True,
            'log_level': current_level
        })

    elif request.method == 'POST':
        try:
            log_level = request.form.get('log_level')
            if not log_level:
                return jsonify({'success': False, 'error': 'Log level is required'})

            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
            if log_level not in valid_levels:
                return jsonify({'success': False, 'error': f'Invalid log level. Must be one of: {", ".join(valid_levels)}'})

            # Update log level in database and Python logging
            LoggingConfig.set_log_level(log_level)

            logging.info(f"Log level changed to {log_level} by admin user {current_user.name}")

            return jsonify({
                'success': True,
                'message': f'Log level updated to {log_level}',
                'log_level': log_level
            })

        except Exception as e:
            logging.error(f"Error updating log level: {e}")
            return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)