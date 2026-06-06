import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import subprocess
import os
import sys

class MockKafkaHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Mock Kafka Webhook Endpoint
        if parsed_path.path == "/mock-kafka":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                event_json = json.loads(post_data.decode('utf-8'))
                
                # Respond to the user immediately
                self.send_response(202)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "accepted", "message": "Event queued to mock Kafka topic"}).encode())
                
                # Kick off the orchestrator in the background to simulate async event consumption
                event_str = json.dumps(event_json)
                script_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'agents', 'blackboard_orchestrator.py'))
                
                def run_orchestrator():
                    print(f"\n[Mock Kafka Consumer] Triggering Orchestrator for alert: {event_json.get('alertname')}")
                    # Change directory to the root of the project to ensure correct module resolution
                    root_dir = os.path.dirname(os.path.dirname(__file__))
                    subprocess.run([sys.executable, "-m", "agents.blackboard_orchestrator", "--event-json", event_str], cwd=root_dir)
                    
                threading.Thread(target=run_orchestrator).start()
                return
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
                return
                
        self.send_response(404)
        self.end_headers()

def run_kafka_mock(port=8092):
    server_address = ('127.0.0.1', port)
    httpd = ThreadingHTTPServer(server_address, MockKafkaHandler)
    print(f"Starting Mock Kafka listener on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run_kafka_mock(8092)
