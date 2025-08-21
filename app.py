import os
import csv
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///volleyball_predictions.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    predictions = db.relationship('Prediction', backref='user', lazy=True, cascade='all, delete-orphan')
    
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
    round_name = db.Column(db.String(100), nullable=False)
    team1_score = db.Column(db.Integer, nullable=True)
    team2_score = db.Column(db.Integer, nullable=True)
    is_finished = db.Column(db.Boolean, default=False)
    predictions = db.relationship('Prediction', backref='game', lazy=True, cascade='all, delete-orphan')
    
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

@app.route('/predictions')
def predictions():
    games = Game.query.filter_by(is_finished=False).order_by(Game.game_date).all()
    users = User.query.all()
    return render_template('predictions.html', games=games, users=users)

@app.route('/leaderboard')
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

@app.route('/add_user', methods=['POST'])
def add_user():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Please enter a valid name', 'error')
        return redirect(url_for('leaderboard'))
    
    if User.query.filter_by(name=name).first():
        flash('User already exists', 'error')
        return redirect(url_for('leaderboard'))
    
    user = User(name=name)
    db.session.add(user)
    db.session.commit()
    flash(f'Welcome {name}!', 'success')
    return redirect(url_for('leaderboard'))

@app.route('/make_prediction', methods=['POST'])
def make_prediction():
    user_id = request.form.get('user_id')
    game_id = request.form.get('game_id')
    team1_score = request.form.get('team1_score')
    team2_score = request.form.get('team2_score')
    
    if not all([user_id, game_id, team1_score, team2_score]):
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
    
    # Check if prediction already exists
    existing = Prediction.query.filter_by(user_id=user_id, game_id=game_id).first()
    if existing:
        existing.team1_score = team1_score
        existing.team2_score = team2_score
        existing.predicted_winner = request.form.get('team1') if team1_score > team2_score else request.form.get('team2')
    else:
        game = Game.query.get(game_id)
        predicted_winner = game.team1 if team1_score > team2_score else game.team2
        prediction = Prediction(
            user_id=user_id,
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
def admin():
    games = Game.query.order_by(Game.game_date).all()
    return render_template('admin.html', games=games)

@app.route('/upload_games', methods=['POST'])
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
                # Expected CSV columns: team1, team2, date, time, round
                game_date = datetime.strptime(f"{row['date']} {row['time']}", "%Y-%m-%d %H:%M")
                
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

@app.route('/get_prediction/<int:user_id>/<int:game_id>')
def get_prediction(user_id, game_id):
    prediction = Prediction.query.filter_by(user_id=user_id, game_id=game_id).first()
    if prediction:
        return jsonify({
            'team1_score': prediction.team1_score,
            'team2_score': prediction.team2_score
        })
    return jsonify({'team1_score': '', 'team2_score': ''})

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)