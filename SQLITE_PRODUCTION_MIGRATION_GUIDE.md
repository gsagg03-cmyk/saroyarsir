# Production SQLite Migration & Deployment Guide

## 🎯 Overview
This guide explains how to safely migrate your production SQLite database to add:
- **JF/TF columns** to fees table (জানুয়ারি ফি and টিউশন ফি)
- **Holiday status** to attendance system
- **Day names** in monthly attendance view (Sat, Sun, Mon, etc.)

## ✅ What Gets Migrated

### Fees Table
- Adds `jf_amount` column (DECIMAL 10,2)
- Adds `tf_amount` column (DECIMAL 10,2)
- **Migrates existing data**: `amount` → `jf_amount` (preserves all data)
- Creates performance indexes

### Attendance Table
- Enables `holiday` status (no column changes needed)
- Creates performance indexes

### Monthly Attendance View
- Shows day names (Sat, Sun, Mon, etc.) under each date
- Example:
  ```
  ┌────────┬─────┬─────┬─────┬─────┐
  │ Name   │  1  │  2  │  3  │  4  │
  │        │ Mon │ Tue │ Wed │ Thu │
  ├────────┼─────┼─────┼─────┼─────┤
  │ Karim  │  P  │  H  │  A  │  P  │
  └────────┴─────┴─────┴─────┴─────┘
  ```

## 🔐 Safety Features

✅ **Automatic Backup**: Creates timestamped backup before any changes
✅ **No Data Loss**: All existing data is preserved and migrated
✅ **Idempotent**: Can run multiple times safely
✅ **Rollback Ready**: Easy to restore from backup if needed
✅ **Production Confirmation**: Requires 'MIGRATE' confirmation for production

## 📋 Pre-Migration Checklist

### For Development
- [ ] Ensure you have Python 3.8+
- [ ] Database file exists and is accessible
- [ ] At least 10MB free disk space for backup

### For Production
- [ ] Take manual backup of database (optional, script does this)
- [ ] Stop application (recommended but not required)
- [ ] Verify database file path is correct
- [ ] Have 30-60 minutes maintenance window
- [ ] Test on development/staging first

## 🚀 Migration Steps

### Step 1: Upload Migration Script

Upload `production_safe_migration.py` to your server:

```bash
# For local/development
cd /workspaces/saroyarsir

# For VPS/production
cd /var/www/saroyarsir
# Upload production_safe_migration.py here
```

### Step 2: Run Migration (Development First)

**Test on development:**
```bash
python production_safe_migration.py --env development
```

**Expected output:**
```
======================================================================
PRODUCTION-SAFE SQLITE MIGRATION
======================================================================
Environment: DEVELOPMENT
Database: /path/to/smartgardenhub.db
======================================================================

[1/5] Creating Database Backup...
✓ Backup created: backups/production_backup_20251122_173028.db (180 KB)

[2/5] Connecting to Database...
✓ Connected to development database

[3/5] Migrating Fees Table (JF/TF columns)...
  ✓ Found 2 existing fee records
  ✓ Added jf_amount column
  ✓ Added tf_amount column
  ✓ Migrated 2 records to jf_amount

[4/5] Verifying Attendance Table (Holiday status)...
  ✓ Attendance table ready for 'holiday' status

[5/5] Creating Performance Indexes...
  ✓ Created 4 performance indexes

======================================================================
✅ MIGRATION COMPLETED SUCCESSFULLY!
======================================================================
```

### Step 3: Verify Data Integrity

**Check fees table:**
```bash
sqlite3 smartgardenhub.db "SELECT id, user_id, jf_amount, tf_amount, amount FROM fees LIMIT 5;"
```

**Expected:** All existing fees should have their `amount` copied to `jf_amount`, `tf_amount` set to 0.

**Check attendance table:**
```bash
sqlite3 smartgardenhub.db "SELECT COUNT(*) FROM attendance;"
```

### Step 4: Run on Production

**IMPORTANT**: Only run after testing on development!

```bash
cd /var/www/saroyarsir
python production_safe_migration.py --env production
```

**You will be prompted:**
```
⚠️  WARNING: PRODUCTION MIGRATION
This will modify your production database.
A backup will be created automatically.

Type 'MIGRATE' to continue: 
```

Type `MIGRATE` (all caps) and press Enter.

### Step 5: Restart Application (Production)

```bash
# If using systemd
sudo systemctl restart saroyarsir

# If using supervisor
sudo supervisorctl restart saroyarsir

# If using gunicorn manually
pkill -f gunicorn
cd /var/www/saroyarsir
gunicorn -b 0.0.0.0:5000 "app:create_app()" &
```

## 🧪 Post-Migration Testing

### 1. Test Fee Management
- [ ] Login as teacher/admin
- [ ] Go to Fee Management
- [ ] Select a batch and year
- [ ] Verify JF and TF columns are visible
- [ ] Try entering JF and TF amounts
- [ ] Save and verify data persists

### 2. Test Attendance
- [ ] Go to Attendance Management
- [ ] Mark Attendance tab
- [ ] Select batch and date
- [ ] Verify 3 buttons: P, A, H
- [ ] Mark some students as holiday (H)
- [ ] Save attendance
- [ ] Go to Monthly Sheet tab
- [ ] Verify holidays show as "H" (orange)
- [ ] Verify day names appear (Mon, Tue, etc.)

