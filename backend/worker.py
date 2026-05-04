from __future__ import annotations

import time

from .pipeline import process_job
from .settings import Settings
from .store import claim_next_job, init_db


def run_forever() -> None:
    settings = Settings.load()
    settings.ensure_dirs()
    init_db(settings)

    while True:
        job = claim_next_job(settings)
        if job is None:
            time.sleep(settings.worker_poll_seconds)
            continue
        process_job(settings, job)


if __name__ == "__main__":
    run_forever()
