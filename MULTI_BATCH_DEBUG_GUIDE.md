# Multi-Batch Student Debug Guide

## Issue

Students enrolled in multiple batches cannot see:
- Monthly exams from all their batches
- Online resources

## Debugging Steps

### Step 1: Deploy Latest Changes

```bash
cd /var/www/saroyarsir
git pull
systemctl restart saro.service
systemctl status saro.service
```

### Step 2: Check Database - Student Batch Enrollment

```bash
cd /var/www/saroyarsir
python3 check_student_batches.py
```

**Expected Output:**
```
📊 Total active students: X
🎓 Students with multiple batches: Y

MULTI-BATCH STUDENTS
👤 Student Name
   Phone: 01712345678
   Batches:
     - HSC Physics (ID: 5)
     - HSC Chemistry (ID: 8)
```

If no multi-batch students found, you need to create one first!

### Step 3: Test Login with Debug Console

1. **Open Browser in Incognito Mode** (Ctrl+Shift+N)

2. **Open Console (F12)** before logging in

3. **Login as student** with phone that has multiple batches

4. **Check Console Output** - Should see:

```javascript
💾 Storing user data in localStorage: {Object}
💾 User batches: Array(2) [{id: 5, name: "HSC Physics"}, {id: 8, name: "HSC Chemistry"}]
💾 User allBatchIds: Array(2) [5, 8]
💾 User batchId: 5
```

**❌ If you see:**
```javascript
💾 User batches: undefined
💾 User allBatchIds: undefined
```
→ **Problem: Session data not being passed to template!**

### Step 4: Check Monthly Exams Tab

1. Click "Monthly Exams" in sidebar

2. **Check Console** - Should see:

```javascript
📚 Student Monthly Exams - User data: {Object}
📚 user.allBatchIds: [5, 8]
📚 user.batches: Array(2)
📚 user.batchId: 5
📚 Loading monthly exams from batches: [5, 8]
✅ Loaded 6 exams from 2 batch(es)
```

**❌ If you see:**
```javascript
📚 user.allBatchIds: undefined
📚 user.batches: undefined
❌ No batch IDs found! User object: {...}
```
→ **Problem: localStorage doesn't have batch data!**

### Step 5: Check Online Resources Tab

1. Click "Online Resources" in sidebar

2. **Check Console** - Should see:

```javascript
📄 Documents - User data: {Object}
📄 User batches: Array(2)
📄 User allBatchIds: [5, 8]
📡 Loading documents from /api/documents/
✅ Total documents loaded: N
```

## Common Issues & Solutions

### Issue 1: `user.batches` and `allBatchIds` are undefined

**Cause:** Session data not being properly passed to template

**Solution:** Check routes/auth.py login function:

```bash
cd /var/www/saroyarsir
grep -A 20 "session_user\['batches'\]" routes/auth.py
```

Should see:
```python
session_user['batches'] = all_batches
session_user['allBatchIds'] = all_batch_ids
```

### Issue 2: Student has batches but console shows empty arrays

**Cause:** Batches not properly loaded from database

**Check Database:**
```bash
cd /var/www/saroyarsir
sqlite3 smartgardenhub.db
```

```sql
-- Check student's batch enrollment
SELECT u.first_name, u.last_name, u.phoneNumber, b.name as batch_name, b.id as batch_id
FROM users u
JOIN user_batches ub ON u.id = ub.user_id
JOIN batches b ON ub.batch_id = b.id
WHERE u.phoneNumber = '01712345678'
  AND u.role = 'student';
```

Should return multiple rows if student is in multiple batches.

### Issue 3: Session has data but localStorage is empty

**Cause:** JavaScript error or template issue

**Solution:**

1. Check browser console for JavaScript errors
2. Clear localStorage and try again:
   ```javascript
   localStorage.clear();
   // Logout and login again
   ```

3. Hard refresh: `Ctrl+Shift+R`

### Issue 4: Only sees first batch, not all batches

**Cause:** Frontend code using `user.batchId` instead of `user.allBatchIds`

**Check:** Look at console output when loading monthly exams:
```javascript
📚 Loading monthly exams from batches: [5]  // ❌ Only one batch
```

Should be:
```javascript
📚 Loading monthly exams from batches: [5, 8]  // ✅ All batches
```

