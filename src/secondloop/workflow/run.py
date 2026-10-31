"""Run the worker: python -m secondloop.workflow.run"""

import logging
import os
import time

from secondloop import slack
from secondloop.workflow import outbox, reconcile, worker
from secondloop.workflow.checks import current_checks
from secondloop.workflow.db import connect, migrate
from secondloop.workflow.vendors import Vendors

log = logging.getLogger("secondloop.worker")


def main(once=False, idle=2.0):
    vendors = Vendors()
    with connect() as conn:
        migrate(conn)
        client = slack.slack_client()
        channel = slack.operations_channel()
        while True:
            reconcile.expire_leases(conn)
            done = None
            if os.environ.get("WORKER_PAUSED") != "1":
                done = worker.run_once(
                    conn, vendors, current_checks
                )
            found = reconcile.reconcile(conn)
            sent = outbox.deliver_one(
                conn, client, channel
            )
            for item in [done, *found, sent]:
                if item:
                    log.info("%s", item)
                    print(item, flush=True)
            if once and not (done or found or sent):
                return
            else:
                time.sleep(idle)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    main(once="--once" in sys.argv)
