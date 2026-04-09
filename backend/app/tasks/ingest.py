import dramatiq


@dramatiq.actor
def ingest_demo_manifest() -> str:
    return "ingest-scheduled"
