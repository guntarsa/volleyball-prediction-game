#!/usr/bin/env python3
"""
Quick migration script for SerpApi columns
Run this if you need to manually add the SerpApi columns to the database
"""
import logging
from app import app, db

def migrate():
    with app.app_context():
        logging.info("Running SerpApi migration...")

        try:
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()

            # Create all tables first (will create SerpApiUsage table)
            db.create_all()
            logging.info("✅ Created any missing tables")

            # Add missing columns to game table
            if 'game' in existing_tables:
                game_columns = [col['name'] for col in inspector.get_columns('game')]

                columns_to_add = [
                    ('auto_update_attempted', 'BOOLEAN DEFAULT FALSE'),
                    ('auto_update_timestamp', 'TIMESTAMP'),
                    ('result_source', "VARCHAR(50) DEFAULT 'manual'"),
                    ('serpapi_search_used', 'BOOLEAN DEFAULT FALSE')
                ]

                for column_name, column_def in columns_to_add:
                    if column_name not in game_columns:
                        logging.info(f"Adding {column_name} column...")
                        with db.engine.connect() as conn:
                            conn.execute(db.text(f'ALTER TABLE game ADD COLUMN {column_name} {column_def}'))
                            conn.commit()
                        logging.info(f"✅ Added {column_name}")
                    else:
                        logging.info(f"ℹ️  {column_name} already exists")

            logging.info("🎉 Migration completed!")

        except Exception as e:
            logging.error(f"❌ Migration failed: {e}")

if __name__ == '__main__':
    migrate()