import json
import time
from kafka import KafkaProducer

def publish():
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda m: json.dumps(m).encode('utf-8')
    )
    
    alert = {
        "alert_name": "HighCPUUsage",
        "cluster": "prod-cluster-1",
        "namespace": "payment-service",
        "hostname": "node-worker-2",
        "correlation_id": f"test-kafka-{int(time.time())}"
    }
    
    topic = "sre_alerts"
    print(f"Publishing to topic '{topic}': {alert}")
    producer.send(topic, alert)
    producer.flush()
    print("Message sent successfully.")

if __name__ == "__main__":
    publish()
