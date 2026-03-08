"""
seeds/002_rwanda_seed.py  (v3 — FK-correct)
============================================
Inserts comprehensive Rwanda data for RideConnect AI model training.

FK mapping (discovered from DB):
  rides.driver_id        → drivers.id
  rides.vehicle_id       → vehicles.id
  trips.driver_id        → mobile_users.id   (mobile app driver)
  trips.passenger_id     → mobile_users.id
  driver_earnings.driver_id → mobile_users.id
  driver_locations.driver_id → drivers.id
  driver_status.driver_id    → drivers.id
  driver_behavior_logs.driver_id → drivers.id
  driver_ratings.driver_id → drivers.id
  driver_ratings.rated_by  → mobile_users.id
  ride_feedback.user_id    → mobile_users.id
  reviews.driver_id → drivers.id  |  reviews.user_id → users.id
  fare_audit.trip_id → trips.id

Currency: RWF (Rwandan Francs)
Names:    Kinyarwanda
"""

import random, datetime, math, hashlib, psycopg2
from psycopg2.extras import execute_values

DB = "postgresql://postgres.tpahuvmhlfluztuhznfj:rOnptMsAAnTbrpIY@aws-1-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"

# -----------------------------------------------------------------
# Rwanda name pools
# -----------------------------------------------------------------
MALE_FIRST = [
    "Jean-Pierre","Claude","Patrick","Emmanuel","Innocent","Etienne","Alexis",
    "Théophile","Faustin","Anastase","Célestin","Callixte","Théogène","Fidèle",
    "Vianney","Modeste","Gaspard","Léonard","Damascène","Clément","Norbert",
    "Cyprien","Athanase","Bonaventure","Gonzague","Médard","Prosper","Valentin",
    "Augustin","Sylvestre","Siméon","Jérôme","Sébastien","Edouard","Félicien",
    "Isidore","Mathieu","Narcisse","Olivier","Rémy","Stanislas","Thierry",
    "Aphrodis","Benoît","Chrysostome","Diogène","Leonidas","Gérard","Alphonse","Paul",
]
FEMALE_FIRST = [
    "Marie","Françoise","Chantal","Immaculée","Pélagie","Solange","Espérance",
    "Vestine","Odette","Henriette","Scholastique","Clotilde","Séraphine",
    "Goretti","Concessa","Anunciata","Béatrice","Cécile","Dévota","Euphrasie",
    "Flavia","Gertrude","Hélène","Isabelle","Joséphine","Liberata","Marguerite",
    "Noëlle","Olive","Prudence","Rose","Salomé","Térèse","Victoire","Yolande",
    "Alphonsine","Bénigne","Candide","Delphine","Eusébie","Fortunée","Grâce",
    "Honorine","Inès","Jacqueline","Laurence","Mérance","Nathalie","Pascaline","Claudine",
]
FAMILY = [
    "Uwimana","Habimana","Nsanzimana","Niyonzima","Mugabo","Nkurunziza",
    "Hakizimana","Nizeyimana","Ntirenganya","Bizimana","Havugimana",
    "Nzabonimana","Munyampundu","Kayitesi","Kagabo","Ndayishimiye",
    "Uwitonze","Mpyisi","Nsabimana","Kamanzi","Umubyeyi","Ingabire",
    "Ndagijimana","Tuyisenge","Rukundo","Mujawimana","Bigirimana",
    "Nyiransengimana","Musabyimana","Mutabazi","Nzeyimana","Uwera",
    "Nduwimana","Twizeyimana","Gasana","Nzabahimana","Habumuremyi",
    "Ntakirutimana","Gakwaya","Sibomana","Rugema","Nzeyumuremyi",
    "Mukamusoni","Mukazitoni","Nyirabashyitsi","Mukarwego","Nyirambabazi",
    "Mukandutiye","Mukangerero","Nyirahabimana",
]

