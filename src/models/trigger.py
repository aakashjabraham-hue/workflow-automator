from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class Trigger:
    workflow_id: int
    type: str
    config: dict = field(default_factory=dict)
    enabled: bool = True
    id: Optional[int] = None
    created_at: Optional[str] = None

    def save(self, conn) -> None:
        config_json = json.dumps(self.config)
        if self.id is None:
            cursor = conn.execute(
                "INSERT INTO triggers (workflow_id, type, config, enabled) VALUES (?, ?, ?, ?)",
                (self.workflow_id, self.type, config_json, self.enabled),
            )
            self.id = cursor.lastrowid
        else:
            conn.execute(
                "UPDATE triggers SET workflow_id=?, type=?, config=?, enabled=? WHERE id=?",
                (self.workflow_id, self.type, config_json, self.enabled, self.id),
            )
        conn.commit()

    def delete(self, conn) -> None:
        if self.id is not None:
            conn.execute("DELETE FROM triggers WHERE id=?", (self.id,))
            conn.commit()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "type": self.type,
            "config": self.config,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, row):
        if isinstance(row, dict):
            return cls(
                id=row["id"],
                workflow_id=row["workflow_id"],
                type=row["type"],
                config=json.loads(row["config"]) if isinstance(row["config"], str) else row["config"],
                enabled=bool(row["enabled"]),
                created_at=row["created_at"],
            )
        # Tuple fallback: id, workflow_id, type, config, enabled, created_at
        return cls(
            id=row[0],
            workflow_id=row[1],
            type=row[2],
            config=json.loads(row[3]) if isinstance(row[3], str) else row[3],
            enabled=bool(row[4]),
            created_at=row[5],
        )


def get_triggers_for_workflow(conn, workflow_id):
    rows = conn.execute(
        "SELECT id, workflow_id, type, config, enabled, created_at FROM triggers WHERE workflow_id=? ORDER BY created_at",
        (workflow_id,),
    ).fetchall()
    return [Trigger.from_row(row) for row in rows]


def get_trigger(conn, trigger_id):
    row = conn.execute(
        "SELECT id, workflow_id, type, config, enabled, created_at FROM triggers WHERE id=?",
        (trigger_id,),
    ).fetchone()
    if row is None:
        return None
    return Trigger.from_row(row)