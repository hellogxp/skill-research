# trojan-go

Deploy trojan-go proxy server on a remote server and configure local macOS client.

## When to use

Use this skill when the user asks to:
- Deploy trojan-go to a new server
- Migrate trojan-go to a different server
- Configure local trojan-go client
- Set up SOCKS5 proxy via trojan-go

## Prerequisites

### Remote Server
- SSH access (username, password)
- Docker installed
- A domain name with DNS pointing to the server (for SSL certificate)

### Local Machine (macOS)
- trojan-go installed via Homebrew: `brew install trojan-go`
- Config file at `/opt/homebrew/etc/trojan-go/config.json`

## Server Variables

The user must provide:
- `SERVER_IP`: Remote server IP address
- `SERVER_USER`: SSH username (usually `root`)
- `SERVER_PASSWORD`: SSH password
- `DOMAIN`: Domain name for SNI (e.g. `malaysia.xiaocilao.com`)
- `PORT`: Server listening port (default: 2035)
- `PASSWORD`: Trojan password (default: 123456)

## Instructions

### Step 1: SSH and check environment

```bash
sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> 'docker --version && cat /etc/os-release | head -3'
```

### Step 2: Install certbot (if not installed)

```bash
sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> \
  'which certbot || (apt-get update && apt-get install -y certbot)'
```

### Step 3: Generate SSL certificate

Try Let's Encrypt first. If DNS not propagated, fall back to self-signed:

```bash
# Try Let's Encrypt
sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> \
  'certbot certonly --standalone -d <DOMAIN> --agree-tos --non-interactive -m admin@<DOMAIN>'

# If that fails, use self-signed (10 year validity)
sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> \
  'mkdir -p /etc/trojan-go && openssl req -x509 -newkey rsa:4096 \
    -keyout /etc/trojan-go/privkey.pem -out /etc/trojan-go/fullchain.pem \
    -days 3650 -nodes -subj "/CN=<DOMAIN>" \
    -addext "subjectAltName=DNS:<DOMAIN>"'
```

If using self-signed, the local client config needs `"verify": false` in SSL section.

### Step 4: Create trojan-go server config

```bash
sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> \
  'cat > /etc/trojan-go/config.json << EOF
{
  "run_type": "server",
  "local_addr": "0.0.0.0",
  "local_port": <PORT>,
  "password": ["<PASSWORD>"],
  "remote_addr": "127.0.0.1",
  "remote_port": 80,
  "ssl": {
    "cert": "/etc/trojan-go/fullchain.pem",
    "key": "/etc/trojan-go/privkey.pem",
    "sni": "<DOMAIN>"
  }
}
EOF'
```

### Step 5: Deploy with Docker Compose (nginx fallback + trojan-go)

```bash
sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> '
mkdir -p /opt/trojan-go
cat > /opt/trojan-go/docker-compose.yml << EOF
services:
  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "<PORT>:<PORT>"
    networks:
      - trojan-net

  trojan-go:
    image: p4gefau1t/trojan-go
    restart: always
    volumes:
      - /etc/trojan-go:/etc/trojan-go
    depends_on:
      - nginx
    network_mode: service:nginx

networks:
  trojan-net:
EOF
docker compose -f /opt/trojan-go/docker-compose.yml up -d'
```

### Step 6: Verify server-side deployment

```bash
sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> '
sleep 5
docker compose -f /opt/trojan-go/docker-compose.yml ps
echo "---"
docker compose -f /opt/trojan-go/docker-compose.yml logs --tail=5 trojan-go
'
```

Verify port is listening:
```bash
sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> 'netstat -tlnp | grep <PORT>'
```

### Step 7: Download SSL cert to local machine

```bash
CERT=$(sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> 'cat /etc/trojan-go/fullchain.pem')
KEY=$(sshpass -p '<SERVER_PASSWORD>' ssh -o StrictHostKeyChecking=no <SERVER_USER>@<SERVER_IP> 'cat /etc/trojan-go/privkey.pem')
```

### Step 8: Update local trojan-go client config

Write `/opt/homebrew/etc/trojan-go/config.json`:

```json
{
    "run_type": "client",
    "local_addr": "127.0.0.1",
    "local_port": 1080,
    "remote_addr": "<SERVER_IP>",
    "remote_port": <PORT>,
    "password": ["<PASSWORD>"],
    "ssl": {
        "sni": "<DOMAIN>",
        "verify": false
    },
    "mux": {
        "enabled": true
    }
}
```

Note: `"verify": false` is needed for self-signed certs. If using Let's Encrypt, set `"verify": true` and add `"cert"` and `"key"` paths.

### Step 9: Restart local trojan-go service

```bash
brew services restart trojan-go
sleep 3
brew services list | grep trojan-go
```

### Step 10: Test proxy connection

```bash
curl -s --socks5 127.0.0.1:1080 --max-time 15 https://www.google.com -o /dev/null -w "HTTP Status: %{http_code}\n"
```

Expected: `HTTP Status: 200`

### Step 11: Firefox + Zero Omega setup instructions

Tell user to configure Firefox Zero Omega:
- **Name**: `Trojan-Go` (or custom)
- **Type**: `SOCKS5`
- **Host**: `127.0.0.1`
- **Port**: `1080`

### Step 12: Report results

Report to user:
```
Trojan-Go deployment complete:
- Server: <SERVER_IP>:<PORT>
- Domain: <DOMAIN>
- Password: <PASSWORD>
- Local SOCKS5: 127.0.0.1:1080
- Connection test: HTTP 200 OK
```

## Troubleshooting

### Port not reachable from client
- Check cloud provider security group / firewall allows inbound `<PORT>/tcp`
- Verify port binding: `netstat -tlnp | grep <PORT>` should show `0.0.0.0:<PORT>`

### trojan-go keeps restarting (crash loop)
- trojan-go needs an HTTP fallback server on port 80
- Docker Compose setup above includes nginx for this purpose
- Check logs: `docker compose logs trojan-go`

### SSL certificate mismatch
- If using self-signed cert, client must have `"verify": false`
- If using Let's Encrypt, DNS must be fully propagated before requesting cert

### `specify init` fails with termios error
- `specify init` requires interactive terminal for AI assistant selection
- Use `specify init <name> --offline --ai copilot` for non-interactive mode
- The `--offline` flag uses bundled assets instead of GitHub download