# Real Rwanda locations with GPS
LOCATIONS = [
    ("Kigali City Center, KN 4 Ave",          -1.9441,  30.0619),
    ("Kacyiru, KG 9 Ave, Kigali",             -1.9350,  30.0893),
    ("Remera, KG 11 Ave, Kigali",             -1.9535,  30.1117),
    ("Kimironko Market, Kigali",              -1.9276,  30.1178),
    ("Nyamirambo, KN 47 St, Kigali",          -1.9741,  30.0453),
    ("Kicukiro Centre, Kigali",               -2.0000,  30.0800),
    ("Gisozi, Kigali",                        -1.9109,  30.0619),
    ("Kagugu, KG 621 St, Kigali",             -1.9218,  30.0800),
    ("Nyabugogo Bus Terminal, Kigali",        -1.9368,  30.0525),
    ("Kanombe, Kigali",                       -1.9686,  30.1386),
    ("Niboye, Kicukiro, Kigali",              -1.9975,  30.0806),
    ("Kabeza, Kigali",                        -1.9800,  30.1200),
    ("Gahanga, Kigali",                       -2.0200,  30.0900),
    ("Rusororo, Kigali",                      -1.8500,  30.1200),
    ("Kibagabaga, Kigali",                    -1.9100,  30.1100),
    ("Ndera, Kigali",                         -1.8900,  30.1500),
    ("Gatenga, Kicukiro, Kigali",             -2.0100,  30.1000),
    ("Masaka, Kicukiro, Kigali",              -2.0400,  30.0700),
    ("Kigali International Airport",          -1.9686,  30.1386),
    ("Kigali Convention Centre, KG 2 Ave",    -1.9522,  30.0931),
    ("Kigali Heights, KG 7 Ave",              -1.9480,  30.0950),
    ("University of Rwanda, Kigali",          -1.9400,  30.0820),
    ("King Faisal Hospital, Kigali",          -1.9379,  30.0865),
    ("Nyarutarama, Kigali",                   -1.9250,  30.1050),
    ("Kabuye, Kigali",                        -1.9100,  30.0400),
    ("Musanze Town Center",                   -1.4990,  29.6344),
    ("Huye (Butare) Town Center",             -2.5960,  29.7400),
    ("Rubavu (Gisenyi) Town Center",          -1.6836,  29.2639),
    ("Muhanga (Gitarama) Town Center",        -2.0833,  29.7500),
    ("Nyanza Town Center",                    -2.3530,  29.7400),
    ("Rwamagana Town Center",                 -1.9490,  30.4337),
    ("Kayonza Town Center",                   -1.8897,  30.6396),
    ("Ngoma (Kibungo) Town Center",           -2.1576,  30.4983),
    ("Bugesera Town Center",                  -2.2174,  30.1082),
    ("Rusizi (Cyangugu) Town Center",         -2.4820,  28.9054),
    ("Nyagatare Town Center",                 -1.2983,  30.3276),
    ("Karongi (Kibuye) Town Center",          -2.0589,  29.3486),
    ("Kirehe Town Center",                    -2.1600,  30.6700),
]
KIGALI_LOCS = LOCATIONS[:25]

# Allowed vehicle_type CHECK: sedan, suv, hatchback, van, motorcycle, compact
VEHICLES = [
    ("Toyota","Hiace",        2018,"White",   "van",     14),
    ("Toyota","Hiace",        2019,"White",   "van",     14),
    ("Toyota","Hiace",        2020,"White",   "van",     14),
    ("Toyota","Corolla",      2019,"Silver",  "sedan",    4),
    ("Toyota","Corolla",      2020,"White",   "sedan",    4),
    ("Toyota","RAV4",         2020,"Black",   "suv",      5),
    ("Toyota","RAV4",         2021,"Grey",    "suv",      5),
    ("Toyota","Land Cruiser", 2019,"White",   "suv",      7),
    ("Toyota","Fortuner",     2020,"Black",   "suv",      7),
    ("Toyota","Prado",        2018,"Silver",  "suv",      7),
    ("Suzuki","Swift",        2019,"Red",     "hatchback",4),
    ("Suzuki","Vitara",       2020,"White",   "suv",      5),
    ("Nissan","X-Trail",      2019,"Black",   "suv",      5),
    ("Nissan","Patrol",       2020,"White",   "suv",      7),
    ("Volkswagen","Polo",     2019,"Blue",    "hatchback",5),
    ("Volkswagen","Golf",     2020,"White",   "hatchback",5),
    ("Subaru","Forester",     2019,"Silver",  "suv",      5),
    ("Subaru","Outback",      2020,"Grey",    "suv",      5),
    ("Honda","CR-V",          2020,"White",   "suv",      5),
    ("Honda","Fit",           2019,"Silver",  "hatchback",5),
    ("Mitsubishi","Outlander",2019,"Black",   "suv",      7),
    ("Mitsubishi","Pajero",   2018,"White",   "suv",      7),
    ("Hyundai","Tucson",      2020,"Grey",    "suv",      5),
    ("Hyundai","i10",         2019,"White",   "compact",  4),
    ("Kia","Sportage",        2020,"Black",   "suv",      5),
    ("Toyota","Hiace",        2021,"White",   "van",     14),
    ("Toyota","Hiace",        2022,"White",   "van",     14),
    ("Toyota","Premio",       2019,"Silver",  "sedan",    5),
    ("Toyota","Allion",       2020,"White",   "sedan",    5),
    ("Toyota","Vitz",         2019,"Red",     "hatchback",4),
    ("Mazda","CX-5",          2020,"White",   "suv",      5),
    ("Mazda","Demio",         2019,"Blue",    "hatchback",5),
    ("Toyota","Rush",         2021,"Silver",  "suv",      7),
    ("Toyota","Wish",         2019,"White",   "sedan",    7),
    ("Toyota","Noah",         2020,"Silver",  "van",      8),
    ("Nissan","Note",         2019,"White",   "hatchback",5),
    ("Nissan","Tiida",        2019,"Black",   "sedan",    5),
    ("Volkswagen","Touareg",  2020,"Black",   "suv",      5),
    ("Toyota","Camry",        2020,"Black",   "sedan",    5),
    ("Toyota","Land Cruiser", 2021,"White",   "suv",      7),
    ("Toyota","Hilux",        2020,"White",   "van",      5),
    ("Suzuki","Ertiga",       2020,"Grey",    "van",      7),
    ("Toyota","Sienta",       2021,"Silver",  "van",      7),
    ("Honda","Fit",           2020,"Blue",    "hatchback",5),
    ("Nissan","Juke",         2020,"White",   "suv",      5),
    ("Kia","Picanto",         2019,"Red",     "compact",  4),
    ("Toyota","Yaris",        2020,"White",   "hatchback",5),
    ("Lexus","RX",            2020,"Black",   "suv",      5),
    ("Hyundai","Elantra",     2020,"Silver",  "sedan",    5),
    ("Kia","Cerato",          2021,"White",   "sedan",    5),
]

# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------
rng = random.Random(42)

def haversine(lat1, lng1, lat2, lng2):
    R = 6371
    p = math.pi / 180
    a = (math.sin((lat2-lat1)*p/2)**2 +
         math.cos(lat1*p) * math.cos(lat2*p) * math.sin((lng2-lng1)*p/2)**2)
    return 2 * R * math.asin(max(0, math.sqrt(a)))

def rwf_fare(dist_km, ride_type="standard"):
    configs = {
        "standard": (600, 350),
        "premium":  (1200, 650),
        "boda":     (300, 150),
        "shared":   (400, 200),
    }
    base, per_km = configs.get(ride_type, (600, 350))
    fare = base + dist_km * per_km
    fare *= rng.uniform(0.85, 1.20)
    return int(round(fare / 50) * 50)

def random_dt(days_back=365):
    base = datetime.datetime(2026, 3, 6, 8, 0, 0)
    offset = datetime.timedelta(
        days=rng.randint(0, days_back),
        hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59),
    )
    return base - offset

def fake_hash():
    return "$2y$10$" + hashlib.sha256(rng.randbytes(16)).hexdigest()[:53]

def rw_phone():
    return rng.choice(["078","079","072","073"]) + str(rng.randint(1000000, 9999999))

def rw_name(gender=None):
    g = gender or rng.choice(["M", "F"])
    first = rng.choice(MALE_FIRST if g == "M" else FEMALE_FIRST)
    last  = rng.choice(FAMILY)
    return first, last, f"{first} {last}"

# -----------------------------------------------------------------
# Connect
# -----------------------------------------------------------------
conn = psycopg2.connect(DB)
conn.autocommit = False
cur = conn.cursor()
print("Connected to Supabase.")

cur.execute("SELECT COALESCE(MAX(id),0) FROM users");        max_uid = cur.fetchone()[0]
cur.execute("SELECT COALESCE(MAX(id),0) FROM drivers");      max_did = cur.fetchone()[0]
cur.execute("SELECT COALESCE(MAX(id),0) FROM vehicles");     max_vid = cur.fetchone()[0]
cur.execute("SELECT COALESCE(MAX(id),0) FROM mobile_users"); max_mid = cur.fetchone()[0]
cur.execute("SELECT COALESCE(MAX(id),0) FROM rides");        max_rid = cur.fetchone()[0]
cur.execute("SELECT COALESCE(MAX(id),0) FROM trips");        max_tid = cur.fetchone()[0]
print(f"Existing: users={max_uid} drivers={max_did} vehicles={max_vid} "
      f"mobile_users={max_mid} rides={max_rid} trips={max_tid}")

# -----------------------------------------------------------------
# Step 1: Web users (role=DRIVER) for drivers.user_id
# -----------------------------------------------------------------
print("1. Inserting web driver users...")
web_drv_rows = []
for i in range(50):
    g = "M" if i % 3 != 2 else "F"
    first, last, full = rw_name(g)
    uid = max_uid + i + 1
    email = f"wdrv{uid}@rideconnect.rw"
    phone = rw_phone()
    created = random_dt(400)
    web_drv_rows.append((
        full, email, None, fake_hash(), None, created, created,
        True, None, created, "DRIVER", None, None, phone, None, True
    ))
execute_values(cur, """
    INSERT INTO users (name,email,email_verified_at,password,remember_token,
        created_at,updated_at,is_approved,approved_by,approved_at,role,
        mobile_user_id,manager_id,phone,profile_photo,is_verified)
    VALUES %s RETURNING id
""", web_drv_rows, page_size=600)
web_drv_user_ids = [r[0] for r in cur.fetchall()]
print(f"   -> {len(web_drv_user_ids)} web driver users (IDs {web_drv_user_ids[0]}-{web_drv_user_ids[-1]})")

