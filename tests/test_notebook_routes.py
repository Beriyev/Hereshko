import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_notebooks import router
from app.core.normalization import Document, SourceType
from app.storage import database


class NotebookRouteTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "notebooks.db"
        connections = []

        def test_connection():
            connection = sqlite3.connect(path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connections.append(connection)
            return connection

        connection_patch = patch.object(database, "get_connection", side_effect=test_connection)
        connection_patch.start()
        self.addCleanup(connection_patch.stop)
        self.addCleanup(lambda: [connection.close() for connection in connections])
        cache_patch = patch.dict(database.notebook_summaries, {}, clear=True)
        cache_patch.start()
        self.addCleanup(cache_patch.stop)
        database.init_db()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def create(self, title="Test notebook"):
        response = self.client.post("/notebooks", json={"title": title})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def add_source(self, notebook_id, document_id):
        database.save_source(Document(
            document_id=document_id, notebook_id=notebook_id, title="Test source",
            content="Synthetic test text", source_type=SourceType.TXT,
            source_identifier="test.txt", ingested_at=datetime.now(timezone.utc), raw_metadata={},
        ))

    def test_create_returns_uuid_dates_and_persists_notebook(self):
        notebook = self.create("  My notebook  ")
        self.assertEqual(notebook["title"], "My notebook")
        self.assertEqual(UUID(notebook["notebook_id"]).version, 4)
        self.assertEqual(notebook["source_count"], 0)
        for field in ("created_at", "updated_at"):
            self.assertIsNotNone(datetime.fromisoformat(notebook[field]).tzinfo)
        fetched = self.client.get(f'/notebooks/{notebook["notebook_id"]}')
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json(), notebook)

    def test_same_title_creates_separate_notebooks(self):
        first = self.create()
        second = self.create()
        self.assertNotEqual(first["notebook_id"], second["notebook_id"])

    def test_invalid_titles_are_rejected_without_inserting(self):
        before = self.client.get("/notebooks").json()
        for title in ("", "   ", "x" * 121):
            with self.subTest(title=title):
                response = self.client.post("/notebooks", json={"title": title})
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/notebooks").json(), before)

    def test_missing_title_is_rejected_and_max_length_is_accepted(self):
        self.assertEqual(self.client.post("/notebooks", json={}).status_code, 422)
        self.assertEqual(len(self.create("x" * 120)["title"]), 120)

    def test_list_includes_empty_notebooks_and_separate_source_counts(self):
        empty = self.create("Empty")
        populated = self.create("Populated")
        self.add_source(populated["notebook_id"], "source-a")
        self.add_source(populated["notebook_id"], "source-b")
        response = self.client.get("/notebooks")
        self.assertEqual(response.status_code, 200)
        notebooks = {item["notebook_id"]: item for item in response.json()["notebooks"]}
        self.assertEqual(notebooks[empty["notebook_id"]]["source_count"], 0)
        self.assertEqual(notebooks[populated["notebook_id"]]["source_count"], 2)
        database.delete_source("source-a", populated["notebook_id"])
        notebooks = {item["notebook_id"]: item for item in self.client.get("/notebooks").json()["notebooks"]}
        self.assertEqual(notebooks[populated["notebook_id"]]["source_count"], 1)

    def test_empty_database_returns_empty_list(self):
        with database.get_connection() as connection:
            connection.execute("DELETE FROM notebooks WHERE notebook_id = ?", ("nb-1",))
        response = self.client.get("/notebooks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"notebooks": []})

    def test_list_is_ordered_by_latest_update(self):
        database.save_notebook("old", "Old", "2020-01-01T00:00:00+00:00", "2020-01-01T00:00:00+00:00")
        database.save_notebook("new", "New", "2030-01-01T00:00:00+00:00", "2030-01-01T00:00:00+00:00")
        response = self.client.get("/notebooks")
        ids = [notebook["notebook_id"] for notebook in response.json()["notebooks"]]
        self.assertEqual(ids[0], "new")
        self.assertEqual(ids[-1], "old")

    def test_created_notebook_can_be_renamed(self):
        notebook = self.create()
        response = self.client.patch(f'/notebooks/{notebook["notebook_id"]}', json={"title": "Renamed"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Renamed")
        self.assertEqual(response.json()["source_count"], 0)


if __name__ == "__main__":
    unittest.main()
