#!/usr/bin/env python3
"""
Script to clear all data from the database and start fresh.
This will delete ALL data including users, games, predictions, etc.
"""

from app import app, db, User, Game, Prediction, TournamentTeam

def clear_all_data():
    """Clear all data from all tables"""
    with app.app_context():
        try:
            print("Starting database cleanup...")
            
            # Delete all data in reverse order of dependencies
            print("Deleting predictions...")
            Prediction.query.delete()
            
            print("Deleting games...")
            Game.query.delete()
            
            print("Deleting tournament teams...")
            TournamentTeam.query.delete()
            
            print("Deleting users...")
            User.query.delete()
            
            # Commit all deletions
            db.session.commit()
            print("✅ All data cleared successfully!")
            
            print("\nDatabase is now empty. You can:")
            print("1. Create a new admin user")
            print("2. Upload new games")
            print("3. Upload tournament teams")
            
        except Exception as e:
            print(f"❌ Error clearing database: {e}")
            db.session.rollback()
            return False
            
    return True

def recreate_tables():
    """Drop and recreate all tables"""
    with app.app_context():
        try:
            print("Dropping all tables...")
            db.drop_all()
            
            print("Creating all tables...")
            db.create_all()
            
            print("✅ All tables recreated successfully!")
            
        except Exception as e:
            print(f"❌ Error recreating tables: {e}")
            return False
            
    return True

if __name__ == "__main__":
    print("⚠️  WARNING: This will delete ALL data in the database!")
    print("This includes:")
    print("- All users and their accounts")
    print("- All games and results")
    print("- All predictions")
    print("- All tournament teams")
    print()
    
    choice = input("Choose an option:\n1. Clear all data (keep table structure)\n2. Drop and recreate all tables\n3. Cancel\nEnter choice (1/2/3): ").strip()
    
    if choice == "1":
        confirm = input("Are you sure? Type 'YES' to confirm: ").strip()
        if confirm == "YES":
            clear_all_data()
        else:
            print("Operation cancelled.")
            
    elif choice == "2":
        confirm = input("Are you sure? This will completely reset the database. Type 'YES' to confirm: ").strip()
        if confirm == "YES":
            recreate_tables()
        else:
            print("Operation cancelled.")
            
    elif choice == "3":
        print("Operation cancelled.")
        
    else:
        print("Invalid choice. Operation cancelled.")