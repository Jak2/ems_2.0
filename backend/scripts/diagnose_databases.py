"""
Database Connection Diagnostic Script

This script tests the actual database connections to help diagnose
why data might not be stored.

Run with: python diagnose_databases.py
"""

import os
from dotenv import load_dotenv
load_dotenv()

print("="*70)
print("DATABASE CONNECTION DIAGNOSTICS")
print("="*70)

# Test 1: Check environment variables
print("\n1. ENVIRONMENT VARIABLES")
print("-" * 70)
database_url = os.getenv("DATABASE_URL")
mongo_uri = os.getenv("MONGO_URI")
print(f"DATABASE_URL: {database_url}")
print(f"MONGO_URI: {mongo_uri}")

# Test 2: Test PostgreSQL connection
print("\n2. POSTGRESQL CONNECTION TEST")
print("-" * 70)
if database_url and database_url.startswith("postgresql"):
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ SUCCESS: Connected to PostgreSQL")
            print(f"   Version: {version[:50]}...")
            
            # Check if employees table exists
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'"
            ))
            tables = [row[0] for row in result.fetchall()]
            print(f"   Tables: {tables}")
            
            if 'employees' in tables:
                result = conn.execute(text("SELECT COUNT(*) FROM employees"))
                count = result.fetchone()[0]
                print(f"   Employee records: {count}")
            else:
                print(f"   ⚠️  WARNING: 'employees' table doesn't exist yet")
                
    except Exception as e:
        print(f"❌ FAILED: Cannot connect to PostgreSQL")
        print(f"   Error: {str(e)}")
        print(f"\n   Troubleshooting:")
        print(f"   1. Is PostgreSQL running? Check with: Get-Service postgresql*")
        print(f"   2. Is the database 'ems' created? Run: createdb ems")
        print(f"   3. Are credentials correct? Check username/password")
        print(f"   4. Is PostgreSQL listening on port 5432?")
else:
    print(f"⚠️  SKIPPED: Not using PostgreSQL (using {database_url})")

# Test 3: Test MongoDB connection
print("\n3. MONGODB CONNECTION TEST")
print("-" * 70)
if mongo_uri:
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        # Force connection
        client.admin.command('ping')
        print(f"✅ SUCCESS: Connected to MongoDB")
        
        db_name = os.getenv("MONGO_DB", "cv_repo")
        db = client[db_name]
        collections = db.list_collection_names()
        print(f"   Database: {db_name}")
        print(f"   Collections: {collections if collections else '(empty)'}")
        
        # Check GridFS
        import gridfs
        fs = gridfs.GridFS(db)
        file_count = db['fs.files'].count_documents({})
        print(f"   GridFS files: {file_count}")
        
    except Exception as e:
        print(f"❌ FAILED: Cannot connect to MongoDB")
        print(f"   Error: {str(e)}")
        print(f"\n   Troubleshooting:")
        print(f"   1. Is MongoDB running? Check with: Get-Service MongoDB")
        print(f"   2. Is it listening on port 27017?")
        print(f"   3. Try: mongosh mongodb://localhost:27017")
else:
    print(f"⚠️  SKIPPED: MongoDB not configured (using local file storage)")

# Test 4: Check local data directory
print("\n4. LOCAL FILE STORAGE")
print("-" * 70)
data_dirs = [
    "../data/files",
    "../data/jobs", 
    "../data/prompts",
    "../data/faiss"
]

for dir_path in data_dirs:
    full_path = os.path.abspath(dir_path)
    if os.path.exists(full_path):
        file_count = len([f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))])
        print(f"✅ {dir_path}: {file_count} files")
    else:
        print(f"⚠️  {dir_path}: Directory doesn't exist")

# Test 5: Check Ollama
print("\n5. OLLAMA LLM CONNECTION TEST")
print("-" * 70)
ollama_url = os.getenv("OLLAMA_API_URL")
if ollama_url:
    try:
        import requests
        # Simple health check
        response = requests.get(ollama_url.replace('/api/generate', '/api/tags'), timeout=3)
        if response.status_code == 200:
            print(f"✅ SUCCESS: Ollama is reachable")
            print(f"   URL: {ollama_url}")
        else:
            print(f"⚠️  WARNING: Ollama responded with status {response.status_code}")
    except Exception as e:
        print(f"❌ FAILED: Cannot reach Ollama")
        print(f"   Error: {str(e)}")
        print(f"\n   Troubleshooting:")
        print(f"   1. Is Ollama running? Start with: ollama serve")
        print(f"   2. Try: ollama list")
else:
    print(f"⚠️  SKIPPED: Using Ollama CLI (not HTTP API)")

# Summary
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print("\nTo fix database storage issues:")
print("1. Ensure PostgreSQL is running: Get-Service postgresql*")
print("2. Create database if needed: createdb ems")
print("3. Ensure MongoDB is running: Get-Service MongoDB")
print("4. Restart backend: uvicorn app.main:app --reload")
print("\nThen test by uploading a PDF and checking:")
print("- PostgreSQL: SELECT * FROM employees;")
print("- MongoDB: mongosh, then: use cv_repo; db.fs.files.find()")
print("="*70)
