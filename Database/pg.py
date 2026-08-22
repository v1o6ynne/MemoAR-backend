import os
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def _supabase_database_url() -> str:
    url = (
        os.getenv("SUPABASE_DATABASE_URL", "").strip()
        or os.getenv("SUPABASE_DB_URL", "").strip()
    )
    if not url:
        raise RuntimeError(
            "SUPABASE_DATABASE_URL (or SUPABASE_DB_URL) is not set for notification_records"
        )
    return url


def get_conn() -> psycopg.Connection:
    return psycopg.connect(_database_url(), row_factory=dict_row)


def get_notification_conn() -> psycopg.Connection:
    return psycopg.connect(_supabase_database_url(), row_factory=dict_row)


def _normalize_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _serialize_dt(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    return value if isinstance(value, str) else None


def _notification_record_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(row["record_id"]),
        "user_id": str(row["user_id"]),
        "memory_id": row.get("memory_id"),
        "record_type": str(row["record_type"]),
        "notification_status": row.get("notification_status"),
        "notification_time": _serialize_dt(row.get("notification_time")),
        "delivered_time": _serialize_dt(row.get("delivered_time")),
        "shown_time": _serialize_dt(row.get("shown_time")),
        "dismissed_time": _serialize_dt(row.get("dismissed_time")),
        "notification_location": _normalize_json_object(row.get("notification_location")),
        "notification_mechanism": _normalize_json_object(row.get("notification_mechanism")),
        "user_location": _normalize_json_object(row.get("user_location")),
        "location_mechanism": _normalize_json_object(row.get("location_mechanism")),
        "location_out_reason": row.get("location_out_reason"),
        "memory_time_context": _normalize_json_object(row.get("memory_time_context")),
        "memory_location_context": _normalize_json_object(row.get("memory_location_context")),
        "clicked": bool(row.get("clicked", False)),
        "click_time": _serialize_dt(row.get("click_time")),
        "click_action": row.get("click_action"),
        "click_usage": _normalize_json_object(row.get("click_usage")),
        "usage_context": _normalize_json_object(row.get("usage_context")),
        "interaction_events": row.get("interaction_events") if isinstance(row.get("interaction_events"), list) else [],
        "memory_time_relevance": row.get("memory_time_relevance"),
        "memory_location_relevance": row.get("memory_location_relevance"),
        "relevance_details": _normalize_json_object(row.get("relevance_details")),
        "notification_payload": _normalize_json_object(row.get("notification_payload")),
        "details": _normalize_json_object(row.get("details")),
        "created_at": _serialize_dt(row.get("created_at")),
        "updated_at": _serialize_dt(row.get("updated_at")),
    }


def _api_process_record_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(row["record_id"]),
        "request_id": str(row["request_id"]),
        "method": str(row["method"]),
        "path": str(row["path"]),
        "route_path": row.get("route_path"),
        "query_string": row.get("query_string"),
        "status_code": row.get("status_code"),
        "process_status": str(row["process_status"]),
        "error_type": row.get("error_type"),
        "error_message": row.get("error_message"),
        "duration_ms": row.get("duration_ms"),
        "client_host": row.get("client_host"),
        "request_meta": _normalize_json_object(row.get("request_meta")),
        "created_at": _serialize_dt(row.get("created_at")),
    }


def _migrate_primary_tables() -> None:
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
            cur.execute(
                """
                create table if not exists api_process_records (
                  record_id text primary key,
                  request_id text not null,
                  method text not null,
                  path text not null,
                  route_path text,
                  query_string text,
                  status_code integer,
                  process_status text not null,
                  error_type text,
                  error_message text,
                  duration_ms integer,
                  client_host text,
                  request_meta jsonb not null default '{}'::jsonb,
                  created_at timestamptz not null default now()
                );
                """
            )
            cur.execute(
                """
                alter table api_process_records
                add column if not exists request_id text,
                add column if not exists route_path text,
                add column if not exists query_string text,
                add column if not exists status_code integer,
                add column if not exists process_status text,
                add column if not exists error_type text,
                add column if not exists error_message text,
                add column if not exists duration_ms integer,
                add column if not exists client_host text,
                add column if not exists request_meta jsonb not null default '{}'::jsonb,
                add column if not exists created_at timestamptz not null default now();
                """
            )
            cur.execute(
                """
                create index if not exists api_process_records_route_created_idx
                on api_process_records (route_path, created_at desc);
                """
            )
            cur.execute(
                """
                create index if not exists api_process_records_status_created_idx
                on api_process_records (process_status, created_at desc);
                """
            )
        conn.commit()


