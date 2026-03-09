"""Create Kafka topics for ride event streams."""

from __future__ import annotations

import os

try:
    from kafka.admin import KafkaAdminClient, NewTopic  # type: ignore
except Exception:  # pragma: no cover
    KafkaAdminClient = None
    NewTopic = None

TOPICS = ["ride_requests", "driver_locations", "ride_status", "demand_metrics"]


def create_topics() -> dict:
    if KafkaAdminClient is None or NewTopic is None:
        return {"status": "skipped", "reason": "kafka admin client unavailable", "topics": TOPICS}

    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    admin = KafkaAdminClient(bootstrap_servers=servers)
    existing = set(admin.list_topics())
    to_create = [
        NewTopic(name=t, num_partitions=6, replication_factor=1)
        for t in TOPICS
        if t not in existing
    ]
    if to_create:
        admin.create_topics(new_topics=to_create, validate_only=False)
    admin.close()
    return {"status": "ok", "created": [t.name for t in to_create], "topics": TOPICS}


if __name__ == "__main__":
    print(create_topics())
