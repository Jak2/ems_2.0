import os
import io
import json
from typing import Optional, Dict, Any
from datetime import datetime
from bson.objectid import ObjectId


class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles MongoDB ObjectId and datetime objects."""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

try:
    from pymongo import MongoClient
    import gridfs
except Exception:
    MongoClient = None
    gridfs = None
    # Note: if pymongo/gridfs are not available, storage will fall back to local filesystem.
    # Install with: pip install pymongo


class Storage:
    """Storage adapter. Tries to use MongoDB GridFS when MONGO_URI is set.
    Falls back to local filesystem storage under backend/data/files.

    Supports:
    - Binary file storage (GridFS or local)
    - JSON document storage (MongoDB collection or local JSON files)
    """

    def __init__(self):
        # lazy import of logging to avoid circular imports
        import logging
        self.logger = logging.getLogger("cv-chat.storage")

        self.mongo_uri = os.getenv("MONGO_URI")
        self.local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "files"))
        self.json_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "extracted"))
        os.makedirs(self.local_dir, exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)
        self.client = None
        self.fs = None
        self.db = None
        if self.mongo_uri and MongoClient:
            self.client = MongoClient(self.mongo_uri)
            dbname = os.getenv("MONGO_DB", "cv_repo")
            self.db = self.client[dbname]
            self.fs = gridfs.GridFS(self.db)

    def save_file(self, data: bytes, filename: str) -> str:
        """Save binary file to GridFS (if available) or local filesystem."""
        if self.fs:
            try:
                oid = self.fs.put(data, filename=filename)
                self.logger.info(f"Saved file to GridFS id={oid} filename={filename}")
                return str(oid)
            except Exception as e:
                self.logger.exception("GridFS save failed, falling back to local file")
        # fallback: save to local dir
        path = os.path.join(self.local_dir, f"{filename}")
        try:
            with open(path, "wb") as f:
                f.write(data)
            self.logger.info(f"Saved file to local path={path}")
        except Exception:
            self.logger.exception("Local file save failed")
        return path

    def get_file(self, file_id: str) -> Optional[bytes]:
        if self.fs:
            try:
                oid = ObjectId(file_id)
                grid_out = self.fs.get(oid)
                data = grid_out.read()
                self.logger.info(f"Read {len(data)} bytes from GridFS id={file_id}")
                return data
            except Exception:
                self.logger.exception(f"Failed to read GridFS id={file_id}")
                return None
        # fallback: treat file_id as path
        try:
            with open(file_id, "rb") as f:
                return f.read()
        except Exception:
            self.logger.exception(f"Failed to read local file path={file_id}")
            return None

    def save_extracted_data(self, employee_id: str, filename: str, extracted_data: Dict[str, Any]) -> str:
        """Save extracted resume data as human-readable JSON.

        Stores in MongoDB 'extracted_resumes' collection (not GridFS/BSON binary).
        Also saves a local JSON file for easy access.

        Args:
            employee_id: The employee ID (e.g., "000001")
            filename: Original filename of the resume
            extracted_data: Dictionary containing all extracted fields

        Returns:
            The document ID (MongoDB _id or local file path)
        """
        # Build the document with metadata
        document = {
            "employee_id": employee_id,
            "original_filename": filename,
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "extracted_data": extracted_data
        }

        doc_id = None

        # Save to MongoDB collection (human-readable JSON, not GridFS binary)
        if self.db is not None:
            try:
                collection = self.db["extracted_resumes"]
                result = collection.insert_one(document)
                doc_id = str(result.inserted_id)
                self.logger.info(f"Saved extracted data to MongoDB collection: employee_id={employee_id}, doc_id={doc_id}")
            except Exception as e:
                self.logger.exception(f"Failed to save to MongoDB collection: {e}")

        # Always save a local JSON file for easy access
        json_filename = f"{employee_id}_{filename.replace('.pdf', '').replace(' ', '_')}.json"
        json_path = os.path.join(self.json_dir, json_filename)
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(document, f, indent=2, ensure_ascii=False, cls=MongoJSONEncoder)
            self.logger.info(f"Saved extracted data to JSON file: {json_path}")
        except Exception as e:
            self.logger.exception(f"Failed to save JSON file: {e}")

        return doc_id or json_path

    def get_extracted_data(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve extracted data by employee_id.

        Args:
            employee_id: The employee ID to look up

        Returns:
            The extracted data document or None
        """
        # Try MongoDB first
        if self.db is not None:
            try:
                collection = self.db["extracted_resumes"]
                doc = collection.find_one({"employee_id": employee_id})
                if doc:
                    # Convert ObjectId to string for JSON serialization
                    doc["_id"] = str(doc["_id"])
                    return doc
            except Exception as e:
                self.logger.exception(f"Failed to read from MongoDB: {e}")

        # Fallback: search local JSON files
        try:
            for filename in os.listdir(self.json_dir):
                if filename.startswith(employee_id) and filename.endswith(".json"):
                    json_path = os.path.join(self.json_dir, filename)
                    with open(json_path, "r", encoding="utf-8") as f:
                        return json.load(f)
        except Exception as e:
            self.logger.exception(f"Failed to read local JSON: {e}")

        return None
