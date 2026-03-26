import os
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def get_conn() -> psycopg.Connection:
    return psycopg.connect(_database_url(), row_factory=dict_row)


def migrate() -> None:
    """
    Minimal migrations. Safe to run on every startup.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists memories (
                  user_id text not null,
                  memory_id text not null,
                  memory jsonb not null,
                  created_at timestamptz not null default now(),
                  updated_at timestamptz not null default now(),
                  primary key (user_id, memory_id)
                );
                """
            )
            cur.execute(
                """
                create index if not exists memories_user_updated_idx
                on memories (user_id, updated_at desc);
                """
            )
            cur.execute(
                """
                create table if not exists memory_labels (
                  user_id text primary key,
                  labels jsonb not null default '{}'::jsonb,
                  updated_at timestamptz not null default now()
                );
                """
            )
        conn.commit()


def upsert_memory(user_id: str, memory_id: str, memory: dict[str, Any]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into memories (user_id, memory_id, memory, created_at, updated_at)
                values (%s, %s, %s::jsonb, now(), now())
                on conflict (user_id, memory_id) do update
                set memory = excluded.memory,
                    updated_at = now();
                """,
                (user_id, memory_id, psycopg.types.json.Jsonb(memory)),
            )
        conn.commit()


def list_memories(user_id: str, limit: int = 200) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select memory
                from memories
                where user_id = %s
                order by updated_at desc
                limit %s;
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
    return [r["memory"] for r in rows]


def get_label_db_text(user_id: str) -> str:
    """
    Returns flattened label db text (same format as read_json_text()).
    Stored in memory_labels.labels as jsonb object: {key: [values]}
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select labels from memory_labels where user_id = %s;",
                (user_id,),
            )
            row = cur.fetchone()

    labels = (row or {}).get("labels") or {}
    if not isinstance(labels, dict):
        labels = {}

    lines: list[str] = []
    for key, values in labels.items():
        if not values:
            continue
        if isinstance(values, list):
            vals = [str(x) for x in values if str(x).strip()]
        else:
            vals = [str(values)]
        if vals:
            lines.append(f"{key}: {', '.join(vals)}")
    return "\n".join(lines)

