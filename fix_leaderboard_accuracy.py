# Fix for User model methods in app.py
# Replace the existing methods with these corrected versions

# FIND AND REPLACE these methods in the User class:

# OLD METHOD:
# def get_total_predictions(self):
#     return len([p for p in self.predictions if p.team1_score is not None])

# NEW METHOD:
def get_total_predictions(self):
    """Count only predictions for finished games"""
    return len([p for p in self.predictions 
               if p.team1_score is not None 
               and p.game.is_finished 
               and p.points is not None])

# OLD METHOD: 
# def get_correct_predictions(self):
#     return len([p for p in self.predictions if p.points and p.points > 0])

# NEW METHOD:
def get_correct_predictions(self):
    """Count only predictions with 2+ points (truly correct predictions)"""
    return len([p for p in self.predictions 
               if p.points is not None 
               and p.points >= 2
               and p.game.is_finished])

# ADDITIONAL METHOD TO ADD:
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
        'correct_predictions': len([p for p in finished_predictions if p.points >= 2]),  # 2+ points
        'accuracy': round((len([p for p in finished_predictions if p.points >= 2]) / max(len(finished_predictions), 1)) * 100, 1)
    }