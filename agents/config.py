import os
import sys

def get_env_or_fail(var_name, default=None, required=True):
    value = os.getenv(var_name, default)
    if required and value is None:
        print(f"[FATAL CONFIG ERROR] Environment variable {var_name} is required but not set.", file=sys.stderr)
        sys.exit(1)
    return value

# --- Database Configuration ---
DB_HOST = get_env_or_fail("DB_HOST", default="localhost", required=False)
DB_PORT = get_env_or_fail("DB_PORT", default="5432", required=False)
DB_NAME = get_env_or_fail("DB_NAME", default="rhokp", required=False)
DB_USER = get_env_or_fail("DB_USER", default="postgres", required=True)
DB_PASSWORD = get_env_or_fail("DB_PASSWORD", default="postgres", required=True)

DATABASE_TARGET = {
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "host": DB_HOST,
    "port": DB_PORT
}

# --- API Endpoints ---
LLM_API_URL = get_env_or_fail("LLM_API_URL", default="http://127.0.0.1:8080/v1/chat/completions", required=False)
PROMETHEUS_URL = get_env_or_fail("PROMETHEUS_URL", default="http://127.0.0.1:9090", required=False)
SPLUNK_URL = get_env_or_fail("SPLUNK_URL", default="http://127.0.0.1:8088", required=False)

# --- Configuration Values ---
SPLUNK_CONTROLLER_NAME = get_env_or_fail("SPLUNK_CONTROLLER_NAME", default="argocd-application-controller", required=False)
EMBED_MODEL_NAME = get_env_or_fail("EMBED_MODEL_NAME", default="all-MiniLM-L6-v2", required=False)
