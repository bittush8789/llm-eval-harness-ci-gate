# ☁️ Deploying on AWS EC2 with Docker & Nginx

This guide provides step-by-step instructions for deploying the **AI Evaluation & Regression Testing Platform** on an **Amazon Web Services (AWS) EC2** virtual machine using Docker, Docker Compose, and an Nginx reverse proxy with automated SSL.

---

## 1. AWS Architecture Overview

```mermaid
graph TD
    subgraph Public_Internet ["Public Internet"]
        USER["Developer / Client / GitHub Actions"]
    end

    subgraph AWS_VPC ["AWS VPC"]
        subgraph EC2_Instance ["EC2 Instance (Ubuntu 24.04 LTS / t3.medium)"]
            NGINX["Nginx Reverse Proxy (Port 80 / 443 with SSL)"]
            
            subgraph Docker_Engine ["Docker Engine (Isolated Network)"]
                API["FastAPI Container (Port 8000)"]
                PG[("PostgreSQL 16 Container")]
                EVAL["Evaluator CLI Runner"]
            end

            EBS[("EBS Volume 20GB gp3: Persistent DB & Logs")]
        end

        SG["AWS Security Group: Ports 22, 80, 443"]
    end

    USER -->|HTTPS 443| SG
    SG --> NGINX
    NGINX -->|Proxy Pass 127.0.0.1:8000| API
    API --> PG
    PG --- EBS
```

---

## 2. Prerequisites & Instance Sizing

| Specification | Recommendation |
| :--- | :--- |
| **Instance Type** | `t3.medium` (2 vCPU, 4 GiB RAM) recommended. `t3.small` (2 vCPU, 2 GiB RAM) minimum. |
| **Operating System** | Ubuntu Server 24.04 LTS (HVM), SSD Volume Type |
| **Storage (EBS)** | 20 GiB General Purpose SSD (`gp3`) |
| **Domain Name** | *(Optional for SSL)* Point your domain (e.g., `eval.yourcompany.com`) to EC2 Elastic IP |

---

## 3. Step 1: Launch EC2 Instance & Configure Security Group

1. Navigate to the **AWS EC2 Console** and click **Launch Instances**.
2. **Name:** `ai-evaluation-platform-prod`
3. **AMI:** `Ubuntu Server 24.04 LTS` (64-bit x86)
4. **Instance Type:** `t3.medium`
5. **Key Pair:** Select or create an SSH key pair (`ai-eval-key.pem`).
6. **Network Settings (Security Group):**
   Configure the following Inbound Security Group Rules:

| Type | Port Range | Source | Purpose |
| :--- | :---: | :--- | :--- |
| **SSH** | `22` | `My IP` (or Company VPN CIDR) | Secure admin SSH access |
| **HTTP** | `80` | `0.0.0.0/0` | Let's Encrypt challenges & HTTPS redirect |
| **HTTPS** | `443` | `0.0.0.0/0` | Secure public API access |
| **Custom TCP** | `8000` | `My IP` (Optional) | Direct testing (disable in production) |

7. **Storage:** Set root volume to `20 GiB gp3`.
8. Click **Launch Instance**.
9. *(Recommended)* Allocate an **Elastic IP** in EC2 Console and associate it with your EC2 instance so the IP address remains static across reboots.

---

## 4. Step 2: Connect to EC2 & Install Docker

Connect to your EC2 instance via SSH:
```bash
chmod 400 ai-eval-key.pem
ssh -i ai-eval-key.pem ubuntu@<EC2_PUBLIC_IP>
```

Update packages and install Docker with Docker Compose plugin:
```bash
# 1. Update system packages
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install prerequisites
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

# 3. Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 4. Set up Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 5. Install Docker Engine and Docker Compose
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 6. Add ubuntu user to docker group (avoids needing sudo for docker commands)
sudo usermod -aG docker ubuntu
newgrp docker

# 7. Verify installation
docker --version
docker compose version
```

---

## 5. Step 3: Clone Repository & Configure Environment

```bash
# 1. Clone repository to /opt or user home
cd /home/ubuntu
git clone https://github.com/abhishekkumar526732-ship-it/llm-eval-harness-ci-gate.git
cd llm-eval-harness-ci-gate

# 2. Create production environment file from template
cp .env.example .env

# 3. Edit .env with your production credentials
nano .env
```