## Testing Checklist

### Create Test Students

**Option 1: Sibling Students (Same Phone, Different Children)**

```
Student 1:
- Name: Test Student One
- Phone: 01712345678
- Batch: HSC Physics

Student 2:
- Name: Test Student Two
- Phone: 01712345678 (same!)
- Batch: HSC Chemistry
```

**Option 2: Same Student, Multiple Batches**

```
Student 1:
- Name: Test Student
- Phone: 01798765432
- Batch: HSC Physics

Then add SAME student again:
- Name: Test Student (exact same!)
- Phone: 01798765432
- Batch: HSC Chemistry
```

### Verify Login

1. Login with phone `01712345678`
2. Password: `student123`
3. Check console immediately after login
4. Navigate to Monthly Exams - should see exams from BOTH batches
5. Navigate to Online Resources - should load documents

## Expected Console Output (Full Flow)

```javascript
// === LOGIN ===
💾 Storing user data in localStorage: {
  id: 123,
  role: "student",
  name: "Test Student One & Test Student Two",
  phoneNumber: "01712345678",
  batches: [
    {id: 5, name: "HSC Physics"},
    {id: 8, name: "HSC Chemistry"}
  ],
  allBatchIds: [5, 8],
  batchId: 5,
  isMultiStudent: true
}
💾 User batches: Array(2)
💾 User allBatchIds: [5, 8]
💾 User batchId: 5

// === MONTHLY EXAMS TAB ===
📚 Student Monthly Exams - User data: {Object}
📚 user.allBatchIds: [5, 8]
📚 user.batches: Array(2)
📚 user.batchId: 5
📚 Loading monthly exams from batches: [5, 8]
📡 Fetching: /api/monthly-exams?batch_id=5
📡 Fetching: /api/monthly-exams?batch_id=8
✅ Loaded 6 exams from 2 batch(es)

// === ONLINE RESOURCES TAB ===
📄 Documents - User data: {Object}
📄 User batches: Array(2)
📄 User allBatchIds: [5, 8]
📡 Loading documents from /api/documents/
📡 Documents response status: 200
✅ Total documents loaded: 5
```

## Manual Fix if Session Data Missing

If `check_student_batches.py` shows students have batches but login console shows undefined:

1. **Check auth.py is collecting batches:**

```bash
cd /var/www/saroyarsir
tail -f /var/log/saro.log | grep -i batch
```

Then login and check logs.

2. **Add temporary debug to auth.py:**

After line that sets `session_user['batches']`:
```python
print(f"DEBUG: session_user batches = {session_user.get('batches')}")
print(f"DEBUG: session_user allBatchIds = {session_user.get('allBatchIds')}")
```

3. **Restart and check logs:**
```bash
systemctl restart saro.service
journalctl -u saro.service -f
```

Then login and watch for DEBUG lines.

## Quick Test Commands

**Check if student has batches:**
```bash
cd /var/www/saroyarsir
python3 -c "
from app import app
from models import User, UserRole

with app.app_context():
    student = User.query.filter_by(phoneNumber='01712345678', role=UserRole.STUDENT).first()
    if student:
        print(f'Student: {student.first_name} {student.last_name}')
        print(f'Batches: {[b.name for b in student.batches]}')
    else:
        print('Student not found')
"
```

**Check session keys:**
```bash
# In Python console on VPS
from flask import session
# After login
print(session.get('user', {}).keys())
# Should include: 'batches', 'allBatchIds', 'batchId'
```

## Success Criteria

✅ `check_student_batches.py` shows student(s) with multiple batches  
✅ Login console shows `allBatchIds: [X, Y]`  
✅ Login console shows `batches: Array(2)`  
✅ Monthly exams console shows "Loading from batches: [X, Y]"  
✅ Monthly exams console shows "Loaded N exams from 2 batch(es)"  
✅ Online resources console shows "User batches: Array(2)"  
✅ Student sees exams from ALL enrolled batches  
✅ Student can view online resources  

## Contact Points

If issue persists after all debugging:

1. Share screenshot of browser console after login
2. Share output of `check_student_batches.py`
3. Share output of:
   ```bash
   journalctl -u saro.service -n 100 | grep -i batch
   ```
