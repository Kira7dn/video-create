# Video Creation API - WSL Management Script
# Usage: .\manage-wsl.ps1 [command]

param(
    [string]$Command = "help",
    [string]$Distribution = "Ubuntu-22.04",
    [string]$Ports = "80,443,8000,9090"
)

# Check if running as Administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Get WSL IP Address
function Get-WSLIPAddress {
    try {
        $wslIP = (wsl -d $Distribution hostname -I).Trim()
        if ($wslIP) {
            return $wslIP
        }
        else {
            Write-Error "Could not get WSL IP address"
            return $null
        }
    }
    catch {
        Write-Error "WSL is not running or accessible"
        return $null
    }
}

# Setup port forwarding
function Set-PortForwarding {
    if (-not (Test-Administrator)) {
        Write-Error "Port forwarding requires Administrator privileges"
        return
    }

    $wslIP = Get-WSLIPAddress
    if (-not $wslIP) { return }

    Write-Host "Setting up port forwarding to WSL IP: $wslIP" -ForegroundColor Green
    
    # Remove existing rules
    netsh interface portproxy reset | Out-Null
    
    # Add new rules
    $portList = $Ports.Split(',')
    foreach ($port in $portList) {
        $port = $port.Trim()
        Write-Host "Forwarding port $port -> WSL:$port"
        netsh interface portproxy add v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$wslIP | Out-Null
    }
    
    Write-Host "Port forwarding configured successfully!" -ForegroundColor Green
    Show-PortForwarding
}

# Show current port forwarding rules
function Show-PortForwarding {
    Write-Host "`nCurrent port forwarding rules:" -ForegroundColor Cyan
    $rules = netsh interface portproxy show all
    if ($rules -match "No entries found") {
        Write-Host "No port forwarding rules configured" -ForegroundColor Yellow
    }
    else {
        $rules | Write-Host
    }
}

# Remove all port forwarding
function Remove-PortForwarding {
    if (-not (Test-Administrator)) {
        Write-Error "Removing port forwarding requires Administrator privileges"
        return
    }
    
    Write-Host "Removing all port forwarding rules..." -ForegroundColor Yellow
    netsh interface portproxy reset | Out-Null
    Write-Host "Port forwarding rules cleared" -ForegroundColor Green
}

# Configure Windows Firewall
function Set-FirewallRules {
    if (-not (Test-Administrator)) {
        Write-Error "Firewall configuration requires Administrator privileges"
        return
    }

    Write-Host "Configuring Windows Firewall..." -ForegroundColor Green
    
    $portList = $Ports.Split(',')
    foreach ($port in $portList) {
        $port = $port.Trim()
        $ruleName = "Video API Port $port"
        
        # Remove existing rule if exists
        try {
            Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        }
        catch {}
        
        # Add new rule
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $port -Action Allow | Out-Null
        Write-Host "Created firewall rule for port $port"
    }
    
    Write-Host "Firewall rules configured successfully!" -ForegroundColor Green
}

# Start WSL and Video API
function Start-VideoAPI {
    Write-Host "Starting Video Creation API on WSL..." -ForegroundColor Green
    
    # Start WSL if not running
    wsl -d $Distribution --exec echo "WSL Started" | Out-Null
    
    # Setup port forwarding
    Set-PortForwarding
    
    # Start services in WSL
    Write-Host "Starting Docker and Video API services..."
    $result = wsl -d $Distribution --exec bash -c "cd ~/video-create && sudo service docker start && docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Video Creation API started successfully!" -ForegroundColor Green
        Show-Status
    }
    else {
        Write-Error "Failed to start Video API"
    }
}

# Stop Video API
function Stop-VideoAPI {
    Write-Host "Stopping Video Creation API..." -ForegroundColor Yellow
    
    $result = wsl -d $Distribution --exec bash -c "cd ~/video-create && docker-compose -f docker-compose.yml -f docker-compose.prod.yml down"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Video API stopped successfully" -ForegroundColor Green
    }
    else {
        Write-Error "Failed to stop Video API"
    }
}

