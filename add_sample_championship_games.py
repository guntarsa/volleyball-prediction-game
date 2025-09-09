#!/usr/bin/env python3
"""
Add Sample Championship Games - Men's World Championship 2025

This script adds sample games for the Men's World Championship 2025
so users can see the predictions system working.

These are placeholder games with realistic matchups from the 32 qualified teams.
Replace with actual fixtures when tournament schedule is announced.
"""

import os
import sys
from datetime import datetime, timedelta
import pytz

# Import the app configuration
sys.path.append(os.path.dirname(__file__))
from app import app, db, Game

RIGA_TZ = pytz.timezone('Europe/Riga')

def get_riga_time():
    """Get current time in Riga timezone"""
    return datetime.now(RIGA_TZ)

def add_sample_games():
    """Add sample championship games"""
    
    print("🏐 Adding Sample Men's World Championship 2025 Games")
    print("=" * 60)
    
    with app.app_context():
        try:
            # Check if games already exist
            existing_games = db.session.query(Game).count()
            if existing_games > 0:
                print(f"⚠️  {existing_games} games already exist in database.")
                confirm = input("Add sample games anyway? (y/N): ")
                if confirm.lower() != 'y':
                    print("❌ Operation cancelled.")
                    return
            
            # Sample games with realistic matchups
            base_date = get_riga_time() + timedelta(days=1)  # Start tomorrow
            
            sample_games = [
                # Pool matches
                ("Poland", "Finland", "Pool A", 0),
                ("Italy", "Algeria", "Pool A", 1), 
                ("Brazil", "Chile", "Pool B", 0),
                ("USA", "Qatar", "Pool B", 1),
                ("Serbia", "Colombia", "Pool C", 2),
                ("France", "Tunisia", "Pool C", 2),
                ("Japan", "Philippines", "Pool D", 3),
                ("Netherlands", "Libya", "Pool D", 3),
                ("Germany", "Romania", "Pool E", 4),
                ("Turkey", "Korea", "Pool E", 4),
                ("Argentina", "Egypt", "Pool F", 5),
                ("Belgium", "Portugal", "Pool F", 5),
                ("China", "Bulgaria", "Pool G", 6),
                ("Canada", "Czechia", "Pool G", 6),
                ("Slovenia", "Ukraine", "Pool H", 7),
                ("Cuba", "Iran", "Pool H", 7),
                
                # Additional pool matches
                ("Poland", "Algeria", "Pool A", 8),
                ("Italy", "Finland", "Pool A", 9),
                ("Brazil", "Qatar", "Pool B", 8),
                ("USA", "Chile", "Pool B", 9),
                ("Serbia", "Tunisia", "Pool C", 10),
                ("France", "Colombia", "Pool C", 11),
            ]
            
            games_added = 0
            
            for team1, team2, round_name, day_offset in sample_games:
                # Game time: spread throughout the day
                hour = 10 + (day_offset * 2) % 12  # Games between 10:00-22:00
                game_time = base_date.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=day_offset // 4)
                
                # Prediction deadline: 1 hour before game
                deadline = game_time - timedelta(hours=1)
                
                game = Game(
                    team1=team1,
                    team2=team2,
                    game_date=game_time,
                    prediction_deadline=deadline,
                    round_name=round_name,
                    is_finished=False
                )
                
                db.session.add(game)
                games_added += 1
                print(f"   ✅ {team1} vs {team2} - {round_name} ({game_time.strftime('%Y-%m-%d %H:%M')})")
            
            # Commit all changes
            db.session.commit()
            
            print()
            print(f"🏆 Successfully added {games_added} sample championship games!")
            print("📅 Games scheduled over the next few days")
            print("⏰ Prediction deadlines set 1 hour before each game")
            print()
            print("🚀 Users can now:")
            print("   • View upcoming games in predictions page")
            print("   • Make match predictions")
            print("   • See the championship schedule")
            print()
            print("📝 Note: These are sample games for testing.")
            print("   Replace with actual fixtures when tournament schedule is announced.")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding games: {str(e)}")
            raise
        
        finally:
            db.session.close()

if __name__ == "__main__":
    add_sample_games()