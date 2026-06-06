import json
import time
from kafka import KafkaProducer

import os

def publish():
    broker = os.environ.get('KAFKA_BROKER_URL', 'localhost:9092')
    producer = KafkaProducer(
        bootstrap_servers=[broker],
        value_serializer=lambda m: json.dumps(m).encode('utf-8')
    )
    
    alert = {
        "alert_name": "KubeletHealthState",
        "cluster": "auclo303",
        "namespace": "machine-config-operator",
        "hostname": "aul12345",
        "correlation_id": f"test-kafka-{int(time.time())}"
    }
    
    topic = "sre_alerts"
    print(f"Publishing to topic '{topic}': {alert}")
    producer.send(topic, alert)
    producer.flush()
    print("Message sent successfully.")

if __name__ == "__main__":
    publish()