# Restart Video API
function Restart-VideoAPI {
    Write-Host "Restarting Video Creation API..." -ForegroundColor Cyan
    Stop-VideoAPI
    Start-Sleep 5
    Start-VideoAPI
}

# Show status
function Show-Status {
    $wslIP = Get-WSLIPAddress
    $computerName = $env:COMPUTERNAME
    
    Write-Host "`n=== Video Creation API Status ===" -ForegroundColor Cyan
    Write-Host "WSL Distribution: $Distribution"
    Write-Host "WSL IP Address: $wslIP"
    Write-Host "Computer Name: $computerName"
    
    # Check WSL status
    $wslStatus = wsl --status
    Write-Host "`nWSL Status:" -ForegroundColor Yellow
    $wslStatus | Write-Host
    
    # Check Docker containers
    Write-Host "`nDocker Containers:" -ForegroundColor Yellow
    wsl -d $Distribution --exec bash -c "cd ~/video-create && docker-compose ps" 2>$null
    
    # Show access URLs
    Write-Host "`nAccess URLs:" -ForegroundColor Green
    Write-Host "  Local:    http://localhost:8000"
    Write-Host "  Network:  http://${computerName}:8000"
    Write-Host "  Direct:   http://${wslIP}:8000"
    Write-Host "  API Docs: http://localhost:8000/docs"
    
    # Test API health
    Write-Host "`nAPI Health Check:" -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
        Write-Host "  Status: HEALTHY" -ForegroundColor Green
        Write-Host "  Version: $($response.version)"
        Write-Host "  Uptime: $($response.uptime) seconds"
    }
    catch {
        Write-Host "  Status: UNHEALTHY" -ForegroundColor Red
        Write-Host "  Error: $($_.Exception.Message)"
    }
    
    Show-PortForwarding
}

# Show logs
function Show-Logs {
    Write-Host "Showing Video API logs (Ctrl+C to exit)..." -ForegroundColor Cyan
    wsl -d $Distribution --exec bash -c "cd ~/video-create && docker-compose logs -f"
}

# Health check
function Test-Health {
    Write-Host "Running comprehensive health check..." -ForegroundColor Cyan
    
    # Test WSL
    Write-Host "`n1. Testing WSL connectivity..." -ForegroundColor Yellow
    try {
        $wslTest = wsl -d $Distribution --exec echo "WSL OK"
        Write-Host "   ✅ WSL is accessible" -ForegroundColor Green
    }
    catch {
        Write-Host "   ❌ WSL is not accessible" -ForegroundColor Red
        return
    }
    
    # Test Docker
    Write-Host "`n2. Testing Docker..." -ForegroundColor Yellow
    $dockerTest = wsl -d $Distribution --exec bash -c "sudo service docker status"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Docker is running" -ForegroundColor Green
    }
    else {
        Write-Host "   ❌ Docker is not running" -ForegroundColor Red
    }
    
    # Test API
    Write-Host "`n3. Testing API..." -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
        Write-Host "   ✅ API is responding" -ForegroundColor Green
        Write-Host "   Status: $($response.status)"
    }
    catch {
        Write-Host "   ❌ API is not responding" -ForegroundColor Red
        Write-Host "   Error: $($_.Exception.Message)"
    }
    
    # Test network connectivity
    Write-Host "`n4. Testing network connectivity..." -ForegroundColor Yellow
    $portList = $Ports.Split(',')
    foreach ($port in $portList) {
        $port = $port.Trim()
        try {
            $connection = Test-NetConnection -ComputerName "localhost" -Port $port -WarningAction SilentlyContinue
            if ($connection.TcpTestSucceeded) {
                Write-Host "   ✅ Port $port is accessible" -ForegroundColor Green
            }
            else {
                Write-Host "   ❌ Port $port is not accessible" -ForegroundColor Red
            }
        }
        catch {
            Write-Host "   ❌ Cannot test port $port" -ForegroundColor Red
        }
    }
    
    Write-Host "`nHealth check completed." -ForegroundColor Cyan
}