# -----------------------------------------------------------------
# Step 2: Mobile users — DRIVER (trips.driver_id, driver_earnings.driver_id)
# -----------------------------------------------------------------
print("2. Inserting mobile driver users...")
mob_drv_rows = []
for i in range(50):
    first, last, full = rw_name("M" if i % 3 != 2 else "F")
    email = f"mdrv{max_mid + i + 1}@rideconnect.rw"
    phone = rw_phone()
    created = random_dt(400)
    mob_drv_rows.append((first, last, "+250" + phone, email, fake_hash(), "DRIVER", None, True, created, created))
execute_values(cur, """
    INSERT INTO mobile_users (first_name,last_name,phone,email,password,role,
        profile_photo,is_verified,created_at,updated_at)
    VALUES %s RETURNING id
""", mob_drv_rows, page_size=600)
mob_drv_ids = [r[0] for r in cur.fetchall()]
print(f"   -> {len(mob_drv_ids)} mobile driver users (IDs {mob_drv_ids[0]}-{mob_drv_ids[-1]})")

# -----------------------------------------------------------------
# Step 3: Mobile users — PASSENGER
# -----------------------------------------------------------------
print("3. Inserting mobile passenger users...")
mob_pax_rows = []
for i in range(50):
    first, last, full = rw_name()
    email = f"mpax{max_mid + 50 + i + 1}@rideconnect.rw"
    phone = rw_phone()
    created = random_dt(400)
    mob_pax_rows.append((first, last, "+250" + phone, email, fake_hash(), "PASSENGER", None, True, created, created))
execute_values(cur, """
    INSERT INTO mobile_users (first_name,last_name,phone,email,password,role,
        profile_photo,is_verified,created_at,updated_at)
    VALUES %s RETURNING id
""", mob_pax_rows, page_size=600)
mob_pax_ids = [r[0] for r in cur.fetchall()]
print(f"   -> {len(mob_pax_ids)} mobile passenger users (IDs {mob_pax_ids[0]}-{mob_pax_ids[-1]})")

# All valid passenger IDs (existing + new)
ALL_PAX_IDS = list(range(1, max_mid + 1)) + mob_pax_ids

# -----------------------------------------------------------------
# Step 4: Drivers (user_id -> web driver users)
# -----------------------------------------------------------------
print("4. Inserting drivers...")
drv_rows = []
for uid in web_drv_user_ids:
    total  = rng.randint(10, 500)
    rating = round(rng.uniform(3.5, 5.0), 2)
    r_cnt  = rng.randint(5, max(5, total))
    bal    = rng.randint(5000, 200000)
    appr   = random_dt(300)
    drv_rows.append((uid, f"RW{rng.randint(100000,999999)}", f"RAC {rng.randint(100,999)} {rng.choice('ABCDEFGHJKLM')}",
                     "approved", total, rating, r_cnt, bal, appr, appr, appr, None))
execute_values(cur, """
    INSERT INTO drivers (user_id,license_number,license_plate,status,total_rides,
        rating,rating_count,balance,approved_at,created_at,updated_at,deleted_at)
    VALUES %s RETURNING id
""", drv_rows, page_size=600)
drv_ids = [r[0] for r in cur.fetchall()]
print(f"   -> {len(drv_ids)} drivers (IDs {drv_ids[0]}-{drv_ids[-1]})")

ALL_DRV_IDS = list(range(1, max_did + 1)) + drv_ids

# -----------------------------------------------------------------
# Step 5: Vehicles
# -----------------------------------------------------------------
print("5. Inserting vehicles...")
veh_rows = []
for i, did in enumerate(drv_ids):
    v  = VEHICLES[i % len(VEHICLES)]
    mk, mo, yr, co, vt, se = v
    now = random_dt(300)
    veh_rows.append((did, mk, mo, yr, co, vt, se, True, True, None, now, now, now))
execute_values(cur, """
    INSERT INTO vehicles (driver_id,make,model,year,color,vehicle_type,seats,
        air_conditioning,is_active,photo_url,verified_at,created_at,updated_at)
    VALUES %s RETURNING id
""", veh_rows, page_size=600)
veh_ids = [r[0] for r in cur.fetchall()]
print(f"   -> {len(veh_ids)} vehicles")

drv_to_veh = {drv_ids[i]: veh_ids[i] for i in range(len(drv_ids))}
drv_to_veh[1] = 1; drv_to_veh[2] = 2; drv_to_veh[3] = 3

