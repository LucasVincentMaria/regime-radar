"""
Shared singletons used across the app.

Keeping the shared Fetcher here (rather than in app.main) avoids circular
imports: routes and the scheduler can import it without importing the FastAPI
app module.
"""

from __future__ import annotations

from app.data.fetcher import Fetcher

# One fetcher shared by the scheduler and on-demand routes (its semaphore caps
# total concurrency across the whole app).
fetcher = Fetcher()
