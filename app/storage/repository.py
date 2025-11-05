from __future__ import annotations

import json
from typing import Any, Optional

from app.storage.database import notes_db, slides_db
from app.utils.identifiers import new_id


SLIDE_ARTIFACT_KINDS = {"parse", "layout", "outline"}


def _db_for_kind(kind: str):
    return slides_db if kind in SLIDE_ARTIFACT_KINDS else notes_db


class Repository:
    def save_artifact(self, session_id: str, kind: str, payload: Any, artifact_id: str | None = None) -> str:
        ident = artifact_id or new_id(kind)
        database = _db_for_kind(kind)
        database.upsert(
            "artifact",
            {
                "id": ident,
                "course_session_id": session_id,
                "kind": kind,
                "payload_json": json.dumps(payload, ensure_ascii=False),
            },
        )
        return ident

    def load_artifact(self, artifact_id: str) -> Optional[Any]:
        row = slides_db.fetch_json("artifact", artifact_id)
        if not row:
            row = notes_db.fetch_json("artifact", artifact_id)
        if not row:
            return None
        return row.get("payload_json")

    def list_artifacts(self, session_id: str, kind: str) -> list[tuple[str, Any]]:
        database = _db_for_kind(kind)
        with database.connect() as conn:
            conn.row_factory = None
            cursor = conn.execute(
                "SELECT id, payload_json FROM artifact WHERE course_session_id=? AND kind=?",
                (session_id, kind),
            )
            results = []
            for row in cursor.fetchall():
                payload = json.loads(row[1])
                results.append((row[0], payload))
            return results

    def list_artifact_ids(self, session_id: str, kind: str) -> list[str]:
        database = _db_for_kind(kind)
        with database.connect() as conn:
            cursor = conn.execute(
                "SELECT id FROM artifact WHERE course_session_id=? AND kind=? ORDER BY rowid",
                (session_id, kind),
            )
            return [row[0] for row in cursor.fetchall()]


repository = Repository()
