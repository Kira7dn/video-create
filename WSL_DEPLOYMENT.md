# 🐧 WSL Production Deployment Guide

## 🌟 Overview

WSL (Windows Subsystem for Linux) là một môi trường tuyệt vời để deploy Video Creation API trong production. WSL cung cấp performance gần như native Linux với khả năng tích hợp tốt với Windows ecosystem.

## ✅ Ưu điểm của WSL cho Production

### Performance Benefits
- **Near-native Linux performance**: WSL2 chạy trên real Linux kernel
- **Better I/O performance**: Đặc biệt quan trọng cho video processing
- **Memory efficiency**: Shared memory với Windows host
- **Network performance**: Direct access to Windows network stack

### Development & Operations
- **Familiar Linux environment**: Sử dụng Linux tools và commands
- **Windows integration**: Access Windows files và applications
- **Docker Desktop integration**: Seamless Docker experience
- **Easy backup**: WSL distributions có thể backup/restore dễ dàng

### Cost Effectiveness
- **No additional hardware**: Sử dụng existing Windows server
- **License efficiency**: Single Windows license
- **Resource sharing**: Share resources với Windows applications

## 🔧 WSL Setup for Production

### 1. Install WSL2

```powershell
# Chạy trong PowerShell as Administrator
# Enable WSL
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# Enable Virtual Machine Platform
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Restart computer
# Restart-Computer

# Set WSL2 as default
wsl --set-default-version 2

# Install Ubuntu (recommended)
wsl --install -d Ubuntu-22.04
```

### 2. WSL Configuration

Create `/etc/wsl.conf` in WSL:
```ini
[boot]
systemd=true

[user]
default=your_username

[network]
generateHosts = false
generateResolvConf = false

[interop]
enabled=true
appendWindowsPath=true

[automount]
enabled=true
root=/mnt/
options="metadata,umask=22,fmask=11"
```

### 3. Resource Allocation

Create `.wslconfig` in Windows home directory (`C:\Users\YourName\.wslconfig`):
```ini
[wsl2]
# Limit memory to 8GB (adjust based on your system)
memory=8GB

# Limit CPU to 4 cores
processors=4

# Limit swap to 2GB
swap=2GB

# Disable swap file
# swapfile=false

# Enable nested virtualization (for Docker)
nestedVirtualization=true

# Network mode
networkingMode=mirrored

# Enable localhost forwarding
localhostforwarding=true
```

### 4. Install Docker in WSL

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Start Docker service
sudo service docker start

# Enable Docker to start on boot
echo 'sudo service docker start' >> ~/.bashrc
```

## 🚀 Production Deployment on WSL

### 1. Project Setup

```bash
# Clone your project
cd /home/your_username
git clone https://your-repo/video-create.git
cd video-create

# Create data directories
./setup-directories.sh
```

### 2. Environment Configuration

```bash
# Create production environment
cp .env.template .env.prod

# Edit with WSL-specific settings
nano .env.prod
```

**WSL-specific `.env.prod`:**
```bash
# Domain Configuration
DOMAIN=your-windows-server-ip
API_BASE_URL=http://your-windows-server-ip
SSL_ENABLED=false  # Start without SSL, add later

# WSL-optimized settings
DEBUG=false
LOG_LEVEL=INFO
MAX_WORKERS=2  # Utilize multiple cores
MEMORY_LIMIT=4G

# File paths (WSL-specific)
MOVIEPY_TEMP_DIR=/home/your_username/video-create/data/temp
UPLOAD_TIMEOUT=600  # Longer timeout for Windows I/O

# Performance optimizations
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1

# Network settings (WSL)
CORS_ORIGINS=*  # Allow all origins for testing
```

### 3. Deploy with Docker

```bash
# Build and start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d

# Check status
docker-compose ps
docker-compose logs -f
```

### 4. Windows Firewall Configuration

```powershell
# Run in Windows PowerShell as Administrator
# Allow incoming connections on port 8000
New-NetFirewallRule -DisplayName "Video API HTTP" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow

# Allow port 80 if using nginx
New-NetFirewallRule -DisplayName "Video API Nginx HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow

# Allow port 443 for HTTPS
New-NetFirewallRule -DisplayName "Video API Nginx HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

### 5. Access from Network

```bash
# Get Windows host IP
ip route show | grep -i default | awk '{ print $3}'

# Or from Windows side
ipconfig | findstr IPv4
```

**API will be available at:**
- From Windows: `http://localhost:8000`
- From network: `http://WINDOWS_IP:8000`
- API docs: `http://WINDOWS_IP:8000/docs`

## 🔧 WSL-Specific Optimizations

### 1. Storage Optimization

```bash
# Move Docker data to Windows drive for better performance
sudo service docker stop

# Create docker directory on Windows drive
sudo mkdir -p /mnt/c/docker-data

# Update Docker daemon configuration
sudo nano /etc/docker/daemon.json
```

