import psycopg2
from datetime import datetime

DB_CONFIG = {
    "dbname": "rhokp",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

def perform_mock_sync():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("Creating snow_sync_status...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS snow_sync_status (
            id SERIAL PRIMARY KEY,
            last_sync_time TIMESTAMP NOT NULL
        );
    """)
    
    print("Inserting mock sync time...")
    cur.execute("TRUNCATE snow_sync_status;")
    cur.execute("INSERT INTO snow_sync_status (last_sync_time) VALUES (NOW());")
    
    print("Creating incident_work_notes...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incident_work_notes (
            id SERIAL PRIMARY KEY,
            alert_fingerprint VARCHAR(255),
            created_by VARCHAR(255),
            created_at TIMESTAMP,
            note TEXT
        );
    """)

    print("Creating agent_action_log...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_action_log (
            id SERIAL PRIMARY KEY,
            alert_fingerprint VARCHAR(255),
            status VARCHAR(50),
            created_at TIMESTAMP
        );
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("Mock sync completed successfully!")

if __name__ == "__main__":
    perform_mock_sync()
