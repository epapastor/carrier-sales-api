import sqlite3
import httpx
import sys
import os
# connect to database - creates the file if it doesn't exist
def get_connection():
    # step 1 - get the absolute path of the current file (database.py)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    one_dir_up = os.path.dirname(current_dir)
    two_dir_up = os.path.dirname(one_dir_up)
    print(current_dir)
    print(one_dir_up)
    db_path = os.path.join(one_dir_up, "data", "loads.db")
    conn = sqlite3.connect(db_path)
    
    # this makes rows behave like dictionaries
    # so you can do row["origin"] instead of row[1]
    conn.row_factory = sqlite3.Row
    return conn

# this creates the table if it doesn't exist yet
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loads (
            load_id         TEXT PRIMARY KEY,
            origin          TEXT NOT NULL,
            destination     TEXT NOT NULL,
            pickup_datetime TEXT,
            delivery_datetime TEXT,
            equipment_type  TEXT,
            loadboard_rate  REAL,
            notes           TEXT,
            weight          INTEGER,
            commodity_type  TEXT,
            num_of_pieces   INTEGER,
            miles           INTEGER,
            dimensions      TEXT
        )
    """)

    
    conn.commit()
    conn.close()

def get_all_coordenates():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS COORDINATES (
            load_id          TEXT PRIMARY KEY,
            origin_lat       FLOAT,
            origin_lon       FLOAT
        )
    """)
    cursor.execute("SELECT load_id, origin FROM loads")
    rows = cursor.fetchall()  # returns a list of all rows
    for row in rows:
        origin = row["origin"]
        load_id = row["load_id"]
    
    # call nominatim for origin
        response_origin = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": origin, "format": "json"},
            headers={"User-Agent": "carrier-sales-api"}
        )
        data = response_origin.json()

        if not data:
            print(f"Could not find coordinates for {origin}")
            continue
        
        lat_origin = data[0]["lat"]
        lon_origin = data[0]["lon"]
        

        cursor.execute(
            "INSERT OR IGNORE INTO COORDINATES VALUES (?, ?, ?)",
            (load_id, lat_origin, lon_origin)
        )

    conn.commit()
    conn.close()


def insert_data():

    conn = get_connection()
    cursor = conn.cursor()

   
    # first load
    cursor.execute("""
    INSERT OR IGNORE INTO loads VALUES (
        'LD-015',
        '2200 S Millard Ave, Chicago, IL 60623',
        '2610 Langford Rd, Dallas, TX 75208',
        '2026-03-23 06:00',
        '2026-03-24 18:00',
        'Dry Van',
        2400.00,
        'No touch freight, dock to dock',
        44000,
        'Retail Goods',
        80,
        921,
        '53x102'
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO loads VALUES (
            'LD-016',
            '3760 Kilroy Airport Way, Long Beach, CA 90806',
            '2025 E McDowell Rd, Phoenix, AZ 85006',
            '2026-03-24 07:00',
            '2026-03-24 21:00',
            'Reefer',
            1800.00,
            'Temperature 34F, food grade',
            38000,
            'Fresh Produce',
            40,
            370,
            '48x102'
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO loads VALUES (
            'LD-017',
            '1 Samsara Way, Atlanta, GA 30354',
            '280 Richards St, Brooklyn, NY 11231',
            '2026-03-25 05:00',
            '2026-03-26 14:00',
            'Dry Van',
            3100.00,
            'Residential delivery, call ahead required',
            35000,
            'Furniture',
            60,
            854,
            '53x102'
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO loads VALUES (
            'LD-018',
            '10777 Northwest Fwy, Houston, TX 77092',
            '8900 NW 18th Terrace, Miami, FL 33172',
            '2026-03-25 08:00',
            '2026-03-27 08:00',
            'Flatbed',
            3800.00,
            'Tarping required, steel coils',
            47000,
            'Steel',
            8,
            1189,
            '48x102'
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO loads VALUES (
            'LD-019',
            '4800 Nome St, Denver, CO 80239',
            '18850 8th Ave S, Seattle, WA 98148',
            '2026-03-24 14:00',
            '2026-03-26 10:00',
            'Dry Van',
            2900.00,
            'Team drivers preferred, drop and hook',
            40000,
            'Auto Parts',
            200,
            1321,
            '53x102'
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO loads VALUES (
            'LD-020',
            '500 Fesslers Ln, Nashville, TN 37210',
            '1500 S Paulina St, Chicago, IL 60608',
            '2026-03-23 07:00',
            '2026-03-23 19:00',
            'Reefer',
            1600.00,
            'Temperature 28F, frozen goods',
            36000,
            'Frozen Food',
            55,
            476,
            '48x102'
        )
    """)

    cursor.execute("DELETE FROM loads WHERE load_id == 'LD-002'" )

    conn.commit()
    conn.close()





