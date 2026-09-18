from events.registry import on_event
from events.services import enqueue


@on_event("material.uploaded")
def queue_processing(event) -> None:
    payload = {key: event.payload[key] for key in ("material_id", "project_id", "user_id")}
    enqueue("process_material", payload, idempotency_key=f"process-material:{payload['material_id']}")
