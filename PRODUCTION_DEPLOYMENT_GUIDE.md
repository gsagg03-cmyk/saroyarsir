# Production Deployment Guide - JF/TF Fee System

## 📋 Overview
This guide covers deploying the JF (জানুয়ারি ফি) and TF (টিউশন ফি) fee system to production.

## 🗄️ Database Schema

### Fees Table Structure
```sql
fees
├── id                 INTEGER PRIMARY KEY
├── user_id            INTEGER (FK to users)
├── batch_id           INTEGER (FK to batches)
├── amount             DECIMAL(10,2)  -- Total (jf_amount + tf_amount)
├── jf_amount          DECIMAL(10,2)  -- জানুয়ারি ফি (NEW)
├── tf_amount          DECIMAL(10,2)  -- টিউশন ফি (NEW)
├── exam_fee           DECIMAL(10,2)  -- Per student exam fee
├── others_fee         DECIMAL(10,2)  -- Per student other fees
├── due_date           DATE
├── paid_date          DATE
├── status             ENUM(pending/paid/overdue/cancelled)
├── payment_method     VARCHAR(50)
├── transaction_id     VARCHAR(255)
├── late_fee           DECIMAL(10,2)
├── discount           DECIMAL(10,2)
├── notes              TEXT
├── created_at         DATETIME
└── updated_at         DATETIME
```

## 🚀 Deployment Steps

### 1. Backup Current Database
```bash
# For VPS/Production
cd /var/www/saroyarsir
cp smartgardenhub.db smartgardenhub_backup_$(date +%Y%m%d_%H%M%S).db

# For local/development
cd /workspaces/saroyarsir
cp smartgardenhub.db smartgardenhub_backup_$(date +%Y%m%d_%H%M%S).db
```

### 2. Upload Files to Production Server

Upload these files to your VPS:
```
/var/www/saroyarsir/
├── models.py                          (UPDATED)
├── routes/fees_new.py                 (UPDATED)
├── templates/templates/partials/
│   └── fee_management_new.html        (UPDATED)
├── production_migrate_jf_tf.py        (NEW)
└── schema_fees_jf_tf_production.sql   (NEW - reference only)
```

### 3. Run Database Migration

#### On Development (First):
```bash
cd /workspaces/saroyarsir
python production_migrate_jf_tf.py --env development
```

#### On Production (After testing):
```bash
cd /var/www/saroyarsir
python production_migrate_jf_tf.py --env production
```

**Migration will prompt for confirmation on production!**

### 4. Restart Application

```bash
# If using systemd
sudo systemctl restart saroyarsir

# If using supervisor
sudo supervisorctl restart saroyarsir

# If running manually with gunicorn
pkill -f gunicorn
gunicorn -b 0.0.0.0:5000 app:create_app() &
```

### 5. Verify Deployment

1. **Check Database Columns**:
```bash
sqlite3 smartgardenhub.db ".schema fees"
```

Should show `jf_amount` and `tf_amount` columns.

2. **Test Fee Management Interface**:
   - Login as teacher/admin
   - Go to Fee Management
   - Select a batch and year
   - Verify you see JF and TF columns for each month
   - Test entering data and saving

3. **Verify Data Integrity**:
```bash
sqlite3 smartgardenhub.db "SELECT COUNT(*) FROM fees WHERE amount != (jf_amount + tf_amount) AND amount > 0;"
```

Should return `0` (no inconsistent records).

## 📊 Migration Script Features

### Safety Features
✅ **Automatic Backup**: Creates backup before any changes  
✅ **Idempotent**: Can run multiple times safely  
✅ **Transaction-based**: Rolls back on error  
✅ **Data Validation**: Checks integrity after migration  
✅ **Production Confirmation**: Requires 'YES' confirmation for production  

### What It Does
1. Connects to database
2. Checks if fees table exists
3. Creates automatic backup
4. Adds `jf_amount` and `tf_amount` columns (if not exist)
5. Migrates existing data (amount → jf_amount)
6. Validates data integrity
7. Fixes any inconsistencies
8. Reports statistics

## 🔧 Rollback Procedure

If something goes wrong:

```bash
# Stop the application
sudo systemctl stop saroyarsir

# Restore from backup
cd /var/www/saroyarsir
cp smartgardenhub_backup_YYYYMMDD_HHMMSS.db smartgardenhub.db

# Or use automatic backup created by migration script
cp backups/fees_backup_YYYYMMDD_HHMMSS.db smartgardenhub.db

# Restart application
sudo systemctl start saroyarsir
```

## 🧪 Testing Checklist

### Before Production Deployment
- [ ] Test migration on development database
- [ ] Verify JF/TF columns display correctly
- [ ] Test data entry with Enter key navigation
- [ ] Test saving fees (both JF and TF)
- [ ] Verify monthly totals calculation
- [ ] Verify yearly totals calculation
- [ ] Test with multiple students and batches
- [ ] Check performance with large datasets

### After Production Deployment
- [ ] Verify database migration completed successfully
- [ ] Check application starts without errors
- [ ] Test fee management interface
- [ ] Verify existing fee data is intact
- [ ] Test new fee entry with JF and TF
- [ ] Check calculations are correct
- [ ] Monitor error logs for 24 hours

## 📈 Performance Considerations

### Recommended Indexes
```sql
CREATE INDEX IF NOT EXISTS idx_fees_user_date 
ON fees(user_id, due_date);

CREATE INDEX IF NOT EXISTS idx_fees_batch_date 
ON fees(batch_id, due_date);

CREATE INDEX IF NOT EXISTS idx_fees_status 
ON fees(status);

CREATE INDEX IF NOT EXISTS idx_fees_year_month 
ON fees(strftime('%Y-%m', due_date));
```

Add these after migration for better query performance.

## 🐛 Troubleshooting

### Issue: Columns already exist error
**Solution**: This is normal if you ran migration before. Script is idempotent.

### Issue: Data inconsistency (amount != jf_amount + tf_amount)
**Solution**: Run validation query and fix:
```sql
UPDATE fees 
SET amount = jf_amount + tf_amount
WHERE amount != (jf_amount + tf_amount);
```

### Issue: Migration script fails
**Solution**: 
1. Check database file permissions
2. Ensure enough disk space
3. Check error logs
4. Restore from backup if needed

### Issue: Frontend doesn't show JF/TF columns
**Solution**:
1. Clear browser cache
2. Hard refresh (Ctrl+Shift+R)
3. Check browser console for errors
4. Verify template file is updated

## 📝 Post-Deployment Tasks

1. **Monitor Application Logs**:
```bash
tail -f /var/log/saroyarsir/error.log
```

2. **Monitor Database Size**:
```bash
du -sh /var/www/saroyarsir/smartgardenhub.db
```

3. **Set up Automated Backups**:
```bash
# Add to crontab
0 2 * * * cd /var/www/saroyarsir && cp smartgardenhub.db backups/daily_$(date +\%Y\%m\%d).db && find backups/ -name "daily_*.db" -mtime +30 -delete
```

4. **Train Users**:
   - Show how to enter JF and TF amounts
   - Demonstrate Enter key navigation
   - Explain monthly and yearly totals

## 🔐 Security Notes

- Database backup files contain sensitive data
- Store backups in secure location
- Implement proper file permissions (chmod 600 for .db files)
- Regular backup rotation (keep last 30 days)

## 📞 Support

For issues or questions:
1. Check error logs
2. Review this guide
3. Test on development first
4. Create backup before any fixes

---

**Deployment Date**: _______________  
**Deployed By**: _______________  
**Production URL**: _______________  
**Backup Location**: _______________
