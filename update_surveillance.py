import os
import json
import math
import datetime
import requests
import pandas as pd

# Base Directory Setup: Dynamic path resolution for local OneDrive & GitHub Actions portability
DEFAULT_DIR = r"c:\Users\hanis\OneDrive\KPAS JKN\Natural Disaster\Data Banjir"
if os.path.exists(DEFAULT_DIR):
    BASE_DIR = DEFAULT_DIR
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EXCEL_PATH = os.path.join(BASE_DIR, "Fasiliti Kesihatan Awam Sehingga 31 Disember 2025.xlsx")
HOTSPOTS_PATH = os.path.join(BASE_DIR, "Flood_Hotspots.csv")
JSON_OUTPUT = os.path.join(BASE_DIR, "surveillance_data.json")
HTML_OUTPUT = os.path.join(BASE_DIR, "index.html")

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two coordinates."""
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except (ValueError, TypeError):
        return float('inf')
    R = 6371000.0  # Earth's radius in meters
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def safe_float(val):
    """Safely convert value to float, returning None if malformed or -9999."""
    if val is None or val == "":
        return None
    try:
        f_val = float(val)
        if f_val == -9999.0:
            return None
        return f_val
    except ValueError:
        return None

def main():
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Real-Time Flood Surveillance update...")
    
    # 1. Load Local Healthcare Facilities (JKN Kedah)
    if not os.path.exists(EXCEL_PATH):
        print(f"Error: Healthcare facility Excel not found at {EXCEL_PATH}")
        return
        
    print("Loading healthcare facilities from Excel...")
    import re
    df_fac = pd.read_excel(EXCEL_PATH, sheet_name="KEDAH", skiprows=3)
    
    # Normalize column headers by stripping whitespace and replacing multiple spaces/newlines with a single space
    df_fac.columns = [re.sub(r'\s+', ' ', str(col).strip()) for col in df_fac.columns]
    
    df_fac = df_fac.dropna(subset=['Latitude', 'Longitude'])
    
    facilities = []
    for _, row in df_fac.iterrows():
        fac_name = row.get('Nama Name', row.get('Nama', 'Unknown'))
        fac_type = row.get('Jenis Fasiliti Facility Type', row.get('Jenis Fasiliti', 'Unknown'))
        fac_district = row.get('Daerah District', row.get('Daerah', 'Unknown'))
        lat = safe_float(row.get('Latitude'))
        lon = safe_float(row.get('Longitude'))
        
        if lat is not None and lon is not None:
            facilities.append({
                'name': str(fac_name).strip(),
                'type': str(fac_type).strip(),
                'district': str(fac_district).strip(),
                'latitude': lat,
                'longitude': lon
            })
    print(f"Loaded {len(facilities)} valid health facilities in Kedah.")

    # 2. Load Historic Flood Hotspots
    hotspots = []
    if os.path.exists(HOTSPOTS_PATH):
        print("Loading historical hotspots...")
        df_hot = pd.read_csv(HOTSPOTS_PATH)
        for _, row in df_hot.iterrows():
            lat = safe_float(row.get('LATITUDE'))
            lon = safe_float(row.get('LONGITUDE'))
            location = row.get('KAWASAN', 'Unknown')
            district = row.get('DAERAH', 'Unknown')
            depth = row.get('KEDALAMAN', 'Unknown')
            
            if lat is not None and lon is not None:
                hotspots.append({
                    'location': str(location).strip(),
                    'district': str(district).strip(),
                    'depth': str(depth).strip(),
                    'latitude': lat,
                    'longitude': lon
                })
        print(f"Loaded {len(hotspots)} historical hotspots.")
    else:
        print("Warning: Historical hotspots CSV not found.")

    # 3. Fetch JPS Telemetry Data (latestreadingstrendabc.json)
    trend_url = "https://publicinfobanjir.water.gov.my/wp-content/themes/enlighten/data/latestreadingstrendabc.json"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print("Fetching live telemetry data from JPS Public Info Banjir...")
    try:
        response = requests.get(trend_url, headers=headers, timeout=15)
        response.raise_for_status()
        telemetry_data = response.json()
        print(f"Fetched {len(telemetry_data)} national stations.")
    except Exception as e:
        print(f"Error fetching JPS telemetry: {e}")
        return

    # Filter for Kedah telemetry stations
    kedah_stations = []
    for item in telemetry_data:
        state = str(item.get('f', '')).strip().upper()
        if state == 'KEDAH':
            lat = safe_float(item.get('c'))
            lon = safe_float(item.get('d'))
            s_id = str(item.get('a', '')).strip()
            s_name = str(item.get('b', '')).strip()
            s_type = str(item.get('i', '')).strip()
            
            # Extract WL specific data
            wl_val = safe_float(item.get('m'))
            wl_status = str(item.get('n', 'Normal')).strip()
            wl_trend = str(item.get('s', 'Stable')).strip()
            wl_time = str(item.get('q', '')).strip()
            
            # Extract RF specific data
            rf_status = str(item.get('x', 'No Rainfall')).strip()
            rf_today = safe_float(item.get('w'))
            rf_1h = safe_float(item.get('u'))
            rf_3h = safe_float(item.get('v'))
            rf_time = str(item.get('y', '')).strip()
            
            if lat is not None and lon is not None:
                kedah_stations.append({
                    'id': s_id,
                    'name': s_name,
                    'type': s_type,
                    'latitude': lat,
                    'longitude': lon,
                    'district': str(item.get('e', '')).strip(),
                    'wl_level': wl_val,
                    'wl_status': wl_status if wl_status else 'Normal',
                    'wl_trend': wl_trend if wl_trend else 'Stable',
                    'wl_time': wl_time,
                    'rf_status': rf_status if rf_status else 'No Rainfall',
                    'rf_today': rf_today,
                    'rf_1h': rf_1h,
                    'rf_3h': rf_3h,
                    'rf_time': rf_time
                })
    print(f"Found {len(kedah_stations)} stations in Kedah.")

    # 4. Generate Amaran Semasa (Active Alerts) from Telemetry
    # This replaces the buggy and malformed currentalert.json endpoint
    print("Generating active alerts (Amaran Semasa) from Kedah telemetry...")
    kedah_current_alerts = []
    for s in kedah_stations:
        is_wl_alert = s['wl_status'] in ['Danger', 'Warning', 'Alert']
        is_rf_alert = s['rf_status'] in ['Heavy', 'Very Heavy']
        
        if is_wl_alert or is_rf_alert:
            kedah_current_alerts.append({
                'station_id': s['id'],
                'station_name': s['name'],
                'district': s['district'],
                'wl_level': s['wl_level'] if s['wl_level'] is not None else "N/A",
                'wl_status': s['wl_status'],
                'wl_time': s['wl_time'] if s['wl_time'] else s['rf_time'],
                'trend': s['wl_trend'],
                'rf_severity': s['rf_status'],
                'rf_today': s['rf_today'] if s['rf_today'] is not None else "N/A",
                'rf_24h': s['rf_today'] if s['rf_today'] is not None else "N/A", # Fallback today's rain
                'rf_3d': s['rf_3h'] if s['rf_3h'] is not None else "N/A" # Fallback 3h rain
            })
    print(f"Generated {len(kedah_current_alerts)} active alerts for Kedah.")

    # 5. Fetch Amaran Banjir (getdisse.php)
    forecast_url = "https://publicinfobanjir.water.gov.my/wp-content/themes/enlighten/query/getdisse.php"
    print("Fetching active flood forecasts (Amaran Banjir)...")
    kedah_forecasts = []
    try:
        res = requests.get(forecast_url, headers=headers, timeout=15)
        res.raise_for_status()
        forecasts_data = res.json()
        for item in forecasts_data:
            state = str(item.get('State', '')).strip().upper()
            if state == 'KEDAH':
                kedah_forecasts.append({
                    'poi': item.get('POI'),
                    'poi_type': item.get('POIType'),
                    'alert_type': item.get('AlertType'),
                    'message_time': item.get('MessageDT'),
                    'est_start': item.get('EstimatedDT'),
                    'est_end': item.get('EstimatedEndDT'),
                    'message': item.get('Message')
                })
        print(f"Found {len(kedah_forecasts)} active flood forecasts for Kedah.")
    except Exception as e:
        print(f"Error fetching Amaran Banjir: {e}")

    # Split stations into WL-capable and RF-capable for targeted spatial joins
    wl_stations = [s for s in kedah_stations if 'WL' in s['type']]
    rf_stations = [s for s in kedah_stations if 'RF' in s['type']]

    # 6. Perform Spatial Joins and Compute Facility Vulnerability
    processed_facilities = []
    high_risk_count = 0
    med_risk_count = 0
    low_risk_count = 0
    normal_count = 0
    
    type_counts = {}
    
    print("Performing spatial join (Haversine distance calculations)...")
    for fac in facilities:
        # Tally facility types
        fac_type = fac['type']
        type_counts[fac_type] = type_counts.get(fac_type, 0) + 1
        
        # A. Find nearest Water Level (WL) station
        nearest_wl = None
        min_wl_dist = float('inf')
        for wl_st in wl_stations:
            dist = haversine(fac['latitude'], fac['longitude'], wl_st['latitude'], wl_st['longitude'])
            if dist < min_wl_dist:
                min_wl_dist = dist
                nearest_wl = wl_st
                
        # B. Find nearest Rainfall (RF) station
        nearest_rf = None
        min_rf_dist = float('inf')
        for rf_st in rf_stations:
            dist = haversine(fac['latitude'], fac['longitude'], rf_st['latitude'], rf_st['longitude'])
            if dist < min_rf_dist:
                min_rf_dist = dist
                nearest_rf = rf_st
                
        # C. Find nearest Historical Hotspot
        nearest_hot = None
        min_hot_dist = float('inf')
        for hot in hotspots:
            dist = haversine(fac['latitude'], fac['longitude'], hot['latitude'], hot['longitude'])
            if dist < min_hot_dist:
                min_hot_dist = dist
                nearest_hot = hot

        # D. Vulnerability Rule Engine
        risk_level = "NORMAL"
        risk_reason = "No active warnings nearby."
        
        # Water level risk evaluation
        if nearest_wl and min_wl_dist <= 5000: # Within 5km radius
            wl_status = nearest_wl['wl_status']
            wl_trend = nearest_wl['wl_trend']
            
            if wl_status == 'Danger':
                risk_level = 'HIGH'
                risk_reason = f"Nearest river station '{nearest_wl['name']}' ({min_wl_dist/1000:.2f}km away) is in DANGER status."
            elif wl_status == 'Warning':
                if min_wl_dist <= 3000:
                    risk_level = 'HIGH'
                    risk_reason = f"Nearest river station '{nearest_wl['name']}' ({min_wl_dist/1000:.2f}km away) is in WARNING status within 3km."
                else:
                    risk_level = 'MEDIUM'
                    risk_reason = f"Nearest river station '{nearest_wl['name']}' ({min_wl_dist/1000:.2f}km away) is in WARNING status."
            elif wl_status == 'Alert':
                if min_wl_dist <= 3000 and wl_trend == 'Rising':
                    risk_level = 'MEDIUM'
                    risk_reason = f"Nearest river station '{nearest_wl['name']}' ({min_wl_dist/1000:.2f}km away) is in ALERT status and rising."
                else:
                    risk_level = 'LOW'
                    risk_reason = f"Nearest river station '{nearest_wl['name']}' ({min_wl_dist/1000:.2f}km away) is in ALERT status."
                    
        # Rainfall risk evaluation (overwrites risk if rainfall threat is higher)
        if nearest_rf and min_rf_dist <= 5000:
            rf_status = nearest_rf['rf_status']
            rf_1h = nearest_rf['rf_1h'] or 0.0
            
            # Very Heavy rain triggers higher caution
            if rf_status == 'Very Heavy' or rf_1h >= 50.0:
                if min_rf_dist <= 2000 and risk_level != 'HIGH':
                    risk_level = 'HIGH'
                    risk_reason = f"Extremely heavy local rainfall at '{nearest_rf['name']}' ({min_rf_dist/1000:.2f}km away)."
                elif risk_level == 'NORMAL':
                    risk_level = 'MEDIUM'
                    risk_reason = f"Heavy local rainfall at '{nearest_rf['name']}' ({min_rf_dist/1000:.2f}km away)."
            elif rf_status == 'Heavy' or rf_1h >= 30.0:
                if min_rf_dist <= 3000 and risk_level in ['NORMAL', 'LOW']:
                    risk_level = 'MEDIUM'
                    risk_reason = f"Heavy local rainfall at '{nearest_rf['name']}' ({min_rf_dist/1000:.2f}km away) within 3km."
                elif risk_level == 'NORMAL':
                    risk_level = 'LOW'
                    risk_reason = f"Local rainfall at '{nearest_rf['name']}' ({min_rf_dist/1000:.2f}km away)."
            elif rf_status == 'Moderate' and risk_level == 'NORMAL':
                risk_level = 'LOW'
                risk_reason = f"Moderate local rainfall at '{nearest_rf['name']}' ({min_rf_dist/1000:.2f}km away)."

        # Historical Hotspot weighting
        if min_hot_dist <= 250 and risk_level == 'NORMAL':
            risk_level = 'LOW'
            risk_reason = f"Extremely close proximity ({min_hot_dist:.0f}m) to historical flood hotspot '{nearest_hot['location']}'."

        # Keep count of risks
        if risk_level == 'HIGH': high_risk_count += 1
        elif risk_level == 'MEDIUM': med_risk_count += 1
        elif risk_level == 'LOW': low_risk_count += 1
        else: normal_count += 1

        processed_facilities.append({
            'name': fac['name'],
            'type': fac['type'],
            'district': fac['district'],
            'latitude': fac['latitude'],
            'longitude': fac['longitude'],
            'risk_level': risk_level,
            'risk_reason': risk_reason,
            'nearest_wl': {
                'id': nearest_wl['id'] if nearest_wl else None,
                'name': nearest_wl['name'] if nearest_wl else "N/A",
                'distance_m': round(min_wl_dist, 1) if nearest_wl else None,
                'status': nearest_wl['wl_status'] if nearest_wl else "N/A",
                'level': nearest_wl['wl_level'] if nearest_wl else None,
                'trend': nearest_wl['wl_trend'] if nearest_wl else "N/A",
                'time': nearest_wl['wl_time'] if nearest_wl else "N/A"
            } if nearest_wl else None,
            'nearest_rf': {
                'id': nearest_rf['id'] if nearest_rf else None,
                'name': nearest_rf['name'] if nearest_rf else "N/A",
                'distance_m': round(min_rf_dist, 1) if nearest_rf else None,
                'status': nearest_rf['rf_status'] if nearest_rf else "N/A",
                'today_mm': nearest_rf['rf_today'] if nearest_rf else None,
                '1h_mm': nearest_rf['rf_1h'] if nearest_rf else None,
                '3h_mm': nearest_rf['rf_3h'] if nearest_rf else None,
                'time': nearest_rf['rf_time'] if nearest_rf else "N/A"
            } if nearest_rf else None,
            'nearest_hotspot': {
                'location': nearest_hot['location'] if nearest_hot else "N/A",
                'distance_m': round(min_hot_dist, 1) if nearest_hot else None,
                'depth': nearest_hot['depth'] if nearest_hot else "N/A"
            } if nearest_hot else None
        })

    # 7. Build output JSON structure
    warning_stations = [s for s in kedah_stations if s['wl_status'] in ['Danger', 'Warning', 'Alert']]
    
    surveillance_data = {
        'last_updated': datetime.datetime.now().strftime('%d/%m/%Y %I:%M %p'),
        'summary': {
            'total_facilities': len(facilities),
            'high_risk_count': high_risk_count,
            'medium_risk_count': med_risk_count,
            'low_risk_count': low_risk_count,
            'normal_count': normal_count,
            'active_warnings_count': len(warning_stations),
            'facility_types': type_counts,
            'districts': sorted(list(set(f['district'] for f in facilities)))
        },
        'facilities': processed_facilities,
        'stations': kedah_stations,
        'hotspots': hotspots,
        'current_alerts': kedah_current_alerts, # Amaran Semasa data
        'forecasts': kedah_forecasts # Amaran Banjir data
    }

    # Save to JSON
    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(surveillance_data, f, indent=2, ensure_ascii=False)
    print(f"Saved spatial join data to {JSON_OUTPUT}")

    # 8. Generate interactive HTML Dashboard
    generate_html_dashboard(surveillance_data)

def generate_html_dashboard(data):
    """Generates the self-contained HTML dashboard with inline JSON data."""
    print("Generating interactive HTML dashboard...")
    
    # Inline JSON string
    json_data_str = json.dumps(data, ensure_ascii=False)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JKN Kedah - Real-Time Flood Surveillance & Facility Vulnerability</title>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <!-- Leaflet.js CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --border-color: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #3b82f6;
            
            --risk-high: #ef4444;
            --risk-med: #f97316;
            --risk-low: #eab308;
            --risk-normal: #10b981;
            
            --wl-danger: #ef4444;
            --wl-warning: #f97316;
            --wl-alert: #eab308;
            --wl-normal: #10b981;
            --wl-error: #64748b;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}

        /* App Layout */
        .sidebar {{
            width: 320px;
            background-color: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            padding: 24px;
            overflow-y: auto;
            flex-shrink: 0;
        }}

        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        /* Typography & UI Elements */
        h1 {{
            font-size: 1.35rem;
            font-weight: 700;
            margin-bottom: 8px;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .subtitle {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 24px;
            line-height: 1.4;
        }}

        .update-badge {{
            background-color: rgba(59, 130, 246, 0.15);
            border: 1px dashed var(--accent-blue);
            color: #60a5fa;
            font-size: 0.8rem;
            padding: 8px 12px;
            border-radius: 8px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .section-title {{
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        /* Filters */
        .filter-group {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 24px;
        }}

        .filter-control {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .filter-control label {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        .filter-control select {{
            background-color: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 10px;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.9rem;
            outline: none;
            cursor: pointer;
            transition: border-color 0.2s;
        }}

        .filter-control select:focus {{
            border-color: var(--accent-blue);
        }}

        /* Summary Stats */
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 12px;
            margin-bottom: 24px;
        }}

        .stat-card {{
            background-color: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--border-color);
            padding: 14px 16px;
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .stat-info {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .stat-label {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        .stat-value {{
            font-size: 1.5rem;
            font-weight: 700;
        }}

        .stat-indicator {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        .indicator-high {{ background-color: var(--risk-high); box-shadow: 0 0 10px var(--risk-high); animation: pulse 1.5s infinite; }}
        .indicator-med {{ background-color: var(--risk-med); }}
        .indicator-low {{ background-color: var(--risk-low); }}
        .indicator-normal {{ background-color: var(--risk-normal); }}
        .indicator-warning {{ background-color: var(--wl-warning); }}

        @keyframes pulse {{
            0% {{ transform: scale(0.9); opacity: 0.8; }}
            50% {{ transform: scale(1.15); opacity: 1; }}
            100% {{ transform: scale(0.9); opacity: 0.8; }}
        }}

        /* Main View Tabs */
        .tabs-header {{
            background-color: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            padding: 0 24px;
            gap: 16px;
        }}

        .tab-btn {{
            background: none;
            border: none;
            color: var(--text-secondary);
            padding: 16px 8px;
            font-family: inherit;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            position: relative;
            transition: color 0.2s;
        }}

        .tab-btn:hover {{
            color: #fff;
        }}

        .tab-btn.active {{
            color: var(--accent-blue);
        }}

        .tab-btn.active::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 3px;
            background-color: var(--accent-blue);
            border-radius: 3px 3px 0 0;
        }}

        /* Tabs Content */
        .tab-content {{
            flex: 1;
            position: relative;
            display: none;
        }}

        .tab-content.active {{
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }}

        #map-tab {{
            height: 100%;
            overflow: hidden;
        }}

        #map-container {{
            width: 100%;
            height: 100%;
            background-color: #111;
        }}

        /* Threat Table View */
        .table-view-container {{
            padding: 24px;
            overflow-y: auto;
            flex: 1;
        }}

        .data-table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
            margin-bottom: 24px;
        }}

        .data-table th {{
            background-color: rgba(30, 41, 59, 0.8);
            border-bottom: 2px solid var(--border-color);
            color: var(--text-primary);
            padding: 14px 16px;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        .data-table td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }}

        .data-table tr:hover td {{
            background-color: rgba(255, 255, 255, 0.02);
            color: #fff;
        }}

        /* Badges */
        .badge {{
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            display: inline-block;
        }}

        .badge-high {{ background-color: rgba(239, 68, 68, 0.15); color: var(--risk-high); border: 1px solid rgba(239, 68, 68, 0.3); }}
        .badge-med {{ background-color: rgba(249, 115, 22, 0.15); color: var(--risk-med); border: 1px solid rgba(249, 115, 22, 0.3); }}
        .badge-low {{ background-color: rgba(234, 179, 8, 0.15); color: var(--risk-low); border: 1px solid rgba(234, 179, 8, 0.3); }}
        .badge-normal {{ background-color: rgba(16, 185, 129, 0.15); color: var(--risk-normal); border: 1px solid rgba(16, 185, 129, 0.3); }}

        /* Popup Custom Styling */
        .leaflet-popup-content-wrapper {{
            background-color: var(--bg-secondary) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-color);
            border-radius: 12px !important;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5) !important;
        }}

        .leaflet-popup-tip {{
            background-color: var(--bg-secondary) !important;
            border: 1px solid var(--border-color);
        }}

        .popup-title {{
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 8px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 6px;
            color: #fff;
        }}

        .popup-section {{
            margin-top: 10px;
            font-size: 0.8rem;
        }}

        .popup-section-title {{
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 4px;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}

        .popup-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 6px;
            background-color: rgba(0, 0, 0, 0.2);
            padding: 8px;
            border-radius: 6px;
        }}

        .popup-grid div {{
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}

        .popup-field {{
            display: flex;
            flex-direction: column;
        }}

        .popup-label {{
            font-size: 0.7rem;
            color: var(--text-secondary);
        }}

        .popup-val {{
            font-weight: 600;
            color: #fff;
        }}

        .search-container {{
            margin-bottom: 16px;
            position: relative;
        }}

        .search-container input {{
            width: 100%;
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 12px 10px 36px;
            color: var(--text-primary);
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s;
        }}

        .search-container input:focus {{
            border-color: var(--accent-blue);
        }}

        .search-container i {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
        }}

        /* Legend Control inside Map */
        .map-legend {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            padding: 12px;
            border-radius: 8px;
            color: var(--text-primary);
            line-height: 1.5;
            font-size: 0.8rem;
        }}

        .map-legend h4 {{
            margin-bottom: 6px;
            font-size: 0.85rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 4px;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }}

        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }}

        .section-header {{
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 16px;
            color: #fff;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        /* SOP & Checklist Styling */
        .sop-container {{
            padding: 24px;
            overflow-y: auto;
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}

        .sop-header-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: var(--bg-secondary);
            padding: 16px 20px;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            flex-wrap: wrap;
            gap: 16px;
        }}

        .sop-selectors {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .progress-container {{
            display: flex;
            align-items: center;
            gap: 12px;
            width: 280px;
        }}

        .progress-bar-bg {{
            flex: 1;
            background-color: var(--bg-primary);
            height: 10px;
            border-radius: 5px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}

        .progress-bar-fill {{
            background-color: var(--risk-normal);
            height: 100%;
            width: 0%;
            transition: width 0.3s ease;
        }}

        .progress-text {{
            font-size: 0.85rem;
            font-weight: 600;
            min-width: 45px;
            text-align: right;
        }}

        .checklist-section {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
        }}

        .checklist-title {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 16px;
            color: #fff;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .checklist-item {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            transition: background-color 0.2s;
            border-radius: 6px;
        }}

        .checklist-item:hover {{
            background-color: rgba(255, 255, 255, 0.02);
        }}

        .checklist-item:last-child {{
            border-bottom: none;
        }}

        .checklist-checkbox {{
            margin-top: 3px;
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: var(--accent-blue);
        }}

        .checklist-content {{
            flex: 1;
        }}

        .checklist-task {{
            font-weight: 600;
            color: #fff;
            margin-bottom: 4px;
            font-size: 0.95rem;
        }}

        .checklist-desc {{
            font-size: 0.82rem;
            color: var(--text-secondary);
            line-height: 1.4;
        }}

        .checklist-time {{
            font-size: 0.75rem;
            background-color: rgba(255, 255, 255, 0.05);
            padding: 2px 6px;
            border-radius: 4px;
            color: #60a5fa;
            display: inline-block;
            margin-top: 6px;
            font-weight: 600;
        }}
    </style>
</head>
<body>

    <!-- Sidebar Control Panel -->
    <div class="sidebar">
        <h1><i class="fa-solid fa-house-flood-water" style="color: var(--risk-high);"></i> JKN Kedah</h1>
        <div class="subtitle">Real-Time Flood Surveillance & Vulnerability Dashboard</div>

        <div class="update-badge">
            <i class="fa-solid fa-rotate"></i>
            <div>Live JPS Telemetry:<br><span id="update-time" style="font-weight: 600;">Loading...</span></div>
        </div>

        <div class="section-title">Risk Summaries</div>
        <div class="stats-grid">
            <div class="stat-card" style="border-left: 4px solid var(--risk-high);">
                <div class="stat-info">
                    <span class="stat-label">High Risk Clinics</span>
                    <span class="stat-value" id="count-high">0</span>
                </div>
                <div class="stat-indicator" id="ind-high"></div>
            </div>
            <div class="stat-card" style="border-left: 4px solid var(--risk-med);">
                <div class="stat-info">
                    <span class="stat-label">Medium Risk Clinics</span>
                    <span class="stat-value" id="count-med">0</span>
                </div>
                <div class="stat-indicator indicator-med"></div>
            </div>
            <div class="stat-card" style="border-left: 4px solid var(--risk-low);">
                <div class="stat-info">
                    <span class="stat-label">Low Risk Clinics</span>
                    <span class="stat-value" id="count-low">0</span>
                </div>
                <div class="stat-indicator indicator-low"></div>
            </div>
            <div class="stat-card" style="border-left: 4px solid var(--wl-warning);">
                <div class="stat-info">
                    <span class="stat-label">Active JPS Warnings</span>
                    <span class="stat-value" id="count-jps">0</span>
                </div>
                <div class="stat-indicator indicator-warning"></div>
            </div>
        </div>

        <div class="section-title">Vulnerability Filters</div>
        <div class="filter-group">
            <div class="filter-control">
                <label for="filter-district">Daerah / District</label>
                <select id="filter-district">
                    <option value="ALL">All Districts</option>
                </select>
            </div>
            <div class="filter-control">
                <label for="filter-risk">Risk Level</label>
                <select id="filter-risk">
                    <option value="ALL">All Risk Levels</option>
                    <option value="HIGH">High Risk Only</option>
                    <option value="MEDIUM">Medium Risk Only</option>
                    <option value="LOW">Low Risk Only</option>
                    <option value="NORMAL">Normal Only</option>
                </select>
            </div>
            <div class="filter-control">
                <label for="filter-type">Facility Type</label>
                <select id="filter-type">
                    <option value="ALL">All Types</option>
                </select>
            </div>
            <div style="display: flex; align-items: center; gap: 8px; margin-top: 4px;">
                <input type="checkbox" id="toggle-rivers" checked style="width: 16px; height: 16px; accent-color: var(--accent-blue); cursor: pointer;">
                <label for="toggle-rivers" style="font-size: 0.85rem; color: var(--text-secondary); cursor: pointer; user-select: none;">Show River Tributaries</label>
            </div>
        </div>
    </div>

    <!-- Main Workspace -->
    <div class="main-content">
        <!-- View Tabs -->
        <div class="tabs-header">
            <button class="tab-btn active" onclick="switchTab('map-tab', this)"><i class="fa-solid fa-map-location-dot"></i> Interactive Map</button>
            <button class="tab-btn" onclick="switchTab('table-tab', this)"><i class="fa-solid fa-table-list"></i> Vulnerable Facilities</button>
            <button class="tab-btn" onclick="switchTab('warnings-tab', this)"><i class="fa-solid fa-triangle-exclamation"></i> Alerts & Warnings</button>
            <button class="tab-btn" onclick="switchTab('telemetry-tab', this)"><i class="fa-solid fa-gauge-high"></i> JPS Telemetry Stations</button>
            <button class="tab-btn" onclick="switchTab('sop-tab', this)"><i class="fa-solid fa-clipboard-check"></i> Action SOP & Checklists</button>
            <button class="tab-btn" onclick="switchTab('methodology-tab', this)"><i class="fa-solid fa-calculator"></i> Methodology & Verification</button>
        </div>

        <!-- Tab Content: Map -->
        <div id="map-tab" class="tab-content active">
            <div id="map-container"></div>
        </div>

        <!-- Tab Content: Threat Table -->
        <div id="table-tab" class="tab-content">
            <div class="table-view-container">
                <div class="section-header"><i class="fa-solid fa-clinic-medical"></i> Facility Flood Vulnerability Join</div>
                <div class="search-container">
                    <i class="fa-solid fa-magnifying-glass"></i>
                    <input type="text" id="table-search" placeholder="Search facilities by name, district, or warning..." onkeyup="filterTable()">
                </div>
                <table class="data-table" id="clinic-table">
                    <thead>
                        <tr>
                            <th>Facility Name</th>
                            <th>District</th>
                            <th>Facility Type</th>
                            <th>Risk Level</th>
                            <th>Nearest Active River Station</th>
                            <th>Status (Level)</th>
                            <th>Distance</th>
                            <th>Nearest Historical Hotspot</th>
                        </tr>
                    </thead>
                    <tbody id="table-body">
                        <!-- Populated by JS -->
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tab Content: Alerts & Forecasts -->
        <div id="warnings-tab" class="tab-content">
            <div class="table-view-container">
                
                <!-- 1. Amaran Banjir (Forecasts) -->
                <div class="section-header" style="border-bottom-color: var(--risk-high);">
                    <i class="fa-solid fa-clock-rotate-left" style="color: var(--risk-high);"></i> Amaran Banjir: JPS Predictive Forecasts
                </div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Target Area / POI</th>
                            <th>POI Type</th>
                            <th>Warning Level</th>
                            <th>Message / Forecast Info</th>
                            <th>Expected Start</th>
                            <th>Expected End</th>
                        </tr>
                    </thead>
                    <tbody id="forecasts-table-body">
                        <!-- Populated by JS -->
                    </tbody>
                </table>

                <!-- 2. Amaran Semasa (Active Alerts) -->
                <div class="section-header" style="border-bottom-color: var(--risk-med); margin-top: 40px;">
                    <i class="fa-solid fa-triangle-exclamation" style="color: var(--risk-med);"></i> Amaran Semasa: Live Telemetry Alerts
                </div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Station Name</th>
                            <th>District</th>
                            <th>Water Level Status</th>
                            <th>WL Level (m)</th>
                            <th>Trend</th>
                            <th>Rain Status</th>
                            <th>Daily Rain (mm)</th>
                            <th>Last Updated</th>
                        </tr>
                    </thead>
                    <tbody id="alerts-table-body">
                        <!-- Populated by JS -->
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tab Content: JPS Telemetry Stations -->
        <div id="telemetry-tab" class="tab-content">
            <div class="table-view-container">
                <div class="section-header"><i class="fa-solid fa-tower-broadcast"></i> Complete Telemetry Stations (Kedah)</div>
                <div class="search-container">
                    <i class="fa-solid fa-magnifying-glass"></i>
                    <input type="text" id="tel-search" placeholder="Search JPS telemetry stations..." onkeyup="filterTelemetryTable()">
                </div>
                <table class="data-table" id="telemetry-table">
                    <thead>
                        <tr>
                            <th>Station Name</th>
                            <th>ID</th>
                            <th>District</th>
                            <th>Type</th>
                            <th>Water Level Status</th>
                            <th>Current Level (m)</th>
                            <th>WL Trend</th>
                            <th>Rain Status</th>
                            <th>Today's Rain</th>
                            <th>1h Rain</th>
                            <th>Last Updated</th>
                        </tr>
                    </thead>
                    <tbody id="telemetry-table-body">
                        <!-- Populated by JS -->
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tab Content: Disaster SOP & Checklists -->
        <div id="sop-tab" class="tab-content">
            <div class="sop-container">
                <div class="section-header"><i class="fa-solid fa-clipboard-check"></i> Pelan Tindakan & Senarai Semak Pengurusan Banjir (KKM Edisi 2 2019)</div>
                
                <div class="sop-header-bar">
                    <div class="sop-selectors">
                        <div class="filter-control" style="margin-bottom: 0;">
                            <label for="sop-level-select" style="font-weight: 600;">Tahap Tanggungjawab / Responsibility Level</label>
                            <select id="sop-level-select" onchange="renderChecklist()" style="padding: 6px 12px; font-size: 0.85rem;">
                                <option value="JKN">Jabatan Kesihatan Negeri (JKN)</option>
                                <option value="PKD">Pejabat Kesihatan Daerah (PKD)</option>
                                <option value="KK">Klinik Kesihatan / Desa (Primary Care)</option>
                            </select>
                        </div>
                        <div class="filter-control" style="margin-bottom: 0;">
                            <label for="sop-phase-select" style="font-weight: 600;">Fasa Bencana / Disaster Phase</label>
                            <select id="sop-phase-select" onchange="renderChecklist()" style="padding: 6px 12px; font-size: 0.85rem;">
                                <option value="SEBELUM">Sebelum Banjir (Kesiapsiagaan & Persediaan)</option>
                                <option value="SEMASA">Semasa Banjir (Respon & Operasi Aktif)</option>
                                <option value="SELEPAS">Selepas Banjir (Pemulihan & Kawalan Penyakit)</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="progress-container">
                        <span style="font-size: 0.8rem; color: var(--text-secondary);">Progress:</span>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" id="sop-progress-bar"></div>
                        </div>
                        <span class="progress-text" id="sop-progress-text">0%</span>
                    </div>
                </div>

                <div class="checklist-section">
                    <div class="checklist-title" id="checklist-title-text">
                        <!-- Populated by JS -->
                    </div>
                    <div id="checklist-items-container">
                        <!-- Populated by JS -->
                    </div>
                </div>
            </div>
        </div>

        <!-- Tab Content: Methodology & Verification -->
        <div id="methodology-tab" class="tab-content">
            <div class="table-view-container">
                <div class="section-header"><i class="fa-solid fa-calculator"></i> Risk Assessment Methodology & Spatial Join Logic</div>
                
                <div class="sop-container" style="padding: 0; gap: 24px;">
                    <div class="checklist-section" style="background-color: var(--bg-secondary); border: 1px solid var(--border-color); padding: 24px; line-height: 1.6;">
                        <h3 style="color: #fff; margin-bottom: 12px; font-size: 1.15rem;"><i class="fa-solid fa-map-marked-alt" style="color: var(--accent-blue);"></i> 1. Spatial Join & Distance Calculations (Haversine Formula)</h3>
                        <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 0.92rem;">
                            To assess facility vulnerability in real-time, the system executes a geographic spatial join between the coordinates of <b>309 Kedah Healthcare Facilities</b> (from the official KKM Registry) and live coordinates of <b>244 active JPS Telemetry Stations</b>. Distances are calculated using the <b>Haversine formula</b> to find the shortest path across the Earth's surface:
                        </p>
                        <div style="background-color: rgba(0,0,0,0.3); border: 1px solid var(--border-color); padding: 16px; border-radius: 8px; text-align: center; margin-bottom: 24px; font-size: 1.1rem; color: #60a5fa; font-family: monospace;">
                            d = 2R &middot; arcsin(&radic;(sin&sup2;(&Delta;lat/2) + cos(lat<sub>1</sub>) &middot; cos(lat<sub>2</sub>) &middot; sin&sup2;(&Delta;lon/2)))
                        </div>
                        <p style="color: var(--text-secondary); margin-bottom: 24px; font-size: 0.92rem;">
                            Where <i>R</i> is the Earth's radius (6,371 km), <i>&Delta;lat</i> and <i>&Delta;lon</i> represent the coordinate differences in radians, and <i>d</i> is the output distance.
                        </p>

                        <h3 style="color: #fff; margin-bottom: 12px; font-size: 1.15rem;"><i class="fa-solid fa-cogs" style="color: var(--risk-med);"></i> 2. Risk Level Decision Matrix</h3>
                        <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 0.92rem;">
                            The real-time threat level for each facility is computed dynamically by mapping spatial buffers against telemetry thresholds:
                        </p>
                        <table class="data-table" style="margin-bottom: 24px; font-size: 0.85rem;">
                            <thead>
                                <tr>
                                    <th>Risk Level</th>
                                    <th>JPS River Level (WL) Conditions</th>
                                    <th>JPS Rainfall (RF) Conditions</th>
                                    <th>Historical Hotspot Conditions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td><span class="badge badge-high">HIGH</span></td>
                                    <td>Nearest WL station is in <b>Danger</b> status within 5km, OR in <b>Warning</b> status within 3km.</td>
                                    <td>Local rainfall is <b>Very Heavy</b> or &ge; 50 mm/h within a 2km radius.</td>
                                    <td>N/A (Historical markers alone do not trigger HIGH risk without live telemetry alerts).</td>
                                </tr>
                                <tr>
                                    <td><span class="badge badge-med">MEDIUM</span></td>
                                    <td>Nearest WL station is in <b>Warning</b> status &gt; 3km (up to 5km), OR in <b>Alert</b> status within 3km with a <b>Rising</b> trend.</td>
                                    <td>Local rainfall is <b>Very Heavy</b>/&ge; 50 mm/h between 2km and 5km, OR <b>Heavy</b>/&ge; 30 mm/h within 3km.</td>
                                    <td>N/A (Saves resources for verified active threats).</td>
                                </tr>
                                <tr>
                                    <td><span class="badge badge-low">LOW</span></td>
                                    <td>Nearest WL station is in <b>Alert</b> status (outside 3km or Stable/Falling trend) within 5km.</td>
                                    <td>Local rainfall is <b>Heavy</b> &gt; 3km, OR <b>Moderate</b> within 5km.</td>
                                    <td>Facility coordinates are within <b>250 meters</b> of a historical flood hotspot.</td>
                                </tr>
                                <tr>
                                    <td><span class="badge badge-normal">NORMAL</span></td>
                                    <td>Nearest WL station has no active alerts or is &gt; 5km away.</td>
                                    <td>No active rainfall warnings or heavy rain &gt; 5km away.</td>
                                    <td>No historical hotspots within 250m.</td>
                                </tr>
                            </tbody>
                        </table>

                        <h3 style="color: #fff; margin-bottom: 12px; font-size: 1.15rem;"><i class="fa-solid fa-shield-halved" style="color: var(--risk-normal);"></i> 3. Verification & Credibility Mechanisms</h3>
                        <ul style="color: var(--text-secondary); margin-left: 20px; margin-bottom: 24px; font-size: 0.92rem; display: flex; flex-direction: column; gap: 8px;">
                            <li><b>Real-Time API Source:</b> Data is dynamically parsed from the official JPS Public Info Banjir API (<code>latestreadingstrendabc.json</code>), ensuring that values match the official government portal exactly.</li>
                            <li><b>Direct Audit Trail:</b> Every telemetry station listed in the <i>JPS Telemetry Stations</i> tab and map popups includes a direct verification link to open the official JPS website and audit the reading.</li>
                            <li><b>Traceable Excel Data:</b> Facility locations are joined using the official KKM registry document <i>Fasiliti Kesihatan Awam Sehingga 31 Disember 2025.xlsx</i>.</li>
                            <li><b>Timestamped Operations:</b> The dashboard features a prominent live update timestamp at the top of the sidebar showing the exact execution date and time of the spatial join.</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Leaflet.js -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <script src="kedah_rivers.js"></script>

    <script>
        // Inline Database injected by Scraper
        const rawData = {json_data_str};

        let map;
        let facilityMarkersGroup;
        let stationMarkersGroup;
        let hotspotMarkersGroup;
        let riversGroup;
        let showRivers = true;
        
        document.addEventListener('DOMContentLoaded', () => {{
            // Populate Update Time
            document.getElementById('update-time').innerText = rawData.last_updated;

            // Populate Filter Dropdowns
            const districtSelect = document.getElementById('filter-district');
            rawData.summary.districts.forEach(d => {{
                const opt = document.createElement('option');
                opt.value = d;
                opt.innerText = d;
                districtSelect.appendChild(opt);
            }});

            const typeSelect = document.getElementById('filter-type');
            Object.keys(rawData.summary.facility_types).forEach(t => {{
                const opt = document.createElement('option');
                opt.value = t;
                opt.innerText = t;
                typeSelect.appendChild(opt);
            }});

            // Bind filter change events
            districtSelect.addEventListener('change', updateAllViews);
            document.getElementById('filter-risk').addEventListener('change', updateAllViews);
            typeSelect.addEventListener('change', updateAllViews);

            document.getElementById('toggle-rivers').addEventListener('change', (e) => {{
                showRivers = e.target.checked;
                updateAllViews();
            }});

            // Populate Summary Cards
            updateSummaryCards(rawData.facilities);

            // Initialize Map
            initMap();
            
            // Render Initial Data
            updateAllViews();
            renderChecklist();
        }});

        function updateSummaryCards(facList) {{
            let high = 0, med = 0, low = 0;
            facList.forEach(f => {{
                if (f.risk_level === 'HIGH') high++;
                else if (f.risk_level === 'MEDIUM') med++;
                else if (f.risk_level === 'LOW') low++;
            }});
            document.getElementById('count-high').innerText = high;
            document.getElementById('count-med').innerText = med;
            document.getElementById('count-low').innerText = low;
            document.getElementById('count-jps').innerText = rawData.summary.active_warnings_count;

            const highIndicator = document.getElementById('ind-high');
            if (high > 0) {{
                highIndicator.className = 'stat-indicator indicator-high';
            }} else {{
                highIndicator.className = 'stat-indicator';
            }}
        }}

        function initMap() {{
            // Centered on Kedah
            map = L.map('map-container').setView([6.12, 100.5], 10);

            // Dark Matter Basemap
            L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 20
            }}).addTo(map);

            facilityMarkersGroup = L.layerGroup().addTo(map);
            stationMarkersGroup = L.layerGroup().addTo(map);
            hotspotMarkersGroup = L.layerGroup().addTo(map);
            riversGroup = L.layerGroup().addTo(map);

            // River Layer Group Styling
            const riverLayer = L.geoJSON(kedahRivers, {{
                style: function(feature) {{
                    const waterway = feature.properties.waterway;
                    if (waterway === 'river') {{
                        return {{
                            color: '#0284c7', // Nice sky blue for rivers
                            weight: 2.2,
                            opacity: 0.85
                        }};
                    }} else {{
                        return {{
                            color: '#38bdf8', // Lighter blue for streams/tributaries
                            weight: 1.0,
                            opacity: 0.55
                        }};
                    }}
                }},
                onEachFeature: function(feature, layer) {{
                    if (feature.properties && feature.properties.name) {{
                        layer.bindTooltip(feature.properties.name, {{ sticky: true }});
                    }}
                }}
            }});
            riversGroup.addLayer(riverLayer);

            // Add Custom Map Legend
            const legend = L.control({{ position: 'bottomright' }});
            legend.onAdd = function() {{
                const div = L.DomUtil.create('div', 'map-legend');
                div.innerHTML = `
                    <h4>Risk Legend</h4>
                    <div class="legend-item"><span class="legend-color" style="background: var(--risk-high)"></span> High Risk Facility</div>
                    <div class="legend-item"><span class="legend-color" style="background: var(--risk-med)"></span> Med Risk Facility</div>
                    <div class="legend-item"><span class="legend-color" style="background: var(--risk-low)"></span> Low Risk Facility</div>
                    <div class="legend-item"><span class="legend-color" style="background: var(--risk-normal)"></span> Normal Facility</div>
                    <div class="legend-item"><span class="legend-color" style="background: #3b82f6; border-radius: 2px; width: 10px; height: 10px;"></span> Active JPS Station</div>
                    <div class="legend-item"><span class="legend-color" style="background: #a855f7; border-radius: 0; width: 12px; height: 8px;"></span> Historical Hotspot</div>
                    <div class="legend-item" style="display: flex; align-items: center; margin-top: 4px;"><span class="legend-color" style="background: #0284c7; border-radius: 0; width: 14px; height: 3px; margin-right: 8px;"></span> River Tributary</div>
                `;
                return div;
            }};
            legend.addTo(map);
        }}

        function switchTab(tabId, btn) {{
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');

            if (tabId === 'map-tab' && map) {{
                setTimeout(() => {{
                    map.invalidateSize();
                }}, 100);
            }}
        }}

        function getFilteredData() {{
            const district = document.getElementById('filter-district').value;
            const risk = document.getElementById('filter-risk').value;
            const type = document.getElementById('filter-type').value;

            return rawData.facilities.filter(f => {{
                const matchDistrict = (district === 'ALL' || f.district === district);
                const matchRisk = (risk === 'ALL' || f.risk_level === risk);
                const matchType = (type === 'ALL' || f.type === type);
                return matchDistrict && matchRisk && matchType;
            }});
        }}

        function updateAllViews() {{
            const filteredFacilities = getFilteredData();
            
            updateSummaryCards(filteredFacilities);
            renderMapMarkers(filteredFacilities);
            renderThreatTable(filteredFacilities);
            renderTelemetryTable();
            renderWarningsTab();
        }}

        function renderMapMarkers(facilitiesList) {{
            facilityMarkersGroup.clearLayers();
            stationMarkersGroup.clearLayers();
            hotspotMarkersGroup.clearLayers();

            // 1. Render Facilities
            facilitiesList.forEach(f => {{
                let markerColor = 'var(--risk-normal)';
                if (f.risk_level === 'HIGH') markerColor = 'var(--risk-high)';
                else if (f.risk_level === 'MEDIUM') markerColor = 'var(--risk-med)';
                else if (f.risk_level === 'LOW') markerColor = 'var(--risk-low)';

                const circleMarker = L.circleMarker([f.latitude, f.longitude], {{
                    radius: f.risk_level === 'HIGH' ? 10 : 8,
                    fillColor: markerColor,
                    color: '#ffffff',
                    weight: 1.5,
                    opacity: 0.9,
                    fillOpacity: 0.8
                }});

                const popupContent = `
                    <div class="popup-title">${{f.name}}</div>
                    <div><b>Type:</b> ${{f.type}}</div>
                    <div><b>District:</b> ${{f.district}}</div>
                    <div style="margin-top: 6px;"><b>Computed Risk:</b> 
                        <span class="badge badge-${{f.risk_level.toLowerCase()}}">${{f.risk_level}}</span>
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary); font-style: italic; margin-top: 4px;">
                        ${{f.risk_reason}}
                    </div>
                    
                    <div class="popup-section">
                        <div class="popup-section-title"><i class="fa-solid fa-water"></i> Nearest Telemetry River</div>
                        <div class="popup-grid">
                            <div class="popup-field"><span class="popup-label">Station</span><span class="popup-val">${{f.nearest_wl ? f.nearest_wl.name : 'N/A'}}</span></div>
                            <div class="popup-field"><span class="popup-label">Distance</span><span class="popup-val">${{f.nearest_wl ? (f.nearest_wl.distance_m/1000).toFixed(2) + ' km' : 'N/A'}}</span></div>
                            <div class="popup-field"><span class="popup-label">Status</span><span class="popup-val">${{f.nearest_wl ? f.nearest_wl.status : 'N/A'}}</span></div>
                            <div class="popup-field"><span class="popup-label">Trend</span><span class="popup-val">${{f.nearest_wl ? f.nearest_wl.trend : 'N/A'}}</span></div>
                        </div>
                    </div>

                    <div class="popup-section">
                        <div class="popup-section-title"><i class="fa-solid fa-cloud-showers-heavy"></i> Nearest Rainfall Station</div>
                        <div class="popup-grid">
                            <div class="popup-field"><span class="popup-label">Station</span><span class="popup-val">${{f.nearest_rf ? f.nearest_rf.name : 'N/A'}}</span></div>
                            <div class="popup-field"><span class="popup-label">Distance</span><span class="popup-val">${{f.nearest_rf ? (f.nearest_rf.distance_m/1000).toFixed(2) + ' km' : 'N/A'}}</span></div>
                            <div class="popup-field"><span class="popup-label">Today's Rain</span><span class="popup-val">${{f.nearest_rf && f.nearest_rf.today_mm !== null ? f.nearest_rf.today_mm + ' mm' : 'N/A'}}</span></div>
                            <div class="popup-field"><span class="popup-label">1h Rate</span><span class="popup-val">${{f.nearest_rf && f.nearest_rf['1h_mm'] !== null ? f.nearest_rf['1h_mm'] + ' mm/h' : 'N/A'}}</span></div>
                        </div>
                    </div>

                    <div class="popup-section">
                        <div class="popup-section-title"><i class="fa-solid fa-triangle-exclamation"></i> Nearest Historic Hotspot</div>
                        <div class="popup-grid">
                            <div class="popup-field"><span class="popup-label">Location</span><span class="popup-val">${{f.nearest_hotspot ? f.nearest_hotspot.location : 'N/A'}}</span></div>
                            <div class="popup-field"><span class="popup-label">Distance</span><span class="popup-val">${{f.nearest_hotspot ? f.nearest_hotspot.distance_m.toFixed(0) + ' m' : 'N/A'}}</span></div>
                        </div>
                    </div>
                `;

                circleMarker.bindPopup(popupContent, {{ minWidth: 260 }});
                facilityMarkersGroup.addLayer(circleMarker);
            }});

            // 2. Render JPS Telemetry Stations (Only WL or Alert/Warning/Danger stations)
            rawData.stations.forEach(s => {{
                let isAlert = ['Danger', 'Warning', 'Alert'].includes(s.wl_status) || ['Heavy', 'Very Heavy'].includes(s.rf_status);
                
                const squareMarker = L.rectangle([
                    [s.latitude - 0.002, s.longitude - 0.002],
                    [s.latitude + 0.002, s.longitude + 0.002]
                ], {{
                    color: isAlert ? '#f59e0b' : '#3b82f6',
                    fillColor: '#1e293b',
                    weight: 1.5,
                    fillOpacity: 0.6
                }});

                const verifyUrl = s.type.includes('WL') 
                    ? "https://publicinfobanjir.water.gov.my/aras-air/data-paras-air/?state=KDH"
                    : "https://publicinfobanjir.water.gov.my/hujan/data-hujan/?state=KDH";

                const popupContent = `
                    <div class="popup-title"><i class="fa-solid fa-tower-broadcast"></i> JPS Station: ${{s.name}}</div>
                    <div><b>Station ID:</b> ${{s.id}}</div>
                    <div><b>Type:</b> ${{s.type}}</div>
                    <div><b>District:</b> ${{s.district}}</div>
                    <div class="popup-section">
                        <div class="popup-section-title">Measurements</div>
                        <div class="popup-grid">
                            <div class="popup-field"><span class="popup-label">WL Level</span><span class="popup-val">${{s.wl_level !== null ? s.wl_level.toFixed(2) + ' m' : 'N/A'}}</span></div>
                            <div class="popup-field"><span class="popup-label">WL Status</span><span class="popup-val">${{s.wl_status}}</span></div>
                            <div class="popup-field"><span class="popup-label">WL Trend</span><span class="popup-val">${{s.wl_trend}}</span></div>
                            <div class="popup-field"><span class="popup-label">Today's Rain</span><span class="popup-val">${{s.rf_today !== null ? s.rf_today + ' mm' : 'N/A'}}</span></div>
                            <div class="popup-field"><span class="popup-label">Rain Rate</span><span class="popup-val">${{s.rf_status}}</span></div>
                            <div class="popup-field"><span class="popup-label">Last WL Update</span><span class="popup-val" style="font-size:0.65rem;">${{s.wl_time}}</span></div>
                        </div>
                    </div>
                    <div style="margin-top: 10px; text-align: right;">
                        <a href="${{verifyUrl}}" target="_blank" style="color: #60a5fa; text-decoration: underline; font-size: 0.75rem; font-weight: 600;"><i class="fa-solid fa-arrow-up-right-from-square"></i> Verify on JPS Portal</a>
                    </div>
                `;

                squareMarker.bindPopup(popupContent, {{ minWidth: 240 }});
                stationMarkersGroup.addLayer(squareMarker);
            }});

            // 3. Render Historical Hotspots (in Purple diamond-like rectangles)
            rawData.hotspots.forEach(h => {{
                const hotspotMarker = L.polygon([
                    [h.latitude, h.longitude - 0.001],
                    [h.latitude - 0.001, h.longitude],
                    [h.latitude, h.longitude + 0.001],
                    [h.latitude + 0.001, h.longitude]
                ], {{
                    color: '#a855f7',
                    fillColor: '#c084fc',
                    weight: 1,
                    fillOpacity: 0.4
                }});

                const popupContent = `
                    <div class="popup-title" style="border-bottom-color: #a855f7;"><i class="fa-solid fa-triangle-exclamation" style="color: #a855f7;"></i> Hotspot: ${{h.location}}</div>
                    <div><b>District:</b> ${{h.district}}</div>
                    <div><b>Historic Depth:</b> ${{h.depth}}</div>
                    <div><b>Lat/Lon:</b> ${{h.latitude.toFixed(5)}}, ${{h.longitude.toFixed(5)}}</div>
                `;
                hotspotMarker.bindPopup(popupContent);
                hotspotMarkersGroup.addLayer(hotspotMarker);
            }});

            // 4. Toggle River Tributaries
            if (showRivers) {{
                if (!map.hasLayer(riversGroup)) {{
                    riversGroup.addTo(map);
                }}
            }} else {{
                if (map.hasLayer(riversGroup)) {{
                    map.removeLayer(riversGroup);
                }}
            }}
        }}

        function renderThreatTable(facilitiesList) {{
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '';

            if (facilitiesList.length === 0) {{
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-secondary);">No facilities match the active filter criteria.</td></tr>`;
                return;
            }}

            const riskWeight = {{ 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'NORMAL': 0 }};
            facilitiesList.sort((a, b) => riskWeight[b.risk_level] - riskWeight[a.risk_level]);

            facilitiesList.forEach(f => {{
                const wl = f.nearest_wl;
                const wl_display = wl ? `${{wl.name}}` : 'N/A';
                const wl_status_display = wl && wl.level !== null ? `${{wl.status}} (${{wl.level.toFixed(2)}}m)` : 'N/A';
                const dist_display = wl && wl.distance_m !== null ? `${{(wl.distance_m/1000).toFixed(2)}} km` : 'N/A';
                const hot_display = f.nearest_hotspot ? `${{f.nearest_hotspot.location}} (${{f.nearest_hotspot.distance_m.toFixed(0)}}m)` : 'N/A';

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #fff;">${{f.name}}</td>
                    <td>${{f.district}}</td>
                    <td>${{f.type}}</td>
                    <td><span class="badge badge-${{f.risk_level.toLowerCase()}}">${{f.risk_level}}</span></td>
                    <td>${{wl_display}}</td>
                    <td><span style="color: var(--wl-${{wl ? wl.status.toLowerCase() : 'normal'}}); font-weight:600;">${{wl_status_display}}</span></td>
                    <td>${{dist_display}}</td>
                    <td>${{hot_display}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function filterTable() {{
            const query = document.getElementById('table-search').value.toLowerCase();
            const filteredFacilities = getFilteredData().filter(f => {{
                return f.name.toLowerCase().includes(query) || 
                       f.district.toLowerCase().includes(query) || 
                       f.risk_level.toLowerCase().includes(query);
            }});
            renderThreatTable(filteredFacilities);
        }}

        function renderWarningsTab() {{
            // 1. Populate Forecasts (Amaran Banjir)
            const forecastBody = document.getElementById('forecasts-table-body');
            forecastBody.innerHTML = '';
            if (rawData.forecasts.length === 0) {{
                forecastBody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-secondary); padding: 20px;">Tiada Amaran Banjir (JPS predictive flood warnings are clean).</td></tr>`;
            }} else {{
                rawData.forecasts.forEach(f => {{
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="font-weight: 600; color:#fff;">${{f.poi}}</td>
                        <td>${{f.poi_type}}</td>
                        <td><span class="badge badge-high">${{f.alert_type}}</span></td>
                        <td>${{f.message}}</td>
                        <td style="font-size: 0.8rem; color:#fff;">${{f.est_start}}</td>
                        <td style="font-size: 0.8rem; color:#fff;">${{f.est_end}}</td>
                    `;
                    forecastBody.appendChild(tr);
                }});
            }}

            // 2. Populate Alerts (Amaran Semasa)
            const alertsBody = document.getElementById('alerts-table-body');
            alertsBody.innerHTML = '';
            if (rawData.current_alerts.length === 0) {{
                alertsBody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-secondary); padding: 20px;">Tiada amaran aktif semasa (JPS water level telemetry warnings are clean).</td></tr>`;
            }} else {{
                rawData.current_alerts.forEach(a => {{
                    const tr = document.createElement('tr');
                    const wl_status_lower = a.wl_status ? a.wl_status.toLowerCase() : 'normal';
                    tr.innerHTML = `
                        <td style="font-weight: 600; color:#fff;">${{a.station_name}}</td>
                        <td>${{a.district}}</td>
                        <td><span class="badge badge-${{wl_status_lower}}">${{a.wl_status}}</span></td>
                        <td>${{a.wl_level}} m</td>
                        <td>${{a.trend}}</td>
                        <td>${{a.rf_severity}}</td>
                        <td>${{a.rf_today}} mm</td>
                        <td style="font-size: 0.75rem;">${{a.wl_time}}</td>
                    `;
                    alertsBody.appendChild(tr);
                }});
            }}
        }}

        function renderTelemetryTable() {{
            const tbody = document.getElementById('telemetry-table-body');
            tbody.innerHTML = '';
            
            const statusWeight = {{ 'Danger': 4, 'Warning': 3, 'Alert': 2, 'Normal': 1, 'Error': 0 }};
            rawData.stations.sort((a, b) => {{
                let valA = statusWeight[a.wl_status] || 0;
                let valB = statusWeight[b.wl_status] || 0;
                return valB - valA;
            }});

            rawData.stations.forEach(s => {{
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #fff;">${{s.name}}</td>
                    <td>${{s.id}}</td>
                    <td>${{s.district}}</td>
                    <td>${{s.type}}</td>
                    <td><span style="color: var(--wl-${{s.wl_status.toLowerCase()}}); font-weight:600;">${{s.wl_status}}</span></td>
                    <td>${{s.wl_level !== null ? s.wl_level.toFixed(2) : 'N/A'}}</td>
                    <td>${{s.wl_trend}}</td>
                    <td>${{s.rf_status}}</td>
                    <td>${{s.rf_today !== null ? s.rf_today + ' mm' : 'N/A'}}</td>
                    <td>${{s.rf_1h !== null ? s.rf_1h + ' mm/h' : 'N/A'}}</td>
                    <td style="font-size:0.75rem;">${{s.wl_time ? s.wl_time : s.rf_time}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function filterTelemetryTable() {{
            const query = document.getElementById('tel-search').value.toLowerCase();
            const filteredStations = rawData.stations.filter(s => {{
                return s.name.toLowerCase().includes(query) || 
                       s.id.toLowerCase().includes(query) || 
                       s.district.toLowerCase().includes(query);
            }});
            
            const tbody = document.getElementById('telemetry-table-body');
            tbody.innerHTML = '';
            filteredStations.forEach(s => {{
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #fff;">${{s.name}}</td>
                    <td>${{s.id}}</td>
                    <td>${{s.district}}</td>
                    <td>${{s.type}}</td>
                    <td><span style="color: var(--wl-${{s.wl_status.toLowerCase()}}); font-weight:600;">${{s.wl_status}}</span></td>
                    <td>${{s.wl_level !== null ? s.wl_level.toFixed(2) : 'N/A'}}</td>
                    <td>${{s.wl_trend}}</td>
                    <td>${{s.rf_status}}</td>
                    <td>${{s.rf_today !== null ? s.rf_today + ' mm' : 'N/A'}}</td>
                    <td>${{s.rf_1h !== null ? s.rf_1h + ' mm/h' : 'N/A'}}</td>
                    <td style="font-size:0.75rem;">${{s.wl_time ? s.wl_time : s.rf_time}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        // Checklist Data from GP Pengurusan Banjir KKK Edisi 2 2019
        const checklistData = {{
            JKN: {{
                SEBELUM: [
                    {{ task: "Hantar Maklumat Persiapan ke KKM", desc: "Mengumpulkan dan menghantar maklumat persiapan dan kesiapsiagaan banjir peringkat negeri ke Sektor KPAS KKM (Bulan Ogos).", time: "Ogos (Setiap Tahun)" }},
                    {{ task: "Kenalpasti Anggota & Pasukan Bantuan", desc: "Mendapatkan maklumat daripada PKD berkenaan senarai anggota bantuan dan pasukan khas kesihatan yang boleh digerakkan bila-bila masa.", time: "Berterusan" }},
                    {{ task: "Mesyuarat Jawatankuasa Kecil JKN", desc: "Mengadakan mesyuarat Jawatankuasa Kecil Kesihatan JKN untuk merancang dan menyelaras bantuan perubatan di PPS.", time: "Julai (Setiap Tahun)" }},
                    {{ task: "Mesyuarat Berkala Antara Agensi", desc: "Mengadakan mesyuarat dengan agensi lain (APM, JPS, MetMalaysia) untuk berkongsi maklumat persediaan cuaca.", time: "Sepanjang Tahun" }},
                    {{ task: "Senarai PPS & Pemeriksaan Kebersihan", desc: "Mendapatkan senarai Pusat Pemindahan Sementara (PPS) dan memastikan pemeriksaan kesihatan persekitaran PPS dijalankan sebelum banjir.", time: "Tahunan" }},
                    {{ task: "Data Golongan Berisiko Tinggi", desc: "Mendapatkan bilangan kes berisiko tinggi (ibu hamil >36 minggu, pesakit hemodialisis, mental, kronik) di kawasan ancaman daripada PKD.", time: "Ogos (Setiap Tahun)" }},
                    {{ task: "Semak Pelan Tindakan Fasiliti & Aset", desc: "Memastikan hospital dan KK mempunyai pelan tindakan fasiliti masing-masing termasuk pemeriksaan generator, diesel, and ubat-ubatan.", time: "Berterusan" }},
                    {{ task: "Penyediaan Jadual Petugas Bilik Gerakan JKN", desc: "Menyediakan jadual petugas Bilik Gerakan Banjir JKN dan petugas PKOB (Kesihatan) Negeri.", time: "September (Setiap Tahun)" }},
                    {{ task: "Semak & Uji Radio GIRN", desc: "Memeriksa status, lokasi, and keberkesanan alat komunikasi Government Integrated Radio Network (GIRN) di negeri.", time: "Berterusan" }},
                    {{ task: "Latihan Water Survival & PFA", desc: "Menyediakan latihan water survival dan Psychological First Aid (PFA) kepada anggota kesihatan yang akan bertugas di lapangan.", time: "Berkala" }}
                ],
                SEMASA: [
                    {{ task: "Buka Bilik Gerakan JKN", desc: "Mengaktifkan Bilik Gerakan Banjir JKN secara serta-merta apabila dua atau lebih daerah terlibat banjir atau diarahkan.", time: "Serta-merta" }},
                    {{ task: "Mesyuarat Harian Bilik Gerakan", desc: "Mengadakan mesyuarat pengurusan dan tindakan banjir di peringkat negeri setiap hari.", time: "Setiap Hari" }},
                    {{ task: "Kumpul Data Cuaca & Telemetri", desc: "Mendapatkan maklumat terkini berkenaan cuaca dan aras air sungai (minima 3 kali sehari) daripada agensi berkaitan.", time: "3x Sehari" }},
                    {{ task: "Arahan Pemindahan Golongan Berisiko", desc: "Mengeluarkan arahan kepada PKD untuk memindahkan pesakit kritikal, hemodialisis, dan ibu hamil >36 minggu apabila amaran kuning MetMalaysia diterima.", time: "Bila Amaran Kuning Diterima" }},
                    {{ task: "Pantau Pergerakan Pasukan Lapangan", desc: "Memantau aktiviti operasi oleh pasukan perubatan dan kesihatan di lapangan (PPS).", time: "Berterusan" }},
                    {{ task: "Laporan Harian ke CPRC Kebangsaan", desc: "Menghantar laporan harian operasi banjir negeri ke CPRC Kebangsaan sebelum jam 12.00 tengah hari keesokannya.", time: "Sebelum 12.00 Tengah Hari" }},
                    {{ task: "Penyelarasan Bantuan Logistik & NGO", desc: "Membantu koordinasi pemindahan pesakit kritikal ke hospital lain dan menyelaraskan bantuan logistik/sumber dari NGO.", time: "Bila Perlu" }},
                    {{ task: "Risk Communication & Media", desc: "Mengendalikan komunikasi risiko (RC) kesihatan banjir kepada orang awam dan mengeluarkan kenyataan media.", time: "Bila Perlu" }},
                    {{ task: "Pantau Wabak Penyakit Bawaan Air", desc: "Memantau sebarang kejadian penyakit luar biasa (cth: AGE, leptospirosis, melioidosis) dalam kalangan mangsa di PPS.", time: "Serta-merta" }}
                ],
                SELEPAS: [
                    {{ task: "Laporan Anggaran Kerosakan & Kerugian", desc: "Menyediakan laporan anggaran kerosakan fasiliti kesihatan dan memajukan kepada EPU Negeri, NADMA, dan KKM.", time: "Serta-merta selepas banjir pulih" }},
                    {{ task: "Pantau Pembersihan Fasiliti", desc: "Memantau kerja-kerja pembersihan di hospital dan klinik yang terjejas akibat banjir.", time: "Serta-merta" }},
                    {{ task: "Penyeliaan Persampelan Makanan", desc: "Menyelaras dan mengkoordinasi aktiviti pemantauan serta persampelan makanan di kawasan terjejas.", time: "Serta-merta" }},
                    {{ task: "Pemulihan Rekod & Dokumen", desc: "Memantau proses pemulihan fail rekod pesakit dan dokumen rasmi sebaik sahaja bilik gerakan ditutup.", time: "Selepas Bilik Gerakan Ditutup" }},
                    {{ task: "Laporan Harian Kesan Banjir (Borang 23)", desc: "Menyediakan laporan harian kesan akibat banjir yang lengkap dengan analisis penyakit, klorinasi air, dan sistem sanitasi PPS.", time: "Setiap hari (selama seminggu)" }},
                    {{ task: "Menjalankan Post-Mortem Banjir", desc: "Menyediakan laporan akhir dan post-mortem banjir berserta cadangan pemulihan jangka pendek dan panjang.", time: "Dalam masa 6 bulan" }}
                ]
            }},
            PKD: {{
                SEBELUM: [
                    {{ task: "Mesyuarat Persiapan Daerah (JPBBD)", desc: "Menghadiri mesyuarat Jawatankuasa Pengurusan Bantuan Banjir Daerah (JPBBD) dan mengemaskini pelan tindakan daerah.", time: "Bulan Jun (Setiap Tahun)" }},
                    {{ task: "Analisis Risiko Kawasan & Fasiliti", desc: "Mengenalpasti kawasan, fasiliti kesihatan (hospital, KK, KD), and populasi yang berisiko dilanda banjir di daerah.", time: "Sebulan Sebelum Musim Hujan" }},
                    {{ task: "Pemeriksaan Kesihatan Persekitaran PPS", desc: "Menjalankan pemeriksaan kesihatan persekitaran di PPS untuk memastikan bekalan air, tandas, dapur, dan pembuangan sampah mencukupi.", time: "Sebulan Sebelum Musim Hujan" }},
                    {{ task: "Senarai Kes Berisiko Tinggi Daerah", desc: "Mengumpul data ibu hamil >36 minggu, pesakit dialisis, pesakit mental, dan OKU terlantar di kawasan banjir.", time: "Sepanjang Masa" }},
                    {{ task: "Semak Stok Ubat-Ubatan & PPE", desc: "Memastikan stok ubat-ubatan, vaksin, dan PPE mencukupi (rujuk Pelan Pengurusan Krisis Farmasi KKM 2016).", time: "Sepanjang Masa" }},
                    {{ task: "Persediaan Bilik Gerakan PKD", desc: "Memastikan bekalan elektrik, air, alat tulis, komputer, dan alat komunikasi (GIRN/Radio Amatur) di Bilik Gerakan PKD sedia.", time: "Sebelum Julai" }}
                ],
                SEMASA: [
                    {{ task: "Buka Bilik Gerakan Daerah", desc: "Membuka Bilik Gerakan Banjir Daerah apabila 2 atau lebih PPS dibuka atau apabila diarahkan.", time: "Serta-merta" }},
                    {{ task: "Evakuasi Golongan Berisiko Tinggi", desc: "Melaksanakan perpindahan/evakuasi pesakit dialisis, ibu hamil >36 minggu, pesakit kronik ke tempat selamat.", time: "Apabila Amaran Diterima" }},
                    {{ task: "Hantar Laporan Analisa Harian Daerah", desc: "Menghantar laporan analisa aktiviti dan status banjir daerah ke JKN Negeri sebelum jam 8.00 malam.", time: "Setiap Hari sebelum 8.00 malam" }},
                    {{ task: "Mobilisasi Pasukan Perubatan ke PPS", desc: "Menugaskan pasukan perubatan membuat lawatan ke PPS (sekurang-kurangnya sekali sehari) dan buka klinik statik jika PPS >1,000 mangsa.", time: "Setiap Hari / Berterusan" }},
                    {{ task: "Kawalan Kesihatan Persekitaran di PPS", desc: "Pasukan kesihatan memeriksa kualiti air minum, kebersihan makanan/pengendali, kawalan pembiakan vektor (LILATI/Aedes) di PPS.", time: "Berterusan" }},
                    {{ task: "Pantau & Notifikasi Penyakit Berjangkit", desc: "Mengesan dan melaporkan sebarang peningkatan kes penyakit berjangkit (AGE, leptospirosis) di PPS.", time: "Serta-merta" }}
                ],
                SELEPAS: [
                    {{ task: "Penilaian Kerosakan Fasiliti Daerah", desc: "Membuat penilaian kerosakan fasiliti kesihatan daerah dan menyelaraskan bantuan pembersihan.", time: "Serta-merta" }},
                    {{ task: "Pemeriksaan Sistem Bekalan Air & Graviti", desc: "Memeriksa sistem bekalan air di daerah termasuk sistem graviti agar selamat digunakan.", time: "Serta-merta" }},
                    {{ task: "Pemeriksaan Premis Makanan Kawasan Banjir", desc: "Memeriksa premis makanan yang dilanda banjir (restoran, kedai runcit, kantin sekolah) sebelum beroperasi semula.", time: "Serta-merta" }},
                    {{ task: "Aktiviti Pasukan Kesihatan di Lapangan", desc: "Melaksanakan aktiviti pasukan kesihatan di lapangan (Setiap hari pada minggu pertama, seminggu sekali pada minggu ke-2, 3 dan 4).", time: "1 Bulan Pasca-Banjir" }},
                    {{ task: "Klorinasi Sumber Air & Perigi", desc: "Menjalankan pengklorinan perigi dan sumber air KKM (sekurang-kurangnya 0.2 ppm sisa klorin).", time: "Serta-merta" }},
                    {{ task: "Kajian Aedes & Larvaciding PPS", desc: "Menjalankan pemeriksaan Aedes di PPS. Jika Indeks Aedes (AI) > 1% or Breteau Indeks (BI) > 5, jalankan larvaciding/fogging.", time: "Seminggu Sekali" }}
                ]
            }},
            KK: {{
                SEBELUM: [
                    {{ task: "Sediakan Profil Kawasan & Peta", desc: "Pegawai Perubatan memastikan profil kawasan operasi, peta, and nombor telefon penting disediakan.", time: "Bulan Jun (Setiap Tahun)" }},
                    {{ task: "Senarai Anggota Tinggal di Kawasan Banjir", desc: "Mengenalpasti anggota klinik yang tinggal di kawasan banjir untuk perancangan tugasan alternatif.", time: "Bulan Jun" }},
                    {{ task: "Persiapan Pemindahan Rekod & Ubatan", desc: "Membuat pelan untuk memindahkan rekod perubatan, ubat-ubatan, vaksin, and peralatan ke tempat tinggi/selamat.", time: "Bulan Jun" }},
                    {{ task: "Semak Stok Diesel & Generator Klinik", desc: "Memastikan stok diesel/petrol untuk kenderaan dan generator klinik mencukupi.", time: "Bulan Jun" }},
                    {{ task: "Senaraikan Golongan Berisiko Kawasan Klinik", desc: "Mengemaskini senarai ibu hamil (kod kuning/merah, atau bersalin dalam bulan banjir), pesakit kronik (hemodialisis, TB), dan OKU.", time: "Bulan Jun" }},
                    {{ task: "Stok Vaksin Minima", desc: "Memastikan hanya stok vaksin minima disimpan di klinik yang dijangka terputus hubungan untuk elak kerosakan jika elektrik padam.", time: "Bulan Jun" }}
                ],
                SEMASA: [
                    {{ task: "Pindahkan Aset & Rekod ke Zon Selamat", desc: "Memindahkan semua rekod, ubat, vaksin, dan peralatan ke tempat selamat/tinggi jika air mula naik.", time: "Serta-merta" }},
                    {{ task: "Pasukan Perubatan Melawat PPS", desc: "Memastikan pasukan perubatan klinik membuat lawatan ke PPS yang ditetapkan sekurang-kurangnya sekali sehari.", time: "Setiap Hari" }},
                    {{ task: "Hantar Reten Penyakit Banjir (Borang 5/6)", desc: "Menyediakan dan menghantar reten kes penyakit berjangkit, kecederaan, dan kematian semasa banjir ke PKD.", time: "Setiap Hari" }},
                    {{ task: "Penjagaan Kesihatan Ibu Hamil & Bersalin", desc: "Merujuk ibu hampir bersalin ke hospital. Sambut kelahiran kecemasan jika tidak dapat dielakkan (cth: head on perineum).", time: "Serta-merta" }},
                    {{ task: "Pengurusan Rawatan Pesakit Kronik di PPS", desc: "Mengenalpasti dan membekalkan ubat kronik yang mencukupi untuk mangsa di PPS.", time: "Setiap Hari" }}
                ],
                SELEPAS: [
                    {{ task: "Laporkan Kerosakan & Kehilangan (Borang 3)", desc: "Segera memaklumkan semua kerosakan, kecurian, atau kehilangan harta benda klinik kepada PKD dalam tempoh 24 jam.", time: "Dalam 24 Jam" }},
                    {{ task: "Menjalankan Pembersihan Klinik", desc: "Menjalankan pembersihan kawasan klinik dengan memastikan anggota menggunakan PPE yang sesuai semasa pembersihan.", time: "Bila Air Surut" }},
                    {{ task: "Hebahan Pendidikan Kesihatan Pasca-Banjir", desc: "Menjalankan pendidikan kesihatan mengenai langkah pencegahan penyakit (AGE, leptospirosis) dan keselamatan elektrik.", time: "Sepanjang Masa" }},
                    {{ task: "Operasi Semula Klinik", desc: "Mengoperasikan semula klinik secepat mungkin jika kerosakan minima, atau maklumkan klinik alternatif kepada orang awam.", time: "Dalam 24 Jam" }}
                ]
            }}
        }};

        // Progress variables and functions
        function getChecklistKey(level, phase) {{
            return `sop_${{level}}_${{phase}}`;
        }}

        function loadSopProgress(level, phase) {{
            const key = getChecklistKey(level, phase);
            const saved = localStorage.getItem(key);
            return saved ? JSON.parse(saved) : [];
        }}

        function saveSopProgress(level, phase, checkedIndices) {{
            const key = getChecklistKey(level, phase);
            localStorage.setItem(key, JSON.stringify(checkedIndices));
        }}

        function renderChecklist() {{
            const level = document.getElementById('sop-level-select').value;
            const phase = document.getElementById('sop-phase-select').value;
            
            const tasks = checklistData[level][phase];
            const checkedIndices = loadSopProgress(level, phase);
            
            // Render Title
            const phaseNames = {{
                SEBELUM: 'Sebelum Banjir (Kesiapsiagaan & Persediaan)',
                SEMASA: 'Semasa Banjir (Respon & Operasi Aktif)',
                SELEPAS: 'Selepas Banjir (Pemulihan & Kawalan Penyakit)'
            }};
            const levelNames = {{
                JKN: 'Jabatan Kesihatan Negeri (JKN)',
                PKD: 'Pejabat Kesihatan Daerah (PKD)',
                KK: 'Klinik Kesihatan / Klinik Desa'
            }};
            
            document.getElementById('checklist-title-text').innerHTML = `
                <i class="fa-solid fa-tasks"></i> Senarai Semak: ${{levelNames[level]}} — ${{phaseNames[phase]}}
            `;
            
            const container = document.getElementById('checklist-items-container');
            container.innerHTML = '';
            
            if (tasks.length === 0) {{
                container.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-secondary);">No tasks available.</div>';
                updateProgressBar(0, 0);
                return;
            }}
            
            tasks.forEach((t, index) => {{
                const isChecked = checkedIndices.includes(index);
                
                const itemDiv = document.createElement('div');
                itemDiv.className = 'checklist-item';
                
                itemDiv.innerHTML = `
                    <input type="checkbox" class="checklist-checkbox" id="task-${{index}}" ${{isChecked ? 'checked' : ''}} onchange="toggleTask('${{level}}', '${{phase}}', ${{index}})">
                    <div class="checklist-content">
                        <label for="task-${{index}}" class="checklist-task" style="cursor:pointer; text-decoration: ${{isChecked ? 'line-through' : 'none'}}; color: ${{isChecked ? 'var(--text-secondary)' : '#fff'}}; font-weight:600;">${{t.task}}</label>
                        <div class="checklist-desc">${{t.desc}}</div>
                        <div class="checklist-time"><i class="fa-regular fa-clock"></i> ${{t.time}}</div>
                    </div>
                `;
                container.appendChild(itemDiv);
            }});
            
            updateProgressBar(checkedIndices.length, tasks.length);
        }}

        function toggleTask(level, phase, index) {{
            const checkedIndices = loadSopProgress(level, phase);
            const isChecked = document.getElementById(`task-${{index}}`).checked;
            
            if (isChecked) {{
                if (!checkedIndices.includes(index)) {{
                    checkedIndices.push(index);
                }}
            }} else {{
                const i = checkedIndices.indexOf(index);
                if (i > -1) {{
                    checkedIndices.splice(i, 1);
                }}
            }}
            
            saveSopProgress(level, phase, checkedIndices);
            
            // Toggle label styling immediately
            const label = document.querySelector(`label[for="task-${{index}}"]`);
            if (label) {{
                label.style.textDecoration = isChecked ? 'line-through' : 'none';
                label.style.color = isChecked ? 'var(--text-secondary)' : '#fff';
            }}
            
            // Recalculate progress
            const tasks = checklistData[level][phase];
            updateProgressBar(checkedIndices.length, tasks.length);
        }}

        function updateProgressBar(checkedCount, totalCount) {{
            const percent = totalCount > 0 ? Math.round((checkedCount / totalCount) * 100) : 0;
            const fill = document.getElementById('sop-progress-bar');
            const text = document.getElementById('sop-progress-text');
            
            fill.style.width = `${{percent}}%`;
            text.innerText = `${{percent}}%`;
            
            if (percent === 100) {{
                fill.style.backgroundColor = '#10b981'; // green
            }} else if (percent >= 50) {{
                fill.style.backgroundColor = 'var(--accent-blue)'; // blue
            }} else {{
                fill.style.backgroundColor = 'var(--risk-low)'; // yellow
            }}
        }}

    </script>
</body>
</html>"""
    
    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Generated interactive HTML dashboard at {HTML_OUTPUT}")

if __name__ == "__main__":
    main()
