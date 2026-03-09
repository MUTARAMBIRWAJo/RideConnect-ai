"""Kafka consumer abstraction with memory fallback."""

from __future__ import annotations

import json
import os
from typing import Dict, List

from streaming.broker_state import MEMORY_TOPICS

try:
    from kafka import KafkaConsumer  # type: ignore
except Exception:  # pragma: no cover
    KafkaConsumer = None


class RideEventConsumer:
    def __init__(self) -> None:
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    def consume_events(self, topic: str, max_messages: int = 100) -> List[Dict]:
        if KafkaConsumer is not None:
            try:
                consumer = KafkaConsumer(
                    topic,
                    bootstrap_servers=self.bootstrap_servers,
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    consumer_timeout_ms=250,
                )
                out = []
                for msg in consumer:
                    out.append(msg.value)
                    if len(out) >= max_messages:
                        break
                consumer.close()
                return out
            except Exception:
                pass

        out: List[Dict] = []
        q = MEMORY_TOPICS[topic]
        while q and len(out) < max_messages:
            out.append(q.popleft())
        return out


_default_consumer = RideEventConsumer()


def consume_events(topic: str, max_messages: int = 100) -> List[Dict]:
    """Consume a batch of events from a Kafka topic (or memory fallback)."""
    return _default_consumer.consume_events(topic, max_messages=max_messages)