Set the following values in your `.env` file:
```env
# Server
ENVIRONMENT=production
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO

# Database (Used by containers)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=generate_a_secure_password_here
POSTGRES_DB=ai_evaluation
DATABASE_URL=postgresql://postgres:generate_a_secure_password_here@postgres:5432/ai_evaluation

# Google Gemini API
GOOGLE_API_KEY=your_production_google_gemini_api_key

# Model Configuration
APP_LLM_MODEL=gemini-3.8-flash
EVALUATOR_LLM_MODEL=gemini-3.8-pro
EVALUATION_OFFLINE_MODE=false
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## 6. Step 4: Build & Run Docker Containers

```bash
# 1. Build the production application container
docker compose build

# 2. Start PostgreSQL and FastAPI in detached mode
docker compose up -d

# 3. Check running containers and health status
docker compose ps
```

You should see both `ai_eval_postgres` and `ai_eval_api` in an `Up (healthy)` state.

```bash
# 4. Run database migrations to initialize tables
docker compose run --rm api alembic upgrade head

# 5. Bootstrap the reference baseline run
docker compose run --rm evaluator python -m scripts.initialize_baseline --dataset-version v1

# 6. Test the API locally
curl http://localhost:8000/health
```

Output:
```json
{"status":"ok","database_connected":true,"version":"0.1.0","environment":"production","offline_mode":false}
```

---

## 7. Step 5: Configure Nginx & SSL (Let's Encrypt Certbot)

Using Nginx as a reverse proxy ensures secure HTTPS communication, rate limiting, and HTTP/2 performance.

### 1. Install Nginx and Certbot
```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 2. Create Nginx Site Configuration
```bash
sudo nano /etc/nginx/sites-available/ai-evaluation
```

Add the following reverse-proxy block (replace `eval.yourcompany.com` with your actual domain or EC2 Public DNS):
```nginx
server {
    listen 80;
    server_name eval.yourcompany.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
        proxy_connect_timeout 60s;
    }
}
```

### 3. Enable the Site & Test Configuration
```bash
sudo ln -s /etc/nginx/sites-available/ai-evaluation /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Obtain Free SSL Certificate via Let's Encrypt
```bash
sudo certbot --nginx -d eval.yourcompany.com
```
Follow the interactive prompts. Certbot will automatically configure SSL certificates and set up HTTP-to-HTTPS redirects.

---

## 8. Step 6: Systemd Service for Auto-Restart on Boot

To ensure the Docker stack automatically restarts if the EC2 instance reboots:

Create a systemd unit file:
```bash
sudo nano /etc/systemd/system/ai-evaluation-docker.service
```

Paste the following definition:
```ini
[Unit]
Description=AI Evaluation Platform Docker Compose Stack
Requires=docker.service
After=docker.service network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ubuntu/llm-eval-harness-ci-gate
User=ubuntu
Group=docker
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-evaluation-docker.service
```

---

## 9. Step 7: Automated Deployment via GitHub Actions (CI/CD)

You can automatically update your EC2 deployment whenever code is pushed to `main`.

Add the following deployment job to `.github/workflows/deploy-ec2.yml`:

```yaml
name: Deploy to AWS EC2

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to EC2 via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ubuntu
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /home/ubuntu/llm-eval-harness-ci-gate
            git pull origin main
            docker compose build
            docker compose up -d
            docker compose run --rm api alembic upgrade head
            echo "Deployment completed successfully!"
```

In GitHub Repository Settings, add:
- `EC2_HOST`: Public IP of your EC2 instance.
- `EC2_SSH_KEY`: Content of your private SSH key (`ai-eval-key.pem`).

---

## 10. Operational Maintenance & Commands

### View Live Application Logs
```bash
docker compose logs -f api
```

### Backup PostgreSQL Database
```bash
docker compose exec postgres pg_dump -U postgres ai_evaluation > /home/ubuntu/backup_$(date +%F).sql
```

### Run Ad-Hoc Evaluation on EC2
```bash
docker compose run --rm evaluator python -m scripts.run_evaluation --dataset-version v1
```

### Clean Up Unused Docker Objects
```bash
docker system prune -f
```
