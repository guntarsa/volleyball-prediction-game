# Safe Deployment Guide for Render.com

## 🛠️ First-Time Setup (Required)

**IMPORTANT:** To prevent losing your admin user on each deployment, you need to use a persistent database instead of SQLite.

### **Step 1: Create PostgreSQL Database on Render**

1. **Go to Render Dashboard** → Create → PostgreSQL
2. **Database Name:** `volleyball-predictions-db`
3. **User:** Choose a username (e.g., `volleyball_admin`)
4. **Region:** Same as your web service
5. **Plan:** Free tier is sufficient
6. **Click "Create Database"**

### **Step 2: Connect Database to Your Web Service**

1. **Go to your Web Service** → Environment
2. **Add Environment Variable:**
   - **Key:** `DATABASE_URL`
   - **Value:** Copy the "External Database URL" from your PostgreSQL service
3. **Click "Save Changes"**

### **Step 3: Deploy with Database Support**

1. **Push your changes to GitHub:**
   ```bash
   git add .
   git commit -m "Add PostgreSQL support and fix admin persistence"
   git push origin main
   ```

2. **Render will automatically deploy** and the app will:
   - ✅ Use persistent PostgreSQL database
   - ✅ Keep all data between deployments
   - ✅ Preserve admin user permanently
   - ✅ Create new tournament tables if missing

## 🚀 Future Deployments

After the initial setup, all future deployments will preserve your data:

1. **Push your changes to GitHub:**
   ```bash
   git add .
   git commit -m "Your changes description"
   git push origin main
   ```

2. **Render will automatically deploy** and maintain:
   - ✅ All user accounts (including admin)
   - ✅ All games and predictions
   - ✅ Tournament configurations
   - ✅ Complete leaderboard history

### **Manual Migration (If Needed)**

If you need to run migrations manually:

1. **Access Render shell:**
   - Go to your Render service dashboard
   - Click "Shell" tab
   - Run: `python migrate_db.py`

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