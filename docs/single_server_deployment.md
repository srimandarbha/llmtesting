# Single-Server Deployment Guide

Since you already have a PostgreSQL database running natively on your server, deploying the rest of the SRE Agent stack is very straightforward using the provided `docker-compose.prod.yml`.

This approach uses Docker containers for the application layer (API, Celery Worker, Frontend, Kafka Consumer) but connects them to your host machine's native PostgreSQL database.

## Prerequisites
1. **Docker & Docker Compose** must be installed on your server.
2. **PostgreSQL** must be running and accessible.
3. You must have created the required databases (e.g., `rhokp` and `rhokp_events`) and granted the appropriate permissions to your database user.

## Step-by-Step Deployment

### 1. Set Up the Environment Variables
Create a `.env` file in the root of the project on your server. You can copy the `.env.example` file and modify it. 

The `docker-compose.prod.yml` is already configured to use `host.docker.internal` as the `DB_HOST`. This special DNS name resolves to your host machine, allowing the Docker containers to seamlessly connect to your native Postgres database.

Ensure your `.env` contains the correct credentials:
```env
# Database Credentials (pointing to host PostgreSQL)
DB_HOST=host.docker.internal
DB_PORT=5432
DB_NAME=rhokp
DB_USER=postgres
DB_PASSWORD=your_secure_password

# External Integrations (Adjust as needed)
LLM_API_URL=http://your-llm-server:8080/v1/chat/completions
LLM_API_KEY=your-api-key
PROMETHEUS_URL=http://your-prometheus:9090
AWX_BASE_URL=http://your-awx:8052
AWX_API_TOKEN=your-awx-token

# Security
API_KEY=your-secure-production-api-key
```

> [!WARNING]
> **Postgres pg_hba.conf:** Ensure your PostgreSQL server is configured to accept connections from the Docker network. You may need to edit `/etc/postgresql/XX/main/pg_hba.conf` to add a line like `host all all 172.17.0.0/16 md5` (or whatever your Docker bridge subnet is), and set `listen_addresses = '*'` in `postgresql.conf`.

### 2. Build and Launch the Containers
With your `.env` file configured, build and start the production stack in detached mode:

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

### 3. What Gets Deployed?
This command will spin up 4 containers:
1. **`frontend` (Port 80)**: The React dashboard served by an optimized Nginx container.
2. **`api` (Port 8000)**: The FastAPI backend handling the WebSocket connections, routing, and REST API.
3. **`worker`**: The Celery worker processing background AI tasks, running the ReAct pipeline, and executing Celery Beat scheduled jobs.
4. **`kafka-consumer`**: The daemon listening for new alerts on the Kafka topic and pushing them to the database.

> [!TIP]
> **Celery Broker & Backend**: Notice that we aren't deploying Redis or RabbitMQ. The `docker-compose.prod.yml` is explicitly configured to use your existing PostgreSQL database as both the message broker and the result backend (`sqla+postgresql://...`). This minimizes your infrastructure footprint on a single server!

### 4. Verify the Deployment
Once running, you can check the logs to ensure the containers are successfully connecting to your database:

```bash
# Check if API started properly
docker-compose -f docker-compose.prod.yml logs -f api

# Check if the Celery worker is connected to Postgres
docker-compose -f docker-compose.prod.yml logs -f worker
```

If everything is green, your SRE dashboard will be accessible via HTTP on port `80` of your server's IP address!
