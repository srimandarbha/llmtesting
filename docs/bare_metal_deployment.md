# Bare-Metal Deployment Guide (No Docker)

If you prefer to run the application directly on your server's OS without using Docker, you will need to manually start and manage the 4 core processes. In a true production environment, you should wrap these commands in **Systemd** services or use a process manager like **PM2** or **Supervisor** to ensure they restart if they crash.

## Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **PostgreSQL** running on `localhost:5432`

---

## 1. Environment Setup

First, clone the repository and set up your Python virtual environment.

```bash
git clone <your-repo>
cd rag_testing

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# Install backend dependencies
pip install -r requirements.txt
```

Create your `.env` file in the root directory:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rhokp
DB_USER=postgres
DB_PASSWORD=your_secure_password

CELERY_BROKER_URL=sqla+postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
CELERY_RESULT_BACKEND=db+postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}

# Kafka Configuration (Optional, for kafka_consumer.py)
KAFKA_BROKER_URL=localhost:9092
KAFKA_TOPIC=sre_alerts
KAFKA_DLQ_TOPIC=sre_alerts_dlq
KAFKA_GROUP_ID=sre-agent-group

# ... [add your LLM and other API keys] ...
```

---

## 2. Start the Backend Processes

You need to run these three Python processes concurrently. 

**Process 1: The FastAPI Server**
This runs the main API and WebSocket connections.
```bash
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Process 2: The Celery Worker & Beat Scheduler**
This executes the background AI tasks and scheduled ingestion scripts. The `-B` flag tells it to also run the Celery Beat scheduler!
```bash
source .venv/bin/activate
celery -A worker.celery_app worker --beat --loglevel=info --queues=default,priority --concurrency=4
```

**Process 3: The Kafka Consumer (Optional)**
If you are ingesting alerts from Kafka, run the listener daemon.
```bash
source .venv/bin/activate
python ingestion/kafka_consumer.py
```

---

## 3. Build & Serve the Frontend

For the frontend, you first need to compile the React TypeScript code into static HTML/JS/CSS files, and then serve them.

```bash
cd frontend
npm install
npm run build
```

The compiled files will now be located in the `frontend/dist/` folder. 

**Serving the Frontend:**
In production, you should point a web server like **Nginx** or **Apache** to serve the `frontend/dist` directory on port 80. 

If you just want to run it quickly for testing without installing Nginx, you can use the node `serve` package:
```bash
npx serve -s dist -l 80
```

---

## Summary
To run the SRE Agent bare-metal, you are managing four distinct components:
1. `uvicorn` (Backend API)
2. `celery` (Background Worker & Schedules)
3. `python ingestion/kafka_consumer.py` (Alert Ingestion)
4. `nginx` or `npx serve` (React Frontend)
