"""
Background work for the harmonize pipeline.

- queue.py      — job dispatch: inline executor vs arq queue + backpressure gate
- tasks.py      — the harmonize task: job lifecycle, progress events, bounded retries
- arq_worker.py — arq WorkerSettings for the separate worker process
- retention.py  — scheduled data-retention cleanup

Workers run the engine through app.engine_adapter (never the wheel directly).
"""
