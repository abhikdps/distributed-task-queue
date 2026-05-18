# PostgreSQL setup for Task Queue

The API expects PostgreSQL with:

- **User (role):** `taskqueue`
- **Password:** `taskqueue_secret`
- **Database:** `taskqueue`

## Option A: Use the project’s Postgres (recommended)

From the **project root** (where `docker-compose.yml` is), start the stack. This starts Postgres with the correct user and database:

```bash
# Docker
docker compose up -d

# Podman
podman compose up -d
# or
./compose.sh up -d
```

Wait ~10 seconds for Postgres to be ready, then start the API:

```bash
cd backend && python -m taskqueue.api.server
```

Check that the `postgres` container is running:

```bash
docker ps
# or
podman ps
```

You should see a container for the `postgres` image. If it exits, check logs:

```bash
docker compose logs postgres
# or
podman compose logs postgres
```

---

## Option B: Use your own PostgreSQL

If you already have PostgreSQL (e.g. installed locally or another container), create the role and database once.

### 1. Connect as a superuser

```bash
psql -U postgres
# or, on macOS with Homebrew Postgres:
psql postgres
# or specify host/port if needed:
psql -h localhost -p 5432 -U postgres
```

### 2. Create the role and database

Run this in `psql`:

```sql
CREATE ROLE taskqueue WITH LOGIN PASSWORD 'taskqueue_secret';
CREATE DATABASE taskqueue OWNER taskqueue;
GRANT ALL PRIVILEGES ON DATABASE taskqueue TO taskqueue;
\q
```

### 3. Point the app at your Postgres

If your Postgres is not on `localhost:5432`, set env vars before starting the API:

```bash
export POSTGRES_HOST=localhost    # or your host
export POSTGRES_PORT=5432
export POSTGRES_USER=taskqueue
export POSTGRES_PASSWORD=taskqueue_secret
export POSTGRES_DB=taskqueue
cd backend && python -m taskqueue.api.server
```

Or create a `.env` file in the project root (or in `backend/`) with:

```text
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=taskqueue
POSTGRES_PASSWORD=taskqueue_secret
POSTGRES_DB=taskqueue
```

---

## Quick one-liner (Option B, Unix)

If you have `psql` and superuser access:

```bash
psql -U postgres -c "CREATE ROLE taskqueue WITH LOGIN PASSWORD 'taskqueue_secret';" -c "CREATE DATABASE taskqueue OWNER taskqueue;" -c "GRANT ALL PRIVILEGES ON DATABASE taskqueue TO taskqueue;"
```

(Adjust `-U postgres` if your superuser has another name.)

---

## Still failing after `podman compose up -d`?

**1. Put `.env` in the project root**
The backend loads `.env` from the project root (the folder that contains `backend/` and `docker-compose.yml`). Create or edit:

```text
/distributed-task-queue/.env
```

with at least:

```text
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=taskqueue
POSTGRES_PASSWORD=taskqueue_secret
POSTGRES_DB=taskqueue
```

Then run the API from the project root or from `backend/`:

```bash
cd distributed-task-queue/backend
python -m taskqueue.api.server
```

**2. Port conflict with local PostgreSQL**
If you have PostgreSQL installed on your Mac (e.g. Homebrew), it may be using port 5432. The API would then talk to that instance (which has no `taskqueue` role) instead of the container.

- **Option A:** Stop the local Postgres so the container can use 5432:

  ```bash
  brew services stop postgresql
  # or
  brew services stop postgresql@14
  ```

- **Option B:** In `docker-compose.yml`, map the postgres container to another port (e.g. `"5433:5432"`). Then in `.env` set `POSTGRES_PORT=5433`.

**3. Try `127.0.0.1`**
In `.env` set:

```text
POSTGRES_HOST=127.0.0.1
```

**4. Confirm the container is listening**
From the host:

```bash
podman port <postgres_container_id_or_name> 5432
# or
nc -zv 127.0.0.1 5432
```

If nothing is listening on 5432, fix the compose/port mapping first.
