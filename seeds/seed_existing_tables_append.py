import datetime
import os
import random

import psycopg2
from psycopg2.extras import execute_values

DB = os.getenv("DATABASE_URL")
if not DB:
    raise SystemExit("DATABASE_URL is not set")

rng = random.Random(42)

DZ_DATA = [
    ("Kigali City Center", -1.9441, 30.0619, 0.95, 850, 0),
    ("Kacyiru", -1.9350, 30.0893, 0.82, 640, 1),
    ("Remera", -1.9535, 30.1117, 0.75, 590, 2),
    ("Kimironko", -1.9276, 30.1178, 0.70, 520, 3),
    ("Nyamirambo", -1.9741, 30.0453, 0.62, 440, 4),
    ("Kicukiro", -2.0000, 30.0800, 0.55, 390, 5),
    ("Gisozi", -1.9109, 30.0619, 0.50, 350, 6),
    ("Kagugu", -1.9218, 30.0800, 0.46, 310, 7),
    ("Nyabugogo", -1.9368, 30.0525, 0.88, 720, 8),
    ("Kanombe / Ikibuga", -1.9686, 30.1386, 0.78, 610, 9),
    ("Musanze", -1.4990, 29.6344, 0.40, 220, 10),
    ("Huye (Butare)", -2.5960, 29.7400, 0.35, 180, 11),
    ("Rubavu (Gisenyi)", -1.6836, 29.2639, 0.38, 200, 12),
    ("Muhanga (Gitarama)", -2.0833, 29.7500, 0.30, 150, 13),
    ("Rwamagana", -1.9490, 30.4337, 0.28, 130, 14),
]


conn = psycopg2.connect(DB)
conn.autocommit = False
cur = conn.cursor()


def table_exists(name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
        )
        """,
        (name,),
    )
    return bool(cur.fetchone()[0])


def column_exists(table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s AND column_name=%s
        )
        """,
        (table_name, column_name),
    )
    return bool(cur.fetchone()[0])


print("Connected to database.")

zone_ids = []
if table_exists("demand_zones"):
    print("1. Upserting demand_zones...")
    has_updated_at = column_exists("demand_zones", "updated_at")
    for zone_name, center_lat, center_lng, demand_score, ride_count, cluster_id in DZ_DATA:
        cur.execute("SELECT id FROM demand_zones WHERE zone_name=%s ORDER BY id LIMIT 1", (zone_name,))
        row = cur.fetchone()
        if row:
            zid = row[0]
            if has_updated_at:
                cur.execute(
                    """
                    UPDATE demand_zones
                    SET center_lat=%s,
                        center_lng=%s,
                        demand_score=%s,
                        ride_count=%s,
                        cluster_id=%s,
                        active=TRUE,
                        updated_at=NOW()
                    WHERE id=%s
                    """,
                    (center_lat, center_lng, demand_score, ride_count, cluster_id, zid),
                )
            else:
                cur.execute(
                    """
                    UPDATE demand_zones
                    SET center_lat=%s,
                        center_lng=%s,
                        demand_score=%s,
                        ride_count=%s,
                        cluster_id=%s,
                        active=TRUE
                    WHERE id=%s
                    """,
                    (center_lat, center_lng, demand_score, ride_count, cluster_id, zid),
                )
        else:
            cur.execute(
                """
                INSERT INTO demand_zones (zone_name,center_lat,center_lng,demand_score,ride_count,cluster_id,active)
                VALUES (%s,%s,%s,%s,%s,%s,TRUE)
                RETURNING id
                """,
                (zone_name, center_lat, center_lng, demand_score, ride_count, cluster_id),
            )
            zid = cur.fetchone()[0]
        zone_ids.append(zid)
    print(f"   -> {len(zone_ids)} zone rows touched")
else:
    print("1. Skipping demand_zones (table missing)")