# -----------------------------------------------------------------
# Step 6: Rides (driver_id -> drivers.id, vehicle_id -> vehicles.id)
# -----------------------------------------------------------------
print("6. Inserting rides...")
ride_rows = []
for _ in range(500):
    did = rng.choice(ALL_DRV_IDS)
    vid = drv_to_veh.get(did, rng.choice(veh_ids))
    o   = rng.choice(LOCATIONS)
    d   = rng.choice([l for l in LOCATIONS if l != o])
    dist = haversine(o[1], o[2], d[1], d[2])
    seats = rng.choice([1,1,2,2,3,4,6,14])
    fare  = rwf_fare(dist, "standard")
    dep   = random_dt(365)
    arr   = dep + datetime.timedelta(minutes=int(dist * 2 + rng.uniform(5, 20)))
    status = rng.choices(
        ["scheduled","in_progress","completed","completed","completed","cancelled"],
        weights=[2,1,5,5,5,1])[0]
    rtype  = rng.choices(["one-way","round-trip"], weights=[8,2])[0]
    desc   = f"Urugendo ruva i {o[0].split(',')[0]} rugana i {d[0].split(',')[0]}"
    ride_rows.append((
        did, vid,
        o[0], round(o[1],7), round(o[2],7),
        d[0], round(d[1],7), round(d[2],7),
        dep, arr, seats, fare, "RWF", desc, status, rtype,
        rng.choice([True,True,True,False]), False, False,
        dep if status == "cancelled" else None,
        "Impamvu zitazwi" if status == "cancelled" else None,
        dep, dep
    ))
execute_values(cur, """
    INSERT INTO rides (driver_id,vehicle_id,origin_address,origin_lat,origin_lng,
        destination_address,destination_lat,destination_lng,departure_time,
        arrival_time_estimated,available_seats,price_per_seat,currency,description,
        status,ride_type,luggage_allowed,pets_allowed,smoking_allowed,
        cancelled_at,cancellation_reason,created_at,updated_at)
    VALUES %s RETURNING id
""", ride_rows, page_size=600)
new_ride_ids = [r[0] for r in cur.fetchall()]
print(f"   -> {len(new_ride_ids)} rides")

# -----------------------------------------------------------------
# Step 7: Trips
#   passenger_id -> mobile_users.id (PASSENGER)
#   driver_id    -> mobile_users.id (DRIVER)  <-- KEY FIX
# -----------------------------------------------------------------
print("7. Inserting trips...")
trip_rows = []
for _ in range(500):
    pid  = rng.choice(ALL_PAX_IDS)
    did  = rng.choice(mob_drv_ids)          # mobile_users DRIVER
    o    = rng.choice(LOCATIONS)
    d    = rng.choice([l for l in LOCATIONS if l != o])
    dist = haversine(o[1], o[2], d[1], d[2])
    rtype = rng.choices(
        ["standard","premium","boda","shared"],
        weights=[6,3,1,1])[0]
    fare = rwf_fare(dist, rtype)
    req  = random_dt(365)
    start = req + datetime.timedelta(minutes=rng.randint(2, 15))
    end   = start + datetime.timedelta(minutes=int(dist * 2 + rng.uniform(3, 25)))
    status = rng.choices(
        ["COMPLETED","COMPLETED","COMPLETED","CANCELLED","PENDING","ACCEPTED"],
        weights=[6,6,6,1,1,1])[0]
    trip_rows.append((
        pid, did,
        o[0], d[0],
        round(o[1],7), round(o[2],7), round(d[1],7), round(d[2],7),
        fare, status,
        req, start,
        end if status == "COMPLETED" else None,
        req, req
    ))
execute_values(cur, """
    INSERT INTO trips (passenger_id,driver_id,pickup_location,dropoff_location,
        pickup_lat,pickup_lng,dropoff_lat,dropoff_lng,
        fare,status,requested_at,started_at,completed_at,created_at,updated_at)
    VALUES %s RETURNING id
""", trip_rows, page_size=600)
new_trip_ids = [r[0] for r in cur.fetchall()]
print(f"   -> {len(new_trip_ids)} trips")

# -----------------------------------------------------------------
# Step 8: Driver earnings (driver_id -> mobile_users.id)  <-- KEY FIX
# -----------------------------------------------------------------
print("8. Inserting driver_earnings...")
cur.execute("""
    SELECT id, driver_id, fare FROM trips
    WHERE status='COMPLETED' AND driver_id IS NOT NULL
    ORDER BY id DESC LIMIT 600
""")
completed_trips = cur.fetchall()
earn_rows = []
for tid, mob_did, fare in completed_trips:
    if fare is None: continue
    fare = float(fare)
    comm = round(fare * rng.uniform(0.12, 0.18), 0)
    earn_rows.append((mob_did, tid, fare, comm, fare - comm))
execute_values(cur, """
    INSERT INTO driver_earnings (driver_id, trip_id, amount, commission, net_amount)
    VALUES %s ON CONFLICT DO NOTHING
""", earn_rows)
print(f"   -> {len(earn_rows)} earnings records")

# -----------------------------------------------------------------
# Step 9: Reviews (driver_id -> drivers.id, user_id -> users.id)
# -----------------------------------------------------------------
print("9. Inserting reviews...")
cur.execute("SELECT id FROM users")
all_user_ids = [r[0] for r in cur.fetchall()]

cur.execute("""
    SELECT id, driver_id FROM rides
    WHERE status='completed'
    ORDER BY random() LIMIT 250
""")
rides_for_review = cur.fetchall()

