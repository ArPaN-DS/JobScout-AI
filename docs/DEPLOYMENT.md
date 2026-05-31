# Deployment Guide

This guide covers deploying Job_bro_AI to production environments.

---

## Deployment Checklist

- [ ] Prepare server environment
- [ ] Configure production settings
- [ ] Setup database (PostgreSQL recommended)
- [ ] Configure web server (Nginx/Apache)
- [ ] Configure WSGI application server (Gunicorn)
- [ ] Setup SSL/TLS certificates
- [ ] Configure environment variables
- [ ] Run database migrations
- [ ] Collect static files
- [ ] Setup background task workers
- [ ] Configure monitoring & logging
- [ ] Backup strategy
- [ ] Security hardening

---

## Server Requirements

### Minimum Specs

- **CPU**: 2 cores
- **RAM**: 2-4 GB
- **Disk**: 20+ GB (SSD recommended)
- **OS**: Ubuntu 20.04 LTS, CentOS 8, or similar

### Recommended Specs (Production)

- **CPU**: 4+ cores
- **RAM**: 8+ GB
- **Disk**: 100+ GB SSD
- **Database**: Separate PostgreSQL server

### Supported Hosting

- **Cloud Platforms**: AWS, Google Cloud, Azure, DigitalOcean, Linode
- **VPS Providers**: Linode, DigitalOcean, Vultr, Hetzner
- **On-Premises**: Any Linux server with Python 3.11+

---

## Step 1: Prepare Server Environment

### Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    build-essential \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    curl \
    wget \
    vim
```

**CentOS/RHEL:**
```bash
sudo yum update -y
sudo yum groupinstall -y "Development Tools"
sudo yum install -y \
    python311 \
    python311-devel \
    postgresql-server \
    postgresql-contrib \
    nginx \
    git
```

### Create Application User

```bash
sudo useradd -m -s /bin/bash jobbroai
sudo usermod -aG sudo jobbroai
sudo su - jobbroai
```

---

## Step 2: Clone and Setup Application

```bash
cd ~
git clone https://github.com/ArPaN-DS/Job_bro_AI.git
cd Job_bro_AI

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

---

## Step 3: Configure Production Environment

### Create `.env` for production

```bash
nano .env
```

```env
# Django Settings
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
DJANGO_SETTINGS_MODULE=career_agent.deploy_settings

# Security
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database (PostgreSQL)
DATABASE_URL=postgresql://jobbroai:YOUR_PASSWORD@localhost:5432/jobbroai

# LLM Providers
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_claude_key

# Security
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true

# Email (for alerts)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=smtp-user@example.com
EMAIL_HOST_PASSWORD=your_app_password

# Logging
LOG_LEVEL=INFO
```

---

## Step 4: Setup PostgreSQL Database

```bash
# Switch to postgres user
sudo su - postgres

# Create database user
createuser jobbroai
# Set password when prompted

# Create database
createdb -O jobbroai jobbroai

# Connect to psql and configure
psql
```

```sql
ALTER USER jobbroai WITH PASSWORD 'your_secure_password';
ALTER USER jobbroai WITH CREATEDB;
\l  -- List databases
\q  -- Quit
```

---

## Step 5: Run Migrations

```bash
cd ~/Job_bro_AI
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

---

## Step 6: Configure Gunicorn

### Create systemd service file

```bash
sudo nano /etc/systemd/system/jobbroai.service
```

```ini
[Unit]
Description=Job_bro_AI Gunicorn Application Server
After=network.target

[Service]
User=jobbroai
Group=www-data
WorkingDirectory=/home/jobbroai/Job_bro_AI

Environment="PATH=/home/jobbroai/Job_bro_AI/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=career_agent.deploy_settings"

ExecStart=/home/jobbroai/Job_bro_AI/venv/bin/gunicorn \
    --workers 4 \
    --worker-class sync \
    --bind unix:/run/gunicorn.sock \
    --access-logfile /var/log/jobbroai/access.log \
    --error-logfile /var/log/jobbroai/error.log \
    career_agent.wsgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Create log directory

```bash
sudo mkdir -p /var/log/jobbroai
sudo chown jobbroai:www-data /var/log/jobbroai
```

### Enable and start service

```bash
sudo systemctl daemon-reload
sudo systemctl enable jobbroai
sudo systemctl start jobbroai
sudo systemctl status jobbroai
```

---

## Step 7: Configure Nginx

### Create Nginx configuration

```bash
sudo nano /etc/nginx/sites-available/jobbroai
```

```nginx
upstream jobbroai {
    server unix:/run/gunicorn.sock fail_timeout=0;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        return 301 https://$server_name$request_uri;
    }

    # Let's Encrypt verification
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Certificates (from Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/jobbroai_access.log;
    error_log /var/log/nginx/jobbroai_error.log;

    # Client upload limit
    client_max_body_size 20M;

    # Static files
    location /static/ {
        alias /home/jobbroai/Job_bro_AI/staticfiles/;
        expires 30d;
    }

    # Media files
    location /media/ {
        alias /home/jobbroai/Job_bro_AI/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://jobbroai;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Deny access to sensitive files
    location ~ /\.env {
        deny all;
    }

    location ~ /\.git {
        deny all;
    }
}
```

### Enable Nginx configuration

```bash
sudo ln -s /etc/nginx/sites-available/jobbroai /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

---

## Step 8: Setup SSL/TLS with Let's Encrypt

### Install Certbot

```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

