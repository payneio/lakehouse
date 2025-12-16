# Lakehouse Deployment Guide

This guide covers different methods for keeping Lakehouse running after disconnect and automatically starting on system reboot.

## Quick Reference

| Method | Platform | Survives Disconnect | Survives Reboot | Auto-Restart | Complexity |
|--------|----------|---------------------|-----------------|--------------|------------|
| [nohup](#nohup) | All | ✅ | ❌ | ❌ | Very Low |
| [tmux/screen](#tmux-screen) | Linux/macOS | ✅ | ❌ | ❌ | Low |
| [systemd](#systemd-linux) | Linux | ✅ | ✅ | ✅ | Medium |
| [launchd](#launchd-macos) | macOS | ✅ | ✅ | ✅ | Medium |
| [Windows Service](#windows-service) | Windows | ✅ | ✅ | ✅ | Medium |
| [Docker Compose](#docker-compose) | All | ✅ | ✅ | ✅ | High |

---

## nohup

**Best for:** Quick background running without auto-restart.

### Usage

```bash
# Start both daemon and webapp in background
nohup lakehouse start > lakehouse.log 2>&1 &

# Check status
lakehouse status

# View logs
tail -f lakehouse.log

# Stop services
lakehouse stop
```

**Pros:**
- ✅ Extremely simple
- ✅ Works on any Unix-like system
- ✅ Survives SSH disconnect

**Cons:**
- ❌ Doesn't survive reboot
- ❌ No automatic restart on crash
- ❌ Manual process management

---

## tmux / screen

**Best for:** Development and debugging with log visibility.

### Using tmux

```bash
# Create new session
tmux new -s lakehouse

# Start services
lakehouse start

# Detach: Press Ctrl+B, then D

# Reconnect later
tmux attach -t lakehouse

# List sessions
tmux ls

# Kill session
tmux kill-session -t lakehouse
```

### Using screen

```bash
# Create new session
screen -S lakehouse

# Start services
lakehouse start

# Detach: Press Ctrl+A, then D

# Reconnect later
screen -r lakehouse

# List sessions
screen -ls

# Kill session
screen -X -S lakehouse quit
```

**Pros:**
- ✅ Easy to reattach and see logs
- ✅ Survives SSH disconnect
- ✅ Good for debugging

**Cons:**
- ❌ Doesn't survive reboot
- ❌ No automatic restart on crash
- ❌ Requires tmux/screen installed

---

## systemd (Linux)

**Best for:** Production Linux servers with auto-restart and boot-time startup.

### Step 1: Create Service Files

**Daemon Service:**

```bash
sudo nano /etc/systemd/system/lakehouse-daemon.service
```

```ini
[Unit]
Description=Lakehouse Daemon
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/lakehouse
ExecStart=/home/YOUR_USERNAME/.local/bin/amplifierd
Restart=always
RestartSec=10
Environment="PATH=/home/YOUR_USERNAME/.local/bin:/usr/local/bin:/usr/bin"

[Install]
WantedBy=multi-user.target
```

**Webapp Service:**

```bash
sudo nano /etc/systemd/system/lakehouse-webapp.service
```

```ini
[Unit]
Description=Lakehouse Webapp
After=network.target lakehouse-daemon.service
Requires=lakehouse-daemon.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/lakehouse/webapp
ExecStart=/usr/bin/pnpm run dev --host
Restart=always
RestartSec=10
Environment="PATH=/usr/local/bin:/usr/bin"

[Install]
WantedBy=multi-user.target
```

### Step 2: Enable and Start Services

```bash
# Reload systemd to read new service files
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable lakehouse-daemon
sudo systemctl enable lakehouse-webapp

# Start services now
sudo systemctl start lakehouse-daemon
sudo systemctl start lakehouse-webapp

# Check status
sudo systemctl status lakehouse-daemon
sudo systemctl status lakehouse-webapp
```

### Managing Services

```bash
# View logs
sudo journalctl -u lakehouse-daemon -f
sudo journalctl -u lakehouse-webapp -f

# Stop services
sudo systemctl stop lakehouse-daemon lakehouse-webapp

# Restart services
sudo systemctl restart lakehouse-daemon lakehouse-webapp

# Disable auto-start
sudo systemctl disable lakehouse-daemon lakehouse-webapp
```

**Pros:**
- ✅ Production-grade reliability
- ✅ Auto-start on boot
- ✅ Auto-restart on crash
- ✅ Integrated logging (journald)
- ✅ Resource limits and security sandboxing

**Cons:**
- ❌ Requires sudo for setup
- ❌ Linux-only
- ❌ More complex configuration

---

## launchd (macOS)

**Best for:** Production macOS servers with auto-restart and boot-time startup.

### Step 1: Create LaunchAgent Files

**Daemon Service:**

```bash
nano ~/Library/LaunchAgents/com.lakehouse.daemon.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.lakehouse.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/.local/bin/amplifierd</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/lakehouse</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/lakehouse-daemon.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/lakehouse-daemon-error.log</string>
</dict>
</plist>
```

**Webapp Service:**

```bash
nano ~/Library/LaunchAgents/com.lakehouse.webapp.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.lakehouse.webapp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/pnpm</string>
        <string>run</string>
        <string>dev</string>
        <string>--host</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/lakehouse/webapp</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/lakehouse-webapp.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/lakehouse-webapp-error.log</string>
</dict>
</plist>
```

### Step 2: Load Services

```bash
# Load daemon
launchctl load ~/Library/LaunchAgents/com.lakehouse.daemon.plist

# Load webapp
launchctl load ~/Library/LaunchAgents/com.lakehouse.webapp.plist

# Check status
launchctl list | grep lakehouse
```

### Managing Services

```bash
# Unload (stop) services
launchctl unload ~/Library/LaunchAgents/com.lakehouse.daemon.plist
launchctl unload ~/Library/LaunchAgents/com.lakehouse.webapp.plist

# View logs
tail -f /tmp/lakehouse-daemon.log
tail -f /tmp/lakehouse-webapp.log

# Restart services (unload then load)
launchctl unload ~/Library/LaunchAgents/com.lakehouse.daemon.plist
launchctl load ~/Library/LaunchAgents/com.lakehouse.daemon.plist
```

**Pros:**
- ✅ Native macOS integration
- ✅ Auto-start on boot
- ✅ Auto-restart on crash
- ✅ User-level services (no sudo needed)

**Cons:**
- ❌ macOS-only
- ❌ XML configuration syntax
- ❌ Less intuitive than systemd

---

## Windows Service

**Best for:** Production Windows servers with auto-restart and boot-time startup.

### Option 1: Using NSSM (Recommended)

**Install NSSM:**
```powershell
# Using Chocolatey
choco install nssm

# Or download from https://nssm.cc/download
```

**Create Services:**

```powershell
# Install daemon service
nssm install lakehouse-daemon "C:\Users\YOUR_USERNAME\.local\bin\amplifierd.exe"
nssm set lakehouse-daemon AppDirectory "C:\path\to\lakehouse"
nssm set lakehouse-daemon Start SERVICE_AUTO_START

# Install webapp service
nssm install lakehouse-webapp "C:\Program Files\nodejs\pnpm.cmd" "run dev --host"
nssm set lakehouse-webapp AppDirectory "C:\path\to\lakehouse\webapp"
nssm set lakehouse-webapp Start SERVICE_AUTO_START

# Start services
nssm start lakehouse-daemon
nssm start lakehouse-webapp
```

**Managing Services:**

```powershell
# Check status
nssm status lakehouse-daemon
nssm status lakehouse-webapp

# Stop services
nssm stop lakehouse-daemon
nssm stop lakehouse-webapp

# Remove services
nssm remove lakehouse-daemon confirm
nssm remove lakehouse-webapp confirm
```

### Option 2: Using Task Scheduler

**Create Scheduled Task:**

```powershell
# Create task for daemon
$action = New-ScheduledTaskAction -Execute "lakehouse" -Argument "start --daemon-only" -WorkingDirectory "C:\path\to\lakehouse"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "Lakehouse Daemon" -Action $action -Trigger $trigger -Settings $settings -User "YOUR_USERNAME"

# Start task now
Start-ScheduledTask -TaskName "Lakehouse Daemon"
```

**Pros:**
- ✅ Native Windows integration
- ✅ Auto-start on boot
- ✅ Auto-restart on crash (with NSSM)
- ✅ GUI management available

**Cons:**
- ❌ Windows-only
- ❌ Requires NSSM for best experience
- ❌ More complex than Linux/macOS

---

## Docker Compose

**Best for:** Containerized deployments with strong isolation.

### docker-compose.yml

```yaml
version: '3.8'

services:
  daemon:
    build:
      context: ./amplifierd
      dockerfile: Dockerfile
    ports:
      - "8421:8421"
    volumes:
      - ./data:/data
      - ./.amplifierd:/app/.amplifierd
    restart: unless-stopped
    environment:
      - AMPLIFIERD_DATA_DIR=/data

  webapp:
    build:
      context: ./webapp
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    depends_on:
      - daemon
    restart: unless-stopped
```

### Dockerfile Examples

**amplifierd/Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY . .

# Install dependencies
RUN uv sync

# Expose port
EXPOSE 8421

# Run daemon
CMD ["uv", "run", "python", "-m", "amplifierd"]
```

**webapp/Dockerfile:**

```dockerfile
FROM node:18-slim

WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy project files
COPY package.json pnpm-lock.yaml ./
RUN pnpm install

COPY . .

# Expose port
EXPOSE 5173

# Run dev server
CMD ["pnpm", "run", "dev", "--host"]
```

### Usage

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart services
docker-compose restart

# Check status
docker-compose ps
```

**Pros:**
- ✅ Cross-platform
- ✅ Strong isolation
- ✅ Easy replication
- ✅ Auto-restart on crash
- ✅ Good for cloud deployments

**Cons:**
- ❌ Higher resource usage
- ❌ More complex setup
- ❌ Additional abstraction layer
- ❌ Requires Docker knowledge

---

## Comparison and Recommendations

### For Development

**Recommended:** tmux or nohup
- Easy to start/stop
- Can see logs easily
- No complex setup
- Easy to iterate

### For Personal Server (Single User)

**Recommended:** systemd (Linux) or launchd (macOS)
- Auto-start on boot
- Auto-restart on crash
- Integrated logging
- Production-grade reliability

### For Production (Multi-User)

**Recommended:** systemd with reverse proxy (nginx/Caddy)
- Professional architecture
- SSL/TLS termination
- Load balancing capabilities
- Monitoring and metrics

### For Cloud Deployment

**Recommended:** Docker Compose or platform services
- Easy replication across environments
- Strong isolation
- Platform-native integration (ECS, GKE, AKS)

---

## Security Considerations

### File Permissions

```bash
# Ensure service files are not world-writable
chmod 644 /etc/systemd/system/lakehouse-*.service

# Ensure data directory has appropriate permissions
chmod 750 /path/to/data
```

### Firewall Rules

```bash
# Linux (ufw)
sudo ufw allow 8421/tcp  # Daemon
sudo ufw allow 5173/tcp  # Webapp

# Linux (iptables)
sudo iptables -A INPUT -p tcp --dport 8421 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 5173 -j ACCEPT
```

### Run as Non-Root User

Always run services as a non-privileged user:
- ✅ Use `User=youruser` in systemd
- ✅ Use user-level LaunchAgents in macOS
- ✅ Specify user in Docker Compose

---

## Troubleshooting

### Service Won't Start

```bash
# Check service status
systemctl status lakehouse-daemon
# or
launchctl list | grep lakehouse

# Check logs
journalctl -u lakehouse-daemon -n 50
# or
tail -f /tmp/lakehouse-daemon.log

# Verify paths
which amplifierd
which pnpm
```

### Port Conflicts

```bash
# Check what's using ports
lsof -i :8421
lsof -i :5173

# Kill conflicting process
kill -9 <PID>
```

### Permission Issues

```bash
# Ensure user owns lakehouse directory
sudo chown -R $USER:$USER /path/to/lakehouse

# Ensure executable permissions
chmod +x ~/.local/bin/amplifierd
chmod +x ~/.local/bin/lakehouse
```

---

## Additional Resources

- [systemd Documentation](https://www.freedesktop.org/wiki/Software/systemd/)
- [launchd Documentation](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [NSSM Documentation](https://nssm.cc/usage)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

## Need Help?

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review service logs
3. Verify paths and permissions
4. Open an issue on GitHub with:
   - Platform and version
   - Deployment method used
   - Error messages/logs
   - Steps to reproduce
