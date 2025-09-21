#!/usr/bin/env python3
"""
Database migration script to add SerpApi columns to Game model and create SerpApiUsage table
Run this script to update the database schema with the new SerpApi features
"""

import os
import sys
from datetime import datetime
from sqlalchemy import text

# Add the current directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_database():
    """Add SerpApi columns to existing database"""
    try:
        from app import app, db

        with app.app_context():
            print("Starting SerpApi database migration...")

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
                    print(f"Adding column {column_name} to game table...")
                    try:
                        with db.engine.connect() as conn:
                            conn.execute(text(f'ALTER TABLE game ADD COLUMN {column_name} {column_def}'))
                            conn.commit()
                        print(f"✅ Successfully added {column_name}")
                    except Exception as e:
                        print(f"❌ Error adding {column_name}: {e}")
                        # Continue with other columns
                else:
                    print(f"ℹ️  Column {column_name} already exists")

            # Create SerpApiUsage table if it doesn't exist
            if 'serpapi_usage' not in existing_tables:
                print("Creating serpapi_usage table...")
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
                    print("✅ Successfully created serpapi_usage table")
                except Exception as e:
                    print(f"❌ Error creating serpapi_usage table: {e}")
            else:
                print("ℹ️  Table serpapi_usage already exists")

            # Create tables for any new models (this will create SerpApiUsage if using SQLAlchemy)
            print("Creating any missing tables...")
            try:
                db.create_all()
                print("✅ Database schema updated")
            except Exception as e:
                print(f"❌ Error creating tables: {e}")

            print("\n🎉 Database migration completed!")
            print("The SerpApi features are now ready to use.")

    except ImportError as e:
        print(f"❌ Failed to import app modules: {e}")
        print("Make sure you're running this from the project directory with all dependencies installed.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
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
                print("❌ Migration needed!")
                if missing_columns:
                    print(f"Missing columns in game table: {', '.join(missing_columns)}")
                if missing_tables:
                    print(f"Missing tables: {', '.join(missing_tables)}")
                return False
            else:
                print("✅ Database is up to date!")
                return True

    except Exception as e:
        print(f"❌ Error checking migration status: {e}")
        return False

if __name__ == '__main__':
    print("SerpApi Database Migration Tool")
    print("=" * 40)

    # Check current status
    if check_migration_status():
        print("No migration needed.")
    else:
        print("\nRunning migration...")
        if migrate_database():
            print("\nMigration completed successfully!")
        else:
            print("\nMigration failed!")
            sys.exit(1)