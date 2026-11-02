"""Synthetic adapters around the real worker, for process termination tests only."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if os.getenv('APP_ENV') != 'test':
    raise SystemExit('This fixture requires APP_ENV=test.')

from backend import main, research_worker as worker, consumption
from test_operational_autonomy import Source, Researcher


def run():
    mode, marker = sys.argv[1], Path(sys.argv[2])
    source, researcher = Source(verified=True), Researcher()
    main.radar_provider = source
    consumption.PROVIDER_LIMITS = {**consumption.PROVIDER_LIMITS, source.name: 100}
    task = None
    def hold(*_):
        marker.write_text(json.dumps(task), encoding='utf8')
        while True: time.sleep(1)
    source.search_page = consumption.metered(source.name)(hold if mode == 'hold' else source.search_page)
    researcher.research = consumption.metered('website')(hold if mode == 'hold' else researcher.research)
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        task = worker.claim()
        if task:
            if not worker.execute(task, provider=source, researcher=researcher):
                raise RuntimeError('Synthetic execution failed to commit.')
            return
        time.sleep(.5)
    raise RuntimeError('No eligible synthetic task within the bounded wait.')


if __name__ == '__main__':
    run()
