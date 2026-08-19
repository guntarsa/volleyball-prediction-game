#!/usr/bin/env python3
"""
Clear Tournament Data Script - EuroVolley Women 2026

This script clears all tournament-related data while preserving:
- User accounts and logins
- User preferences and settings
- Leaderboard structure (scores will reset as games are cleared)

What gets cleared:
- All game highlights
- All match predictions
- All games/matches
- Tournament predictions
- Tournament configuration
- Match results

Run this before switching to a new tournament to start fresh
while keeping all registered users.
"""

import os
import sys
from datetime import datetime
import pytz
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Import the app configuration
sys.path.append(os.path.dirname(__file__))
from app import app, db, Game, Prediction, TournamentPrediction, TournamentConfig, GameHighlight

RIGA_TZ = pytz.timezone('Europe/Riga')

def get_riga_time():
    """Get current time in Riga timezone"""
    return datetime.now(RIGA_TZ)

def clear_tournament_data():
    """Clear all tournament data while keeping users"""
    
    print("🏐 EuroVolley Women 2026 - Tournament Data Reset")
    print("=" * 60)

    with app.app_context():
        try:
            # Count existing data
            highlight_count = db.session.query(GameHighlight).count()
            prediction_count = db.session.query(Prediction).count()
            game_count = db.session.query(Game).count()
            tournament_prediction_count = db.session.query(TournamentPrediction).count()
            tournament_config_count = db.session.query(TournamentConfig).count()

            print(f"📊 Current data to be cleared:")
            print(f"   • Game highlights: {highlight_count}")
            print(f"   • Match predictions: {prediction_count}")
            print(f"   • Games: {game_count}")
            print(f"   • Tournament predictions: {tournament_prediction_count}")
            print(f"   • Tournament configs: {tournament_config_count}")
            print()

            # Confirm deletion
            if prediction_count > 0 or game_count > 0:
                confirm = input("⚠️  This will clear ALL tournament data. Type 'CLEAR' to confirm: ")
                if confirm != 'CLEAR':
                    print("❌ Operation cancelled.")
                    return

            print("🗑️ Clearing tournament data...")

            # Clear game highlights first (FK references game.id)
            if highlight_count > 0:
                db.session.query(GameHighlight).delete()
                print(f"   ✅ Cleared {highlight_count} game highlights")

            # Clear tournament predictions
            if tournament_prediction_count > 0:
                db.session.query(TournamentPrediction).delete()
                print(f"   ✅ Cleared {tournament_prediction_count} tournament predictions")

            # Clear match predictions
            if prediction_count > 0:
                db.session.query(Prediction).delete()
                print(f"   ✅ Cleared {prediction_count} match predictions")

            # Clear games
            if game_count > 0:
                db.session.query(Game).delete()
                print(f"   ✅ Cleared {game_count} games")

            # Clear tournament configuration
            if tournament_config_count > 0:
                db.session.query(TournamentConfig).delete()
                print(f"   ✅ Cleared {tournament_config_count} tournament configurations")

            # Commit all changes
            db.session.commit()

            print()
            print("🏆 Successfully cleared tournament data!")
            print("👥 All user accounts preserved")
            print("📈 Leaderboard structure maintained (scores will rebuild)")
            print()
            print("🚀 Ready for EuroVolley Women 2026!")
            print("   • Upload eurovolley_women_2026_pools.csv via Admin panel")
            print("   • Set tournament prediction deadline")
            print("   • Users can start making predictions")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error clearing data: {str(e)}")
            raise
        
        finally:
            db.session.close()

if __name__ == "__main__":
    clear_tournament_data()