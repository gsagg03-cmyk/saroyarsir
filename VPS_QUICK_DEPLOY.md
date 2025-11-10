# 🚀 VPS DEPLOYMENT - QUICK REFERENCE

## ✅ Everything is pushed to GitHub!

### 📦 What's Included:
- ✅ Complete online exam system (Bangla + equations support)
- ✅ Mobile-responsive student exam interface
- ✅ Fee system with 14 columns (12 months + exam_fee + other_fee)
- ✅ SMS templates permanent save
- ✅ Monthly exam cascade delete fix
- ✅ SQLite production database configuration
- ✅ Systemd service file

---

## 🔗 Database Configuration

### Development (Your local):
```
sqlite:////workspaces/saroyarsir/smartgardenhub.db
```

### Production (VPS):
```
sqlite:////root/saroyarsir/smartgardenhub_production.db
```

**Both are configured automatically in `config.py` and `app.py`**

---

## 🖥️ Deploy to VPS (SSH Commands)

### Option 1: Quick Deploy Script
```bash
ssh root@your-vps-ip
cd /root/saroyarsir
git pull origin main
chmod +x deploy_to_vps_sqlite.sh
./deploy_to_vps_sqlite.sh
```

### Option 2: Manual Step by Step
```bash
ssh root@your-vps-ip
cd /root/saroyarsir

# Pull code
git pull origin main

# Stop service
sudo systemctl stop saro_vps

# Set environment
export FLASK_ENV=production

# Copy service file
sudo cp saro_vps.service /etc/systemd/system/

# Reload and start
sudo systemctl daemon-reload
sudo systemctl start saro_vps
sudo systemctl enable saro_vps

# Check status
sudo systemctl status saro_vps
```

---

## 🔐 Default Login (Production)

### Admin/Super User:
- Phone: `01700000000`
- Password: `admin123`

### Teacher:
- Phone: `01800000000`
- Password: `teacher123`

**⚠️ Change passwords after first login!**

---

## 📁 Important Files on VPS

### Service File:
```
/etc/systemd/system/saro_vps.service
```

### Database File:
```
/root/saroyarsir/smartgardenhub_production.db
```

### App Directory:
```
/root/saroyarsir/
```

### Logs:
```
sudo journalctl -u saro_vps -f
```

---

## 🌐 Access Application

### After deployment, access at:
```
http://YOUR_VPS_IP:8001
```

Example:
```
http://192.168.1.100:8001
```

Or with domain:
```
http://yourdomain.com:8001
```

---

## 🔧 Service Commands

```bash
# Start
sudo systemctl start saro_vps

# Stop
sudo systemctl stop saro_vps

# Restart
sudo systemctl restart saro_vps

# Status
sudo systemctl status saro_vps

# Logs (live)
sudo journalctl -u saro_vps -f

# Logs (last 100 lines)
sudo journalctl -u saro_vps -n 100
```

---

## 🆘 Troubleshooting

### Service won't start?
```bash
sudo journalctl -u saro_vps -n 50
sudo lsof -i :8001
sudo kill -9 $(sudo lsof -t -i:8001)
sudo systemctl restart saro_vps
```

### Database issues?
```bash
ls -la /root/saroyarsir/*.db
chmod 644 /root/saroyarsir/smartgardenhub_production.db
```

### Can't access from browser?
```bash
sudo systemctl status saro_vps
sudo netstat -tulpn | grep 8001
sudo ufw allow 8001/tcp
```

---

## 📊 Database Backup (Recommended)

### Create backup directory:
```bash
mkdir -p /root/backups
```

### Daily backup command:
```bash
cp /root/saroyarsir/smartgardenhub_production.db \
   /root/backups/smartgardenhub_$(date +%Y%m%d).db
```

### Add to crontab (daily at 2 AM):
```bash
crontab -e
```
Add line:
```
0 2 * * * cp /root/saroyarsir/smartgardenhub_production.db /root/backups/smartgardenhub_$(date +\%Y\%m\%d).db
```

---

## ✨ New Features Ready to Use

### 1. Online Exams
- Teacher creates exam with 20-40 questions
- Supports Bangla text: **বাংলায় প্রশ্ন লিখুন**
- Supports equations: **$$E=mc^2$$** or **$$x^2+y^2=z^2$$**
- Mobile-responsive student interface
- Auto-submit when timer ends
- Instant results

### 2. Fee Management
- 14 columns: January to December + Exam Fee + Other Fee
- Automatic total calculation
- Bulk create fees for all students

### 3. SMS Templates
- Save permanently to database
- Use everywhere in the system

---

## 📝 GitHub Repository

All code is at:
```
https://github.com/sa5613675-jpg/saroyarsir
```

Latest commit includes:
- Online exam system
- Fee system updates
- SMS fixes
- Mobile responsive UI
- Bangla & equation support
- VPS deployment scripts

---

## 🎯 You're Ready!

1. ✅ Code pushed to GitHub
2. ✅ SQLite configured for production
3. ✅ Service file ready
4. ✅ Deployment script ready
5. ✅ All features working

**Just SSH to VPS and run the deployment script!**

```bash
ssh root@your-vps-ip
cd /root/saroyarsir
git pull
./deploy_to_vps_sqlite.sh
```

**That's it! Your app will be live on port 8001** 🚀
