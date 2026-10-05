"""Deletion contract tests; database access is mocked, so no live data is touched."""

import unittest
import json
import sqlite3
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Database import pg
from Routes import write_file_route


class DeleteMemoryRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(write_file_route.router)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.delete = patch.object(pg, "delete_memory", return_value=True).start()
        self.connect = patch.object(pg, "get_conn", side_effect=AssertionError("Live database access")).start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.client.close)

    def test_deletes_only_requested_user_and_memory(self):
        response = self.client.post("/writeData/delete-memory", json={
            "user_id": "P01", "memory_id": "memory-1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True, "user_id": "P01", "memory_id": "memory-1", "deleted": True,
        })
        self.delete.assert_called_once_with("P01", "memory-1")
        self.connect.assert_not_called()

    def test_retry_of_absent_record_succeeds(self):
        self.delete.return_value = False
        response = self.client.post("/writeData/delete-memory", json={
            "user_id": "P01", "memory_id": "memory-1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(response.json()["deleted"])

    def test_invalid_user_or_empty_memory_is_rejected(self):
        for payload in (
            {"user_id": "../P01", "memory_id": "memory-1"},
            {"user_id": "P01", "memory_id": "   "},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/writeData/delete-memory", json=payload).status_code, 400)
        self.delete.assert_not_called()

    def test_missing_field_is_rejected(self):
        response = self.client.post("/writeData/delete-memory", json={"user_id": "P01"})
        self.assertEqual(response.status_code, 422)
        self.delete.assert_not_called()

    def test_database_failure_is_not_reported_as_success(self):
        self.delete.side_effect = RuntimeError("database unavailable")
        response = self.client.post("/writeData/delete-memory", json={
            "user_id": "P01", "memory_id": "memory-1",
        })
        self.assertEqual(response.status_code, 500)


class DeleteMemoryDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.cur = self.conn.cursor.return_value.__enter__.return_value
        self.connection = patch.object(pg, "get_conn").start()
        self.connection.return_value.__enter__.return_value = self.conn
        self.addCleanup(patch.stopall)

    def test_query_is_scoped_and_parameterized(self):
        self.cur.rowcount = 1
        memory_id = "memory'; delete from memories; --"
        self.assertTrue(pg.delete_memory("P01", memory_id))
        self.cur.execute.assert_called_once_with(
            "delete from memories where user_id = %s and memory_id = %s;",
            ("P01", memory_id),
        )
        self.conn.commit.assert_called_once()

    def test_absent_record_returns_false(self):
        self.cur.rowcount = 0
        self.assertFalse(pg.delete_memory("P01", "absent"))
        self.conn.commit.assert_called_once()

    def test_failed_delete_does_not_commit(self):
        self.cur.execute.side_effect = RuntimeError("database unavailable")
        with self.assertRaises(RuntimeError):
            pg.delete_memory("P01", "memory-1")
        self.conn.commit.assert_not_called()


class DeleteMemoryListTests(unittest.TestCase):
    def test_deleted_record_disappears_from_list_and_other_records_remain(self):
        # Run the real DELETE and list queries against an isolated SQL database.
        database = sqlite3.connect(":memory:", check_same_thread=False)
        self.addCleanup(database.close)
        database.execute("create table memories (user_id text, memory_id text, memory text, updated_at text)")
        database.executemany("insert into memories values (?, ?, ?, ?)", [
            ("P01", "memory-1", json.dumps({"id": "memory-1"}), "2026-10-01"),
            ("P01", "memory-2", json.dumps({"id": "memory-2"}), "2026-10-02"),
            ("P02", "memory-1", json.dumps({"id": "memory-1"}), "2026-10-01"),
        ])
        database.commit()

        class Cursor:
            def __enter__(self):
                self.cursor = database.cursor()
                return self

            def __exit__(self, *args):
                self.cursor.close()

            def execute(self, sql, params):
                self.cursor.execute(sql.replace("%s", "?"), params)
                self.rowcount = self.cursor.rowcount

            def fetchall(self):
                return [{"memory": json.loads(row[0])} for row in self.cursor.fetchall()]

        connection = MagicMock()
        connection.cursor.side_effect = Cursor
        connection.commit.side_effect = database.commit
        connection.__enter__.return_value = connection
        app = FastAPI()
        app.include_router(write_file_route.router)
        with patch.object(pg, "get_conn", return_value=connection), TestClient(app) as client:
            response = client.post("/writeData/delete-memory", json={
                "user_id": "P01", "memory_id": "memory-1",
            })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["deleted"])
            self.assertEqual(pg.list_memories("P01"), [{"id": "memory-2"}])
            self.assertEqual(pg.list_memories("P02"), [{"id": "memory-1"}])
            response = client.post("/writeData/delete-memory", json={
                "user_id": "P01", "memory_id": "memory-1",
            })
            self.assertFalse(response.json()["deleted"])


if __name__ == "__main__":
    unittest.main()
