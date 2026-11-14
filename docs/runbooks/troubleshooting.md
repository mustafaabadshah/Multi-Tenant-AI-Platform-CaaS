# Operational Troubleshooting Guide

**Scope:** Common operational failure modes, diagnosis, and remediation.

---

## 1. Backend Startup Failures

* **Symptom:** `ValueError: SECRET_KEY must be set in production`
  * **Cause:** Environment variables missing.
  * **Fix:** Populate `.env` with minimum 32-byte secret generated via `python -c "import secrets; print(secrets.token_hex(32))"`.
* **Symptom:** `alembic.util.exc.CommandError: Can't locate revision identified by '0004_...'`
  * **Cause:** Missing migration file or out-of-sync database head.
  * **Fix:** Run `alembic history` and `alembic current` to check database state; run `alembic upgrade head`.

---

## 2. Database Connection Errors

* **Symptom:** `asyncpg.exceptions.CannotConnectNowError: the database system is starting up`
  * **Cause:** PostgreSQL container or managed service is still initializing.
  * **Fix:** The `/ready` endpoint automatically checks database readiness. Wait for health check to return HTTP 200 before routing traffic.

---

## 3. Streaming (SSE) Disconnects

* **Symptom:** Chat stream terminates prematurely with `message_error` frame.
  * **Cause:** Remote LLM provider timeout, 401 invalid API key, or 429 rate limit.
  * **Fix:** Check assistant settings in `/dashboard/assistants`. Verify provider credentials. Ensure `LLM_BASE_URL` is accessible.

---

## 4. Docker Desktop Startup Issues (Windows)

* **Symptom:** `error during connect: Get "http://%2F%2F.%2Fpipe%2Fdocker_engine/v1.24/info": open //./pipe/docker_engine: The system cannot find the file specified.`
  * **Cause:** Docker Desktop background service is stopped or host RAM is $< 2$ GB.
  * **Fix:** Ensure host has at least 2 GB free RAM. Start Docker Desktop from the Start menu with administrator privileges.
