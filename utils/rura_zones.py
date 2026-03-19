"""Official RURA Kigali transport zones and route references.

Source: RURA tariff update effective 16 March 2024.
Used for GPS->zone mapping, deterministic zone encoding, and fare floor helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math


@dataclass
class Zone:
    name: str
    lat_min: float
    lat_max: float
    lng_min: float
    lng_max: float
    corridor: str
    terminal: str
    fare_base_rwf: int
    description: str = ""

    def contains(self, lat: float, lng: float) -> bool:
        return self.lat_min <= lat <= self.lat_max and self.lng_min <= lng <= self.lng_max

    @property
    def center(self) -> Tuple[float, float]:
        return (
            (self.lat_min + self.lat_max) / 2,
            (self.lng_min + self.lng_max) / 2,
        )


RURA_ZONES: List[Zone] = [
    Zone(
        name="Remera",
        lat_min=-1.935,
        lat_max=-1.905,
        lng_min=30.105,
        lng_max=30.143,
        corridor="A/B/C/E",
        terminal="Remera Bus Park",
        fare_base_rwf=256,
        description="Routes 101,105,108,109,111-115,120-122,125 origin/destination",
    ),
    Zone(
        name="Nyabugogo",
        lat_min=-1.960,
        lat_max=-1.940,
        lng_min=30.050,
        lng_max=30.080,
        corridor="A/B/D/F/G",
        terminal="Nyabugogo Bus Park",
        fare_base_rwf=205,
        description="Major hub routes 102,105,112,118,204,206,305,310-315,321,404-419",
    ),
    Zone(
        name="CBD",
        lat_min=-1.955,
        lat_max=-1.935,
        lng_min=30.055,
        lng_max=30.085,
        corridor="A/B/D/E/F/G",
        terminal="Down Town Bus Park",
        fare_base_rwf=205,
        description="Routes 101,103,104,201,205,301,302,304,308,313,317,401-403,415",
    ),
    Zone(
        name="Kabuga",
        lat_min=-1.935,
        lat_max=-1.905,
        lng_min=30.140,
        lng_max=30.165,
        corridor="A/E",
        terminal="Kabuga Bus Park",
        fare_base_rwf=420,
        description="Routes 102,111,124,325 eastern terminus",
    ),
    Zone(
        name="Kanombe",
        lat_min=-1.975,
        lat_max=-1.950,
        lng_min=30.120,
        lng_max=30.150,
        corridor="B",
        terminal="Kanombe / Kibaya Bus Terminal",
        fare_base_rwf=224,
        description="Routes 104,114,118 near airport",
    ),
    Zone(
        name="Masaka",
        lat_min=-1.980,
        lat_max=-1.960,
        lng_min=30.055,
        lng_max=30.090,
        corridor="B",
        terminal="Masaka Bus Terminal",
        fare_base_rwf=384,
        description="Routes 107,322",
    ),
    Zone(
        name="Busanza",
        lat_min=-1.975,
        lat_max=-1.955,
        lng_min=30.095,
        lng_max=30.130,
        corridor="B",
        terminal="Busanza Bus Terminal",
        fare_base_rwf=227,
        description="Routes 113,115,125",
    ),
    Zone(
        name="Nyanza",
        lat_min=-1.980,
        lat_max=-1.960,
        lng_min=30.035,
        lng_max=30.060,
        corridor="C",
        terminal="Nyanza Bus Park",
        fare_base_rwf=256,
        description="Routes 202,203,204,208,211,213,214",
    ),
    Zone(
        name="Kimironko",
        lat_min=-1.930,
        lat_max=-1.905,
        lng_min=30.110,
        lng_max=30.143,
        corridor="C/D/E/F",
        terminal="Kimironko Bus Park",
        fare_base_rwf=204,
        description="Routes 213,215,302,305-309,314,316,318,322,325",
    ),
    Zone(
        name="Gahanga",
        lat_min=-1.980,
        lat_max=-1.960,
        lng_min=30.065,
        lng_max=30.095,
        corridor="C",
        terminal="Gahanga Bus Terminal",
        fare_base_rwf=278,
        description="Route 208",
    ),
    Zone(
        name="Gikondo",
        lat_min=-1.975,
        lat_max=-1.955,
        lng_min=30.075,
        lng_max=30.105,
        corridor="D",
        terminal="Gikondo / Bwerankori Bus Terminal",
        fare_base_rwf=377,
        description="Routes 109,205,206,215",
    ),
    Zone(
        name="Kicukiro",
        lat_min=-1.980,
        lat_max=-1.960,
        lng_min=30.100,
        lng_max=30.130,
        corridor="D/B",
        terminal="Kicukiro / Saint Joseph Bus Terminal",
        fare_base_rwf=383,
        description="Routes 201,212",
    ),
    Zone(
        name="Nyamirambo",
        lat_min=-1.975,
        lat_max=-1.955,
        lng_min=30.038,
        lng_max=30.065,
        corridor="G",
        terminal="Nyamirambo Bus Terminal (Ryanyuma)",
        fare_base_rwf=205,
        description="Routes 401,402,406,417",
    ),
    Zone(
        name="Kacyiru",
        lat_min=-1.950,
        lat_max=-1.925,
        lng_min=30.082,
        lng_max=30.112,
        corridor="A/C/E/F",
        terminal="Kacyiru Bus Stop / Terminal",
        fare_base_rwf=355,
        description="Routes 105,118,211,304,305",
    ),
    Zone(
        name="Kinyinya",
        lat_min=-1.920,
        lat_max=-1.900,
        lng_min=30.080,
        lng_max=30.115,
        corridor="E/F",
        terminal="Kinyinya Bus Terminal",
        fare_base_rwf=301,
        description="Routes 301,309,315,317",
    ),
    Zone(
        name="Batsinda",
        lat_min=-1.935,
        lat_max=-1.912,
        lng_min=30.038,
        lng_max=30.070,
        corridor="E/F",
        terminal="Batsinda Bus Terminal",
        fare_base_rwf=301,
        description="Routes 303,310,311,313,318",
    ),
    Zone(
        name="Gisozi",
        lat_min=-1.935,
        lat_max=-1.910,
        lng_min=30.060,
        lng_max=30.090,
        corridor="F",
        terminal="Gisozi / Gasanze Bus Terminal",
        fare_base_rwf=301,
        description="Route 321",
    ),
    Zone(
        name="Musave",
        lat_min=-1.945,
        lat_max=-1.920,
        lng_min=30.038,
        lng_max=30.068,
        corridor="E/F",
        terminal="Musave Bus Terminal (via Zindiro)",
        fare_base_rwf=204,
        description="Routes 308,316",
    ),
    Zone(
        name="Nyacyonga",
        lat_min=-1.910,
        lat_max=-1.893,
        lng_min=30.060,
        lng_max=30.090,
        corridor="G",
        terminal="Nyacyonga Bus Terminal",
        fare_base_rwf=306,
        description="Routes 403,407",
    ),
    Zone(
        name="Karama",
        lat_min=-1.980,
        lat_max=-1.958,
        lng_min=30.038,
        lng_max=30.060,
        corridor="G",
        terminal="Karama Bus Terminal",
        fare_base_rwf=205,
        description="Routes 414,417",
    ),
    Zone(
        name="Bishenyi",
        lat_min=-1.960,
        lat_max=-1.940,
        lng_min=30.038,
        lng_max=30.058,
        corridor="G",
        terminal="Bishenyi Bus Terminal",
        fare_base_rwf=383,
        description="Route 404",
    ),
]


@dataclass
class RURARoute:
    route_no: int
    corridor: str
    origin: str
    destination: str
    via: str
    fare_rwf: int


RURA_ROUTES: List[RURARoute] = [
    RURARoute(101, "A", "Remera Bus Park", "Down Town Bus Park", "Sonatube", 307),
    RURARoute(102, "A", "Kabuga Bus Park", "Nyabugogo Bus Park", "Sonatube", 741),
    RURARoute(103, "A", "Down Town Bus Park", "Rubirizi Bus Terminal", "Kabeza/Remera", 484),
    RURARoute(105, "A", "Remera Bus Park", "Nyabugogo Bus Park", "Kacyiru", 355),
    RURARoute(108, "A", "Remera Bus Park", "Nyanza Bus Park", "", 256),
    RURARoute(109, "A", "Remera Bus Park", "Bwerankori Bus Terminal", "Gikondo", 306),
    RURARoute(112, "A", "Remera Bus Park", "Nyabugogo Bus Park", "Sonatube", 307),
    RURARoute(120, "A", "Remera Bus Park", "SEZ Bus Terminal", "", 295),
    RURARoute(124, "A", "Down Town Bus Park", "Kabuga Bus Park", "Sonatube", 741),
    RURARoute(125, "A", "Remera Bus Park", "Busanza Bus Terminal", "Itunda", 267),
    RURARoute(104, "B", "Down Town Bus Park", "Kibaya Bus Terminal", "Kanombe/Sonatube", 516),
    RURARoute(106, "B", "Remera Bus Park", "Ndera Bus Terminal", "Ku Gasima", 269),
    RURARoute(107, "B", "Remera Bus Park", "Masaka Bus Terminal", "", 384),
    RURARoute(111, "B", "Remera Bus Park", "Kabuga Bus Park", "", 420),
    RURARoute(113, "B", "Remera Bus Park", "Busanza Bus Terminal", "Rubirizi", 227),
    RURARoute(114, "B", "Remera Bus Park", "Kibaya Bus Terminal", "Kanombe", 224),
    RURARoute(115, "B", "Remera Bus Park", "Busanza Bus Terminal", "Nyarugunga", 291),
    RURARoute(118, "B", "Nyabugogo Bus Park", "Kibaya Bus Terminal", "Kanombe/Kacyiru", 565),
    RURARoute(121, "B", "Remera Bus Park", "Masoro (AUCA) Bus Terminal", "", 291),
    RURARoute(122, "B", "Remera Bus Park", "Gasogi Bus Terminal", "", 439),
    RURARoute(202, "C", "Nyanza Bus Park", "Down Town Bus Park", "Zion", 340),
    RURARoute(203, "C", "Nyanza Bus Park", "Down Town Bus Park", "Gatenga", 390),
    RURARoute(204, "C", "Nyanza Bus Park", "Nyabugogo Bus Park", "Zion", 422),
    RURARoute(208, "C", "Nyanza Bus Park", "Gahanga Bus Terminal", "", 278),
    RURARoute(211, "C", "Nyanza Bus Park", "Kacyiru Bus Stop", "", 364),
    RURARoute(213, "C", "Nyanza Bus Park", "Kimironko Bus Park", "", 323),
    RURARoute(214, "C", "Nyanza Bus Park", "Nyabugogo Bus Park", "Gatenga", 422),
    RURARoute(201, "D", "Down Town Bus Park", "Saint Joseph Bus Terminal", "", 403),
    RURARoute(205, "D", "Down Town Bus Park", "Bwerankori Bus Terminal", "Gikondo", 377),
    RURARoute(206, "D", "Nyabugogo Bus Park", "Bwerankori Bus Terminal", "Gikondo", 382),
    RURARoute(212, "D", "Nyabugogo Bus Park", "Saint Joseph Bus Terminal", "", 383),
    RURARoute(215, "D", "Kimironko Bus Park", "Bwerankori Bus Terminal", "Gikondo", 408),
    RURARoute(217, "D", "Muyange Bus Terminal", "Zinia MKT Bus Terminal", "", 278),
    RURARoute(218, "D", "Muyange Bus Terminal", "Zinia MKT Bus Terminal", "", 278),
    RURARoute(301, "E", "Down Town Bus Park", "Kinyinya Bus Terminal", "Nyarutarama", 403),
    RURARoute(302, "E", "Kimironko Bus Park", "Down Town Bus Park", "", 355),
    RURARoute(304, "E", "Down Town Bus Park", "Kacyiru Bus Terminal", "", 371),
    RURARoute(306, "E", "Kimironko Bus Park", "Birembo Bus Terminal", "Masizi", 301),
    RURARoute(309, "E", "Kimironko Bus Park", "Kinyinya Bus Terminal", "", 301),
    RURARoute(316, "E", "Kimironko Bus Park", "Musave Bus Terminal", "Zindiro", 204),
    RURARoute(318, "E", "Kimironko Bus Park", "Batsinda Bus Terminal", "", 301),
    RURARoute(322, "E", "Kimironko Bus Park", "Masaka Bus Terminal", "", 355),
    RURARoute(325, "E", "Kabuga Bus Park", "Kimironko Bus Park", "", 420),
    RURARoute(303, "F", "Down Town Bus Park", "Batsinda Bus Terminal", "Agakiriro", 301),
    RURARoute(305, "F", "Nyabugogo Bus Park", "Kimironko Bus Park", "Kacyiru", 371),
    RURARoute(308, "F", "Down Town Bus Park", "Musave Bus Terminal", "Zindiro", 484),
    RURARoute(310, "F", "Nyabugogo Bus Park", "Batsinda Bus Terminal", "Agakiriro", 301),
    RURARoute(311, "F", "Nyabugogo Bus Park", "Batsinda Bus Terminal", "ULK", 301),
    RURARoute(313, "F", "Down Town Bus Park", "Batsinda Bus Terminal", "", 301),
    RURARoute(314, "F", "Nyabugogo Bus Park", "Kimironko Bus Park", "Kibagabaga", 339),
    RURARoute(315, "F", "Nyabugogo Bus Park", "Kinyinya Bus Terminal", "Utexrwa", 387),
    RURARoute(317, "F", "Down Town Bus Park", "Kinyinya Bus Terminal", "Utexrwa", 342),
    RURARoute(321, "F", "Nyabugogo Bus Park", "Gasanze Bus Terminal", "Batsinda", 462),
    RURARoute(401, "G", "Down Town Bus Park", "Nyamirambo Bus Terminal", "Ryanyuma", 243),
    RURARoute(402, "G", "Down Town Bus Park", "Nyamirambo Bus Terminal", "Ryanyuma/Kimisagara", 307),
    RURARoute(403, "G", "Down Town Bus Park", "Nyacyonga Bus Terminal", "", 420),
    RURARoute(404, "G", "Nyabugogo Bus Park", "Bishenyi Bus Terminal", "", 383),
    RURARoute(405, "G", "Nyabugogo Terminal", "Kanyinya Bus Terminal", "", 484),
    RURARoute(406, "G", "Mageragere Bus Terminal", "ERP Nyamirambo Bus Terminal", "", 377),
    RURARoute(407, "G", "Nyabugogo Bus Park", "Nyacyonga Bus Terminal", "", 306),
    RURARoute(414, "G", "Nyabugogo Bus Park", "Karama Bus Terminal", "", 310),
    RURARoute(415, "G", "Nyabugogo Bus Park", "Down Town Bus Park", "", 205),
    RURARoute(416, "G", "Nyabugogo Bus Park", "Gihara Bus Terminal", "", 383),
    RURARoute(417, "G", "Nyamirambo Bus Terminal", "Karama Bus Terminal", "Ryanyuma", 205),
    RURARoute(418, "G", "Nyabugogo Bus Park", "Bweramvura Bus Terminal", "", 278),
    RURARoute(419, "G", "Nyabugogo Bus Park", "Cyumbati Bus Terminal", "", 307),
]


_ZONE_INDEX: Dict[str, Zone] = {z.name: z for z in RURA_ZONES}
ZONE_NAMES: List[str] = sorted(_ZONE_INDEX.keys()) + ["Other"]
ZONE_TO_INT: Dict[str, int] = {name: i for i, name in enumerate(ZONE_NAMES)}
INT_TO_ZONE: Dict[int, str] = {i: name for name, i in ZONE_TO_INT.items()}


def coords_to_zone(lat: float, lng: float) -> str:
    for zone in RURA_ZONES:
        if zone.contains(lat, lng):
            return zone.name

    min_dist = float("inf")
    nearest = "Other"
    for zone in RURA_ZONES:
        clat, clng = zone.center
        dist = math.hypot(lat - clat, lng - clng)
        if dist < min_dist:
            min_dist = dist
            nearest = zone.name

    return nearest if min_dist < 0.005 else "Other"


def encode_zone(zone_name: str) -> int:
    return ZONE_TO_INT.get(zone_name, ZONE_TO_INT["Other"])


def decode_zone(code: int) -> str:
    return INT_TO_ZONE.get(code, "Other")


def get_zone(name: str) -> Optional[Zone]:
    return _ZONE_INDEX.get(name)


def get_corridor_zones(corridor: str) -> List[Zone]:
    c = corridor.upper()
    return [z for z in RURA_ZONES if c in z.corridor]


def get_min_fare(origin_zone: str, dest_zone: str) -> Optional[int]:
    origin = _ZONE_INDEX.get(origin_zone)
    dest = _ZONE_INDEX.get(dest_zone)
    if not origin or not dest:
        return None

    matching = [
        r.fare_rwf
        for r in RURA_ROUTES
        if (origin.terminal in r.origin or origin.terminal in r.destination)
        and (dest.terminal in r.origin or dest.terminal in r.destination)
    ]
    return min(matching) if matching else None


ZONE_PEAK_HOURS: Dict[str, List[int]] = {
    "Nyabugogo": [6, 7, 8, 9, 17, 18, 19],
    "CBD": [7, 8, 9, 12, 13, 17, 18],
    "Remera": [7, 8, 9, 17, 18, 19],
    "Kacyiru": [7, 8, 9, 16, 17, 18],
    "Kimironko": [7, 8, 17, 18, 19, 20],
    "Gikondo": [6, 7, 8, 17, 18],
    "Nyamirambo": [7, 8, 18, 19, 20, 21],
    "Gisozi": [7, 8, 17, 18],
    "Kicukiro": [7, 8, 9, 17, 18],
    "Kinyinya": [7, 8, 17, 18],
    "Kanombe": [5, 6, 7, 18, 19, 20, 21],
    "Kabuga": [6, 7, 8, 17, 18],
    "Nyanza": [7, 8, 9, 17, 18],
    "Masaka": [7, 8, 17, 18],
    "Busanza": [7, 8, 17, 18],
    "Gahanga": [7, 8, 17, 18],
    "Nyacyonga": [6, 7, 8, 17, 18],
    "Karama": [7, 8, 17, 18],
    "Bishenyi": [7, 8, 17, 18],
    "Musave": [7, 8, 17, 18],
    "Batsinda": [7, 8, 17, 18],
}


def is_peak_hour(zone_name: str, hour: int) -> bool:
    return hour in ZONE_PEAK_HOURS.get(zone_name, [7, 8, 9, 17, 18, 19])
