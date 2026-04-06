# PriceWise - Production Deployment Guide

This guide covers deploying PriceWise to a production server using Docker.

## Prerequisites

- A server running Ubuntu 20.04+ or similar Linux distribution
- Root or sudo access
- At least 2GB RAM
- Ports 80 and 443 open (for web access)
- Port 22 open (for SSH)

---

## 1. Server Setup

### Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Log out and back in for changes to take effect
```

### Install Docker Compose

```bash
sudo apt install docker-compose-plugin -y
```

---

## 2. Deploy Application

### Clone or Upload Files

Option A - Using Git:
```bash
git clone <your-repo-url> pricewise
cd pricewise
```

Option B - Using SCP (from your local machine):
```bash
scp -r ./* user@your-server-ip:/home/user/pricewise/
```

### Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your values
nano .env
```

**Important settings:**
- `SECRET_KEY` - Generate a random string: `openssl rand -hex 32`
- `SERPAPI_API_KEY` - Your SerpAPI key
- Email settings if using alerts

### Start Services

```bash
# Build and start all services
docker compose -f docker-compose.prod.yml up -d --build

# Check status
docker compose -f docker-compose.prod.yml ps
```

### Verify Deployment

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs -f backend

# Test health endpoint
curl http://localhost/health
```

Open in browser: `http://your-server-ip`

---

## 3. SSL/HTTPS Setup (Recommended)

### Using Certbot with Nginx

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Stop nginx temporarily (if using port 80)
sudo docker compose -f docker-compose.prod.yml stop nginx

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Create SSL config
cat > ssl.conf << EOF
server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    # Static files
    location /static/ {
        root /usr/share/nginx/html;
        expires 30d;
    }

    # API proxy
    location /api/ {
        proxy_pass http://backend:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /health {
        proxy_pass http://backend:5000;
    }

    location / {
        root /usr/share/nginx/html;
        try_files \$uri \$uri/ /index.html;
    }
}

# HTTP redirect
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://\$host\$request_uri;
}
EOF
```

### Update Docker Compose for SSL

Edit `docker-compose.prod.yml` to mount SSL certificates:

```yaml
nginx:
  volumes:
    - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    - ./:/usr/share/nginx/html:ro
    - /etc/letsencrypt:/etc/letsencrypt:ro
```

Then restart:
```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate nginx
```

---

## 4. Maintenance

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx
```

### Restart Services

```bash
# Restart all
docker compose -f docker-compose.prod.yml restart

# Restart specific service
docker compose -f docker-compose.prod.yml restart backend
```

### Update Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build
```

### Backup Data

```bash
# MongoDB backup
docker exec pricewise-mongo mongodump --archive > backup_$(date +%Y%m%d).archive

# Data directory
 tar -czf data_backup_$(date +%Y%m%d).tar.gz data/
```

### Stop Services

```bash
docker compose -f docker-compose.prod.yml down
```

---

## 5. Troubleshooting

### Port Already in Use

```bash
# Check what is using port 80
sudo lsof -i :80

# Stop conflicting services
sudo systemctl stop nginx  # if system nginx is running
```

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs backend

# Check container status
docker ps -a
```

### Cannot Connect to MongoDB/Redis

```bash
# Verify containers are running
docker compose -f docker-compose.prod.yml ps

# Test connections
docker exec pricewise-backend ping -c 3 mongo
docker exec pricewise-backend ping -c 3 redis
```

### SSL Certificate Issues

```bash
# Renew certificate
certbot renew

# Test renewal
certbot renew --dry-run
```

---

## 6. Security Recommendations

1. **Firewall** - Use UFW to restrict access:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

2. **Regular Updates** - Keep system and Docker updated

3. **Strong Secrets** - Use strong `SECRET_KEY` and database passwords

4. **Monitor Logs** - Check logs regularly for suspicious activity

5. **Backup Regularly** - Set up automated backups

---

## Quick Reference

| Task | Command |
|-------|--------|
| Start | `docker compose -f docker-compose.prod.yml up -d` |
| Stop | `docker compose -f docker-compose.prod.yml down` |
| Logs | `docker compose -f docker-compose.prod.yml logs -f` |
| Restart | `docker compose -f docker-compose.prod.yml restart` |
| Update | `docker compose -f docker-compose.prod.yml up -d --build` |
| Status | `docker compose -f docker-compose.prod.yml ps` |