# Update system
function Update-System {
    Write-Host "Updating WSL and Video API..." -ForegroundColor Cyan
    
    # Update WSL system
    Write-Host "`n1. Updating WSL system packages..." -ForegroundColor Yellow
    wsl -d $Distribution --exec bash -c "sudo apt update && sudo apt upgrade -y"
    
    # Update Docker images
    Write-Host "`n2. Updating Docker images..." -ForegroundColor Yellow
    wsl -d $Distribution --exec bash -c "cd ~/video-create && docker-compose pull"
    
    # Restart services
    Write-Host "`n3. Restarting services..." -ForegroundColor Yellow
    wsl -d $Distribution --exec bash -c "cd ~/video-create && docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d"
    
    Write-Host "`nUpdate completed!" -ForegroundColor Green
    Test-Health
}

# Backup data
function Backup-Data {
    $backupDir = "C:\VideoAPI-Backup"
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = "$backupDir\backup-$timestamp"
    
    Write-Host "Creating backup..." -ForegroundColor Cyan
    
    # Create backup directory
    New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
    
    # Export WSL distribution
    Write-Host "Backing up WSL distribution..."
    wsl --export $Distribution "$backupPath\wsl-distribution.tar"
    
    # Backup application data
    Write-Host "Backing up application data..."
    wsl -d $Distribution --exec bash -c "cd ~/video-create && tar -czf /mnt/c/temp/video-api-data.tar.gz data/ .env.prod docker-compose*.yml"
    Move-Item "C:\temp\video-api-data.tar.gz" "$backupPath\video-api-data.tar.gz"
    
    Write-Host "Backup completed: $backupPath" -ForegroundColor Green
    Get-ChildItem $backupPath | Format-Table Name, Length, LastWriteTime
}

# Show help
function Show-Help {
    Write-Host "Video Creation API - WSL Management Script" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "USAGE:" -ForegroundColor Yellow
    Write-Host "  .\manage-wsl.ps1 [command] [options]"
    Write-Host ""
    Write-Host "COMMANDS:" -ForegroundColor Yellow
    Write-Host "  start         Start Video API services"
    Write-Host "  stop          Stop Video API services"
    Write-Host "  restart       Restart Video API services"
    Write-Host "  status        Show current status"
    Write-Host "  logs          Show real-time logs"
    Write-Host "  health        Run health check"
    Write-Host "  update        Update system and services"
    Write-Host "  backup        Create backup"
    Write-Host ""
    Write-Host "  ports         Setup port forwarding"
    Write-Host "  ports-show    Show current port forwarding"
    Write-Host "  ports-clear   Clear all port forwarding"
    Write-Host "  firewall      Configure Windows Firewall"
    Write-Host ""
    Write-Host "OPTIONS:" -ForegroundColor Yellow
    Write-Host "  -Distribution WSL distribution name (default: Ubuntu-22.04)"
    Write-Host "  -Ports        Comma-separated ports (default: 80,443,8000,9090)"
    Write-Host ""
    Write-Host "EXAMPLES:" -ForegroundColor Green
    Write-Host "  .\manage-wsl.ps1 start"
    Write-Host "  .\manage-wsl.ps1 status"
    Write-Host "  .\manage-wsl.ps1 ports -Ports '8000,9090'"
    Write-Host "  .\manage-wsl.ps1 health"
    Write-Host ""
    Write-Host "NOTES:" -ForegroundColor Cyan
    Write-Host "  - Run as Administrator for port forwarding and firewall configuration"
    Write-Host "  - Ensure WSL2 and Docker are installed in the WSL distribution"
    Write-Host "  - Video API project should be located at ~/video-create in WSL"
}

# Main command handler
switch ($Command.ToLower()) {
    "start" { Start-VideoAPI }
    "stop" { Stop-VideoAPI }
    "restart" { Restart-VideoAPI }
    "status" { Show-Status }
    "logs" { Show-Logs }
    "health" { Test-Health }
    "update" { Update-System }
    "backup" { Backup-Data }
    "ports" { Set-PortForwarding }
    "ports-show" { Show-PortForwarding }
    "ports-clear" { Remove-PortForwarding }
    "firewall" { Set-FirewallRules }
    "help" { Show-Help }
    default { 
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host "Use '.\manage-wsl.ps1 help' for available commands"
    }
}
