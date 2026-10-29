"""Continuous real worker loop with controlled source/research adapters only."""
import smart_browser_fixture as fixture

fixture.worker.INTERVAL=0
original=fixture.worker.execute
fixture.worker.execute=lambda task:original(task,provider=fixture.Source(),researcher=fixture.Researcher())
fixture.worker.run()
