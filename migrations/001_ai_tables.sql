-- =============================================================
-- RideConnect AI Service — Extended Schema Migration
-- Run against the shared Supabase PostgreSQL database.
-- All tables use IF NOT EXISTS so re-running is safe.
-- =============================================================

-- -----------------------------------------------------------
-- Driver real-time locations (updated by POST /update-driver-location)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS driver_locations (
    id              BIGSERIAL PRIMARY KEY,
    driver_id       BIGINT NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    latitude        NUMERIC(10, 7) NOT NULL,
    longitude       NUMERIC(10, 7) NOT NULL,
    heading         NUMERIC(5, 2),          -- degrees 0–360
    speed_kmh       NUMERIC(6, 2),
    recorded_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_driver_locations_driver_id  ON driver_locations(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_locations_recorded_at ON driver_locations(recorded_at DESC);

-- -----------------------------------------------------------
-- Driver availability / status
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS driver_status (
    id          BIGSERIAL PRIMARY KEY,
    driver_id   BIGINT NOT NULL UNIQUE REFERENCES drivers(id) ON DELETE CASCADE,
    status      VARCHAR(20) NOT NULL DEFAULT 'offline',  -- online|offline|on_trip
    last_seen   TIMESTAMP DEFAULT NOW(),
    idle_since  TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- -----------------------------------------------------------
-- Passenger ride requests (on-demand)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS ride_requests (
    id                  BIGSERIAL PRIMARY KEY,
    passenger_id        BIGINT REFERENCES mobile_users(id),
    pickup_lat          NUMERIC(10, 7) NOT NULL,
    pickup_lng          NUMERIC(10, 7) NOT NULL,
    dropoff_lat         NUMERIC(10, 7) NOT NULL,
    dropoff_lng         NUMERIC(10, 7) NOT NULL,
    pickup_address      TEXT,
    dropoff_address     TEXT,
    ride_type           VARCHAR(30) DEFAULT 'standard',
    status              VARCHAR(30) DEFAULT 'pending',  -- pending|matched|cancelled|completed
    matched_driver_id   BIGINT REFERENCES drivers(id),
    matching_score      NUMERIC(5, 4),
    estimated_fare      NUMERIC(10, 2),
    requested_at        TIMESTAMP DEFAULT NOW(),
    matched_at          TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ride_requests_status       ON ride_requests(status);
CREATE INDEX IF NOT EXISTS idx_ride_requests_passenger_id ON ride_requests(passenger_id);

-- -----------------------------------------------------------
-- Driver ratings (post-trip reviews normalised for ML)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS driver_ratings (
    id              BIGSERIAL PRIMARY KEY,
    driver_id       BIGINT NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    trip_id         BIGINT REFERENCES trips(id),
    rating          NUMERIC(3, 2) NOT NULL CHECK (rating BETWEEN 1 AND 5),
    punctuality     NUMERIC(3, 2),
    safety          NUMERIC(3, 2),
    communication   NUMERIC(3, 2),
    comment         TEXT,
    rated_by        BIGINT REFERENCES mobile_users(id),
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_driver_ratings_driver_id ON driver_ratings(driver_id);

-- -----------------------------------------------------------
-- Ride feedback (passenger → platform)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS ride_feedback (
    id          BIGSERIAL PRIMARY KEY,
    trip_id     BIGINT REFERENCES trips(id),
    user_id     BIGINT REFERENCES mobile_users(id),
    rating      INTEGER CHECK (rating BETWEEN 1 AND 5),
    category    VARCHAR(50),   -- pricing|safety|punctuality|comfort
    comment     TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- -----------------------------------------------------------
-- Demand zones (populated by K-Means clustering)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS demand_zones (
    id              BIGSERIAL PRIMARY KEY,
    zone_name       VARCHAR(100),
    center_lat      NUMERIC(10, 7) NOT NULL,
    center_lng      NUMERIC(10, 7) NOT NULL,
    radius_km       NUMERIC(6, 3) DEFAULT 2.0,
    cluster_id      INTEGER,
    demand_score    NUMERIC(5, 4) DEFAULT 0,
    ride_count      INTEGER DEFAULT 0,
    active          BOOLEAN DEFAULT TRUE,
    computed_at     TIMESTAMP DEFAULT NOW(),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- -----------------------------------------------------------
-- Traffic logs (for ETA and routing features)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS traffic_logs (
    id              BIGSERIAL PRIMARY KEY,
    zone_id         BIGINT REFERENCES demand_zones(id),
    latitude        NUMERIC(10, 7),
    longitude       NUMERIC(10, 7),
    congestion_level INTEGER CHECK (congestion_level BETWEEN 1 AND 5),
    avg_speed_kmh   NUMERIC(6, 2),
    incident_flag   BOOLEAN DEFAULT FALSE,
    recorded_at     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_traffic_logs_recorded_at ON traffic_logs(recorded_at DESC);

-- -----------------------------------------------------------
-- Route checkpoints (for route optimisation)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS route_checkpoints (
    id          BIGSERIAL PRIMARY KEY,
    trip_id     BIGINT REFERENCES trips(id),
    sequence    INTEGER NOT NULL,
    latitude    NUMERIC(10, 7) NOT NULL,
    longitude   NUMERIC(10, 7) NOT NULL,
    name        VARCHAR(200),
    is_mandatory BOOLEAN DEFAULT FALSE,
    passed_at   TIMESTAMP,
    created_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_route_checkpoints_trip_id ON route_checkpoints(trip_id);

-- -----------------------------------------------------------
-- Predicted demand (output of POST /predict-demand)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS predicted_demand (
    id                  BIGSERIAL PRIMARY KEY,
    zone_id             BIGINT REFERENCES demand_zones(id),
    hour                INTEGER NOT NULL,
    day_of_week         INTEGER NOT NULL,
    demand_score        NUMERIC(5, 4) NOT NULL,
    predicted_requests  INTEGER NOT NULL,
    confidence          NUMERIC(5, 4),
    weather_condition   VARCHAR(50),
    model_version       VARCHAR(50) DEFAULT 'v1',
    predicted_at        TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_predicted_demand_zone_hour ON predicted_demand(zone_id, hour, day_of_week);

-- -----------------------------------------------------------
-- Driver behavior logs (output of behavior analysis)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS driver_behavior_logs (
    id                  BIGSERIAL PRIMARY KEY,
    driver_id           BIGINT NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
    trip_id             BIGINT REFERENCES trips(id),
    behavior_class      VARCHAR(20) NOT NULL,  -- safe|efficient|risky|inefficient
    confidence          NUMERIC(5, 4),
    avg_speed_kmh       NUMERIC(6, 2),
    route_deviation_pct NUMERIC(6, 3),
    cancellation_rate   NUMERIC(5, 4),
    avg_rating          NUMERIC(3, 2),
    raw_features        JSONB,
    analyzed_at         TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_driver_behavior_driver_id ON driver_behavior_logs(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_behavior_class     ON driver_behavior_logs(behavior_class);

-- -----------------------------------------------------------
-- Fare audit log (populated by anomaly detection)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS fare_audit (
    id              BIGSERIAL PRIMARY KEY,
    trip_id         BIGINT REFERENCES trips(id),
    ride_id         BIGINT REFERENCES rides(id),
    original_fare   NUMERIC(10, 2) NOT NULL,
    predicted_fare  NUMERIC(10, 2),
    anomaly_flag    BOOLEAN DEFAULT FALSE,
    anomaly_type    VARCHAR(50),   -- double_pricing|abnormal_surge|unusual_distance
    anomaly_score   NUMERIC(8, 4),
    z_score         NUMERIC(8, 4),
    resolved        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fare_audit_anomaly_flag ON fare_audit(anomaly_flag) WHERE anomaly_flag = TRUE;

-- -----------------------------------------------------------
-- System metrics (for /analytics/system-health)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_metrics (
    id              BIGSERIAL PRIMARY KEY,
    metric_name     VARCHAR(100) NOT NULL,
    metric_value    NUMERIC,
    metric_unit     VARCHAR(30),
    tags            JSONB,
    recorded_at     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_system_metrics_name ON system_metrics(metric_name, recorded_at DESC);

-- -----------------------------------------------------------
-- AI price predictions audit (optional — used by predict-price)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_price_predictions (
    id              BIGSERIAL PRIMARY KEY,
    distance_km     NUMERIC(8, 3),
    demand_level    INTEGER,
    traffic_level   INTEGER,
    ride_type       VARCHAR(30),
    predicted_price NUMERIC(10, 2),
    created_at      TIMESTAMP DEFAULT NOW()
);
