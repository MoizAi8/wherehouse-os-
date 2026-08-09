import sqlite3
import uuid
conn = sqlite3.connect('fulfillment.db')
c = conn.cursor()
fcs = [
    ('Lahore FC', '1 KM Defense Rd, Lahore', '54000', 'Lahore', 'Punjab', 'PK', 31.5204, 74.3587, 0.75, 500, 187),
    ('Karachi FC', 'Port Qasim Authority, Karachi', '74000', 'Karachi', 'Sindh', 'PK', 24.8607, 67.0011, 0.60, 400, 120),
    ('Islamabad FC', 'Sector I-9, Islamabad', '44000', 'Islamabad', 'Islamabad', 'PK', 33.6844, 73.0479, 0.45, 300, 68),
]
for fc in fcs:
    c.execute('INSERT INTO fulfillment_centers (id, name, address, zip_code, city, state, country, latitude, longitude, is_active, capacity_pct, max_daily_orders, current_daily_orders) VALUES (?,?,?,?,?,?,?,?,?,1,?,?,?)', (str(uuid.uuid4()), *fc))
carriers_data = [
    # origin_zip must match a fulfillment_centers.zip_code so routing can join them.
    # destination_zip must match the customer order's shipping_zip to be selectable.
    # Each Pakistani FC city has carriers serving it (domestic + a couple of
    # international origin bands for cross-border orders).
    ('TCS', 'Express', '54000', '54000', 0, 50, 12.0, 1.8, 1, 3),
    ('TCS', 'Express', '74000', '74000', 0, 50, 12.0, 1.8, 1, 3),
    ('TCS', 'Express', '44000', '44000', 0, 50, 12.0, 1.8, 1, 3),
    ('Leopards', 'Standard', '54000', '54000', 0, 20, 8.0, 1.2, 2, 5),
    ('Leopards', 'Standard', '74000', '74000', 0, 20, 8.0, 1.2, 2, 5),
    ('Leopards', 'Standard', '44000', '44000', 0, 20, 8.0, 1.2, 2, 5),
    ('DHL', 'Express', '54000', '54000', 0, 30, 18.0, 2.5, 1, 4),
    ('FedEx', 'Economy', '54000', '54000', 0, 30, 14.0, 2.0, 2, 5),
    # International cross-border bands (origin is a major airport ZIP).
    ('DHL', 'Express', '10001', '10001', 0, 30, 25.0, 3.5, 2, 6),
    ('FedEx', 'Economy', '10001', '10001', 0, 30, 19.0, 2.2, 3, 7),
]
for cd in carriers_data:
    c.execute('INSERT INTO carrier_rates (id, carrier_name, service_name, origin_zip, destination_zip, weight_kg_min, weight_kg_max, base_rate, rate_per_kg, estimated_days_min, estimated_days_max, is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)', (str(uuid.uuid4()), *cd))
conn.commit()
c.execute('SELECT COUNT(*) FROM fulfillment_centers')
print(f'FCs: {c.fetchone()[0]}')
c.execute('SELECT COUNT(*) FROM carrier_rates')
print(f'Carriers: {c.fetchone()[0]}')
conn.close()
