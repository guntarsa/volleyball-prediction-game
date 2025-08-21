#!/usr/bin/env python3
"""
Database migration script for adding tournament prediction features.
Run this after deploying new code to add new tables safely.
"""

import os
import sys
from datetime import datetime
from app import app, db, User, Game, Prediction, TournamentPrediction, TournamentConfig

def migrate_database():
    """Safely migrate database with new tournament tables"""
    with app.app_context():
        try:
            print("Starting database migration...")
            
            # Check if new tables already exist
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            print(f"Existing tables: {existing_tables}")
            
            # Check if TournamentPrediction table exists
            if 'tournament_prediction' not in existing_tables:
                print("Creating TournamentPrediction table...")
                TournamentPrediction.__table__.create(db.engine)
                print("✅ TournamentPrediction table created")
            else:
                print("ℹ️  TournamentPrediction table already exists")
            
            # Check if TournamentConfig table exists
            if 'tournament_config' not in existing_tables:
                print("Creating TournamentConfig table...")
                TournamentConfig.__table__.create(db.engine)
                print("✅ TournamentConfig table created")
            else:
                print("ℹ️  TournamentConfig table already exists")
            
            # Check if new column exists in User table
            user_columns = [col['name'] for col in inspector.get_columns('user')]
            if 'password_reset_required' not in user_columns:
                print("Adding password_reset_required column to User table...")
                db.engine.execute('ALTER TABLE user ADD COLUMN password_reset_required BOOLEAN DEFAULT FALSE')
                print("✅ password_reset_required column added")
            else:
                print("ℹ️  password_reset_required column already exists")
            
            print("Database migration completed successfully! ✅")
            
            # Print current data summary
            user_count = User.query.count()
            game_count = Game.query.count()
            prediction_count = Prediction.query.count()
            
            print(f"\nCurrent data summary:")
            print(f"Users: {user_count}")
            print(f"Games: {game_count}")
            print(f"Match Predictions: {prediction_count}")
            print(f"Tournament Predictions: {TournamentPrediction.query.count()}")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    migrate_database()