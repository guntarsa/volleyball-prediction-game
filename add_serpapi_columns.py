#!/usr/bin/env python3
"""
Database migration script to add SerpApi columns to Game model and create SerpApiUsage table
Run this script to update the database schema with the new SerpApi features
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import text

# Add the current directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_database():
    """Add SerpApi columns to existing database"""
    try:
        from app import app, db

        with app.app_context():
            logging.info("Starting SerpApi database migration...")

            # Check if columns already exist
            inspector = db.inspect(db.engine)
            game_columns = [col['name'] for col in inspector.get_columns('game')]
            existing_tables = inspector.get_table_names()

            # Add SerpApi columns to Game table if they don't exist
            columns_to_add = [
                ('auto_update_attempted', 'BOOLEAN DEFAULT FALSE'),
                ('auto_update_timestamp', 'TIMESTAMP'),
                ('result_source', "VARCHAR(50) DEFAULT 'manual'"),
                ('serpapi_search_used', 'BOOLEAN DEFAULT FALSE')
            ]

            for column_name, column_def in columns_to_add:
                if column_name not in game_columns:
                    logging.info(f"Adding column {column_name} to game table...")
                    try:
                        with db.engine.connect() as conn:
                            conn.execute(text(f'ALTER TABLE game ADD COLUMN {column_name} {column_def}'))
                            conn.commit()
                        logging.info(f"✅ Successfully added {column_name}")
                    except Exception as e:
                        logging.error(f"❌ Error adding {column_name}: {e}")
                        # Continue with other columns
                else:
                    logging.info(f"ℹ️  Column {column_name} already exists")

            # Create SerpApiUsage table if it doesn't exist
            if 'serpapi_usage' not in existing_tables:
                logging.info("Creating serpapi_usage table...")
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text('''
                            CREATE TABLE serpapi_usage (
                                id SERIAL PRIMARY KEY,
                                month_year VARCHAR(7) UNIQUE NOT NULL,
                                searches_used INTEGER DEFAULT 0,
                                monthly_limit INTEGER DEFAULT 250,
                                last_search_date TIMESTAMP,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        '''))
                        conn.commit()
                    logging.info("✅ Successfully created serpapi_usage table")
                except Exception as e:
                    logging.error(f"❌ Error creating serpapi_usage table: {e}")
            else:
                logging.info("ℹ️  Table serpapi_usage already exists")

            # Create tables for any new models (this will create SerpApiUsage if using SQLAlchemy)
            logging.info("Creating any missing tables...")
            try:
                db.create_all()
                logging.info("✅ Database schema updated")
            except Exception as e:
                logging.error(f"❌ Error creating tables: {e}")

            logging.info("\n🎉 Database migration completed!")
            logging.info("The SerpApi features are now ready to use.")

    except ImportError as e:
        logging.error(f"❌ Failed to import app modules: {e}")
        logging.error("Make sure you're running this from the project directory with all dependencies installed.")
    except Exception as e:
        logging.error(f"❌ Migration failed: {e}")
        return False

    return True

def check_migration_status():
    """Check if migration is needed"""
    try:
        from app import app, db

        with app.app_context():
            inspector = db.inspect(db.engine)
            game_columns = [col['name'] for col in inspector.get_columns('game')]
            existing_tables = inspector.get_table_names()

            missing_columns = []
            required_columns = ['auto_update_attempted', 'auto_update_timestamp', 'result_source', 'serpapi_search_used']

            for col in required_columns:
                if col not in game_columns:
                    missing_columns.append(col)

            missing_tables = []
            if 'serpapi_usage' not in existing_tables:
                missing_tables.append('serpapi_usage')

            if missing_columns or missing_tables:
                logging.warning("❌ Migration needed!")
                if missing_columns:
                    logging.warning(f"Missing columns in game table: {', '.join(missing_columns)}")
                if missing_tables:
                    logging.warning(f"Missing tables: {', '.join(missing_tables)}")
                return False
            else:
                logging.info("✅ Database is up to date!")
                return True

    except Exception as e:
        logging.error(f"❌ Error checking migration status: {e}")
        return False

if __name__ == '__main__':
    logging.info("SerpApi Database Migration Tool")
    logging.info("=" * 40)

    # Check current status
    if check_migration_status():
        logging.info("No migration needed.")
    else:
        logging.info("\nRunning migration...")
        if migrate_database():
            logging.info("\nMigration completed successfully!")
        else:
            logging.error("\nMigration failed!")
            sys.exit(1)