if zone_ids and table_exists("traffic_logs"):
    print("2. Inserting traffic_logs (append)...")
    peak_hours = {7, 8, 9, 17, 18, 19, 20}
    tl_rows = []
    for zi, zid in enumerate(zone_ids):
        zlat = DZ_DATA[zi][1]
        zlng = DZ_DATA[zi][2]
        for day_offset in range(14):
            for hour in range(24):
                if hour in peak_hours:
                    base = rng.uniform(0.72, 0.95)
                elif hour in {6, 10, 12, 13, 21, 22}:
                    base = rng.uniform(0.45, 0.70)
                else:
                    base = rng.uniform(0.08, 0.32)
                congestion = max(1, min(5, int(round(base * 4)) + 1))
                speed = round(rng.uniform(10, 60) * (1 - base * 0.5), 1)
                ts = datetime.datetime(2026, 2, 21, hour, 0, 0) + datetime.timedelta(days=day_offset)
                lat = round(zlat + rng.uniform(-0.01, 0.01), 7)
                lng = round(zlng + rng.uniform(-0.01, 0.01), 7)
                tl_rows.append((zid, lat, lng, congestion, speed, base > 0.80, ts))
    execute_values(
        cur,
        """
        INSERT INTO traffic_logs (zone_id,latitude,longitude,congestion_level,avg_speed_kmh,incident_flag,recorded_at)
        VALUES %s
        """,
        tl_rows,
        page_size=1000,
    )
    print(f"   -> {len(tl_rows)} traffic rows inserted")
else:
    print("2. Skipping traffic_logs (missing table or no zones)")

if zone_ids and table_exists("predicted_demand"):
    print("3. Inserting predicted_demand (append)...")
    peak_hours = {7, 8, 9, 17, 18, 19, 20}
    pd_rows = []
    for zid in zone_ids:
        for dow in range(7):
            for hour in range(24):
                if hour in peak_hours:
                    score = rng.uniform(0.68, 0.98)
                    reqs = rng.randint(25, 90)
                elif hour in {6, 10, 12, 13, 21, 22}:
                    score = rng.uniform(0.40, 0.70)
                    reqs = rng.randint(10, 40)
                else:
                    score = rng.uniform(0.05, 0.38)
                    reqs = rng.randint(1, 15)
                pd_rows.append((zid, hour, dow, round(score, 4), reqs, round(rng.uniform(0.70, 0.95), 3), "clear"))
    execute_values(
        cur,
        """
        INSERT INTO predicted_demand (zone_id,hour,day_of_week,demand_score,predicted_requests,confidence,weather_condition)
        VALUES %s
        """,
        pd_rows,
        page_size=1000,
    )
    print(f"   -> {len(pd_rows)} predicted demand rows inserted")
else:
    print("3. Skipping predicted_demand (missing table or no zones)")

if table_exists("fare_audit") and table_exists("trips"):
    print("4. Inserting fare_audit examples...")
    cur.execute(
        """
        SELECT id, fare FROM trips
        WHERE fare > 30000 OR fare < 300
        ORDER BY random() LIMIT 50
        """
    )
    fa_trips = cur.fetchall()
    fa_rows = []
    for tid, fare in fa_trips:
        if fare is None:
            continue
        fare = float(fare)
        atype = "abnormal_surge" if fare > 30000 else "underfare"
        fa_rows.append((None, tid, fare, True, atype, round(rng.uniform(0.5, 0.9), 4), round(rng.uniform(2.5, 6.0), 4)))
    if fa_rows:
        execute_values(
            cur,
            """
            INSERT INTO fare_audit (ride_id,trip_id,original_fare,anomaly_flag,anomaly_type,anomaly_score,z_score)
            VALUES %s
            ON CONFLICT DO NOTHING
            """,
            fa_rows,
        )
    print(f"   -> {len(fa_rows)} fare audit rows inserted")
else:
    print("4. Skipping fare_audit (missing fare_audit/trips)")

if table_exists("system_metrics"):
    print("5. Inserting system_metrics (append)...")
    sm_rows = []
    now = datetime.datetime.now(datetime.UTC)
    for i in range(72):
        ts = now - datetime.timedelta(hours=i)
        sm_rows.extend(
            [
                ("api_requests_per_minute", rng.uniform(10, 120), "req/min", ts),
                ("avg_prediction_latency_ms", rng.uniform(8, 80), "ms", ts),
                ("active_drivers", float(rng.randint(5, 45)), "count", ts),
                ("completed_trips_last_hour", float(rng.randint(3, 35)), "count", ts),
            ]
        )
    execute_values(
        cur,
        """
        INSERT INTO system_metrics (metric_name,metric_value,metric_unit,recorded_at)
        VALUES %s
        """,
        sm_rows,
        page_size=1000,
    )
    print(f"   -> {len(sm_rows)} system metric rows inserted")
else:
    print("5. Skipping system_metrics (table missing)")

conn.commit()
print("\nAppend seeding complete.")

for t in ["demand_zones", "traffic_logs", "predicted_demand", "fare_audit", "system_metrics"]:
    if table_exists(t):
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t:20s}: {cur.fetchone()[0]}")

cur.close()
conn.close()
