# Backend Utility Scripts

This directory contains utility scripts for database diagnostics and testing.

## Scripts

### check_db_connection.py
Verifies database connectivity for both PostgreSQL and MongoDB.

**Usage:**
```bash
python scripts/check_db_connection.py
```

### diagnose_databases.py
Comprehensive database diagnostics tool that checks:
- PostgreSQL connection and schema
- MongoDB connection and GridFS
- Employee table structure
- Sample data queries

**Usage:**
```bash
python scripts/diagnose_databases.py
```

## Notes
- These scripts use the same `.env` configuration as the main application
- Make sure to run them from the backend directory root