# bookings.id is required (NOT NULL FK) — fetch existing booking IDs to cycle through
cur.execute("SELECT id FROM bookings ORDER BY id")
booking_ids = [r[0] for r in cur.fetchall()]
if not booking_ids:
    print("   -> 0 reviews (no bookings available — skipping)")
else:
    COMMENTS_RW = [
        "Serivisi nziza cyane, urakoze!","Inzira yagenze neza. Nzagaruka.",
        "Umushoferi yatwaye neza kandi yubaha amategeko.","Imodoka yari isukuye kandi nziza.",
        "Bageze mu gihe, nzagaruka gukoresha serivisi yanyu.","Umushoferi yari umunyamwete.",
        "Urugendo rwagenze neza cyane, ndashima.","Buri kintu cyagenze neza!",
        "Umushoferi yari inzobere kandi afite ubwenge bwo kuyobora.","Imodoka nziza cyane.",
        "Serivisi ikwiye gushimwa.","Ntibyakunzwe ariko byagenze neza.",
        "Byose byari neza, nshimira itsinda ryose.","Ntamakosa, urugendo rwasoje neza.",
    ]
    rev_rows = []
    for idx, (ride_id, did) in enumerate(rides_for_review):
        u_id   = rng.choice(all_user_ids)
        rating = rng.choices([3,4,4,5,5,5], weights=[1,2,2,3,3,3])[0]
        bk_val = booking_ids[idx % len(booking_ids)]  # cycle through valid booking IDs
        rev_rows.append((
            bk_val, u_id, did, ride_id, rating,
            rng.choice(COMMENTS_RW),
            rng.choice([4,5,5]),rng.choice([3,4,5,5]),
            rng.choice([4,4,5,5]),rng.choice([3,4,5,5]),
            "passenger", True,
            random_dt(300), random_dt(300)
        ))
    execute_values(cur, """
        INSERT INTO reviews (booking_id,user_id,driver_id,ride_id,rating,comment,
            safety_rating,punctuality_rating,communication_rating,
            vehicle_condition_rating,reviewer_type,is_public,created_at,updated_at)
        VALUES %s
    """, rev_rows)
    print(f"   -> {len(rev_rows)} reviews")

    cur.execute("""
        UPDATE drivers d SET rating=sub.avg_r, rating_count=sub.cnt, updated_at=NOW()
        FROM (SELECT driver_id,ROUND(AVG(rating)::numeric,2) avg_r,COUNT(*) cnt
              FROM reviews GROUP BY driver_id) sub
        WHERE d.id=sub.driver_id
    """)

# -----------------------------------------------------------------
# Step 10: Ride feedback (trip_id -> trips.id, user_id -> mobile_users.id)
# -----------------------------------------------------------------
print("10. Inserting ride_feedback...")
cur.execute("""
    SELECT id, passenger_id FROM trips
    WHERE status='COMPLETED'
    ORDER BY random() LIMIT 250
""")
fb_trips = cur.fetchall()
FB_TEXTS = [
    "Umushoferi yagenze neza cyane!","Imodoka yari isukuye.",
    "Mfite ibyishimo by'urugendo!","Yageze mu gihe nk'uko byasabwaga.",
    "Serivisi nziza kuruta izindi.","Umushoferi yari inzobere.",
    "Nzagaruka gukoresha serivisi yanyu.","Urugendo rwagenze neza.",
    "Byose byagenze neza, urakoze!","Akazi kamaze gukorwa neza.",
    "Shyigikiro ry'imodoka ryari ryiza.","Umushoferi yabuze ikibazo cyose.",
]
fb_rows = []
for tid, pid in fb_trips:
    cat = rng.choice(["comfort","safety","punctuality","cleanliness","overall"])
    fb_rows.append((
        tid, pid,
        rng.choices([3,4,4,5,5,5], weights=[1,2,2,3,3,3])[0],
        cat,
        rng.choice(FB_TEXTS),
        random_dt(180)
    ))
execute_values(cur, """
    INSERT INTO ride_feedback (trip_id,user_id,rating,category,comment,created_at)
    VALUES %s ON CONFLICT DO NOTHING
""", fb_rows)
print(f"   -> {len(fb_rows)} ride feedback records")

# -----------------------------------------------------------------
# Step 11: Driver locations (driver_id -> drivers.id)
# -----------------------------------------------------------------
print("11. Inserting driver_locations...")
loc_rows = []
for did in ALL_DRV_IDS:
    loc = rng.choice(KIGALI_LOCS)
    lat = round(loc[1] + rng.uniform(-0.015, 0.015), 7)
    lng = round(loc[2] + rng.uniform(-0.015, 0.015), 7)
    rec = datetime.datetime.utcnow() - datetime.timedelta(minutes=rng.randint(0, 30))
    loc_rows.append((did, lat, lng, round(rng.uniform(0,360),2), round(rng.uniform(0,60),1), rec, rec))
