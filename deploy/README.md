# Deploying the assistant as a live service

The whole stack is one Docker container (web UI + API + ChromaDB +
embedding model). `deploy/install_on_ubuntu.sh` turns a fresh Ubuntu
machine into a running instance.

## Requirements

| | Minimum | Recommended |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU (ingestion is CPU-bound) |
| RAM | 4 GB | 8 GB |
| Disk | 15 GB | 20 GB (image ≈ 3.2 GB, Ushahidi + DB ≈ 0.3 GB) |
| OS | Ubuntu 22.04 / 24.04 | |
| Open port | 8000 (or `PORT`) | |

On AWS this is a `t3.large` (2 vCPU / 8 GB) or `c5.xlarge` (4 vCPU / 8 GB).
First start fetches Ushahidi at the pinned commit and builds the vector
database: ~20–40 min on 4 vCPU. Every later start is instant because the
data lives in the `rag-data` Docker volume.

## AWS EC2, step by step

1. **Launch an instance:** Ubuntu 24.04 AMI, `t3.large` or larger, 20 GB
   gp3 disk, a key pair you own.
2. **Security group:** allow inbound TCP 22 (your IP) and TCP 8000
   (anywhere, or your team's IPs).
3. **User data (optional, Advanced details → User data):** paste the
   script with your key on the first line, and the instance deploys itself
   on boot:
   ```bash
   #!/bin/bash
   export GROQ_API_KEY=gsk_...
   curl -fsSL https://raw.githubusercontent.com/manyaagarwal23/disaster-response-intelligence-repo-hub/main/deploy/install_on_ubuntu.sh | bash
   ```
   Or run the same two lines over SSH after boot (`sudo -i` first).
4. **Wait for the database:** `curl http://localhost:8000/healthz` returns
   `"database_ready": true` when ingestion has finished. Watch progress
   with `docker compose -f /opt/disaster-response-rag/docker-compose.yml logs -f`.
5. **Open** `http://<public-ip>:8000`.

## Any other VM / bare Ubuntu

```bash
sudo GROQ_API_KEY=gsk_... bash deploy/install_on_ubuntu.sh
```

## Operating it

| Task | Command (in `/opt/disaster-response-rag`) |
|---|---|
| Logs | `docker compose logs -f` |
| Stop / start | `docker compose stop` / `docker compose start` |
| Update to latest code | `sudo bash deploy/install_on_ubuntu.sh` (keeps the DB) |
| Rebuild the vector DB | `docker compose exec rag python ingestion.py` |
| Change the Groq key | edit `.env`, then `docker compose up -d` |
| Health | `curl localhost:8000/healthz`, `curl localhost:8000/api/stats` |

The container restarts automatically after a reboot (`restart: unless-stopped`).

## Production notes

- Put a reverse proxy with TLS in front for public use (Caddy: two lines
  of config, automatic HTTPS). The app itself serves plain HTTP on 8000.
- The Groq key is read from `.env`, which is never committed. Rotate it
  from the Groq console if it leaks.
- Without a key the service still answers with search results, so a
  deployment never goes fully dark when the LLM provider is down.
- `scripts/smoke_test_compose.sh` verifies the exact one-command start
  used here, from scratch, and writes `reports/compose-smoke-<date>.log`.
