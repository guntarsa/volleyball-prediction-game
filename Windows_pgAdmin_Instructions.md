# PostgreSQL Scripts for Windows pgAdmin

## 🪟 **Windows Setup Instructions**

### **Prerequisites:**
1. **Create backup folder**: Create `C:\temp\` folder on your Windows PC
2. **pgAdmin access**: Make sure pgAdmin can access local files (run as Administrator if needed)
3. **File permissions**: Ensure PostgreSQL service has write access to `C:\temp\`

### **Alternative Folder Paths:**
If `C:\temp\` doesn't work, you can use:
- `C:\Users\%USERNAME%\Documents\db_backup\`
- `D:\backup\` (if you have D: drive)
- Any folder that PostgreSQL service can access

## 📝 **How to Modify Scripts for Your System:**

### **1. Update Backup Paths**
In `backup_database.sql`, replace all instances of `C:\temp\` with your preferred folder:
```sql
-- Change this line:
) TO 'C:\temp\users_backup.sql';

-- To your preferred path:
) TO 'C:\Users\YourUsername\Documents\backup\users_backup.sql';
```

### **2. Update CSV Import Path**  
In `import_predictions_from_csv.sql`, update the CSV file path:
```sql
-- Change this line:
FROM 'C:\temp\predictions.csv' 

-- To your CSV file location:
FROM 'C:\Users\YourUsername\Documents\predictions.csv'
```

## 🚀 **Step-by-Step Usage:**

### **BACKUP Process:**
1. **Create folder**: `mkdir C:\temp` in Command Prompt
2. **Open pgAdmin** → Connect to your database
3. **Open Query Tool** → Load `backup_database.sql`
4. **Replace paths** if needed (see above)
5. **Execute script** → Backup files will be created in `C:\temp\`

### **RESTORE Process:**
1. **Open** `C:\temp\full_database_backup.sql` in Notepad
2. **Copy content** of the backup file
3. **Open pgAdmin** → Query Tool → Load `restore_database.sql`
4. **Paste backup data** in the designated section
5. **Execute script**

### **CSV IMPORT Process:**
1. **Prepare CSV file** using `sample_predictions_import.csv` as template
2. **Save CSV** to `C:\temp\predictions.csv`
3. **Open pgAdmin** → Load `import_predictions_from_csv.sql`
4. **Uncomment COPY command** and verify path
5. **Execute script**

## 🛠️ **Troubleshooting Windows Issues:**

### **"Permission Denied" Error:**
- Run pgAdmin as Administrator
- Check folder permissions
- Try using your Documents folder instead

### **"File Not Found" Error:**
- Use full absolute paths
- Use forward slashes: `C:/temp/file.csv` instead of `C:\temp\file.csv`
- Verify file exists in the specified location

### **"Access Denied to Server" Error:**
- Ensure PostgreSQL service has file system permissions
- Try copying files to PostgreSQL data directory
- Use pgAdmin's import/export wizard as alternative

## 📁 **Alternative Method - Manual Copy/Paste:**

If file operations don't work, you can:

1. **For Backup**: 
   - Run queries section by section
   - Copy results manually to text files

2. **For Import**:
   - Use METHOD 2 in the CSV import script
   - Manually enter INSERT statements

3. **For Restore**:
   - Copy backup SQL statements
   - Paste directly into pgAdmin query editor

## 🔧 **Windows-Specific File Paths Examples:**

```sql
-- Good Windows paths:
'C:/temp/backup.sql'
'C:/Users/John/Documents/backup.sql'
'D:/database_backups/backup.sql'

-- Problematic paths:
'C:\temp\backup.sql'     -- Use forward slashes
'/tmp/backup.sql'        -- Linux path, won't work
'backup.sql'             -- Need full path
```

## ✅ **Testing Your Setup:**

Run this simple test query in pgAdmin:
```sql
-- Test file write permissions
COPY (SELECT 'Test successful!' as message) TO 'C:/temp/test.txt';
```

If this works, your setup is correct for the backup scripts!

## 📞 **Need Help?**

If you encounter issues:
1. Check PostgreSQL error logs
2. Verify folder permissions
3. Try running pgAdmin as Administrator
4. Use the manual copy/paste method as fallback