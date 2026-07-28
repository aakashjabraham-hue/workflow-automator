from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class Workflow:
    name: str
    enabled: bool = True
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def save(self, conn) -> None:
        if self.id is None:
            cursor = conn.execute(
                "INSERT INTO workflows (name, enabled) VALUES (?, ?)",
                (self.name, self.enabled),
            )
            self.id = cursor.lastrowid
        else:
            conn.execute(
                "UPDATE workflows SET name=?, enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (self.name, self.enabled, self.id),
            )
        conn.commit()

    def delete(self, conn) -> None:
        if self.id is not None:
            conn.execute("DELETE FROM workflows WHERE id=?", (self.id,))
            conn.commit()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row):
        if isinstance(row, dict):
            return cls(
                id=row["id"],
                name=row["name"],
                enabled=bool(row["enabled"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        # Tuple fallback — map by column position (id, name, enabled, created_at, updated_at)
        return cls(
            id=row[0],
            name=row[1],
            enabled=bool(row[2]),
            created_at=row[3],
            updated_at=row[4],
        )


def get_all_workflows(conn):
    rows = conn.execute(
        "SELECT id, name, enabled, created_at, updated_at FROM workflows ORDER BY created_at DESC"
    ).fetchall()
    return [Workflow.from_row(row) for row in rows]


def get_workflow(conn, workflow_id):
    row = conn.execute(
        "SELECT id, name, enabled, created_at, updated_at FROM workflows WHERE id=?",
        (workflow_id,),
    ).fetchone()
    if row is None:
        return None
    return Workflow.from_row(row)