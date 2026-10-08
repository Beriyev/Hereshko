import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.core.normalization import Document, SourceType
from app.storage import database


class NotebookSummaryTests(unittest.TestCase):
    def setUp(self):
        cache_patch = patch.object(database, "notebook_summaries", {})
        cache_patch.start()
        self.addCleanup(cache_patch.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "test.db"
        for name, value in (("DATA_DIR", self.path.parent), ("DATABASE_PATH", self.path)):
            patcher = patch.object(database, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # SQLite's context manager commits but does not close the connection.
        connections = []
        original_get_connection = database.get_connection

        def tracked_connection():
            connection = original_get_connection()
            connections.append(connection)
            return connection

        patcher = patch.object(database, "get_connection", side_effect=tracked_connection)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: [connection.close() for connection in connections])
        database.init_db()

    def save_summary(self):
        database.notebook_summaries["nb-1"] = "Saved overview"

    def save_source(self):
        database.save_source(Document(
            document_id="doc", notebook_id="nb-1", content="Source text",
            source_type=SourceType.TXT, source_identifier="test.txt", title="test.txt",
            ingested_at=datetime.now(timezone.utc), raw_metadata={},
        ))

    def test_summary_is_available_from_dictionary(self):
        self.assertIsNone(database.notebook_summaries.get("nb-1"))
        self.save_summary()
        self.assertEqual(database.notebook_summaries["nb-1"], "Saved overview")
        notebook = database.get_notebook("nb-1")
        assert notebook is not None
        self.assertNotIn("summary", notebook)

    def test_database_does_not_need_summary_column(self):
        database.init_db()
        with database.get_connection() as connection:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(notebooks)")}
        self.assertNotIn("summary", columns)
        self.save_summary()

    def test_empty_cache_does_not_restore_summary_from_database(self):
        self.save_summary()
        database.notebook_summaries.clear()
        self.assertIsNone(database.notebook_summaries.get("nb-1"))

    def test_source_ingestion_clears_summary(self):
        self.save_summary()
        self.save_source()
        self.assertIsNone(database.notebook_summaries.get("nb-1"))

    def test_source_removal_clears_summary(self):
        self.save_source()
        self.save_summary()
        database.delete_source("doc", "nb-1")
        self.assertIsNone(database.notebook_summaries.get("nb-1"))

    def test_removing_all_sources_clears_summary(self):
        self.save_source()
        self.save_summary()
        database.delete_all_sources("nb-1")
        self.assertIsNone(database.notebook_summaries.get("nb-1"))

    def test_notebook_summaries_are_separate(self):
        self.save_summary()
        database.notebook_summaries["nb-2"] = "Other overview"
        self.save_source()
        self.assertIsNone(database.notebook_summaries.get("nb-1"))
        self.assertEqual(database.notebook_summaries["nb-2"], "Other overview")


class SummaryRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_summary_is_saved(self):
        from app.api import routes_notebooks
        from app.core.notebook import GeneratedOverview

        notebook = {"source_count": 1, "updated_at": "2026-10-07T00:00:00+00:00"}
        overview = GeneratedOverview(title="Title", summary="Generated overview")
        with patch.object(routes_notebooks, "get_notebook", return_value=notebook), patch.object(
            routes_notebooks, "list_sources", return_value=[{"title": "Source", "metadata": {"preview_text": "Text"}}]
        ), patch.object(routes_notebooks, "generate_preview_summary", return_value=overview), patch.object(
            routes_notebooks, "notebook_summaries", {}
        ) as summaries:
            response = await routes_notebooks.generate_notebook_summary("nb-1")
        self.assertEqual(summaries["nb-1"], "Generated overview")
        self.assertEqual(response.summary, "Generated overview")


if __name__ == "__main__":
    unittest.main()
