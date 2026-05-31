import warnings
from neo4j import GraphDatabase
import openai

# 1. Quiet down the MinGW Windows float precision warnings in your virtual env
warnings.filterwarnings("ignore", message="invalid value encountered in.*", category=RuntimeWarning)

# 2. Configure Neo4j Database Credentials
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password123")

def get_graph_context(tx, pod_name):
    # Extracts localized topology path: Pod -> Topic -> Alert context
    query = """
    MATCH (p:Pod {name: $pod_name})-[:CONSUMES_FROM]->(t:Topic)
    MATCH (a:Alert {severity: "Critical"})-[:AFFECTS]->(t)
    MATCH (t)<-[:HOSTS]-(broker:Pod)
    RETURN p.name AS pod, p.status AS pod_status, 
           t.name AS topic, 
           a.name AS alert, a.summary AS alert_details,
           broker.name AS broker_node
    """
    result = tx.run(query, pod_name=pod_name)
    return [record.data() for record in result]

# 3. Pull context from your local Neo4j Graph
print("[INFO] Harvesting dependency topology maps from Neo4j...")
with GraphDatabase.driver(URI, auth=AUTH) as driver:
    with driver.session() as session:
        graph_data = session.execute_read(get_graph_context, "order-processor-xyz")

# Convert the explicit graph architecture paths into structural text
context_str = ""
for record in graph_data:
    context_str += f"- Pod '{record['pod']}' (Status: {record['pod_status']}) consumes from Topic '{record['topic']}'.\n"
    context_str += f"- CRITICAL ALERT: '{record['alert']}' is active on this topic. Details: {record['alert_details']}.\n"
    context_str += f"- This topic is hosted on broker node: '{record['broker_node']}'.\n"

# 4. Route payload to local llama.cpp endpoint hosting Phi-4
print("[INFO] Routing payloads to local llama-server (Phi-4)...")

# Point the SDK to your running local binary server instead of public cloud URLs
client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="local-llama-cpp"  # A string is required by the SDK validator, but ignored by llama.cpp
)

system_instruction = "You are an expert SRE assistant. Use the provided operational graph context to diagnose root causes."
user_question = f"Context from Knowledge Graph:\n{context_str}\n\nQuestion: What is causing the issue in the order-processor-xyz pod and how do I fix it?"

response = client.chat.completions.create(
    model="local-model", # llama.cpp defaults to using whatever model file is loaded on the binary
    messages=[
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_question}
    ],
    temperature=0.2 # Lower temperature guarantees precise, structured troubleshooting analysis
)

print("\n--- Phi-4 Local Inference Diagnostics ---")
print(response.choices[0].message.content)