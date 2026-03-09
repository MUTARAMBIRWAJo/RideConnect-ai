"""Kafka producer abstraction with local-memory fallback."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict

from streaming.broker_state import MEMORY_TOPICS

try:
    from kafka import KafkaProducer  # type: ignore
except Exception:  # pragma: no cover
    KafkaProducer = None


class RideEventProducer:
    def __init__(self) -> None:
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self._producer = None
        if KafkaProducer is not None:
            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                )
            except Exception:
                self._producer = None

    def publish_event(self, topic: str, data: Dict) -> Dict:
        payload = {
            "event_id": data.get("event_id") or f"evt-{datetime.now(timezone.utc).timestamp()}",
            "timestamp": data.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            **data,
        }
        if self._producer is not None:
            self._producer.send(topic, payload)
            return {"status": "published", "backend": "kafka", "topic": topic}

        MEMORY_TOPICS[topic].append(payload)
        return {"status": "published", "backend": "memory", "topic": topic}


_default_producer = RideEventProducer()


def publish_event(topic: str, data: Dict) -> Dict:
    """Publish a single event to a Kafka topic (or memory fallback)."""
    return _default_producer.publish_event(topic, data)
