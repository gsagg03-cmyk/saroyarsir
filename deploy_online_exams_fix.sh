#!/bin/bash
# Quick deployment and diagnostic script for Online Exams fix

echo "=============================================="
echo "Online Exams & Resources - Fix Deployment"
echo "=============================================="
echo ""

# Step 1: Pull latest
echo "Step 1: Pulling latest code..."
git pull || { echo "❌ Git pull failed"; exit 1; }
echo "✅ Code updated"
echo ""

# Step 2: Restart service
echo "Step 2: Restarting service..."
systemctl restart saro.service || { echo "❌ Service restart failed"; exit 1; }
sleep 2
systemctl status saro.service --no-pager -l | head -20
echo "✅ Service restarted"
echo ""

# Step 3: Run diagnostic
echo "Step 3: Running diagnostic..."
python3 debug_online_exams_full.py
echo ""

# Step 4: Ask about auto-publish
echo "=============================================="
read -p "Auto-publish ready exams? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]
then
    python3 publish_ready_exams.py
    echo "✅ Published exams"
fi
echo ""

# Step 5: Show final status
echo "=============================================="
echo "DEPLOYMENT COMPLETE"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Test student login in INCOGNITO browser"
echo "2. Click 'Online Exam' tab"
echo "3. Look for 'v1.2' badge (confirms latest UI)"
echo "4. Check browser console for:"
echo "   - 🎯 student_online_exams partial init triggered"
echo "   - ✅ Published exams for student: N"
echo ""
echo "If still showing 0 exams:"
echo "  - Hard refresh: Ctrl+Shift+R"
echo "  - Check console logs for errors"
echo "  - Run: journalctl -u saro.service -n 50 | grep online_exams"
echo ""
echo "Teacher actions needed:"
echo "  - For each exam: Click eye icon to publish"
echo "  - Or: Manage Questions → Save All & Publish"
echo ""
