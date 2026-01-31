"""
Diagnostic script to verify backend-database connectivity.
Run this from the backend directory to check:
- SQLAlchemy connection to DB
- Table existence
- Basic CRUD operations
- Storage backend connectivity (GridFS or filesystem)
"""

import os
import sys

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import engine, SessionLocal
from app.db import models
from app.services.storage import Storage
from sqlalchemy import text, inspect

def check_database():
    """Check database connection and schema."""
    print("=" * 60)
    print("DATABASE CONNECTION CHECK")
    print("=" * 60)
    
    # 1. Check DATABASE_URL
    db_url = os.getenv("DATABASE_URL", "sqlite:///./backend_dev.db")
    print(f"\n✓ Database URL: {db_url}")
    
    # 2. Test connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✓ Database connection: SUCCESS")
    except Exception as e:
        print(f"✗ Database connection: FAILED")
        print(f"  Error: {e}")
        return False
    
    # 3. Check tables exist
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"\n✓ Tables found: {tables}")
        
        if "employees" in tables:
            print("✓ 'employees' table exists")
            
            # Check columns
            columns = [col["name"] for col in inspector.get_columns("employees")]
            print(f"  Columns: {columns}")
            
            expected = ["id", "name", "email", "raw_text", "phone"]
            missing = [c for c in expected if c not in columns]
            if missing:
                print(f"  ⚠ Missing columns: {missing}")
        else:
            print("✗ 'employees' table NOT FOUND")
            print("  Run the app once to create tables automatically")
            return False
            
    except Exception as e:
        print(f"✗ Table inspection failed: {e}")
        return False
    
    # 4. Test basic CRUD
    print("\n" + "=" * 60)
    print("CRUD OPERATIONS TEST")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Count existing
        count = db.query(models.Employee).count()
        print(f"\n✓ Current employee count: {count}")
        
        # Create test record
        test_emp = models.Employee(
            name="Test Employee (Diagnostic)",
            email="test@diagnostic.local",
            raw_text="This is a test record created by check_db_connection.py"
        )
        db.add(test_emp)
        db.commit()
        db.refresh(test_emp)
        print(f"✓ CREATE: Created test employee with id={test_emp.id}")
        
        # Read
        fetched = db.query(models.Employee).filter(models.Employee.id == test_emp.id).first()
        if fetched:
            print(f"✓ READ: Successfully fetched employee id={fetched.id}, name={fetched.name}")
        else:
            print(f"✗ READ: Could not fetch created employee")
        
        # Update
        fetched.email = "updated@diagnostic.local"
        db.commit()
        print(f"✓ UPDATE: Updated email to {fetched.email}")
        
        # Delete
        db.delete(fetched)
        db.commit()
        print(f"✓ DELETE: Removed test employee")
        
        final_count = db.query(models.Employee).count()
        print(f"\n✓ Final employee count: {final_count}")
        
    except Exception as e:
        print(f"✗ CRUD test failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()
    
    return True


def check_storage():
    """Check storage backend (GridFS or filesystem)."""
    print("\n" + "=" * 60)
    print("STORAGE BACKEND CHECK")
    print("=" * 60)
    
    storage = Storage()
    print(f"\n✓ Storage backend: {storage.__class__.__name__}")
    
    # Check if GridFS is configured
    mongo_uri = os.getenv("MONGO_URI")
    if mongo_uri:
        print(f"✓ MONGO_URI configured: {mongo_uri[:30]}...")
        if hasattr(storage, 'fs') and storage.fs:
            print("✓ GridFS initialized successfully")
        else:
            print("✗ GridFS NOT initialized (check MONGO_URI)")
    else:
        print("⚠ MONGO_URI not set - using filesystem fallback")
        print(f"  Files will be stored in: {os.path.abspath('data/files')}")
    
    # Test save/retrieve
    try:
        test_data = b"Diagnostic test file content"
        file_id = storage.save_file(test_data, filename="diagnostic_test.txt")
        print(f"\n✓ SAVE: Saved test file with id={file_id}")
        
        retrieved = storage.get_file(file_id)
        if retrieved == test_data:
            print("✓ RETRIEVE: Successfully retrieved test file")
        else:
            print("✗ RETRIEVE: Retrieved data doesn't match")
            
    except Exception as e:
        print(f"✗ Storage test failed: {e}")
        return False
    
    return True


def check_llm():
    """Check LLM adapter connectivity."""
    print("\n" + "=" * 60)
    print("LLM ADAPTER CHECK")
    print("=" * 60)
    
    from app.services.llm_adapter import OllamaAdapter
    
    llm = OllamaAdapter()
    print(f"\n✓ LLM Model: {llm.model}")
    
    ollama_url = os.getenv("OLLAMA_API_URL")
    if ollama_url:
        print(f"✓ OLLAMA_API_URL: {ollama_url}")
    else:
        print("⚠ OLLAMA_API_URL not set - will use CLI fallback")
    
    # Test generation
    try:
        print("\nTesting LLM generation (5s timeout)...")
        response = llm.generate("Reply with: DIAGNOSTIC_OK", timeout=5)
        print(f"✓ LLM Response: {response[:100]}")
        
        if "DIAGNOSTIC_OK" in response or "diagnostic" in response.lower():
            print("✓ LLM is responding correctly")
        else:
            print("⚠ LLM responded but output may be unexpected")
            
    except Exception as e:
        print(f"✗ LLM generation failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("BACKEND CONNECTIVITY DIAGNOSTIC")
    print("=" * 60)
    print("\nThis script checks:")
    print("  1. Database connection (SQLAlchemy)")
    print("  2. Storage backend (GridFS or filesystem)")
    print("  3. LLM adapter (Ollama)")
    print("")
    
    results = []
    
    # Run checks
    results.append(("Database", check_database()))
    results.append(("Storage", check_storage()))
    results.append(("LLM", check_llm()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} - {name}")
    
    all_pass = all(r[1] for r in results)
    
    if all_pass:
        print("\n✓ All checks passed! Backend is ready.")
        sys.exit(0)
    else:
        print("\n✗ Some checks failed. Review errors above.")
        print("\nCommon fixes:")
        print("  - Ensure backend dependencies are installed: pip install -r requirements.txt")
        print("  - Start the backend once to create tables: uvicorn app.main:app")
        print("  - Set MONGO_URI if you want GridFS storage")
        print("  - Set OLLAMA_API_URL or ensure 'ollama' is on PATH")
        sys.exit(1)
