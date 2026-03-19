"""RURA Kigali public transport tariffs and lookup utilities.

Tariffs are based on the March 16, 2024 notice shared by the user.
Use route code first when available for deterministic compliance.
"""

from __future__ import annotations

import re
from statistics import median
from typing import Any


def _norm(value: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9 ]+", " ", str(value or "").upper())
    return re.sub(r"\s+", " ", cleaned).strip()


RURA_TARIFFS: list[dict[str, Any]] = [
    {"route_code": "101", "corridor": "A", "origin_stop": "REMERA BUS PARK", "destination_stop": "DOWN TOWN BUS PARK", "fare_rwf": 307},
    {"route_code": "102", "corridor": "A", "origin_stop": "KABUGA BUS PARK", "destination_stop": "NYABUGOGO BUS PARK", "fare_rwf": 741},
    {"route_code": "103", "corridor": "A", "origin_stop": "DOWN TOWN BUS PARK", "destination_stop": "RUBIRIZI BUS TERMINAL", "fare_rwf": 484},
    {"route_code": "105", "corridor": "A", "origin_stop": "REMERA BUS PARK", "destination_stop": "NYABUGOGO BUS PARK", "fare_rwf": 355},
    {"route_code": "108", "corridor": "A", "origin_stop": "REMERA BUS PARK", "destination_stop": "NYANZA BUS PARK", "fare_rwf": 256},
    {"route_code": "109", "corridor": "A", "origin_stop": "REMERA BUS PARK", "destination_stop": "BWERANKORI BUS TERMINAL", "fare_rwf": 306},
    {"route_code": "112", "corridor": "A", "origin_stop": "REMERA BUS PARK", "destination_stop": "NYABUGOGO BUS PARK", "fare_rwf": 307},
    {"route_code": "120", "corridor": "A", "origin_stop": "REMERA BUS PARK", "destination_stop": "SEZ BUS TERMINAL", "fare_rwf": 295},
    {"route_code": "124", "corridor": "A", "origin_stop": "DOWN TOWN BUS PARK", "destination_stop": "KABUGA BUS PARK", "fare_rwf": 741},
    {"route_code": "125", "corridor": "A", "origin_stop": "REMERA BUS PARK", "destination_stop": "BUSANZA BUS TERMINAL", "fare_rwf": 267},
    {"route_code": "104", "corridor": "B", "origin_stop": "DOWN TOWN BUS PARK", "destination_stop": "KIBAYA BUS TERMINAL", "fare_rwf": 516},
    {"route_code": "106", "corridor": "B", "origin_stop": "REMERA BUS PARK", "destination_stop": "NDERA BUS TERMINAL", "fare_rwf": 269},
    {"route_code": "107", "corridor": "B", "origin_stop": "REMERA BUS PARK", "destination_stop": "MASAKA BUS TERMINAL", "fare_rwf": 384},
    {"route_code": "111", "corridor": "B", "origin_stop": "REMERA BUS PARK", "destination_stop": "KABUGA BUS PARK", "fare_rwf": 420},
    {"route_code": "113", "corridor": "B", "origin_stop": "REMERA BUS PARK", "destination_stop": "BUSANZA BUS TERMINAL", "fare_rwf": 227},
    {"route_code": "114", "corridor": "B", "origin_stop": "REMERA BUS PARK", "destination_stop": "KIBAYA BUS TERMINAL", "fare_rwf": 224},
    {"route_code": "115", "corridor": "B", "origin_stop": "REMERA BUS PARK", "destination_stop": "BUSANZA BUS TERMINAL", "fare_rwf": 291},
    {"route_code": "118", "corridor": "B", "origin_stop": "NYABUGOGO BUS PARK", "destination_stop": "KIBAYA BUS TERMINAL", "fare_rwf": 565},
    {"route_code": "121", "corridor": "B", "origin_stop": "REMERA BUS PARK", "destination_stop": "MASORO AUCA BUS TERMINAL", "fare_rwf": 291},
    {"route_code": "122", "corridor": "B", "origin_stop": "REMERA BUS PARK", "destination_stop": "GASOGI BUS TERMINAL", "fare_rwf": 439},
    {"route_code": "202", "corridor": "C", "origin_stop": "NYANZA BUS PARK", "destination_stop": "DOWN TOWN BUS PARK", "fare_rwf": 340},
    {"route_code": "203", "corridor": "C", "origin_stop": "NYANZA BUS PARK", "destination_stop": "DOWN TOWN BUS PARK", "fare_rwf": 390},
    {"route_code": "204", "corridor": "C", "origin_stop": "NYANZA BUS PARK", "destination_stop": "NYABUGOGO BUS PARK", "fare_rwf": 422},
    {"route_code": "208", "corridor": "C", "origin_stop": "NYANZA BUS PARK", "destination_stop": "GAHANGA BUS TERMINAL", "fare_rwf": 278},
    {"route_code": "211", "corridor": "C", "origin_stop": "NYANZA BUS PARK", "destination_stop": "KACYIRU BUS STOP", "fare_rwf": 364},
    {"route_code": "213", "corridor": "C", "origin_stop": "NYANZA BUS PARK", "destination_stop": "KIMIRONKO BUS PARK", "fare_rwf": 323},
    {"route_code": "214", "corridor": "C", "origin_stop": "NYANZA BUS PARK", "destination_stop": "NYABUGOGO BUS PARK", "fare_rwf": 422},
    {"route_code": "201", "corridor": "D", "origin_stop": "DOWN TOWN BUS PARK", "destination_stop": "SAINT JOSEPH BUS TERMINAL", "fare_rwf": 403},
    {"route_code": "205", "corridor": "D", "origin_stop": "DOWN TOWN BUS PARK", "destination_stop": "BWERANKORI BUS TERMINAL", "fare_rwf": 377},
    {"route_code": "206", "corridor": "D", "origin_stop": "NYABUGOGO BUS PARK", "destination_stop": "BWERANKORI BUS TERMINAL", "fare_rwf": 382},
    {"route_code": "212", "corridor": "D", "origin_stop": "NYABUGOGO BUS PARK", "destination_stop": "SAINT JOSEPH BUS TERMINAL", "fare_rwf": 383},
    {"route_code": "215", "corridor": "D", "origin_stop": "KIMIRONKO BUS PARK", "destination_stop": "BWERANKORI BUS TERMINAL", "fare_rwf": 408},
    {"route_code": "217", "corridor": "D", "origin_stop": "MUYANGE BUS TERMINAL", "destination_stop": "ZINIA MKT BUS TERMINAL", "fare_rwf": 278},
    {"route_code": "218", "corridor": "D", "origin_stop": "MUYANGE BUS TERMINAL", "destination_stop": "ZINIA MKT BUS TERMINAL", "fare_rwf": 278},
]


