"""Run the worker: python -m secondloop.workflow.run"""

import logging
import time

from secondloop.workflow import worker
from secondloop.workflow.checks import current_checks
from secondloop.workflow.db import connect, migrate
from secondloop.workflow.vendors import Vendors

log = logging.getLogger("secondloop.worker")


def main(once=False, idle=2.0):
    vendors = Vendors()
    with connect() as conn:
        migrate(conn)
        while True:
            done = worker.run_once(
                conn, vendors, current_checks
            )
            if done:
                log.info("operation %s", done)
                print(done, flush=True)
            elif once:
                return
            else:
                time.sleep(idle)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    main(once="--once" in sys.argv)