### Obtain SSL Certificate

```bash
sudo certbot certonly --webroot \
    -w /var/www/certbot \
    -d yourdomain.com \
    -d www.yourdomain.com
```

### Auto-renewal

```bash
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
sudo certbot renew --dry-run  # Test renewal
```

---

## Step 9: Setup Background Task Workers

### Create systemd service for django-q2

```bash
sudo nano /etc/systemd/system/jobbroai-worker.service
```

```ini
[Unit]
Description=Job_bro_AI Django-Q2 Worker
After=network.target jobbroai.service

[Service]
User=jobbroai
Group=www-data
WorkingDirectory=/home/jobbroai/Job_bro_AI

Environment="PATH=/home/jobbroai/Job_bro_AI/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=career_agent.deploy_settings"

ExecStart=/home/jobbroai/Job_bro_AI/venv/bin/python \
    manage.py qcluster

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable jobbroai-worker
sudo systemctl start jobbroai-worker
sudo systemctl status jobbroai-worker
```

---

## Step 10: Configure Monitoring & Logging

### Create log rotation configuration

```bash
sudo nano /etc/logrotate.d/jobbroai
```

```
/var/log/jobbroai/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 jobbroai www-data
    sharedscripts
    postrotate
        systemctl reload jobbroai > /dev/null 2>&1 || true
    endscript
}

/var/log/nginx/jobbroai*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts
}
```

### Setup monitoring alerts

```bash
# Example: Monitor disk space
sudo apt-get install -y sysstat

# Configure cron for health checks
crontab -e
```

```cron
# Check application health every 5 minutes
*/5 * * * * curl -s http://localhost/health || systemctl restart jobbroai
```

---

## Step 11: Backup Strategy

### Database backups

```bash
# Create backup script
nano ~/backup_db.sh
```

```bash
#!/bin/bash
BACKUP_DIR=/backups/jobbroai
DB_NAME=jobbroai
DB_USER=jobbroai
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
pg_dump -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/db_$DATE.sql.gz"
```

### Automate backups

```bash
chmod +x ~/backup_db.sh
crontab -e
```

```cron
# Daily backup at 2 AM
0 2 * * * ~/backup_db.sh >> ~/backup.log 2>&1
```

---

## Step 12: Security Hardening

### Firewall configuration (UFW)

```bash
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw status
```

### Fail2Ban installation

```bash
sudo apt-get install -y fail2ban

sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Security updates

```bash
# Enable automatic security updates
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## Production Deployment Verification

### Verify application is running

```bash
# Check Gunicorn
sudo systemctl status jobbroai

# Check Nginx
sudo systemctl status nginx

# Check workers
sudo systemctl status jobbroai-worker

# Check logs
tail -f /var/log/jobbroai/error.log
tail -f /var/log/nginx/jobbroai_error.log
```

### Run health checks

```bash
# From your local machine
curl -v https://yourdomain.com
curl https://yourdomain.com/health  # If endpoint exists

# Check SSL certificate
openssl s_client -connect yourdomain.com:443

# Check Django admin
curl https://yourdomain.com/admin
```

---

## Scaling for High Traffic

### Database optimization

```sql
-- Add indexes for frequently queried fields
CREATE INDEX idx_job_lead_match_score ON core_joblead(match_score);
CREATE INDEX idx_application_status ON core_application(status);
CREATE INDEX idx_candidate_profile_updated ON core_candidateprofile(updated_at);
```

### Caching

```bash
# Install Redis
sudo apt-get install -y redis-server

# Configure in .env
CACHE_BACKEND=redis://127.0.0.1:6379/0
SESSION_ENGINE=django.contrib.sessions.backends.cache

# Check Redis
redis-cli ping  # Should return PONG
```

### Load balancing

For multiple application servers:
- Setup Nginx upstream
- Configure PostgreSQL connection pooling
- Use shared Redis cache
- Implement session sharing

---

## Troubleshooting

### Application not responding

```bash
# Check if Gunicorn is running
sudo systemctl restart jobbroai

# Check logs
journalctl -u jobbroai -n 50

# Check Nginx
sudo systemctl restart nginx
```

### Database connection errors

```bash
# Check PostgreSQL
sudo systemctl status postgresql

# Test connection
psql -U jobbroai -d jobbroai -h localhost
```

### High CPU usage

```bash
# Check processes
top

# Profile Gunicorn workers
ps aux | grep gunicorn

# Check if queueing is working
python manage.py shell
```

---

## Updating in Production

```bash
# Pull latest code
cd ~/Job_bro_AI
git pull origin main

# Install new dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart services
sudo systemctl restart jobbroai
sudo systemctl restart jobbroai-worker

# Verify deployment
curl https://yourdomain.com/health
```

---

## Performance Optimization Checklist

- [ ] Database indexes optimized
- [ ] Caching configured (Redis)
- [ ] Static files served by Nginx
- [ ] Gzip compression enabled
- [ ] CDN configured (optional)
- [ ] Gunicorn workers tuned (CPU count * 2 + 1)
- [ ] Connection pooling configured
- [ ] Query optimization done
- [ ] N+1 queries eliminated
- [ ] Monitoring and alerts setup

---

## Support

- [Django Deployment Guide](https://docs.djangoproject.com/en/5.2/howto/deployment/)
- [Issue Tracker](https://github.com/ArPaN-DS/Job_bro_AI/issues)

---

**Ready to deploy! **
