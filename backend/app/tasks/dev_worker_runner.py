"""Development worker runner that avoids Dramatiq's CLI multiprocessing shell."""

from __future__ import annotations

import argparse
import signal
import time
from importlib import import_module
from threading import Event

from dramatiq import Worker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()

    bootstrap = import_module("backend.app.tasks.worker_bootstrap")
    broker = import_module("backend.app.tasks.broker").get_broker()
    worker_threads = max(1, int(args.threads))
    worker = Worker(broker, worker_threads=worker_threads)
    stopped = Event()

    def handle_stop(_signum, _frame) -> None:
        stopped.set()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, handle_stop)

    print(
        f"[dev-worker] loaded {len(bootstrap.LOADED_TASK_MODULES)} task modules; "
        f"starting in-process Dramatiq worker with {worker_threads} thread(s)",
        flush=True,
    )
    worker.start()
    try:
        while not stopped.is_set():
            time.sleep(0.5)
    finally:
        worker.stop()
        broker.close()


if __name__ == "__main__":
    main()
