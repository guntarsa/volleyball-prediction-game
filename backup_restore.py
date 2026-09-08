#!/usr/bin/env python3
"""
Backup and Restore Script for Volleyball Prediction Game

BACKUP  — saves all tournament data to a JSON file (users preserved separately)
RESTORE — loads a JSON backup back into the database

Usage:
  python3 backup_restore.py backup              # backup to backups/backup_<timestamp>.json
  python3 backup_restore.py backup myfile.json  # backup to specific file
  python3 backup_restore.py restore myfile.json # restore from file
  python3 backup_restore.py list                # list available backups
"""

import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.dirname(__file__))
from app import (
    app, db,
    Game, Prediction, TournamentPrediction, TournamentConfig,
    GameHighlight, TournamentTeam
)

BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'backups')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_dict(row):
    """Convert a SQLAlchemy model instance to a plain dict."""
    d = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        d[col.name] = val
    return d


def _dt(value):
    """Parse an ISO datetime string back to a datetime object (or None)."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup(filepath=None):
    os.makedirs(BACKUP_DIR, exist_ok=True)

    if filepath is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(BACKUP_DIR, f'backup_{ts}.json')

    with app.app_context():
        data = {
            'created_at': datetime.now().isoformat(),
            'games': [_to_dict(g) for g in Game.query.order_by(Game.id).all()],
            'predictions': [_to_dict(p) for p in Prediction.query.order_by(Prediction.id).all()],
            'tournament_predictions': [_to_dict(p) for p in TournamentPrediction.query.order_by(TournamentPrediction.id).all()],
            'tournament_configs': [_to_dict(c) for c in TournamentConfig.query.all()],
            'tournament_teams': [_to_dict(t) for t in TournamentTeam.query.order_by(TournamentTeam.id).all()],
            'game_highlights': [_to_dict(h) for h in GameHighlight.query.order_by(GameHighlight.id).all()],
        }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in data.values() if isinstance(v, list))
    print(f"✅ Backup saved to: {filepath}")
    print(f"   Games:                  {len(data['games'])}")
    print(f"   Predictions:            {len(data['predictions'])}")
    print(f"   Tournament predictions: {len(data['tournament_predictions'])}")
    print(f"   Tournament teams:       {len(data['tournament_teams'])}")
    print(f"   Game highlights:        {len(data['game_highlights'])}")
    print(f"   Total records:          {total}")
    return filepath


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def restore(filepath):
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"📂 Restoring from: {filepath}")
    print(f"   Backup created: {data.get('created_at', 'unknown')}")
    print(f"   Games:                  {len(data.get('games', []))}")
    print(f"   Predictions:            {len(data.get('predictions', []))}")
    print(f"   Tournament predictions: {len(data.get('tournament_predictions', []))}")
    print(f"   Tournament teams:       {len(data.get('tournament_teams', []))}")
    print(f"   Game highlights:        {len(data.get('game_highlights', []))}")
    print()

    confirm = input("⚠️  This will OVERWRITE existing tournament data. Type 'RESTORE' to confirm: ")
    if confirm != 'RESTORE':
        print("❌ Cancelled.")
        return

    with app.app_context():
        try:
            # Clear existing tournament data (keep users)
            db.session.query(GameHighlight).delete()
            db.session.query(Prediction).delete()
            db.session.query(TournamentPrediction).delete()
            db.session.query(Game).delete()
            db.session.query(TournamentConfig).delete()
            db.session.query(TournamentTeam).delete()
            db.session.commit()
            print("🗑️  Cleared existing data.")

            # Restore tournament teams
            for row in data.get('tournament_teams', []):
                db.session.add(TournamentTeam(
                    id=row['id'],
                    name=row['name'],
                    country_code=row.get('country_code'),
                ))
            db.session.commit()

            # Restore games
            for row in data.get('games', []):
                db.session.add(Game(
                    id=row['id'],
                    team1=row['team1'],
                    team2=row['team2'],
                    game_date=_dt(row['game_date']),
                    prediction_deadline=_dt(row.get('prediction_deadline')),
                    round_name=row['round_name'],
                    team1_score=row.get('team1_score'),
                    team2_score=row.get('team2_score'),
                    is_finished=row.get('is_finished', False),
                ))
            db.session.commit()

            # Restore tournament config
            for row in data.get('tournament_configs', []):
                db.session.add(TournamentConfig(
                    id=row['id'],
                    config_key=row['config_key'],
                    config_value=row.get('config_value'),
                    created_at=_dt(row.get('created_at')),
                ))
            db.session.commit()

            # Restore predictions
            for row in data.get('predictions', []):
                db.session.add(Prediction(
                    id=row['id'],
                    user_id=row['user_id'],
                    game_id=row['game_id'],
                    predicted_winner=row.get('predicted_winner'),
                    team1_score=row.get('team1_score'),
                    team2_score=row.get('team2_score'),
                    points=row.get('points'),
                    created_at=_dt(row.get('created_at')),
                    updated_at=_dt(row.get('updated_at')),
                ))
            db.session.commit()

            # Restore tournament predictions
            for row in data.get('tournament_predictions', []):
                db.session.add(TournamentPrediction(
                    id=row['id'],
                    user_id=row['user_id'],
                    winner_team=row.get('winner_team'),
                    second_team=row.get('second_team'),
                    third_team=row.get('third_team'),
                    points_earned=row.get('points_earned', 0),
                    created_at=_dt(row.get('created_at')),
                    updated_at=_dt(row.get('updated_at')),
                ))
            db.session.commit()

            # Restore game highlights
            for row in data.get('game_highlights', []):
                db.session.add(GameHighlight(
                    id=row['id'],
                    game_id=row['game_id'],
                    youtube_url=row['youtube_url'],
                    youtube_video_id=row['youtube_video_id'],
                    title=row['title'],
                    description=row.get('description'),
                    thumbnail_url=row.get('thumbnail_url'),
                    duration=row.get('duration'),
                    video_type=row.get('video_type', 'highlight'),
                    view_count=row.get('view_count'),
                    upload_date=_dt(row.get('upload_date')),
                    channel_name=row.get('channel_name'),
                    is_active=row.get('is_active', True),
                    is_featured=row.get('is_featured', False),
                    auto_detected=row.get('auto_detected', False),
                    created_at=_dt(row.get('created_at')),
                ))
            db.session.commit()

            # Reset sequences so new records don't collide (PostgreSQL only)
            try:
                for table, model in [
                    ('game', Game), ('prediction', Prediction),
                    ('tournament_prediction', TournamentPrediction),
                    ('tournament_config', TournamentConfig),
                    ('tournament_team', TournamentTeam),
                    ('game_highlight', GameHighlight),
                ]:
                    max_id = db.session.execute(
                        db.text(f'SELECT MAX(id) FROM {table}')
                    ).scalar()
                    if max_id:
                        db.session.execute(
                            db.text(f"SELECT setval('{table}_id_seq', {max_id})")
                        )
                db.session.commit()
            except Exception:
                pass  # Silently skip for SQLite (no sequences)

            print()
            print("✅ Restore complete!")
            print(f"   Games restored:                  {Game.query.count()}")
            print(f"   Predictions restored:            {Prediction.query.count()}")
            print(f"   Tournament predictions restored: {TournamentPrediction.query.count()}")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during restore: {e}")
            raise


# ---------------------------------------------------------------------------
# List backups
# ---------------------------------------------------------------------------

def list_backups():
    if not os.path.exists(BACKUP_DIR):
        print("No backups folder found.")
        return
    files = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith('.json')],
        reverse=True
    )
    if not files:
        print("No backups found.")
        return
    print(f"📁 Backups in {BACKUP_DIR}:")
    for f in files:
        path = os.path.join(BACKUP_DIR, f)
        size = os.path.getsize(path)
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M')
        print(f"   {f}  ({size/1024:.1f} KB)  {mtime}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'

    if cmd == 'backup':
        filepath = sys.argv[2] if len(sys.argv) > 2 else None
        backup(filepath)

    elif cmd == 'restore':
        if len(sys.argv) < 3:
            print("Usage: python3 backup_restore.py restore <file.json>")
            sys.exit(1)
        restore(sys.argv[2])

    elif cmd == 'list':
        list_backups()

    else:
        print(__doc__)
