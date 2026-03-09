"""Fallback in-memory event bus when Kafka is unavailable in local development."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import DefaultDict, Deque, Dict

MEMORY_TOPICS: DefaultDict[str, Deque[dict]] = defaultdict(deque)


def topic_metrics() -> Dict[str, int]:
    return {k: len(v) for k, v in MEMORY_TOPICS.items()}
