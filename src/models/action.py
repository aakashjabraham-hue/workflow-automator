from dataclasses import dataclass, field
from typing import Optional, Any
import json


@dataclass
class Action:
    workflow_id: int
    type: str
    command: str = ""
    args: list = field(default_factory=list)
    enabled: bool = True
    id: Optional[int] = None
    created_at: Optional[str] = None

    def save(self, conn) -> None:
        args_json = json.dumps(self.args)
        if self.id is None:
            cursor = conn.execute(
                "INSERT INTO actions (workflow_id, type, command, args, enabled) VALUES (?, ?, ?, ?, ?)",
                (self.workflow_id, self.type, self.command, args_json, self.enabled),
            )
            self.id = cursor.lastrowid
        else:
            conn.execute(
                "UPDATE actions SET workflow_id=?, type=?, command=?, args=?, enabled=? WHERE id=?",
                (self.workflow_id, self.type, self.command, args_json, self.enabled, self.id),
            )
        conn.commit()

    def delete(self, conn) -> None:
        if self.id is not None:
            conn.execute("DELETE FROM actions WHERE id=?", (self.id,))
            conn.commit()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "type": self.type,
            "command": self.command,
            "args": self.args,
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
                command=row["command"],
                args=json.loads(row["args"]) if isinstance(row["args"], str) else row["args"],
                enabled=bool(row["enabled"]),
                created_at=row["created_at"],
            )
        # Tuple fallback: id, workflow_id, type, command, args, enabled, created_at
        return cls(
            id=row[0],
            workflow_id=row[1],
            type=row[2],
            command=row[3],
            args=json.loads(row[4]) if isinstance(row[4], str) else row[4],
            enabled=bool(row[5]),
            created_at=row[6],
        )


def get_actions_for_workflow(conn, workflow_id):
    rows = conn.execute(
        "SELECT id, workflow_id, type, command, args, enabled, created_at FROM actions WHERE workflow_id=? ORDER BY created_at",
        (workflow_id,),
    ).fetchall()
    return [Action.from_row(row) for row in rows]


def get_action(conn, action_id):
    row = conn.execute(
        "SELECT id, workflow_id, type, command, args, enabled, created_at FROM actions WHERE id=?",
        (action_id,),
    ).fetchone()
    if row is None:
        return None
    return Action.from_row(row)