"""Named child-process barriers. All callers supply disposable Docker test paths."""

import http.client
import json
import multiprocessing
import os
import traceback
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from twin_lab import lifecycle_files, lifecycle_restore
from twin_lab.lifecycle import Lifecycle
from twin_lab.server import Handler, make_server
from twin_lab.store import Store


def checkpoint(pipe, name):
    pipe.send({"boundary": name})
    # No timing race: the parent kills this child only after receiving the boundary.
    pipe.recv()
    raise AssertionError("An interruption barrier must not be resumed")


@contextmanager
def before_statement(store, sql_prefix, pipe, boundary):
    original = store.connection

    class ConnectionProxy:
        def __init__(self, db):
            self.db = db

        def execute(self, sql, *args):
            if sql.strip().startswith(sql_prefix):
                checkpoint(pipe, boundary)
            return self.db.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(self.db, name)

    @contextmanager
    def connection():
        with original() as db:
            yield ConnectionProxy(db)

    with patch.object(store, "connection", connection):
        yield


def perform(pipe, db_path, operation, data):
    """Patches exist only in this child, never in the running application."""
    try:
        # The offline restore operation never opens the live database itself.
        store = None if operation.startswith("restore_") else Store(db_path)
        if data.get("clock"):
            store.lifecycle.clock = lambda: data["clock"]
        if operation == "response_before_commit":
            original = Lifecycle.attach

            def attach(self, *args, **kwargs):
                result = original(self, *args, **kwargs)
                checkpoint(pipe, operation)
                return result

            with patch.object(Lifecycle, "attach", attach):
                store.submit(data["presentation_id"], data["values"])
        elif operation == "response_before_ack":
            original = Handler.reply

            def reply(self, status, body, *args, **kwargs):
                if self.path == "/api/responses" and status == 201:
                    checkpoint(pipe, operation)
                return original(self, status, body, *args, **kwargs)

            server = make_server(store)
            pipe.send({"port": server.server_address[1]})
            with patch.object(Handler, "reply", reply):
                server.handle_request()
                # Keep the HTTP worker alive until the parent terminates this process.
                pipe.recv()
        elif operation in ("withdrawal_after_journal", "disposal_after_journal"):
            original = lifecycle_files.append_ledger

            def append(path, entry):
                original(path, entry)
                checkpoint(pipe, operation)

            with patch.object(lifecycle_files, "append_ledger", append):
                if operation.startswith("withdrawal"):
                    store.lifecycle.withdraw(data["body"])
                else:
                    store.lifecycle.apply_disposal(data["plan"], "FAULT_TEST")
        elif operation == "backup_before_manifest":
            with before_statement(store, "INSERT INTO local_backups", pipe, operation):
                store.collection.backup(data["body"])
        elif operation == "disposal_during_cleanup":
            original = Path.unlink

            def unlink(path, *args, **kwargs):
                result = original(path, *args, **kwargs)
                if path.name == data["filename"]:
                    checkpoint(pipe, operation)
                return result

            with patch.object(Path, "unlink", unlink):
                store.lifecycle.apply_disposal(data["plan"], "FAULT_TEST")
        elif operation in ("restore_before_publish", "restore_after_publish"):
            original = os.link

            def publish(source, destination, *args, **kwargs):
                if operation == "restore_before_publish":
                    checkpoint(pipe, operation)
                result = original(source, destination, *args, **kwargs)
                checkpoint(pipe, operation)
                return result

            with patch.object(lifecycle_restore.os, "link", publish):
                lifecycle_restore.restore_snapshot(
                    data["source"],
                    data["destination"],
                    Path(db_path).parent / "deletion-ledger.jsonl",
                )
        else:
            raise ValueError(f"Unknown interruption operation: {operation}")
        pipe.send({"error": "Operation returned without reaching its required barrier"})
    except BaseException:
        pipe.send({"error": traceback.format_exc()})
    finally:
        pipe.close()


class ChildBarrier:
    """The timeout diagnoses a missing barrier; it never determines operation order."""

    def __init__(self, test, path, operation, data):
        self.test, self.operation = test, operation
        context = multiprocessing.get_context("spawn")
        self.pipe, child_pipe = context.Pipe()
        self.process = context.Process(target=perform, args=(child_pipe, path, operation, data))
        self.process.start()
        child_pipe.close()
        test.addCleanup(self.close)

    def receive(self):
        self.test.assertTrue(self.pipe.poll(20), f"No child event: {self.operation}")
        message = self.pipe.recv()
        self.test.assertNotIn("error", message, message.get("error"))
        return message

    def kill_at_boundary(self):
        self.test.assertEqual(self.receive(), {"boundary": self.operation})
        self.test.assertTrue(self.process.is_alive())
        self.process.kill()
        self.process.join(10)
        self.test.assertFalse(self.process.is_alive())
        self.test.assertEqual(self.process.exitcode, -9)

    def close(self):
        if self.process.is_alive():
            self.process.kill()
            self.process.join(10)
        self.pipe.close()


def submit_http(port, data):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        connection.request(
            "POST",
            "/api/responses",
            json.dumps(data),
            {
                "Content-Type": "application/json",
                "X-Twin-Lab": "1",
            },
        )
        response = connection.getresponse()
        return response.status, response.read()
    except (http.client.RemoteDisconnected, ConnectionResetError) as exc:
        return type(exc).__name__
    finally:
        connection.close()
