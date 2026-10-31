"""Chapter 10: lose a Slack reply on purpose, then recover.

The escalation is posted for real, then the worker is told
the reply was lost. Reconciliation finds the message by
its operation ID in the channel history.
"""

import asyncio
import sys

from demo_approval import approve, propose
from fastapi.testclient import TestClient

from secondloop.console.app import app
from secondloop.workflow import reconcile, worker
from secondloop.workflow.checks import current_checks
from secondloop.workflow.db import connect, migrate
from secondloop.workflow.vendors import Vendors


class LosesReplies(Vendors):
    def send_escalation(self, op):
        super().send_escalation(op)
        raise worker.Uncertain("ReadTimeout (simulated)")


if __name__ == "__main__":
    with connect() as conn:
        migrate(conn)
        pid = asyncio.run(
            propose(
                "propose_escalation",
                {
                    "case_id": "CASE-17",
                    "summary": sys.argv[1],
                },
            )
        )
        approve(TestClient(app), pid)
        print(
            "send:",
            worker.run_once(
                conn, LosesReplies(), current_checks
            ),
        )
        print(
            "again:",
            worker.run_once(
                conn, LosesReplies(), current_checks
            ),
        )
        print("reconcile:", reconcile.reconcile(conn))