**Docker daemon config:**
```json
{
  "data-root": "/mnt/c/docker-data",
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
# Restart Docker
sudo service docker start
```

### 2. Performance Tuning

```bash
# Enable performance governors (if available)
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Increase file descriptors limit
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Optimize memory overcommit
echo 'vm.overcommit_memory = 1' | sudo tee -a /etc/sysctl.conf
```

### 3. Network Optimization

```bash
# Enable IPv4 forwarding
echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.conf

# Optimize network buffers
echo 'net.core.rmem_max = 67108864' | sudo tee -a /etc/sysctl.conf
echo 'net.core.wmem_max = 67108864' | sudo tee -a /etc/sysctl.conf

# Apply settings
sudo sysctl -p
```

## 🌐 External Access Configuration

### 1. Port Forwarding (Simple)

```bash
# Forward traffic from Windows to WSL
# Run in Windows PowerShell as Administrator

# Get WSL IP
wsl hostname -I

# Forward port 8000
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=WSL_IP_ADDRESS

# Forward port 80 (if using nginx)
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=80 connectaddress=WSL_IP_ADDRESS

# Check port proxy rules
netsh interface portproxy show all
```

### 2. Dynamic Port Forwarding Script

Create `wsl-port-forward.ps1` in Windows:
```powershell
# WSL Port Forwarding Script
param(
    [string]$Ports = "80,443,8000,9090"
)

# Get WSL IP
$wslIP = (wsl hostname -I).Trim()
Write-Host "WSL IP: $wslIP"

# Remove existing rules
netsh interface portproxy reset

# Add new rules
$portList = $Ports.Split(',')
foreach ($port in $portList) {
    $port = $port.Trim()
    Write-Host "Forwarding port $port to WSL"
    netsh interface portproxy add v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$wslIP
}

Write-Host "Port forwarding configured. Current rules:"
netsh interface portproxy show all
```

Run script:
```powershell
# Run as Administrator
.\wsl-port-forward.ps1
```

### 3. Automatic Startup Configuration

Create startup script `start-video-api.ps1`:
```powershell
# Video API Startup Script

Write-Host "Starting Video Creation API on WSL..."

# Start WSL if not running
wsl --distribution Ubuntu-22.04 --exec echo "WSL Started"

# Setup port forwarding
$wslIP = (wsl hostname -I).Trim()
netsh interface portproxy reset
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=80 connectaddress=$wslIP
netsh interface portproxy add v4tov4 listenport=443 listenaddress=0.0.0.0 connectport=443 connectaddress=$wslIP
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wslIP
netsh interface portproxy add v4tov4 listenport=9090 listenaddress=0.0.0.0 connectport=9090 connectaddress=$wslIP

# Start Docker and services in WSL
wsl --distribution Ubuntu-22.04 --exec bash -c "cd /home/your_username/video-create && sudo service docker start && docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d"

Write-Host "Video Creation API started successfully!"
Write-Host "API available at: http://$(hostname):8000"
Write-Host "API docs: http://$(hostname):8000/docs"
```

Add to Windows startup:
```powershell
# Create scheduled task for startup
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File C:\path\to\start-video-api.ps1"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "VideoAPIStartup" -Action $action -Trigger $trigger -Principal $principal
```

## 🔒 WSL Security Considerations

### 1. Network Security

```bash
# Configure UFW firewall in WSL
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow specific ports
sudo ufw allow 8000/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow from Windows network only
sudo ufw allow from 192.168.0.0/16 to any port 8000
```

### 2. File Permissions

```bash
# Secure configuration files
chmod 600 .env.prod
chmod 700 nginx/ssl/
chmod 600 nginx/ssl/*

# Secure data directories
sudo chown -R your_username:docker data/
chmod 755 data/
chmod 755 data/temp data/logs data/cache
```

### 3. Docker Security

```bash
# Enable Docker content trust
echo 'export DOCKER_CONTENT_TRUST=1' >> ~/.bashrc

# Scan images for vulnerabilities
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v $HOME/Library/Caches:/root/.cache/ \
  aquasec/trivy image video-create_video
```

## 📊 Monitoring WSL Performance

### 1. Resource Monitoring Script