### 3. Verify Data Integrity
```bash
# Check fee totals match
sqlite3 smartgardenhub.db "SELECT SUM(amount), SUM(jf_amount + tf_amount) FROM fees;"
# Both numbers should be identical

# Check attendance records
sqlite3 smartgardenhub.db "SELECT COUNT(*), status FROM attendance GROUP BY status;"
```

## 🔄 Rollback Procedure

If anything goes wrong:

### Option 1: Automatic Backup (Recommended)

```bash
# Stop application
sudo systemctl stop saroyarsir

# Find backup file
ls -lh backups/production_backup_*.db

# Restore from backup
cp backups/production_backup_YYYYMMDD_HHMMSS.db smartgardenhub.db

# Restart application
sudo systemctl start saroyarsir
```

### Option 2: Manual Backup

If you created a manual backup before migration:

```bash
sudo systemctl stop saroyarsir
cp /path/to/your/backup.db smartgardenhub.db
sudo systemctl start saroyarsir
```

## 📊 Database Schema Changes

### Fees Table (Before)
```sql
CREATE TABLE fees (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    batch_id INTEGER,
    amount DECIMAL(10,2),
    -- other columns...
);
```

### Fees Table (After)
```sql
CREATE TABLE fees (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    batch_id INTEGER,
    amount DECIMAL(10,2),      -- kept for compatibility
    jf_amount DECIMAL(10,2),   -- NEW: জানুয়ারি ফি
    tf_amount DECIMAL(10,2),   -- NEW: টিউশন ফি
    -- other columns...
);
```

### Indexes Created
```sql
CREATE INDEX idx_fees_user_date ON fees(user_id, due_date);
CREATE INDEX idx_fees_batch_date ON fees(batch_id, due_date);
CREATE INDEX idx_attendance_user_date ON attendance(user_id, date);
CREATE INDEX idx_attendance_batch_date ON attendance(batch_id, date);
```

## 📝 Files Changed

### Backend
- `models.py` - Added HOLIDAY to AttendanceStatus
- `production_safe_migration.py` - Migration script (NEW)

### Frontend
- `templates/partials/attendance_management.html` - Added H button, day names
- `templates/dashboard_teacher.html` - Added getDayName() function

## 💡 Best Practices

### Backup Retention
- Keep automatic backups for **30 days**
- Create manual backup before production migration
- Store backups in separate location/drive

### Monitoring
```bash
# Monitor application logs
tail -f /var/log/saroyarsir/error.log

# Monitor database size
watch -n 60 'du -h smartgardenhub.db'
```

### Regular Maintenance
```bash
# Vacuum database monthly (optimizes file size)
sqlite3 smartgardenhub.db "VACUUM;"

# Analyze for query optimization
sqlite3 smartgardenhub.db "ANALYZE;"
```

## 🆘 Troubleshooting

### Issue: "Database is locked"
**Solution:**
```bash
# Stop application first
sudo systemctl stop saroyarsir
# Run migration
python production_safe_migration.py --env production
# Restart application
sudo systemctl start saroyarsir
```

### Issue: "Backup failed"
**Cause:** Insufficient disk space or permissions
**Solution:**
```bash
# Check disk space
df -h

# Check permissions
ls -l smartgardenhub.db
chmod 644 smartgardenhub.db
```

### Issue: "No data in JF/TF columns"
**Expected:** First time - data migrates from `amount` to `jf_amount`
**Verify:**
```bash
sqlite3 smartgardenhub.db "SELECT COUNT(*) FROM fees WHERE jf_amount > 0;"
```

### Issue: "Day names not showing"
**Solution:**
- Clear browser cache (Ctrl+Shift+R)
- Verify `dashboard_teacher.html` is updated
- Check browser console for JavaScript errors

## 📞 Support Commands

### Database Info
```bash
# Table structure
sqlite3 smartgardenhub.db ".schema fees"
sqlite3 smartgardenhub.db ".schema attendance"

# Record counts
sqlite3 smartgardenhub.db "SELECT 
    (SELECT COUNT(*) FROM fees) as total_fees,
    (SELECT COUNT(*) FROM attendance) as total_attendance;"

# Check indexes
sqlite3 smartgardenhub.db ".indexes fees"
```

### Backup Management
```bash
# List all backups
ls -lh backups/

# Cleanup old backups (older than 30 days)
find backups/ -name "production_backup_*.db" -mtime +30 -delete
```

---

## ✅ Success Checklist

After migration, verify:
- [ ] Application starts without errors
- [ ] Fee management shows JF and TF columns
- [ ] Existing fee data is intact
- [ ] Attendance has P, A, H buttons
- [ ] Monthly attendance shows day names
- [ ] Holiday status displays with orange "H"
- [ ] Backup file created successfully
- [ ] No data loss confirmed

---

**Migration prepared by:** GitHub Copilot  
**Date:** November 22, 2025  
**Version:** 1.0 - Production Safe  
**Tested on:** SQLite 3.x, Python 3.12
