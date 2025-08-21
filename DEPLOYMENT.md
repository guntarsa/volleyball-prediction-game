# Safe Deployment Guide for Render.com

## 🚀 Deploying Changes Without Losing Data

### **Method 1: Automatic Migration (Recommended)**

The app now handles database migrations automatically on startup. Simply:

1. **Push your changes to GitHub:**
   ```bash
   git add .
   git commit -m "Add tournament predictions and password reset features"
   git push origin main
   ```

2. **Render will automatically deploy** and the app will:
   - ✅ Keep all existing tables and data
   - ✅ Create new tournament tables if missing  
   - ✅ Add password_reset_required column if missing
   - ✅ Preserve all user accounts, games, and predictions

### **Method 2: Manual Migration (If Needed)**

If automatic migration fails, you can run the migration script manually:

1. **After deployment, access Render shell:**
   - Go to your Render service dashboard
   - Click "Shell" tab
   - Run: `python migrate_db.py`

2. **Or update via local script:**
   ```bash
   # If you have database access
   python migrate_db.py
   ```

## 📊 What Gets Preserved

✅ **All User Accounts** - Names, emails, passwords, admin status
✅ **All Games** - Teams, dates, scores, deadlines  
✅ **All Match Predictions** - User predictions and points
✅ **Leaderboard Data** - Total scores and statistics

## 🆕 What Gets Added

🆕 **Tournament Prediction Tables** - New tables for tournament predictions
🆕 **Tournament Configuration** - Admin can set tournament deadline
🆕 **Password Reset Feature** - Admin can reset user passwords
🆕 **Enhanced Scoring** - Tournament points added to total scores

## 🔧 Database Changes Made

### New Tables:
- `tournament_prediction` - User tournament predictions
- `tournament_config` - Tournament deadline and results

### Modified Tables:
- `user` - Added `password_reset_required` column (default: False)

## 🚨 Rollback Plan (If Needed)

If something goes wrong, you can rollback:

1. **Revert Git changes:**
   ```bash
   git revert HEAD
   git push origin main
   ```

2. **Remove new tables** (if absolutely necessary):
   ```sql
   DROP TABLE IF EXISTS tournament_prediction;
   DROP TABLE IF EXISTS tournament_config;
   ALTER TABLE user DROP COLUMN IF EXISTS password_reset_required;
   ```

## ✅ Post-Deployment Checklist

After deployment, verify:

1. **Login works** - Existing users can still log in
2. **Leaderboard shows** - All previous scores intact
3. **Match predictions work** - Users can still predict games
4. **Tournament predictions available** - New feature accessible
5. **Admin panel works** - New tournament management visible

## 🎯 Next Steps After Deployment

1. **Set Tournament Deadline:**
   - Go to Admin Panel
   - Set tournament prediction deadline
   - Users can then make tournament predictions

2. **Test Tournament Features:**
   - Make a test tournament prediction
   - Verify deadline enforcement works
   - Test tournament results input

3. **Inform Users:**
   - Let friends know about new tournament prediction feature
   - Share the 50/25/25 point scoring system
   - Remind about deadline for tournament predictions

## 🔍 Monitoring

Check Render logs for:
- ✅ "Database tables initialized successfully"
- ✅ "password_reset_required column added successfully" 
- ❌ Any database errors (contact support if needed)

Your data is safe! The migration preserves all existing information while adding new features.