execute_values(cur, """
    INSERT INTO driver_locations (driver_id,latitude,longitude,heading,speed_kmh,recorded_at,created_at)
    VALUES %s
""", loc_rows)
print(f"   -> {len(loc_rows)} driver location records")

# -----------------------------------------------------------------
# Step 12: Driver status (driver_id -> drivers.id)
# -----------------------------------------------------------------
print("12. Inserting driver_status...")
ds_rows = []
for did in ALL_DRV_IDS:
    st = rng.choices(["online","online","offline","on_trip"], weights=[3,3,2,1])[0]
    ds_rows.append((did, st,
                    datetime.datetime.utcnow() - datetime.timedelta(minutes=rng.randint(0,60)),
                    datetime.datetime.utcnow()))
execute_values(cur, """
    INSERT INTO driver_status (driver_id,status,last_seen,updated_at)
    VALUES %s
    ON CONFLICT (driver_id) DO UPDATE
        SET status=EXCLUDED.status, last_seen=EXCLUDED.last_seen, updated_at=EXCLUDED.updated_at
""", ds_rows)
print(f"   -> {len(ds_rows)} driver status records")

# -----------------------------------------------------------------
# Step 13: Driver behavior logs (driver_id -> drivers.id)
# -----------------------------------------------------------------
print("13. Inserting driver_behavior_logs...")
beh_rows = []
for did in ALL_DRV_IDS:
    for _ in range(rng.randint(1, 4)):
        speed  = rng.uniform(25, 75)
        cancel = rng.uniform(0.0, 0.18)
        rating = rng.uniform(3.2, 5.0)
        cls    = rng.choices(
            ["safe","efficient","risky","inefficient"],
            weights=[3,3,2,1] if rating > 4.0 else [1,2,3,3])[0]
        conf   = rng.uniform(0.58, 0.96)
        dev    = rng.uniform(0, 20)
        total  = rng.randint(10, 500)
        feat   = ('{"avg_trip_duration_min":' + f'{rng.uniform(15,45):.1f}' +
                  ',"route_deviation_pct":' + f'{dev:.1f}' +
                  ',"total_rides":' + str(total) + '}')
        beh_rows.append((did, cls, round(conf,4), round(speed,1),
                         round(cancel,4), round(rating,2), feat, random_dt(180)))
execute_values(cur, """
    INSERT INTO driver_behavior_logs
        (driver_id,behavior_class,confidence,avg_speed_kmh,
         cancellation_rate,avg_rating,raw_features,analyzed_at)
    VALUES %s
""", beh_rows)
print(f"   -> {len(beh_rows)} behavior log records")

# -----------------------------------------------------------------
# Step 14: Demand zones (refresh)
# -----------------------------------------------------------------
print("14. Refreshing demand_zones...")
# Must delete FK-referencing tables first
cur.execute("DELETE FROM traffic_logs")
cur.execute("DELETE FROM predicted_demand")
cur.execute("DELETE FROM demand_zones")
dz_data = [
    ("Kigali City Center",  -1.9441, 30.0619, 0.95, 850,  0),
    ("Kacyiru",             -1.9350, 30.0893, 0.82, 640,  1),
    ("Remera",              -1.9535, 30.1117, 0.75, 590,  2),
    ("Kimironko",           -1.9276, 30.1178, 0.70, 520,  3),
    ("Nyamirambo",          -1.9741, 30.0453, 0.62, 440,  4),
    ("Kicukiro",            -2.0000, 30.0800, 0.55, 390,  5),
    ("Gisozi",              -1.9109, 30.0619, 0.50, 350,  6),
    ("Kagugu",              -1.9218, 30.0800, 0.46, 310,  7),
    ("Nyabugogo",           -1.9368, 30.0525, 0.88, 720,  8),
    ("Kanombe / Ikibuga",   -1.9686, 30.1386, 0.78, 610,  9),
    ("Musanze",             -1.4990, 29.6344, 0.40, 220, 10),
    ("Huye (Butare)",       -2.5960, 29.7400, 0.35, 180, 11),
    ("Rubavu (Gisenyi)",    -1.6836, 29.2639, 0.38, 200, 12),
    ("Muhanga (Gitarama)",  -2.0833, 29.7500, 0.30, 150, 13),
    ("Rwamagana",           -1.9490, 30.4337, 0.28, 130, 14),
]
execute_values(cur, """
    INSERT INTO demand_zones (zone_name,center_lat,center_lng,demand_score,ride_count,cluster_id,active)
    VALUES %s
""", [(r[0],r[1],r[2],r[3],r[4],r[5],True) for r in dz_data])
cur.execute("SELECT id FROM demand_zones")
zone_ids = [r[0] for r in cur.fetchall()]
print(f"   -> {len(zone_ids)} demand zones")

