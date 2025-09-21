#!/usr/bin/env python3
"""
Database migration script for updating TournamentTeam table with country_code column.
Run this if you get the error: column tournament_team.country_code does not exist
"""

import os
import sys
import logging
from datetime import datetime
from app import app, db, TournamentTeam

def migrate_tournament_teams():
    """Add country_code column to tournament_team table if missing"""
    with app.app_context():
        try:
            logging.info("Starting TournamentTeam table migration...")
            
            # Check if table and column exist
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            logging.debug(f"Existing tables: {existing_tables}")
            
            # Check if TournamentTeam table exists
            if 'tournament_team' not in existing_tables:
                logging.info("Creating TournamentTeam table...")
                TournamentTeam.__table__.create(db.engine)
                logging.info("✅ TournamentTeam table created with country_code column")
            else:
                logging.info("ℹ️  TournamentTeam table exists, checking columns...")
                
                # Check if country_code column exists
                team_columns = [col['name'] for col in inspector.get_columns('tournament_team')]
                logging.debug(f"Existing columns: {team_columns}")
                
                if 'country_code' not in team_columns:
                    logging.info("Adding country_code column to TournamentTeam table...")
                    
                    # Use the appropriate SQL for adding column
                    db.engine.execute('ALTER TABLE tournament_team ADD COLUMN country_code VARCHAR(2)')
                    logging.info("✅ country_code column added to TournamentTeam table")
                else:
                    logging.info("ℹ️  country_code column already exists")
            
            logging.info("TournamentTeam migration completed successfully! ✅")
            
            # Print current tournament teams
            team_count = TournamentTeam.query.count()
            logging.info(f"\nCurrent tournament teams: {team_count}")
            
            if team_count > 0:
                logging.info("Teams:")
                for team in TournamentTeam.query.all():
                    country = team.country_code or 'N/A'
                    logging.info(f"  - {team.name} ({country})")
            
        except Exception as e:
            logging.error(f"❌ Migration failed: {str(e)}")
            print(f"Error details: {type(e).__name__}: {e}")
            sys.exit(1)

if __name__ == "__main__":
    migrate_tournament_teams()