for row in RURA_TARIFFS:
    row["_route_norm"] = _norm(row["route_code"])
    row["_origin_norm"] = _norm(row["origin_stop"])
    row["_destination_norm"] = _norm(row["destination_stop"])
    row["_corridor_norm"] = _norm(row["corridor"])


def lookup_rura_tariff(
    route_code: str | int | None = None,
    origin_stop: str | None = None,
    destination_stop: str | None = None,
    corridor: str | None = None,
) -> dict[str, Any] | None:
    corridor_norm = _norm(corridor or "")

    if route_code is not None and str(route_code).strip():
        code_norm = _norm(str(route_code))
        for row in RURA_TARIFFS:
            if row["_route_norm"] == code_norm and (not corridor_norm or row["_corridor_norm"] == corridor_norm):
                return {
                    "route_code": row["route_code"],
                    "corridor": row["corridor"],
                    "origin_stop": row["origin_stop"],
                    "destination_stop": row["destination_stop"],
                    "fare_rwf": int(row["fare_rwf"]),
                    "source": "rura_official",
                }

    if origin_stop and destination_stop:
        o = _norm(origin_stop)
        d = _norm(destination_stop)
        for row in RURA_TARIFFS:
            if corridor_norm and row["_corridor_norm"] != corridor_norm:
                continue
            forward = row["_origin_norm"] == o and row["_destination_norm"] == d
            reverse = row["_origin_norm"] == d and row["_destination_norm"] == o
            if forward or reverse:
                return {
                    "route_code": row["route_code"],
                    "corridor": row["corridor"],
                    "origin_stop": row["origin_stop"],
                    "destination_stop": row["destination_stop"],
                    "fare_rwf": int(row["fare_rwf"]),
                    "source": "rura_official",
                }

    return None


def corridor_reference_fare(corridor: str | None) -> float | None:
    corridor_norm = _norm(corridor or "")
    if not corridor_norm:
        return None
    fares = [int(r["fare_rwf"]) for r in RURA_TARIFFS if r["_corridor_norm"] == corridor_norm]
    if not fares:
        return None
    return float(median(fares))
