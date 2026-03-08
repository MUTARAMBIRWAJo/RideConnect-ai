-- =============================================================
-- RideConnect AI Service — Seed Data
-- Inserts realistic test data for Rwanda/East-Africa context.
-- Run AFTER migrations/001_ai_tables.sql
-- Assumes at least one row exists in: users, mobile_users, drivers
-- =============================================================

-- -----------------------------------------------------------
-- Driver statuses
-- -----------------------------------------------------------
INSERT INTO driver_status (driver_id, status, last_seen, idle_since)
SELECT d.id,
       CASE WHEN d.id % 3 = 0 THEN 'online'
            WHEN d.id % 3 = 1 THEN 'on_trip'
            ELSE 'offline' END,
       NOW() - (random() * INTERVAL '30 minutes'),
       NOW() - (random() * INTERVAL '60 minutes')
FROM   drivers d
ON CONFLICT (driver_id) DO UPDATE
    SET status    = EXCLUDED.status,
        last_seen = EXCLUDED.last_seen;

-- -----------------------------------------------------------
-- Driver locations (within Kigali, Rwanda)
-- -----------------------------------------------------------
INSERT INTO driver_locations (driver_id, latitude, longitude, heading, speed_kmh, recorded_at)
SELECT d.id,
       -1.9441 + (random() - 0.5) * 0.15,   -- lat ± 0.075 deg (~8 km)
       30.0619 + (random() - 0.5) * 0.15,   -- lng
       random() * 360,
       CASE WHEN d.id % 3 = 1 THEN 25 + random() * 30 ELSE 0 END,
       NOW() - (random() * INTERVAL '5 minutes')
FROM   drivers d;

-- -----------------------------------------------------------
-- Demand zones (major Kigali areas)
-- -----------------------------------------------------------
INSERT INTO demand_zones (zone_name, center_lat, center_lng, radius_km, demand_score, ride_count)
VALUES
    ('Kigali City Center',   -1.9441, 30.0619, 2.0, 0.9200, 420),
    ('Kacyiru',              -1.9403, 30.0888, 1.5, 0.7800, 310),
    ('Remera',               -1.9535, 30.1117, 1.5, 0.6900, 280),
    ('Nyamirambo',           -1.9741, 30.0453, 1.8, 0.5500, 190),
    ('Kimironko',            -1.9276, 30.1178, 1.5, 0.6200, 240),
    ('Gisozi',               -1.9109, 30.0619, 1.5, 0.4800, 160),
    ('Kicukiro',             -2.0000, 30.0800, 2.0, 0.5100, 175),
    ('Kagugu',               -1.9218, 30.0800, 1.5, 0.4200, 140),
    ('Kigali Airport Area',  -1.9686, 30.1386, 3.0, 0.7100, 295),
    ('Musanze',              -1.4990, 29.6344, 3.0, 0.3800, 110)
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------
-- Traffic logs (24 hours × 10 zones)
-- -----------------------------------------------------------
INSERT INTO traffic_logs (zone_id, latitude, longitude, congestion_level, avg_speed_kmh, recorded_at)
SELECT z.id,
       z.center_lat + (random() - 0.5) * 0.02,
       z.center_lng + (random() - 0.5) * 0.02,
       CASE WHEN h.h BETWEEN 7 AND 9   THEN 4 + (random() > 0.5)::int
            WHEN h.h BETWEEN 17 AND 19 THEN 4 + (random() > 0.5)::int
            WHEN h.h BETWEEN 22 AND 23 THEN 1 + (random() > 0.7)::int
            ELSE 2 + (random() * 2)::int END,
       CASE WHEN h.h BETWEEN 7 AND 9   THEN 8 + random() * 12
            WHEN h.h BETWEEN 17 AND 19 THEN 10 + random() * 10
            ELSE 25 + random() * 20 END,
       NOW() - ((24 - h.h) * INTERVAL '1 hour')
FROM   demand_zones z
CROSS JOIN generate_series(0, 23) AS h(h);

-- -----------------------------------------------------------
-- Driver ratings  (2–4 ratings per existing driver)
-- -----------------------------------------------------------
INSERT INTO driver_ratings (driver_id, rating, punctuality, safety, communication, comment)
SELECT d.id,
       3.5 + random() * 1.4,
       3.0 + random() * 2.0,
       3.5 + random() * 1.5,
       3.0 + random() * 2.0,
       (ARRAY['Great ride!','On time','Safe driver','Very professional','Could be better'])[floor(random()*5+1)]
FROM   drivers d,
       generate_series(1, 3);

-- -----------------------------------------------------------
-- Ride feedback
-- -----------------------------------------------------------
INSERT INTO ride_feedback (trip_id, rating, category, comment)
SELECT t.id,
       3 + (random() * 2)::int,
       (ARRAY['pricing','safety','punctuality','comfort'])[floor(random()*4+1)],
       (ARRAY['Good service','Price seems fair','Fast pickup','Comfortable car','Late arrival'])[floor(random()*5+1)]
FROM   trips t
LIMIT  50;

-- -----------------------------------------------------------
-- Predicted demand (sample — 1 week × 24h × 3 zones)
-- -----------------------------------------------------------
INSERT INTO predicted_demand (zone_id, hour, day_of_week, demand_score, predicted_requests, confidence)
SELECT z.id,
       h.h,
       d.d,
       CASE WHEN h.h BETWEEN 7  AND 9  THEN 0.75 + random() * 0.20
            WHEN h.h BETWEEN 17 AND 19 THEN 0.80 + random() * 0.15
            WHEN h.h BETWEEN 22 AND 23 THEN 0.20 + random() * 0.15
            ELSE 0.35 + random() * 0.30 END,
       CASE WHEN h.h BETWEEN 7  AND 9  THEN 45 + (random() * 30)::int
            WHEN h.h BETWEEN 17 AND 19 THEN 55 + (random() * 35)::int
            ELSE 10 + (random() * 20)::int END,
       0.70 + random() * 0.25
FROM   demand_zones z,
       generate_series(0, 23) AS h(h),
       generate_series(0, 6)  AS d(d)
WHERE  z.id <= 3;

-- -----------------------------------------------------------
-- Driver behavior logs (classify existing drivers)
-- -----------------------------------------------------------
INSERT INTO driver_behavior_logs (driver_id, behavior_class, confidence, avg_speed_kmh, cancellation_rate, avg_rating)
SELECT d.id,
       (ARRAY['safe','efficient','risky','inefficient'])[floor(random()*4+1)],
       0.65 + random() * 0.30,
       25 + random() * 40,
       random() * 0.25,
       3.0 + random() * 2.0
FROM   drivers d;

-- -----------------------------------------------------------
-- System metrics (startup baseline)
-- -----------------------------------------------------------
INSERT INTO system_metrics (metric_name, metric_value, metric_unit, tags)
VALUES
    ('api_requests_total',     0,    'count',   '{"service":"ai"}'),
    ('prediction_latency_ms',  0,    'ms',      '{"endpoint":"predict-price"}'),
    ('model_accuracy_mae',     402,  'KES',     '{"model":"price_v1"}'),
    ('active_drivers',         0,    'count',   '{"status":"online"}'),
    ('demand_score_avg',       0.62, 'score',   '{"city":"kigali"}');
