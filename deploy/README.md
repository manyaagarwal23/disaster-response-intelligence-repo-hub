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
   (anywhere, or your team's IPs). (The CloudFormation template above does steps 1–3 for you.)
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

## AWS with one click: CloudFormation

`deploy/aws-cloudformation.yml` creates the instance, the security group,
the 20 GB disk, a Secrets Manager secret for the Groq key(s) and an instance
role that may read it, then runs the install script as user data (linted
with `cfn-lint`, no findings). The key never appears in user data. It needs
an AWS account with a default VPC, and the stack must be allowed to create
the IAM role (the **CAPABILITY_IAM** checkbox in the console, or the flag below).

1. AWS Console → **CloudFormation → Create stack → Upload a template file**
   → choose `deploy/aws-cloudformation.yml`.
2. Parameters: paste the Groq key(s) into **GroqApiKeys** (comma-separated,
   tried in order; hidden in the console), pick a **KeyPairName** if you
   want SSH, and narrow **AllowedCidr** to your IP for a private demo.
3. Create the stack. The **Outputs** tab shows `AppUrl` and `HealthUrl`;
   the URL answers when `database_ready` is true (20–40 min).

Or from the AWS CLI:

```bash
aws cloudformation deploy --stack-name rag-assistant \
  --template-file deploy/aws-cloudformation.yml \
  --parameter-overrides GroqApiKeys=gsk_first,gsk_second KeyPairName=my-key AllowedCidr=203.0.113.4/32
aws cloudformation describe-stacks --stack-name rag-assistant --query 'Stacks[0].Outputs'
```

Delete the stack to remove everything (the instance, the disk, the security
group, the secret and the role). The first-start log is `/var/log/rag-install.log`.

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
- Groq keys are read from `.env`, which is never committed (`GROQ_API_KEYS=k1,k2,...`
  tried in order). Rotate a key from the Groq console if it leaks.
- Optional local fallback: install Ollama on the host and set `OLLAMA_MODEL`
  (e.g. `llama3.2:3b`); the container reaches it via `host.docker.internal`.
- Without a key the service still answers with search results, so a
  deployment never goes fully dark when the LLM provider is down.
- `scripts/smoke_test_compose.sh` verifies the exact one-command start
  used here, from scratch, and writes `reports/compose-smoke-<date>.log`.
