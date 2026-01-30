import os
import io
from typing import Optional
from bson.objectid import ObjectId

try:
    from pymongo import MongoClient
    import gridfs
except Exception:
    MongoClient = None
    gridfs = None


class Storage:
    """Storage adapter. Tries to use MongoDB GridFS when MONGO_URI is set.
    Falls back to local filesystem storage under backend/data/files.
    """

    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI")
        self.local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "files"))
        os.makedirs(self.local_dir, exist_ok=True)
        self.client = None
        self.fs = None
        if self.mongo_uri and MongoClient:
            self.client = MongoClient(self.mongo_uri)
            dbname = os.getenv("MONGO_DB", "cv_repo")
            self.db = self.client[dbname]
            self.fs = gridfs.GridFS(self.db)

    def save_file(self, data: bytes, filename: str) -> str:
        if self.fs:
            oid = self.fs.put(data, filename=filename)
            return str(oid)
        # fallback: save to local dir
        path = os.path.join(self.local_dir, f"{filename}")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def get_file(self, file_id: str) -> Optional[bytes]:
        if self.fs:
            try:
                oid = ObjectId(file_id)
                grid_out = self.fs.get(oid)
                return grid_out.read()
            except Exception:
                return None
        # fallback: treat file_id as path
        try:
            with open(file_id, "rb") as f:
                return f.read()
        except Exception:
            return None
