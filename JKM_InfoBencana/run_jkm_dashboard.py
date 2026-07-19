import os
import json
import webbrowser
from http.server import SimpleHTTPRequestHandler, HTTPServer
import scrape_jkm

class JKMDashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/live':
            try:
                print("\n[Server] Client requested live update. Scraping JKM v2 portal...")
                # Trigger the scrape and get live data
                data = scrape_jkm.scrape_data()
                
                # Send headers
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                self.end_headers()
                
                # Return data
                self.wfile.write(json.dumps(data).encode('utf-8'))
                print("[Server] Live scraping complete. Data sent to client.")
            except Exception as e:
                print(f"[Server] Error during live scrape: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            # Serve files from the current folder (jkm_realtime_dashboard.html, etc.)
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/save_health':
            try:
                # Read content length
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                payload = json.loads(post_data.decode('utf-8'))
                
                pps_id = str(payload.get('pps_id'))
                pregnant = int(payload.get('pregnant', 0))
                postnatal = int(payload.get('postnatal', 0))
                hemodialysis = int(payload.get('hemodialysis', 0))
                palliative = int(payload.get('palliative', 0))
                
                screened_total = int(payload.get('screened_total', 0))
                chronic_disease = int(payload.get('chronic_disease', 0))
                injuries = int(payload.get('injuries', 0))
                
                age = int(payload.get('age', 0))
                ari = int(payload.get('ari', 0))
                conjunctivitis = int(payload.get('conjunctivitis', 0))
                skin_infection = int(payload.get('skin_infection', 0))
                fever = int(payload.get('fever', 0))
                other_infectious = int(payload.get('other_infectious', 0))
                
                remarks = str(payload.get('remarks', ''))
                
                print(f"\n[Server] Saving custom health data for PPS {pps_id}...")
                
                # Load existing health data
                workspace_dir = r"c:\Users\hanis\OneDrive\KPAS JKN\Natural Disaster\Data Banjir\JKM_InfoBencana"
                health_file = os.path.join(workspace_dir, "pps_health_data.json")
                health_data = {}
                
                if os.path.exists(health_file):
                    try:
                        with open(health_file, "r", encoding="utf-8") as hf:
                            health_data = json.load(hf)
                    except Exception as ex:
                        print(f"[Server] Warning reading health file: {ex}")
                
                # Update
                health_data[pps_id] = {
                    "pregnant": pregnant,
                    "postnatal": postnatal,
                    "hemodialysis": hemodialysis,
                    "palliative": palliative,
                    "screened_total": screened_total,
                    "chronic_disease": chronic_disease,
                    "injuries": injuries,
                    "age": age,
                    "ari": ari,
                    "conjunctivitis": conjunctivitis,
                    "skin_infection": skin_infection,
                    "fever": fever,
                    "other_infectious": other_infectious,
                    "remarks": remarks
                }
                
                # Write back
                with open(health_file, "w", encoding="utf-8") as hf:
                    json.dump(health_data, hf, indent=4, ensure_ascii=False)
                print(f"[Server] Successfully saved health data to pps_health_data.json")
                
                # Re-run scrape_data to update static files (jkm_realtime_data.json)
                print("[Server] Refreshing local JSON database with new health metrics...")
                scrape_jkm.scrape_data()
                
                # Send headers
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                print(f"[Server] Error saving health data: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    # Lock server directory to this workspace
    workspace_dir = r"c:\Users\hanis\OneDrive\KPAS JKN\Natural Disaster\Data Banjir\JKM_InfoBencana"
    os.chdir(workspace_dir)
    
    port = 8000
    server_address = ('', port)
    httpd = HTTPServer(server_address, JKMDashboardHandler)
    
    dashboard_url = f"http://localhost:{port}/jkm_realtime_dashboard.html"
    print("=" * 60)
    print(f" JKM REAL-TIME DISASTER SURVEILLANCE SERVER STARTED")
    print(f" Dashboard URL: {dashboard_url}")
    print("=" * 60)
    
    # Open default web browser to the dashboard page
    print(f"[Server] Launching browser: {dashboard_url}")
    webbrowser.open(dashboard_url)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Stopping dashboard server.")
        httpd.server_close()
        print("[Server] Server stopped successfully.")

if __name__ == "__main__":
    run_server()