Create `monitor-wsl.ps1`:
```powershell
# WSL Resource Monitor
while ($true) {
    Clear-Host
    Write-Host "=== WSL Video API Monitor ===" -ForegroundColor Green
    Write-Host "Time: $(Get-Date)" -ForegroundColor Yellow
    
    # WSL resource usage
    $wslStats = wsl --exec bash -c "free -h && df -h /home && docker stats --no-stream"
    Write-Host "`nWSL Resources:" -ForegroundColor Cyan
    Write-Host $wslStats
    
    # Windows resources
    Write-Host "`nWindows Resources:" -ForegroundColor Cyan
    Get-Process | Where-Object {$_.ProcessName -eq "wsl"} | Format-Table Name, CPU, WorkingSet -AutoSize
    
    # Network connections
    Write-Host "`nNetwork Connections:" -ForegroundColor Cyan
    netstat -an | Select-String ":8000|:80|:443" | Select-Object -First 10
    
    Start-Sleep 30
}
```

### 2. Health Check Script

Create `health-check.sh` in WSL:
```bash
#!/bin/bash
# WSL Video API Health Check

echo "=== Video API Health Check ==="
echo "Time: $(date)"

# Check Docker containers
echo -e "\n📦 Container Status:"
docker-compose ps

# Check API health
echo -e "\n🔍 API Health:"
curl -s http://localhost:8000/health | jq '.' || echo "❌ API not responding"

# Check resources
echo -e "\n💾 Resource Usage:"
free -h
df -h /home

# Check logs for errors
echo -e "\n📋 Recent Errors:"
docker-compose logs --tail=10 video | grep -i error || echo "✅ No recent errors"

echo -e "\n✅ Health check completed"
```

## 🚨 Troubleshooting WSL Issues

### Common WSL Issues

#### 1. WSL Service Not Starting
```powershell
# Restart WSL
wsl --shutdown
wsl --distribution Ubuntu-22.04

# Check WSL status
wsl --status
wsl --list --verbose
```

#### 2. Docker Issues in WSL
```bash
# Restart Docker
sudo service docker restart

# Check Docker status
sudo service docker status
docker --version

# Reset Docker if needed
sudo apt remove docker docker-engine docker.io containerd runc
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

#### 3. Port Forwarding Issues
```powershell
# Clear all port proxy rules
netsh interface portproxy reset

# Re-add rules
$wslIP = (wsl hostname -I).Trim()
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wslIP

# Check Windows firewall
Get-NetFirewallRule -DisplayName "*Video*"
```

#### 4. Performance Issues
```bash
# Check WSL resource limits
cat /proc/meminfo
cat /proc/cpuinfo

# Monitor Docker resource usage
docker stats

# Check disk I/O
iostat -x 1 5
```

#### 5. Network Connectivity Issues
```bash
# Test internal connectivity
curl http://localhost:8000/health

# Test from Windows
# In PowerShell:
curl http://localhost:8000/health

# Check DNS resolution
nslookup your-domain.com
ping your-domain.com
```

## 🎯 Production Best Practices for WSL

### 1. Backup Strategy

```bash
# Export WSL distribution
wsl --export Ubuntu-22.04 C:\backup\video-api-backup.tar

# Backup application data
tar -czf /mnt/c/backup/video-api-data-$(date +%Y%m%d).tar.gz data/

# Backup configuration
cp .env.prod /mnt/c/backup/
cp docker-compose*.yml /mnt/c/backup/
```

### 2. Update Strategy

```bash
# Update WSL system
sudo apt update && sudo apt upgrade -y

# Update Docker images
docker-compose pull
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d

# Health check after update
./health-check.sh
```

### 3. Monitoring and Alerting

```bash
# Setup log rotation
sudo logrotate -f /etc/logrotate.conf

# Monitor disk space
echo "df -h /home | awk 'NR==2{print \$5}' | sed 's/%//' | awk '{if(\$1 > 80) print \"Disk usage high: \" \$1\"%\"}'" | crontab -
```

## 📋 WSL vs Native Linux Comparison

| Aspect | WSL2 | Native Linux | Winner |
|--------|------|--------------|--------|
| **Performance** | 95% native | 100% | Linux |
| **I/O Performance** | Good | Excellent | Linux |
| **Memory Usage** | Shared with Windows | Dedicated | WSL |
| **Network Performance** | Very Good | Excellent | Linux |
| **Ease of Setup** | Excellent | Good | WSL |
| **Windows Integration** | Excellent | None | WSL |
| **Resource Efficiency** | High | Medium | WSL |
| **Maintenance** | Low | Medium | WSL |

## 🎉 Conclusion

WSL2 là một lựa chọn tuyệt vời cho production deployment của Video Creation API khi:

✅ **Phù hợp khi:**
- Bạn đã có Windows server infrastructure
- Cần tích hợp với Windows applications
- Team quen thuộc với Windows environment
- Muốn giảm chi phí hardware và licensing

❌ **Không phù hợp khi:**
- Cần maximum performance cho high-volume processing
- Yêu cầu 24/7 uptime critical applications
- Complex networking requirements
- Large-scale container orchestration

**Recommendation:** WSL2 hoàn hảo cho small-to-medium production deployments và development environments. Cho enterprise-scale, consider native Linux hoặc cloud platforms.

---

*WSL deployment guide last updated: June 30, 2025*
