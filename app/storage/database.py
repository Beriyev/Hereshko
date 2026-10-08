import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core.normalization import Document


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "hereshko.db"
PREVIEW_CHARS = 2000
notebook_summaries: dict[str, str] = {}


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS notebooks (
                notebook_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sources (
                document_id TEXT PRIMARY KEY,
                notebook_id TEXT NOT NULL,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_identifier TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',

                FOREIGN KEY (notebook_id)
                    REFERENCES notebooks(notebook_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sources_notebook_id
            ON sources(notebook_id);
            """
        )

        now = datetime.now(timezone.utc).isoformat()
        connection.execute(
            """
            INSERT INTO notebooks (
                notebook_id,
                title,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(notebook_id) DO NOTHING
            """,
            ("nb-1", "Untitled notebook", now, now),
        )


def save_source(document: Document) -> None:
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO notebooks (
                notebook_id,
                title,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(notebook_id) DO NOTHING
            """,
            (
                document.notebook_id,
                "Untitled notebook",
                now,
                now,
            ),
        )

        connection.execute(
            """
            INSERT INTO sources (
                document_id,
                notebook_id,
                title,
                source_type,
                source_identifier,
                ingested_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                title = excluded.title,
                source_type = excluded.source_type,
                source_identifier = excluded.source_identifier,
                ingested_at = excluded.ingested_at,
                metadata_json = excluded.metadata_json
            """,
            (
                document.document_id,
                document.notebook_id,
                document.title,
                document.source_type.value,
                document.source_identifier,
                document.ingested_at.isoformat(),
                json.dumps(
                    {
                        **document.raw_metadata,
                        "preview_text": document.content[:PREVIEW_CHARS],
                    },
                    default=str,
                ),
            ),
        )

        connection.execute(
            """
            UPDATE notebooks
            SET updated_at = ?
            WHERE notebook_id = ?
            """,
            (now, document.notebook_id),
        )

    notebook_summaries.pop(document.notebook_id, None)


def get_notebook(notebook_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                n.notebook_id,
                n.title,
                n.created_at,
                n.updated_at,
                COUNT(s.document_id) AS source_count
            FROM notebooks n
            LEFT JOIN sources s
                ON s.notebook_id = n.notebook_id
            WHERE n.notebook_id = ?
            GROUP BY n.notebook_id
            """,
            (notebook_id,),
        ).fetchone()

    return dict(row) if row else None


def update_notebook_title(notebook_id: str, title: str) -> dict | None:
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE notebooks
            SET title = ?, updated_at = ?
            WHERE notebook_id = ?
            """,
            (title, now, notebook_id),
        )

    return get_notebook(notebook_id)


def list_sources(notebook_id: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                document_id,
                notebook_id,
                title,
                source_type,
                source_identifier,
                ingested_at,
                metadata_json
            FROM sources
            WHERE notebook_id = ?
            ORDER BY ingested_at DESC
            """,
            (notebook_id,),
        ).fetchall()

    sources = []

    for row in rows:
        source = dict(row)
        source["metadata"] = json.loads(source.pop("metadata_json"))
        sources.append(source)

    return sources


def delete_source(document_id: str, notebook_id: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM sources
            WHERE document_id = ? AND notebook_id = ?
            """,
            (document_id, notebook_id),
        )
        if cursor.rowcount == 0:
            return False

        connection.execute(
            """
            UPDATE notebooks
            SET updated_at = ?
            WHERE notebook_id = ?
            """,
            (now, notebook_id),
        )

    notebook_summaries.pop(notebook_id, None)
    return True


def delete_all_sources(notebook_id: str) -> int:
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM sources WHERE notebook_id = ?",
            (notebook_id,),
        )
        connection.execute(
            """
            UPDATE notebooks
            SET updated_at = ?
            WHERE notebook_id = ?
            """,
            (now, notebook_id),
        )

    notebook_summaries.pop(notebook_id, None)
    return cursor.rowcount

def save_notebook(notebook_id: str, title: str, created_at: str, updated_at: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
                INSERT INTO notebooks(notebook_id, title, created_at, updated_at)
                VALUES
                (?,?,?,?)
            """,
            (notebook_id,title,created_at,updated_at)
        )

def get_notebooks() -> list[dict]:
    with get_connection() as connection:
        notebooks = connection.execute(
            """
                select n.notebook_id, n.title, n.created_at, n.updated_at, count(s.notebook_id) as source_count
                from notebooks n
                left join sources s on s.notebook_id = n.notebook_id
                group by n.notebook_id
                order by n.updated_at desc
            """
        ).fetchall()

    notebook_list = []
    for notebook in notebooks:
        notebook_list.append(dict(notebook))
    return notebook_list