@echo off
REM Production deployment script for Video Creation API (Windows)
REM Usage: deploy-production.bat

echo 🚀 Video Creation API - Production Deployment
echo ==============================================

REM Check if Docker is running
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running or not installed
    pause
    exit /b 1
)

REM Configuration
set /p DOMAIN=Enter your domain name (e.g., api.yourdomain.com): 
if "%DOMAIN%"=="" (
    echo ❌ Domain is required for production deployment
    pause
    exit /b 1
)

echo 📋 Deployment Configuration:
echo    Domain: %DOMAIN%
echo    Environment: production
echo.

REM Create necessary directories
echo 📁 Creating directories...
if not exist "data\temp" mkdir data\temp
if not exist "data\logs" mkdir data\logs
if not exist "data\cache" mkdir data\cache
if not exist "nginx\ssl" mkdir nginx\ssl
if not exist "monitoring" mkdir monitoring
if not exist "backups" mkdir backups

REM Setup environment file
if not exist ".env.prod" (
    echo ⚙️ Creating production environment file...
    copy .env.template .env.prod
    
    echo 📝 Please edit .env.prod with your production settings
    echo    Especially update: DOMAIN, SSL_ENABLED, NGROK_AUTHTOKEN
    echo.
    echo Opening .env.prod for editing...
    notepad .env.prod
    
    pause
)

REM SSL Certificate setup
echo 🔒 SSL Certificate Setup
if not exist "nginx\ssl\cert.pem" (
    echo ⚠️ SSL certificates not found!
    echo Generating self-signed certificate for testing...
    
    REM Generate self-signed certificate using OpenSSL (if available)
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx\ssl\key.pem -out nginx\ssl\cert.pem -subj "/C=US/ST=State/L=City/O=Organization/CN=%DOMAIN%"
    
    if errorlevel 1 (
        echo ❌ OpenSSL not found. Please:
        echo 1. Install OpenSSL
        echo 2. Or place your SSL certificates in nginx\ssl\ as:
        echo    - nginx\ssl\cert.pem (certificate)
        echo    - nginx\ssl\key.pem (private key)
        pause
    )
)

REM Build and deploy
echo 🔨 Building Docker images...
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

if errorlevel 1 (
    echo ❌ Build failed
    pause
    exit /b 1
)

echo 🚀 Starting production services...
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d

if errorlevel 1 (
    echo ❌ Deployment failed
    pause
    exit /b 1
)

REM Wait for services to be healthy
echo ⏳ Waiting for services to be healthy...
timeout /t 30 /nobreak

REM Health check
echo 🔍 Running health checks...
curl -f http://localhost/health
if errorlevel 1 (
    echo ❌ Health check failed
) else (
    echo ✅ Health check passed
)

REM Display access information
echo.
echo 🎉 Deployment completed!
echo ========================
echo.
echo 🌐 API Access URLs:
echo    HTTP:  http://%DOMAIN%
echo    HTTPS: https://%DOMAIN%
echo    Health: http://%DOMAIN%/health
echo    Docs:   http://%DOMAIN%/docs
echo.
echo 📊 Monitoring:
echo    Prometheus: http://localhost:9090
echo.
echo 🔧 Management Commands:
echo    View logs: docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
echo    Stop:      docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
echo    Restart:   docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart
echo.
echo 📝 Next steps:
echo 1. Update DNS records to point %DOMAIN% to this server
echo 2. Configure firewall to allow ports 80, 443  
echo 3. Setup monitoring alerts
echo 4. Configure backup schedules
echo.

pause
