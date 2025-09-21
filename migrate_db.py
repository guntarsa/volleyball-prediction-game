#!/usr/bin/env python3
"""
Database migration script for adding tournament prediction features.
Run this after deploying new code to add new tables safely.
"""

import os
import sys
import logging
from datetime import datetime
from app import app, db, User, Game, Prediction, TournamentPrediction, TournamentConfig

def migrate_database():
    """Safely migrate database with new tournament tables"""
    with app.app_context():
        try:
            logging.info("Starting database migration...")
            
            # Check if new tables already exist
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            logging.debug(f"Existing tables: {existing_tables}")
            
            # Check if TournamentPrediction table exists
            if 'tournament_prediction' not in existing_tables:
                logging.info("Creating TournamentPrediction table...")
                TournamentPrediction.__table__.create(db.engine)
                logging.info("✅ TournamentPrediction table created")
            else:
                logging.info("ℹ️  TournamentPrediction table already exists")
            
            # Check if TournamentConfig table exists
            if 'tournament_config' not in existing_tables:
                logging.info("Creating TournamentConfig table...")
                TournamentConfig.__table__.create(db.engine)
                logging.info("✅ TournamentConfig table created")
            else:
                logging.info("ℹ️  TournamentConfig table already exists")
            
            # Check if new column exists in User table
            user_columns = [col['name'] for col in inspector.get_columns('user')]
            if 'password_reset_required' not in user_columns:
                logging.info("Adding password_reset_required column to User table...")
                db.engine.execute('ALTER TABLE user ADD COLUMN password_reset_required BOOLEAN DEFAULT FALSE')
                logging.info("✅ password_reset_required column added")
            else:
                logging.info("ℹ️  password_reset_required column already exists")
            
            logging.info("Database migration completed successfully! ✅")
            
            # Print current data summary
            user_count = User.query.count()
            game_count = Game.query.count()
            prediction_count = Prediction.query.count()
            
            logging.info(f"\nCurrent data summary:")
            logging.info(f"Users: {user_count}")
            logging.info(f"Games: {game_count}")
            logging.info(f"Match Predictions: {prediction_count}")
            logging.info(f"Tournament Predictions: {TournamentPrediction.query.count()}")
            
        except Exception as e:
            logging.error(f"❌ Migration failed: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    migrate_database()