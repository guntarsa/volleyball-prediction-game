import os
import csv
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'winamount-could-be-huge-default-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///volleyball_predictions.db')
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    predictions = db.relationship('Prediction', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_total_score(self):
        return sum([p.points for p in self.predictions if p.points is not None])
    
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
        return datetime.now(timezone.utc) < self.prediction_deadline.replace(tzinfo=timezone.utc)
    
    def are_predictions_visible(self):
        return datetime.now(timezone.utc) >= self.prediction_deadline.replace(tzinfo=timezone.utc)
    
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
    games = Game.query.filter_by(is_finished=False).order_by(Game.game_date).all()
    return render_template('predictions.html', games=games)

@app.route('/leaderboard')
@login_required
def leaderboard():
    users = User.query.all()
    user_stats = []
    for user in users:
        stats = {
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
        return redirect(url_for('predictions'))
    
    try:
        team1_score = int(team1_score)
        team2_score = int(team2_score)
        if team1_score < 0 or team2_score < 0:
            raise ValueError("Scores cannot be negative")
    except ValueError:
        flash('Please enter valid scores', 'error')
        return redirect(url_for('predictions'))
    
    game = Game.query.get(game_id)
    if not game:
        flash('Game not found', 'error')
        return redirect(url_for('predictions'))
    
    # Check prediction deadline
    if not game.is_prediction_open():
        flash('Prediction deadline has passed for this game', 'error')
        return redirect(url_for('predictions'))
    
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
    return redirect(url_for('predictions'))

@app.route('/admin')
@login_required
@admin_required
def admin():
    games = Game.query.order_by(Game.game_date).all()
    return render_template('admin.html', games=games)

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
                game_date = datetime.strptime(f"{row['date']} {row['time']}", "%Y-%m-%d %H:%M")
                
                # Parse prediction deadline
                if 'prediction_deadline' in row and row['prediction_deadline']:
                    prediction_deadline = datetime.strptime(row['prediction_deadline'], "%Y-%m-%d %H:%M")
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
    except ValueError:
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

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)