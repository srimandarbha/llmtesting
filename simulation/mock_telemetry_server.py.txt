import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

class MockTelemetryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Mock Prometheus Endpoint
        if parsed_path.path == "/api/v1/query":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Simulate alert STILL firing (non-empty result list)
            response = {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {"alertname": "KubeEtcdVolumeCorruptions"}, "value": [1680000000, "1"]}]
                }
            }
            self.wfile.write(json.dumps(response).encode())
            return
            
        # Mock Splunk Endpoint
        elif parsed_path.path == "/services/search/jobs/export":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            # Simulate a log indicating ArgoCD failed to sync
            response = '{"result": {"_raw": "msg=\\"Sync operation failed due to drift\\""}}'
            self.wfile.write(response.encode())
            return
            
        self.send_response(404)
        self.end_headers()

def run_server(port):
    server_address = ('127.0.0.1', port)
    httpd = ThreadingHTTPServer(server_address, MockTelemetryHandler)
    print(f"Starting mock telemetry server on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    # Port 9090 for Prometheus
    t1 = threading.Thread(target=run_server, args=(9090,))
    # Port 8088 for Splunk
    t2 = threading.Thread(target=run_server, args=(8088,))
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