def _migrate_notification_tables() -> None:
    with get_notification_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists notification_records (
                  record_id text primary key,
                  user_id text not null,
                  memory_id text,
                  record_type text not null default 'notification',
                  notification_status text,
                  notification_time timestamptz,
                  delivered_time timestamptz,
                  shown_time timestamptz,
                  dismissed_time timestamptz,
                  notification_location jsonb not null default '{}'::jsonb,
                  notification_mechanism jsonb not null default '{}'::jsonb,
                  user_location jsonb not null default '{}'::jsonb,
                  location_mechanism jsonb not null default '{}'::jsonb,
                  location_out_reason text,
                  memory_time_context jsonb not null default '{}'::jsonb,
                  memory_location_context jsonb not null default '{}'::jsonb,
                  clicked boolean not null default false,
                  click_time timestamptz,
                  click_action text,
                  click_usage jsonb not null default '{}'::jsonb,
                  usage_context jsonb not null default '{}'::jsonb,
                  interaction_events jsonb not null default '[]'::jsonb,
                  memory_time_relevance text,
                  memory_location_relevance text,
                  relevance_details jsonb not null default '{}'::jsonb,
                  notification_payload jsonb not null default '{}'::jsonb,
                  details jsonb not null default '{}'::jsonb,
                  created_at timestamptz not null default now(),
                  updated_at timestamptz not null default now()
                );
                """
            )
            cur.execute(
                """
                alter table notification_records
                add column if not exists notification_status text,
                add column if not exists delivered_time timestamptz,
                add column if not exists shown_time timestamptz,
                add column if not exists dismissed_time timestamptz,
                add column if not exists notification_mechanism jsonb not null default '{}'::jsonb,
                add column if not exists location_mechanism jsonb not null default '{}'::jsonb,
                add column if not exists memory_time_context jsonb not null default '{}'::jsonb,
                add column if not exists memory_location_context jsonb not null default '{}'::jsonb,
                add column if not exists click_action text,
                add column if not exists usage_context jsonb not null default '{}'::jsonb,
                add column if not exists interaction_events jsonb not null default '[]'::jsonb,
                add column if not exists relevance_details jsonb not null default '{}'::jsonb,
                add column if not exists notification_payload jsonb not null default '{}'::jsonb;
                """
            )
            cur.execute(
                """
                create index if not exists notification_records_user_updated_idx
                on notification_records (user_id, updated_at desc);
                """
            )
            cur.execute(
                """
                create index if not exists notification_records_user_clicked_idx
                on notification_records (user_id, clicked, updated_at desc);
                """
            )
        conn.commit()


def migrate() -> None:
    """
    Minimal migrations. Safe to run on every startup.
    """
    _migrate_primary_tables()
    _migrate_notification_tables()


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


def upsert_notification_record(
    user_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    record_id = str(record.get("record_id") or uuid4())
    memory_id = record.get("memory_id")
    record_type = str(record.get("record_type") or "notification")
    notification_status = record.get("notification_status")
    notification_time = record.get("notification_time")
    delivered_time = record.get("delivered_time")
    shown_time = record.get("shown_time")
    dismissed_time = record.get("dismissed_time")
    notification_location = _normalize_json_object(record.get("notification_location"))
    notification_mechanism = _normalize_json_object(record.get("notification_mechanism"))
    user_location = _normalize_json_object(record.get("user_location"))
    location_mechanism = _normalize_json_object(record.get("location_mechanism"))
    location_out_reason = record.get("location_out_reason")
    memory_time_context = _normalize_json_object(record.get("memory_time_context"))
    memory_location_context = _normalize_json_object(record.get("memory_location_context"))
    clicked = bool(record.get("clicked", False))
    click_time = record.get("click_time")
    click_action = record.get("click_action")
    click_usage = _normalize_json_object(record.get("click_usage"))
    usage_context = _normalize_json_object(record.get("usage_context"))
    interaction_events = record.get("interaction_events")
    if not isinstance(interaction_events, list):
        interaction_events = []
    memory_time_relevance = record.get("memory_time_relevance")
    memory_location_relevance = record.get("memory_location_relevance")
    relevance_details = _normalize_json_object(record.get("relevance_details"))
    notification_payload = _normalize_json_object(record.get("notification_payload"))
    details = _normalize_json_object(record.get("details"))

    with get_notification_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into notification_records (
                  record_id,
                  user_id,
                  memory_id,
                  record_type,
                  notification_status,
                  notification_time,
                  delivered_time,
                  shown_time,
                  dismissed_time,
                  notification_location,
                  notification_mechanism,
                  user_location,
                  location_mechanism,
                  location_out_reason,
                  memory_time_context,
                  memory_location_context,
                  clicked,
                  click_time,
                  click_action,
                  click_usage,
                  usage_context,
                  interaction_events,
                  memory_time_relevance,
                  memory_location_relevance,
                  relevance_details,
                  notification_payload,
                  details,
                  created_at,
                  updated_at
                )
                values (
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s::timestamptz,
                  %s::timestamptz,
                  %s::timestamptz,
                  %s::timestamptz,
                  %s::jsonb,
                  %s::jsonb,
                  %s::jsonb,
                  %s::jsonb,
                  %s,
                  %s::jsonb,
                  %s::jsonb,
                  %s,
                  %s::timestamptz,
                  %s,
                  %s::jsonb,
                  %s::jsonb,
                  %s::jsonb,
                  %s,
                  %s,
                  %s::jsonb,
                  %s::jsonb,
                  %s::jsonb,
                  now(),
                  now()
                )
                on conflict (record_id) do update
                set user_id = excluded.user_id,
                    memory_id = excluded.memory_id,
                    record_type = excluded.record_type,
                    notification_status = excluded.notification_status,
                    notification_time = excluded.notification_time,
                    delivered_time = excluded.delivered_time,
                    shown_time = excluded.shown_time,
                    dismissed_time = excluded.dismissed_time,
                    notification_location = excluded.notification_location,
                    notification_mechanism = excluded.notification_mechanism,
                    user_location = excluded.user_location,
                    location_mechanism = excluded.location_mechanism,
                    location_out_reason = excluded.location_out_reason,
                    memory_time_context = excluded.memory_time_context,
                    memory_location_context = excluded.memory_location_context,
                    clicked = excluded.clicked,
                    click_time = excluded.click_time,
                    click_action = excluded.click_action,
                    click_usage = excluded.click_usage,
                    usage_context = excluded.usage_context,
                    interaction_events = excluded.interaction_events,
                    memory_time_relevance = excluded.memory_time_relevance,
                    memory_location_relevance = excluded.memory_location_relevance,
                    relevance_details = excluded.relevance_details,
                    notification_payload = excluded.notification_payload,
                    details = excluded.details,
                    updated_at = now()
                returning *;
                """,
                (
                    record_id,
                    user_id,
                    memory_id,
                    record_type,
                    notification_status,
                    notification_time,
                    delivered_time,
                    shown_time,
                    dismissed_time,
                    psycopg.types.json.Jsonb(notification_location),
                    psycopg.types.json.Jsonb(notification_mechanism),
                    psycopg.types.json.Jsonb(user_location),
                    psycopg.types.json.Jsonb(location_mechanism),
                    location_out_reason,
                    psycopg.types.json.Jsonb(memory_time_context),
                    psycopg.types.json.Jsonb(memory_location_context),
                    clicked,
                    click_time,
                    click_action,
                    psycopg.types.json.Jsonb(click_usage),
                    psycopg.types.json.Jsonb(usage_context),
                    psycopg.types.json.Jsonb(interaction_events),
                    memory_time_relevance,
                    memory_location_relevance,
                    psycopg.types.json.Jsonb(relevance_details),
                    psycopg.types.json.Jsonb(notification_payload),
                    psycopg.types.json.Jsonb(details),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    if not row:
        raise RuntimeError("Failed to save notification record")

    return _notification_record_from_row(row)


def list_notification_records(
    user_id: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    with get_notification_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from notification_records
                where user_id = %s
                order by updated_at desc
                limit %s;
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()

    return [_notification_record_from_row(row) for row in rows]


def get_notification_record(record_id: str) -> Optional[dict[str, Any]]:
    with get_notification_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from notification_records
                where record_id = %s;
                """,
                (record_id,),
            )
            row = cur.fetchone()

    if not row:
        return None

    return _notification_record_from_row(row)


def insert_api_process_record(record: dict[str, Any]) -> dict[str, Any]:
    record_id = str(record.get("record_id") or uuid4())
    request_id = str(record.get("request_id") or uuid4())
    method = str(record.get("method") or "UNKNOWN")
    path = str(record.get("path") or "/")
    route_path = record.get("route_path")
    query_string = record.get("query_string")
    status_code = record.get("status_code")
    process_status = str(record.get("process_status") or "success")
    error_type = record.get("error_type")
    error_message = record.get("error_message")
    duration_ms = record.get("duration_ms")
    client_host = record.get("client_host")
    request_meta = _normalize_json_object(record.get("request_meta"))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into api_process_records (
                  record_id,
                  request_id,
                  method,
                  path,
                  route_path,
                  query_string,
                  status_code,
                  process_status,
                  error_type,
                  error_message,
                  duration_ms,
                  client_host,
                  request_meta,
                  created_at
                )
                values (
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s::jsonb,
                  now()
                )
                returning *;
                """,
                (
                    record_id,
                    request_id,
                    method,
                    path,
                    route_path,
                    query_string,
                    status_code,
                    process_status,
                    error_type,
                    error_message,
                    duration_ms,
                    client_host,
                    psycopg.types.json.Jsonb(request_meta),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    if not row:
        raise RuntimeError("Failed to insert api process record")

    return _api_process_record_from_row(row)


def list_api_process_records(
    limit: int = 200,
    route_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if route_path:
                cur.execute(
                    """
                    select *
                    from api_process_records
                    where route_path = %s
                    order by created_at desc
                    limit %s;
                    """,
                    (route_path, limit),
                )
            else:
                cur.execute(
                    """
                    select *
                    from api_process_records
                    order by created_at desc
                    limit %s;
                    """,
                    (limit,),
                )
            rows = cur.fetchall()

    return [_api_process_record_from_row(row) for row in rows]


def api_process_stats(limit: int = 200) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  coalesce(route_path, path) as api_path,
                  method,
                  count(*) as total_requests,
                  count(*) filter (where coalesce(status_code, 200) < 400 and process_status = 'success') as success_count,
                  count(*) filter (where coalesce(status_code, 500) >= 400 or process_status = 'error') as error_count,
                  avg(duration_ms)::float as avg_duration_ms,
                  max(created_at) as last_processed_at
                from api_process_records
                group by coalesce(route_path, path), method
                order by total_requests desc, last_processed_at desc
                limit %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "api_path": row["api_path"],
            "method": row["method"],
            "total_requests": row["total_requests"],
            "success_count": row["success_count"],
            "error_count": row["error_count"],
            "avg_duration_ms": row["avg_duration_ms"],
            "last_processed_at": _serialize_dt(row.get("last_processed_at")),
        }
        for row in rows
    ]
