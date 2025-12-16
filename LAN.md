# LAN Access Guide

**Using Amplifier Daemon and Webapp from other devices on your local network**

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Configuration Reference](#configuration-reference)
5. [Verification & Testing](#verification--testing)
6. [Troubleshooting](#troubleshooting)
7. [Security Considerations](#security-considerations)
8. [Advanced Topics](#advanced-topics)
9. [FAQ](#faq)
10. [Related Documentation](#related-documentation)

---

## Overview

### What This Enables

Access your Amplifier daemon and webapp from any device on your local network:
- Use your phone/tablet to interact with Amplifier
- Access from other computers on your network
- Share with team members on the same LAN

### Architecture

```
[Host Machine: your-machine.local]
  ├─ Amplifier Daemon (port 8420)
  └─ Webapp Dev Server (port 5173)
        ↓
[Local Network: 192.168.1.x]
        ↓
[Client Device]
  └─ Browser → http://your-machine.local:5173
```

**How it works:**
1. Daemon runs on host machine, binds to `0.0.0.0:8420` (accessible from network)
2. Webapp dev server runs on host, binds to `0.0.0.0:5173` (accessible from network)
3. Client devices connect via host's IP or hostname
4. Webapp makes API calls to daemon from client browser

---

## Prerequisites

### Checklist

- [ ] Host machine and client devices on same local network
- [ ] Host machine has static IP or discoverable hostname
- [ ] Firewall allows incoming connections on ports 8420 and 5173
- [ ] You understand the security implications (see [Security Considerations](#security-considerations))

### Finding Your Host Machine Address

**Option 1: IP Address**
```bash
# Linux/Mac
ip addr show | grep "inet " | grep -v 127.0.0.1

# Mac (alternative)
ifconfig | grep "inet " | grep -v 127.0.0.1

# Windows
ipconfig | findstr IPv4
```

**Option 2: Hostname**
```bash
# Linux/Mac
hostname

# Windows
hostname
```

Most networks support `.local` mDNS resolution:
- If hostname is `dev-laptop`, try `dev-laptop.local`
- Test: `ping dev-laptop.local` from client device

### Firewall Configuration

**Linux (UFW)**
```bash
sudo ufw allow 8420/tcp comment "Amplifier daemon"
sudo ufw allow 5173/tcp comment "Amplifier webapp"
sudo ufw status
```

**Mac (Built-in Firewall)**
```bash
# System Settings → Network → Firewall
# Allow incoming connections for:
# - "amplifierd" (or Python)
# - "node" (for Vite dev server)
```

**Windows Firewall**
```powershell
# Allow inbound on ports 8420 and 5173
New-NetFirewallRule -DisplayName "Amplifier Daemon" -Direction Inbound -LocalPort 8420 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Amplifier Webapp" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow
```

---

## Quick Start

### Step 1: Configure Daemon

Edit `.amplifierd/config/daemon.yaml`:

```yaml
daemon:
  host: 0.0.0.0  # Bind to all interfaces (default: 127.0.0.1)
  port: 8420
  cors_origins:
    - "http://localhost:5173"          # Local development
    - "http://localhost:5174"          # Alternative port
    - "http://your-machine.local:5173" # LAN access via hostname
    - "http://192.168.1.100:5173"      # LAN access via IP (use your actual IP)
```

**Before:**
```yaml
daemon:
  host: 127.0.0.1  # Only localhost
  cors_origins:
    - "http://localhost:5173"
```

**After:**
```yaml
daemon:
  host: 0.0.0.0    # All network interfaces
  cors_origins:
    - "http://localhost:5173"
    - "http://your-machine.local:5173"  # Add LAN URLs
    - "http://192.168.1.100:5173"       # Add IP addresses
```

**CRITICAL:** The `cors_origins` list must include the exact URL clients will use to access the webapp. Both hostname and IP address variants should be included.

### Step 2: Configure Webapp

Create `webapp/.env.local`:

```bash
# Use your actual hostname or IP
VITE_API_URL=http://your-machine.local:8420

# Or with IP address
# VITE_API_URL=http://192.168.1.100:8420
```

### Step 3: Start Services

```bash
# Start both daemon and webapp (runs in background)
lakehouse start

# Alternative: View logs while starting
lakehouse start && lakehouse logs -f
```

**Access from client device:**
```
http://your-machine.local:5173
```

**Note:** The `lakehouse` CLI runs services in the background, so you don't need multiple terminals. Use:
- `lakehouse status` - Check if services are running
- `lakehouse logs` - View output
- `lakehouse logs -f` - Stream live logs
- `lakehouse stop` - Stop services
- `lakehouse restart` - Restart after config changes

---

## Configuration Reference

### Daemon Configuration

**File:** `.amplifierd/config/daemon.yaml`

The configuration is organized into two main sections: `startup` and `daemon`.

```yaml
# Startup behavior (profile discovery and compilation)
startup:
  auto_discover_profiles: true
  auto_compile_profiles: true
  check_cache_on_startup: true
  update_stale_caches: false
  parallel_compilation: true
  max_parallel_workers: 4

# Daemon server settings
daemon:
  host: 0.0.0.0           # 0.0.0.0 = all interfaces, 127.0.0.1 = localhost only
  port: 8420              # Default daemon port
  workers: 1              # Number of worker processes
  log_level: "INFO"       # Logging level (DEBUG, INFO, WARNING, ERROR)
  cors_origins:
    - "http://localhost:5173"           # Local development
    - "http://localhost:5174"           # Alternative port
    - "http://your-machine.local:5173"  # LAN access via hostname
    - "http://192.168.1.100:5173"       # LAN access via IP (use your actual IP)
  watch_for_changes: false              # Watch for config file changes
  watch_interval_seconds: 60            # How often to check for changes
  cache_ttl_hours: null                 # Cache expiration (null = no expiration)
  enable_metrics: true                  # Enable performance metrics
```

**CORS Security Note:**
- The `cors_origins` list controls which web origins can access your daemon
- **NEVER use `["*"]`** - allows ANY website to access your daemon
- Always list specific origins
- For LAN access, you must add your host's IP/hostname to the list
- Include both hostname (`http://your-machine.local:5173`) and IP (`http://192.168.1.100:5173`) variants
- Omitting a client's URL will result in CORS errors in the browser

### Webapp Configuration

**File:** `webapp/.env.local`

```bash
# Development (local)
VITE_API_URL=http://localhost:8420

# LAN access via hostname
VITE_API_URL=http://your-machine.local:8420

# LAN access via IP
VITE_API_URL=http://192.168.1.100:8420
```

**Priority:**
1. `.env.local` (highest - never commit)
2. `.env.development`
3. `.env`

### Vite Dev Server Options

```bash
# Bind to all interfaces (required for LAN access)
pnpm run dev --host

# Specify port
pnpm run dev --host --port 5173

# Bind to specific interface
pnpm run dev --host 192.168.1.100
```

---

## Verification & Testing

### Step 1: Check Services Running

**From host machine:**
```bash
lakehouse status
# Expected: Both daemon and webapp should be "running"
```

### Step 2: Test Daemon

**From host machine:**
```bash
curl http://localhost:8420/health
# Expected: {"status": "ok"}
```

**From client device:**
```bash
curl http://your-machine.local:8420/health
# Expected: {"status": "ok"}
```

### Step 3: Test Webapp Access

**From client device browser:**
```
http://your-machine.local:5173
```

**Expected:** Webapp loads and displays UI

### Step 4: Test API Communication

**From client device browser console (F12):**
```javascript
fetch('http://your-machine.local:8420/health')
  .then(r => r.json())
  .then(console.log)
```

**Expected:** `{status: "ok"}`

### Common Issues

**Issue:** "Connection refused"
- **Check:** Firewall blocking ports
- **Fix:** Add firewall rules (see [Prerequisites](#prerequisites))

**Issue:** "CORS error" in browser console
- **Check:** CORS origins in `daemon.yaml`
- **Fix:** Add client URL to `cors.origins` list

**Issue:** "Network error" in webapp
- **Check:** `VITE_API_URL` in `.env.local`
- **Fix:** Use correct hostname/IP

---

## Troubleshooting

### Problem: Cannot Access Daemon from Client Device

**Symptoms:**
- `curl http://your-machine.local:8420/health` fails
- Browser shows "connection refused"

**Diagnosis:**
```bash
# 1. Check daemon is running and bound to 0.0.0.0
netstat -tuln | grep 8420
# Expected: tcp 0.0.0.0:8420 (not 127.0.0.1:8420)

# 2. Check firewall
sudo ufw status | grep 8420  # Linux
netstat -an | findstr 8420    # Windows

# 3. Test from host machine first
curl http://localhost:8420/health

# 4. Test from client machine
ping your-machine.local
curl http://your-machine.local:8420/health
```

**Solutions:**
1. Verify `daemon.host: 0.0.0.0` in `daemon.yaml` (under `daemon:` section)
2. Restart services: `lakehouse restart`
3. Add firewall rules (see [Prerequisites](#prerequisites))
4. Try IP address instead of hostname

### Problem: Webapp Loads But Cannot Connect to API

**Symptoms:**
- Webapp displays but API calls fail
- Browser console shows CORS errors
- Network tab shows failed requests

**Diagnosis:**
```bash
# 1. Check VITE_API_URL
cat webapp/.env.local

# 2. Check CORS config
cat .amplifierd/config/daemon.yaml | grep -A 10 cors

# 3. Test API directly
curl http://your-machine.local:8420/health
```

**Solutions:**
1. Verify `VITE_API_URL` matches daemon host
2. Add client URL to CORS origins in `daemon.yaml`:
   ```yaml
   daemon:
     cors_origins:
       - "http://localhost:5173"
       - "http://client-device-ip:5173"
   ```
3. Restart services after config changes: `lakehouse restart`
4. Clear browser cache and reload

### Problem: Webapp Not Accessible from Client Device

**Symptoms:**
- Cannot load `http://your-machine.local:5173`
- Connection timeout

**Diagnosis:**
```bash
# 1. Check services are running
lakehouse status

# 2. Check logs for bind address
lakehouse logs --webapp | grep -i "network"

# 3. Test from host
curl http://localhost:5173

# 4. Check firewall
sudo ufw status | grep 5173
```

**Solutions:**
1. Ensure services are running: `lakehouse start`
2. Add firewall rule for port 5173
3. Use IP address: `http://192.168.1.100:5173`
4. Check logs for errors: `lakehouse logs --webapp`

### Problem: Hostname Resolution Fails

**Symptoms:**
- `ping your-machine.local` fails
- "Could not resolve host"

**Solutions:**
1. **Use IP address directly:**
   ```bash
   # Find IP
   ip addr show | grep "inet "

   # Use in .env.local
   VITE_API_URL=http://192.168.1.100:8420
   ```

2. **Configure mDNS (Linux):**
   ```bash
   sudo apt install avahi-daemon
   sudo systemctl start avahi-daemon
   ```

3. **Add to hosts file (client device):**
   ```bash
   # /etc/hosts (Linux/Mac) or C:\Windows\System32\drivers\etc\hosts (Windows)
   192.168.1.100  your-machine.local
   ```

### Problem: Works from Some Devices But Not Others

**Symptoms:**
- Desktop works, mobile doesn't
- Some browsers work, others don't

**Diagnosis:**
```bash
# Check what network interfaces are active
ip addr show  # Linux/Mac
ipconfig /all # Windows

# Check if devices are on same subnet
# Both should have IPs like 192.168.1.x
```

**Solutions:**
1. Ensure all devices on same network (not guest WiFi)
2. Check for network isolation/guest network restrictions
3. Try different network (mobile hotspot, different WiFi)
4. Verify both devices use same gateway (router)

---

## Security Considerations

### ⚠️ CRITICAL WARNINGS

**1. LAN access exposes daemon to network**
- Any device on your network can access the daemon
- No authentication by default
- Data transmitted in plain HTTP (not encrypted)

**2. Never expose to public internet**
- Don't port-forward 8420 or 5173
- Don't bind to public IP
- Don't expose through reverse proxy without authentication

**3. Trusted networks only**
- Only enable on home/office networks you control
- Disable on public WiFi, coffee shops, hotels
- Use VPN if accessing across networks

### Best Practices

**1. Use specific origins in `cors_origins`:**
```yaml
# Bad (allows any website)
daemon:
  cors_origins:
    - "*"

# Good (specific origins)
daemon:
  cors_origins:
    - "http://localhost:5173"
    - "http://your-machine.local:5173"
    - "http://192.168.1.100:5173"
```

**2. Firewall rules for specific sources:**
```bash
# Allow only from specific IP range
sudo ufw allow from 192.168.1.0/24 to any port 8420
```

**3. Monitor access logs:**
```bash
# Check daemon logs for unexpected access
lakehouse logs --daemon -f
```

**4. Disable when not needed:**
```yaml
# When done with LAN access, change back to:
daemon:
  host: 127.0.0.1  # localhost only
  cors_origins:
    - "http://localhost:5173"  # Remove LAN origins
```

### What's NOT Protected

- ❌ No authentication (anyone on network can access)
- ❌ No encryption (traffic visible to network sniffers)
- ❌ No rate limiting (susceptible to DoS)
- ❌ No audit logging (can't track who accessed what)

### Future Security Features

See roadmap for planned features:
- User authentication
- HTTPS/TLS support
- API key authentication
- Rate limiting
- Audit logging

---

## Advanced Topics

### Static IP Configuration

**Why:** Hostname resolution can be unreliable

**Linux (netplan):**
```yaml
# /etc/netplan/01-netcfg.yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: no
      addresses: [192.168.1.100/24]
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
```

```bash
sudo netplan apply
```

**Mac:**
```
System Settings → Network → [Interface] → TCP/IP → Configure IPv4: Manually
IP Address: 192.168.1.100
Subnet Mask: 255.255.255.0
Router: 192.168.1.1
```

### Reverse Proxy Setup (Nginx)

**Use case:** Single entry point, HTTPS, better control

```nginx
# /etc/nginx/sites-available/amplifier
server {
    listen 80;
    server_name your-machine.local;

    # Webapp
    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8420/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Enable:**
```bash
sudo ln -s /etc/nginx/sites-available/amplifier /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Update webapp config:**
```bash
# webapp/.env.local
VITE_API_URL=http://your-machine.local/api
```

### Multiple Network Interfaces

**Scenario:** Host has WiFi + Ethernet, want to bind to specific interface

**Find interface IPs:**
```bash
ip addr show
```

**Bind daemon to specific interface:**
```yaml
# daemon.yaml
daemon:
  host: 192.168.1.100  # Specific interface, not 0.0.0.0
```

### VPN Access

**Use case:** Access from outside LAN via VPN

**Setup (example with Tailscale):**
```bash
# Install Tailscale on host and client
curl -fsSL https://tailscale.com/install.sh | sh

# Connect both devices
tailscale up
```

**Configure webapp:**
```bash
# Use Tailscale IP
VITE_API_URL=http://100.x.x.x:8420
```

**Benefits:**
- Encrypted traffic
- Works across networks
- Authentication via Tailscale

---

## FAQ

### Q: Do I need to rebuild anything when switching between localhost and LAN access?

**A:** No. Just update config files and restart services:
1. Edit `daemon.yaml` → change `host`
2. Edit `.env.local` → change `VITE_API_URL`
3. Restart services: `lakehouse restart`

### Q: Can I use both localhost and LAN access simultaneously?

**A:** Yes. When daemon binds to `0.0.0.0`, it's accessible from both:
- `http://localhost:8420` (host machine)
- `http://your-machine.local:8420` (LAN devices)

### Q: What if my hostname changes?

**A:** Use IP address in `.env.local` instead:
```bash
VITE_API_URL=http://192.168.1.100:8420
```

Or configure static IP (see [Advanced Topics](#advanced-topics))

### Q: How do I secure this setup?

**A:** For now:
1. Only enable on trusted networks
2. Use specific CORS origins (not `*`)
3. Add firewall rules for specific IPs
4. Monitor access logs

For better security, wait for planned authentication features.

### Q: Can I access from outside my network?

**A:** Not recommended without proper security:
- ⚠️ Don't port-forward without authentication
- ⚠️ Don't expose daemon directly to internet
- ✅ Use VPN (Tailscale, WireGuard) for remote access
- ✅ Wait for planned authentication/HTTPS features

### Q: Why use hostname vs IP address?

**Hostname (`your-machine.local`):**
- ✅ Survives DHCP changes
- ✅ Easier to remember
- ❌ Requires mDNS support
- ❌ May not work on all devices

**IP Address (`192.168.1.100`):**
- ✅ Always works
- ✅ No DNS dependencies
- ❌ May change if using DHCP
- ❌ Need to update if IP changes

**Recommendation:** Use IP with static IP configuration (see [Advanced Topics](#advanced-topics))

### Q: Does this work with Docker?

**A:** Yes, but requires additional port mapping:
```bash
docker run -p 8420:8420 -p 5173:5173 amplifier
```

Container must bind to `0.0.0.0` inside Docker as well.

### Q: Performance impact of LAN access?

**A:** Minimal:
- Same code execution on host
- Network latency: ~1-5ms on LAN
- No additional processing overhead

**Factors affecting performance:**
- Network congestion
- WiFi signal strength
- Router quality

### Q: Can multiple clients access simultaneously?

**A:** Yes. Daemon handles multiple concurrent connections.

**Considerations:**
- Each client gets independent session
- No shared state between clients (currently)
- Sessions stored per-directory basis

---

## Related Documentation

### Project Documentation
- [README.md](./README.md) - Project overview and getting started
- [AGENTS.md](./AGENTS.md) - AI agent guidance and development patterns
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Production deployment guide

### Component Documentation
- [Amplifier Daemon README](./amplifierd/README.md) - Daemon architecture
- [Webapp README](./webapp/README.md) - Frontend development guide
- [Amplifier Library README](./amplifier_library/README.md) - Core library docs

### Configuration
- `.amplifierd/config/daemon.yaml` - Daemon configuration reference
- `webapp/.env.local` - Webapp environment variables (create this file)

### Security & Networking
- [Security Considerations](#security-considerations) (this document)
- Router documentation for port forwarding, static IPs, firewall rules

---

## Quick Reference Card

### Host Machine Setup

```bash
# 1. Configure daemon
cat > .amplifierd/config/daemon.yaml << EOF
daemon:
  host: 0.0.0.0
  port: 8420
  cors_origins:
    - "http://localhost:5173"
    - "http://localhost:5174"
    - "http://your-machine.local:5173"
    - "http://192.168.1.100:5173"
EOF

# 2. Configure webapp
cat > webapp/.env.local << EOF
VITE_API_URL=http://your-machine.local:8420
EOF

# 3. Add firewall rules (Linux)
sudo ufw allow 8420/tcp
sudo ufw allow 5173/tcp

# 4. Start services (runs in background)
lakehouse start
```

### Client Device Access

```bash
# Find host IP
ping your-machine.local

# Test daemon
curl http://your-machine.local:8420/health

# Access webapp in browser
http://your-machine.local:5173
```

### Common Commands

```bash
# Check service status
lakehouse status

# View logs (live)
lakehouse logs -f              # All logs
lakehouse logs --daemon -f     # Daemon only
lakehouse logs --webapp -f     # Webapp only

# Open webapp in browser
lakehouse open

# Test from host
curl http://localhost:8420/health

# Test from network
curl http://your-machine.local:8420/health

# Check what's listening
netstat -tuln | grep -E "8420|5173"

# Check CORS config
grep -A 5 cors_origins .amplifierd/config/daemon.yaml
```

### Reverting to Localhost Only

```bash
# 1. Edit daemon.yaml - change host and remove LAN origins
# Change: daemon.host from 0.0.0.0 to 127.0.0.1
# Keep only: - "http://localhost:5173" in cors_origins

# 2. Edit .env.local
echo "VITE_API_URL=http://localhost:8420" > webapp/.env.local

# 3. Restart services
lakehouse restart
```
