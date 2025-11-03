# VPS Deployment - Final Production Ready Guide

## 🚀 Quick Start

### SSH into your VPS
```bash
ssh user@YOUR_VPS_IP
```

### One-Command Deployment
```bash
git clone https://github.com/sahidrahman1/saroyarsir.git
cd saroyarsir
chmod +x deploy_vps_final.sh
./deploy_vps_final.sh
```

---

## 📡 IMPORTANT: Database Check URLs

After deployment, verify your database is working properly:

### 1. Comprehensive Database Check
```
http://YOUR_VPS_IP:8001/api/database/check
```
**Shows:** All tables, record counts, health status, sample data

### 2. Quick Statistics
```
http://YOUR_VPS_IP:8001/api/database/stats
```
**Shows:** User counts, exams, attendance, fees, SMS stats

### 3. Table Information
```
http://YOUR_VPS_IP:8001/api/database/tables
```
**Shows:** All database tables and their columns

### 4. Application Health
```
http://YOUR_VPS_IP:8001/health
```
**Shows:** Overall application status

---

## ⚙️ Configuration

### Port: 8001
### Host: 0.0.0.0 (all interfaces)

The application is configured to run on port **8001** and bind to all network interfaces (0.0.0.0).

---

## 🔧 Service Management

```bash
# Check status
sudo systemctl status smartgardenhub

# Restart
sudo systemctl restart smartgardenhub

# View logs
sudo journalctl -u smartgardenhub -f

# Error logs
tail -f logs/error.log
```

---

## 🗄️ Database Verification

### Via Script
```bash
cd /home/YOUR_USER/saroyarsir
source venv/bin/activate
python check_database_vps.py
```

### Via Browser
Open in your browser:
```
http://YOUR_VPS_IP:8001/api/database/check
```

---

## 🔄 Update Application

```bash
cd /home/YOUR_USER/saroyarsir

# Backup database
cp madrasha.db backups/backup_$(date +%Y%m%d).db

# Pull latest code
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart
sudo systemctl restart smartgardenhub
```

---

## 🐛 Troubleshooting

### Service not running?
```bash
sudo journalctl -u smartgardenhub -n 50
tail -f logs/error.log
```

### Port already in use?
```bash
sudo lsof -i :8001
sudo pkill -f "gunicorn"
sudo systemctl restart smartgardenhub
```

### Database issues?
```bash
# Check database file
ls -lh madrasha.db

# Verify via API
curl http://localhost:8001/api/database/check
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] Service running: `sudo systemctl status smartgardenhub`
- [ ] Port open: `sudo netstat -tulpn | grep 8001`
- [ ] Application responds: `curl http://localhost:8001/health`
- [ ] Database working: `curl http://localhost:8001/api/database/check`
- [ ] Can access via browser: `http://YOUR_VPS_IP:8001`

---

## 📊 Monitoring

```bash
# Watch service
watch -n 5 'sudo systemctl status smartgardenhub'

# Monitor logs
tail -f logs/error.log logs/access.log

# System resources
htop
```

---

## 🔥 Firewall

```bash
# Allow port 8001
sudo ufw allow 8001/tcp

# Check firewall status
sudo ufw status
```

---

## 📝 Quick Commands Reference

```bash
# Deployment
./deploy_vps_final.sh

# Check database
python check_database_vps.py

# Restart service
sudo systemctl restart smartgardenhub

# View logs
sudo journalctl -u smartgardenhub -f

# Update app
git pull && source venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart smartgardenhub
```

---

## 🌐 Access Points

Replace `YOUR_VPS_IP` with your actual VPS IP address:

- **Main App:** `http://YOUR_VPS_IP:8001`
- **Database Check:** `http://YOUR_VPS_IP:8001/api/database/check`
- **Statistics:** `http://YOUR_VPS_IP:8001/api/database/stats`
- **Health:** `http://YOUR_VPS_IP:8001/health`

---

## 💾 Backup Strategy

```bash
# Manual backup
cp madrasha.db backups/backup_$(date +%Y%m%d_%H%M%S).db

# Automated daily backup (add to crontab)
0 2 * * * cd /home/YOUR_USER/saroyarsir && cp madrasha.db backups/daily_$(date +\%Y\%m\%d).db
```

---

**🎯 Key Points:**
1. Application runs on port **8001**
2. Database check URL: `http://YOUR_VPS_IP:8001/api/database/check`
3. All latest features included (Monthly Exams, SMS Templates, Archive Students)
4. Auto-restart enabled via systemd
5. Production-ready configuration
