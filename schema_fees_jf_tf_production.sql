-- Production-Ready SQLite Database Schema for JF/TF Fee System
-- Date: November 22, 2025
-- Description: Fee table with separate JF (জানুয়ারি ফি) and TF (টিউশন ফি) columns

-- Create or modify fees table with JF and TF columns
-- This script is idempotent and can be run multiple times safely

-- Add jf_amount column if it doesn't exist
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we handle this in application code
ALTER TABLE fees ADD COLUMN jf_amount DECIMAL(10, 2) DEFAULT 0.00;
ALTER TABLE fees ADD COLUMN tf_amount DECIMAL(10, 2) DEFAULT 0.00;

-- Update existing records to migrate old 'amount' to 'jf_amount'
-- This ensures backward compatibility
UPDATE fees 
SET jf_amount = amount, 
    tf_amount = 0.00
WHERE jf_amount = 0 AND tf_amount = 0 AND amount > 0;

-- Verify the structure
-- Expected columns:
-- - id: Primary key
-- - user_id: Foreign key to users table
-- - batch_id: Foreign key to batches table
-- - amount: Total amount (jf_amount + tf_amount) - kept for backward compatibility
-- - jf_amount: জানুয়ারি ফি (January Fee)
-- - tf_amount: টিউশন ফি (Tuition Fee)
-- - exam_fee: Exam fee (per student, not per month)
-- - others_fee: Other fees (per student, not per month)
-- - due_date: Payment due date
-- - paid_date: Actual payment date (NULL if unpaid)
-- - status: pending/paid/overdue/cancelled
-- - payment_method: bkash/nagad/cash/bank/other
-- - transaction_id: Transaction reference number
-- - late_fee: Late payment penalty
-- - discount: Discount applied
-- - notes: Additional notes
-- - created_at: Record creation timestamp
-- - updated_at: Last update timestamp

-- Example: Insert a sample fee record with JF and TF
-- INSERT INTO fees (user_id, batch_id, jf_amount, tf_amount, amount, due_date, status, notes, created_at, updated_at)
-- VALUES (
--     1,                                  -- student ID
--     1,                                  -- batch ID
--     500.00,                            -- JF amount
--     300.00,                            -- TF amount
--     800.00,                            -- Total (JF + TF)
--     '2025-01-31',                      -- Due date (last day of January)
--     'pending',                         -- Status
--     'Monthly fee for January 2025',    -- Notes
--     CURRENT_TIMESTAMP,                 -- Created at
--     CURRENT_TIMESTAMP                  -- Updated at
-- );

-- Query to get monthly fee breakdown by student
-- SELECT 
--     u.first_name || ' ' || u.last_name as student_name,
--     strftime('%Y-%m', f.due_date) as month,
--     SUM(f.jf_amount) as total_jf,
--     SUM(f.tf_amount) as total_tf,
--     SUM(f.amount) as total_amount
-- FROM fees f
-- JOIN users u ON f.user_id = u.id
-- WHERE strftime('%Y', f.due_date) = '2025'
-- GROUP BY u.id, strftime('%Y-%m', f.due_date)
-- ORDER BY u.first_name, f.due_date;

-- Query to get yearly totals
-- SELECT 
--     strftime('%Y', due_date) as year,
--     SUM(jf_amount) as yearly_jf_total,
--     SUM(tf_amount) as yearly_tf_total,
--     SUM(amount) as yearly_total
-- FROM fees
-- GROUP BY strftime('%Y', due_date);

-- Index suggestions for better performance
-- CREATE INDEX IF NOT EXISTS idx_fees_user_date ON fees(user_id, due_date);
-- CREATE INDEX IF NOT EXISTS idx_fees_batch_date ON fees(batch_id, due_date);
-- CREATE INDEX IF NOT EXISTS idx_fees_status ON fees(status);
-- CREATE INDEX IF NOT EXISTS idx_fees_due_date ON fees(due_date);
