# SQLite Database Schema & Index Reference

## Tables
1. **`students`**:
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `enrollment_no`: VARCHAR(32) UNIQUE NOT NULL (Indexed)
   - `name`: VARCHAR(128) NOT NULL
   - `email`: VARCHAR(128) UNIQUE NOT NULL
   - `department`: VARCHAR(64) NOT NULL
   - `year`: INTEGER NOT NULL
   - `semester`: INTEGER NOT NULL
   - `cgpa`: REAL NOT NULL
   - `status`: VARCHAR(20) DEFAULT 'ACTIVE'
   - `created_at`: TIMESTAMP DEFAULT CURRENT_TIMESTAMP

2. **`academic_results`**:
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `student_id`: INTEGER (FOREIGN KEY -> students.id) (Indexed)
   - `semester`: INTEGER NOT NULL
   - `subject_code`: VARCHAR(16) NOT NULL
   - `subject_name`: VARCHAR(128) NOT NULL
   - `credits`: INTEGER NOT NULL
   - `grade`: VARCHAR(4) NOT NULL
   - `points`: REAL NOT NULL
   - `published_date`: VARCHAR(32) NOT NULL

3. **`query_audit_logs`**:
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `enrollment_no`: VARCHAR(32) NOT NULL
   - `query_type`: VARCHAR(32) NOT NULL
   - `duration_ms`: REAL NOT NULL
   - `cache_hit`: INTEGER NOT NULL
   - `timestamp`: TIMESTAMP DEFAULT CURRENT_TIMESTAMP (Indexed)
