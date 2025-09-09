# 🏆 Update to Men's World Championship 2025

Quick guide to switch your existing volleyball prediction game to the Men's World Championship 2025.

## ✅ Changes Made

### 🌍 Team Updates
- **Updated team mappings** for all 32 World Championship teams
- **Added new teams**: Algeria, Chile, Colombia, Finland, Libya, Philippines, Qatar, Tunisia, etc.
- **Flag support** for all participating nations

### 🎨 Branding Updates  
- **Championship titles** throughout the app
- **Philippines 2025** tournament context
- **Men's World Championship** branding

### 🗑️ Data Clearing Script
- **`clear_tournament_data.py`** - Clears games and predictions, keeps users

## 🚀 Deployment Steps

### 1. Clear Tournament Data (Optional)
If you want to start fresh while keeping users:
```bash
# Run locally first to test:
python clear_tournament_data.py

# Or run on Render via shell:
# Go to Render dashboard → your service → Shell tab
# Run: python clear_tournament_data.py
```

### 2. Deploy Updates
```bash
git add .
git commit -m "Update to Men's World Championship 2025

- All 32 championship teams with flags
- Championship branding throughout app  
- Data clearing script for fresh start
- Ready for Philippines 2025 tournament

🏆 Generated with Claude Code"
git push origin main
```

### 3. Post-Deployment
1. **Set tournament deadline** in Admin panel
2. **Add championship games** as fixtures are announced
3. **Inform users** about the championship switch

## 🎯 What's Preserved
- ✅ **All user accounts** and login credentials
- ✅ **User preferences** and settings  
- ✅ **Database structure** and relationships
- ✅ **Admin permissions** and roles

## 🆕 What's Updated
- 🌍 **32 championship teams** instead of mixed teams
- 🏆 **Championship branding** and messaging
- 🇵🇭 **Philippines 2025** tournament context
- 🗑️ **Fresh tournament data** (if cleared)

## 📅 Championship Details
- **Dates**: September 12-28, 2025
- **Location**: Philippines (Manila)
- **Teams**: 32 qualified nations
- **Format**: Pools → Round of 16 → Knockout

Your existing Render deployment will automatically update when you push the changes!

🏐 Ready to predict the Men's World Championship! 🏆