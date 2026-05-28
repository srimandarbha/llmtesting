import os
import sys


def get_env_or_fail(var_name, default=None, required=True):
    value = os.getenv(var_name, default)
    if required and value is None:
        print(
            f"[FATAL CONFIG ERROR] Environment variable {var_name} is required but not set.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


# ---------------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------------
DB_HOST = get_env_or_fail("DB_HOST", default="localhost", required=False)
DB_PORT = get_env_or_fail("DB_PORT", default="5432", required=False)
DB_NAME = get_env_or_fail("DB_NAME", default="rhokp", required=False)
DB_USER = get_env_or_fail("DB_USER", required=True)
DB_PASSWORD = get_env_or_fail("DB_PASSWORD", default="", required=False)

DATABASE_TARGET = {
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "host": DB_HOST,
    "port": DB_PORT,
}

# ---------------------------------------------------------------------------
# LLM / Observability API Endpoints
# ---------------------------------------------------------------------------
LLM_API_URL = get_env_or_fail(
    "LLM_API_URL",
    default="http://127.0.0.1:8080/v1/chat/completions",
    required=False,
)
LLM_API_KEY = get_env_or_fail(
    "LLM_API_KEY",
    default="local",
    required=False,
)
LLM_MODEL = get_env_or_fail(
    "LLM_MODEL",
    default="local-model",
    required=False,
)
PROMETHEUS_URL = get_env_or_fail(
    "PROMETHEUS_URL", default="http://127.0.0.1:9090", required=False
)
SPLUNK_URL = get_env_or_fail(
    "SPLUNK_URL", default="http://127.0.0.1:8088", required=False
)

# ---------------------------------------------------------------------------
# AWX / Ansible Tower
# ---------------------------------------------------------------------------
AWX_BASE_URL = get_env_or_fail(
    "AWX_BASE_URL", default="http://localhost:8052", required=False
)
AWX_API_TOKEN = get_env_or_fail("AWX_API_TOKEN", default="changeme", required=False)
# Set USE_MOCK_AWX=false in production to use the real AWX client
USE_MOCK_AWX = get_env_or_fail("USE_MOCK_AWX", default="true", required=False).lower() == "true"

# ---------------------------------------------------------------------------
# Celery (uses PostgreSQL as broker — no Redis needed)
# ---------------------------------------------------------------------------
_CELERY_DB_URL = f"db+postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
CELERY_BROKER_URL = get_env_or_fail(
    "CELERY_BROKER_URL", default=_CELERY_DB_URL, required=False
)
CELERY_RESULT_BACKEND = get_env_or_fail(
    "CELERY_RESULT_BACKEND", default=_CELERY_DB_URL, required=False
)

# ---------------------------------------------------------------------------
# Auth / API Key
# ---------------------------------------------------------------------------
API_KEY = get_env_or_fail("API_KEY", default="dev-api-key-change-in-prod", required=False)

# ---------------------------------------------------------------------------
# PagerDuty (escalation)
# ---------------------------------------------------------------------------
PAGERDUTY_API_KEY = get_env_or_fail("PAGERDUTY_API_KEY", default="", required=False)
PAGERDUTY_ESCALATION_POLICY_ID = get_env_or_fail(
    "PAGERDUTY_ESCALATION_POLICY_ID", default="", required=False
)

# ---------------------------------------------------------------------------
# Safety Controls
# ---------------------------------------------------------------------------
# Max concurrent auto-executing incidents per cluster per hour
BLAST_RADIUS_CAP = int(
    get_env_or_fail("BLAST_RADIUS_CAP", default="5", required=False)
)
# Minutes within which identical (alert+cluster+namespace) events are deduplicated
DEDUP_WINDOW_MINUTES = int(
    get_env_or_fail("DEDUP_WINDOW_MINUTES", default="10", required=False)
)

# ---------------------------------------------------------------------------
# Embedding Model / Misc
# ---------------------------------------------------------------------------
SPLUNK_CONTROLLER_NAME = get_env_or_fail(
    "SPLUNK_CONTROLLER_NAME",
    default="argocd-application-controller",
    required=False,
)
EMBED_MODEL_NAME = get_env_or_fail(
    "EMBED_MODEL_NAME", default="all-MiniLM-L6-v2", required=False
)
