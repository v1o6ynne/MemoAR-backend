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
            cur.execute(
                """
                create table if not exists user_profiles (
                  user_id text primary key,
                  email text not null,
                  created_at timestamptz not null default now(),
                  updated_at timestamptz not null default now()
                );
                """
            )
            cur.execute(
                """
                create table if not exists user_app_usage (
                  user_id text primary key,
                  usage jsonb not null default '{}'::jsonb,
                  created_at timestamptz not null default now(),
                  updated_at timestamptz not null default now()
                );
                """
            )
            cur.execute(
                """
                create table if not exists capture_surveys (
                  user_id text not null,
                  memory_id text not null,
                  survey jsonb not null,
                  created_at timestamptz not null default now(),
                  updated_at timestamptz not null default now(),
                  primary key (user_id, memory_id)
                );
                """
            )
            cur.execute(
                """
                create index if not exists capture_surveys_user_updated_idx
                on capture_surveys (user_id, updated_at desc);
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


def upsert_capture_survey(
    user_id: str,
    memory_id: str,
    survey: dict[str, Any],
) -> dict[str, Any]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into capture_surveys (user_id, memory_id, survey, created_at, updated_at)
                values (%s, %s, %s::jsonb, now(), now())
                on conflict (user_id, memory_id) do update
                set survey = excluded.survey,
                    updated_at = now();
                """,
                (user_id, memory_id, psycopg.types.json.Jsonb(survey)),
            )
        conn.commit()

    return capture_survey_stats(user_id)


def capture_survey_stats(user_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select survey
                from capture_surveys
                where user_id = %s;
                """,
                (user_id,),
            )
            rows = cur.fetchall()

    surveys = [row["survey"] for row in rows]
    mechanism_counts: dict[str, int] = {}
    expanded_count = 0
    normal_count = 0

    for survey in surveys:
        if survey.get("isExpandedCapture") is True:
            expanded_count += 1
        elif survey.get("isExpandedCapture") is False:
            normal_count += 1

        mechanisms = survey.get("captureMechanisms")
        if isinstance(mechanisms, list):
            for mechanism in mechanisms:
                if mechanism:
                    key = str(mechanism)
                    mechanism_counts[key] = mechanism_counts.get(key, 0) + 1
            continue

        mechanism = survey.get("captureMechanism")
        if mechanism:
            key = str(mechanism)
            mechanism_counts[key] = mechanism_counts.get(key, 0) + 1

    return {
        "total": len(surveys),
        "expanded_capture_count": expanded_count,
        "normal_capture_count": normal_count,
        "mechanism_counts": mechanism_counts,
    }


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


def upsert_user_email(user_id: str, email: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into user_profiles (user_id, email, created_at, updated_at)
                values (%s, %s, now(), now())
                on conflict (user_id) do update
                set email = excluded.email,
                    updated_at = now();
                """,
                (user_id, email),
            )
        conn.commit()


def get_user_email(user_id: str) -> Optional[str]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select email
                from user_profiles
                where user_id = %s;
                """,
                (user_id,),
            )
            row = cur.fetchone()

    if not row:
        return None

    email = row.get("email")
    if email is None:
        return None

    return str(email)


def upsert_user_app_usage(user_id: str, usage: dict[str, Any]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into user_app_usage (user_id, usage, created_at, updated_at)
                values (%s, %s::jsonb, now(), now())
                on conflict (user_id) do update
                set usage = excluded.usage,
                    updated_at = now();
                """,
                (user_id, psycopg.types.json.Jsonb(usage)),
            )
        conn.commit()


def get_user_app_usage(user_id: str) -> Optional[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select usage
                from user_app_usage
                where user_id = %s;
                """,
                (user_id,),
            )
            row = cur.fetchone()

    if not row:
        return None

    usage = row.get("usage")
    if usage is None or not isinstance(usage, dict):
        return None

    return usage