# -----------------------------------------------------------------
# Step 15: Traffic logs
# -----------------------------------------------------------------
print("15. Inserting traffic_logs...")
peak_hours = {7,8,9,17,18,19,20}
tl_rows = []
for zi, zid in enumerate(zone_ids):
    zlat = dz_data[zi][1]
    zlng = dz_data[zi][2]
    for day_offset in range(14):
        for hour in range(24):
            if hour in peak_hours:
                base = rng.uniform(0.72, 0.95)
            elif hour in {6,10,12,13,21,22}:
                base = rng.uniform(0.45, 0.70)
            else:
                base = rng.uniform(0.08, 0.32)
            congestion = max(1, min(5, int(round(base * 4)) + 1))
            speed = round(rng.uniform(10, 60) * (1 - base * 0.5), 1)
            ts = datetime.datetime(2026, 2, 21, hour, 0, 0) + datetime.timedelta(days=day_offset)
            lat = round(zlat + rng.uniform(-0.01, 0.01), 7)
            lng = round(zlng + rng.uniform(-0.01, 0.01), 7)
            tl_rows.append((zid, lat, lng, congestion, speed, base > 0.80, ts))
execute_values(cur, """
    INSERT INTO traffic_logs (zone_id,latitude,longitude,congestion_level,avg_speed_kmh,incident_flag,recorded_at)
    VALUES %s
""", tl_rows)
print(f"   -> {len(tl_rows)} traffic log entries")

# -----------------------------------------------------------------
# Step 16: Predicted demand
# -----------------------------------------------------------------
print("16. Refreshing predicted_demand...")
pd_rows = []
for zid in zone_ids:
    for dow in range(7):
        for hour in range(24):
            if hour in peak_hours:
                score = rng.uniform(0.68, 0.98); reqs = rng.randint(25, 90)
            elif hour in {6,10,12,13,21,22}:
                score = rng.uniform(0.40, 0.70); reqs = rng.randint(10, 40)
            else:
                score = rng.uniform(0.05, 0.38); reqs = rng.randint(1, 15)
            pd_rows.append((zid, hour, dow, round(score,4), reqs,
                            round(rng.uniform(0.70,0.95),3), "clear"))
execute_values(cur, """
    INSERT INTO predicted_demand
        (zone_id,hour,day_of_week,demand_score,predicted_requests,confidence,weather_condition)
    VALUES %s
""", pd_rows)
print(f"   -> {len(pd_rows)} predicted demand entries")

# -----------------------------------------------------------------
# Step 17: Fare audit (anomaly training examples)
# -----------------------------------------------------------------
print("17. Inserting fare_audit...")
cur.execute("""
    SELECT id, fare FROM trips
    WHERE fare > 30000 OR fare < 300
    ORDER BY random() LIMIT 50
""")
fa_trips = cur.fetchall()
fa_rows = []
for tid, fare in fa_trips:
    if fare is None: continue
    fare = float(fare)
    atype = "abnormal_surge" if fare > 30000 else "underfare"
    fa_rows.append((None, tid, fare, True, atype,
                    round(rng.uniform(0.5, 0.9), 4),
                    round(rng.uniform(2.5, 6.0), 4)))
if fa_rows:
    execute_values(cur, """
        INSERT INTO fare_audit (ride_id,trip_id,original_fare,anomaly_flag,anomaly_type,anomaly_score,z_score)
        VALUES %s ON CONFLICT DO NOTHING
    """, fa_rows)
print(f"   -> {len(fa_rows)} fare audit entries")

# -----------------------------------------------------------------
# Step 18: System metrics
# -----------------------------------------------------------------
print("18. Inserting system_metrics...")
cur.execute("DELETE FROM system_metrics")
sm_rows = []
for i in range(72):
    ts = datetime.datetime.utcnow() - datetime.timedelta(hours=i)
    sm_rows.extend([
        ("api_requests_per_minute",   rng.uniform(10, 120),      "req/min", ts),
        ("avg_prediction_latency_ms", rng.uniform(8,  80),       "ms",      ts),
        ("active_drivers",            float(rng.randint(5, 45)), "count",   ts),
        ("completed_trips_last_hour", float(rng.randint(3, 35)), "count",   ts),
    ])
execute_values(cur, """
    INSERT INTO system_metrics (metric_name,metric_value,metric_unit,recorded_at)
    VALUES %s
""", sm_rows)
print(f"   -> {len(sm_rows)} system metric entries")

# -----------------------------------------------------------------
# Commit and final row counts
# -----------------------------------------------------------------
conn.commit()
print("\nAll Rwanda seed data committed!")

tables = [
    "users","drivers","vehicles","mobile_users","rides","trips",
    "reviews","driver_earnings","driver_locations","driver_status",
    "driver_behavior_logs","demand_zones","traffic_logs","predicted_demand",
    "ride_feedback","fare_audit","system_metrics",
]
print("\nFinal row counts:")
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"  {t:30s}: {cur.fetchone()[0]:>6}")

conn.close()
