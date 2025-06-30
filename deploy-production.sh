#!/bin/bash

# Production deployment script for Video Creation API
# Usage: ./deploy-production.sh

set -e

echo "🚀 Video Creation API - Production Deployment"
echo "=============================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ Don't run this script as root for security reasons"
   exit 1
fi

# Configuration
DOMAIN=${DOMAIN:-""}
SSL_ENABLED=${SSL_ENABLED:-"false"}
ENVIRONMENT=${ENVIRONMENT:-"production"}

echo "📋 Deployment Configuration:"
echo "   Domain: ${DOMAIN:-"Not set - will use IP"}"
echo "   SSL: ${SSL_ENABLED}"
echo "   Environment: ${ENVIRONMENT}"
echo ""

# Validate domain for production
if [[ "$ENVIRONMENT" == "production" && -z "$DOMAIN" ]]; then
    read -p "⚠️  No domain set. Enter your domain name (e.g., api.yourdomain.com): " DOMAIN
    if [[ -z "$DOMAIN" ]]; then
        echo "❌ Domain is required for production deployment"
        exit 1
    fi
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/{temp,logs,cache}
mkdir -p nginx/ssl
mkdir -p monitoring
mkdir -p backups

# Setup environment file
if [[ ! -f .env.prod ]]; then
    echo "⚙️  Creating production environment file..."
    cp .env.template .env.prod
    
    # Update domain in .env.prod
    if [[ -n "$DOMAIN" ]]; then
        sed -i "s/DOMAIN=your-domain.com/DOMAIN=${DOMAIN}/g" .env.prod
        sed -i "s|API_BASE_URL=https://your-domain.com|API_BASE_URL=https://${DOMAIN}|g" .env.prod
    fi
    
    echo "📝 Please edit .env.prod with your production settings"
    echo "   Especially update: DOMAIN, SSL_ENABLED, NGROK_AUTHTOKEN"
    
    read -p "Press Enter after editing .env.prod to continue..."
fi

# SSL Certificate setup
if [[ "$SSL_ENABLED" == "true" ]]; then
    echo "🔒 SSL Certificate Setup"
    
    if [[ ! -f "nginx/ssl/cert.pem" || ! -f "nginx/ssl/key.pem" ]]; then
        echo "⚠️  SSL certificates not found!"
        echo "Options:"
        echo "1. Generate self-signed certificate (for testing)"
        echo "2. Use Let's Encrypt (recommended for production)"
        echo "3. Upload your own certificates"
        
        read -p "Choose option (1-3): " ssl_option
        
        case $ssl_option in
            1)
                echo "🔧 Generating self-signed certificate..."
                openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                    -keyout nginx/ssl/key.pem \
                    -out nginx/ssl/cert.pem \
                    -subj "/C=US/ST=State/L=City/O=Organization/CN=${DOMAIN}"
                ;;
            2)
                echo "📖 For Let's Encrypt, run these commands after deployment:"
                echo "   docker run --rm -v \$(pwd)/nginx/ssl:/etc/letsencrypt/live/${DOMAIN} \\"
                echo "     certbot/certbot certonly --standalone -d ${DOMAIN}"
                echo ""
                echo "🔧 Using self-signed certificate for now..."
                openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                    -keyout nginx/ssl/key.pem \
                    -out nginx/ssl/cert.pem \
                    -subj "/C=US/ST=State/L=City/O=Organization/CN=${DOMAIN}"
                ;;
            3)
                echo "📁 Place your certificates in nginx/ssl/ as:"
                echo "   nginx/ssl/cert.pem (certificate)"
                echo "   nginx/ssl/key.pem (private key)"
                read -p "Press Enter after placing certificates..."
                ;;
        esac
    fi
fi

# Build and deploy
echo "🔨 Building Docker images..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

echo "🚀 Starting production services..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 30

# Health check
echo "🔍 Running health checks..."
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ HTTP health check passed"
else
    echo "❌ HTTP health check failed"
fi

if [[ "$SSL_ENABLED" == "true" ]] && curl -f -k https://localhost/health > /dev/null 2>&1; then
    echo "✅ HTTPS health check passed"
elif [[ "$SSL_ENABLED" == "true" ]]; then
    echo "❌ HTTPS health check failed"
fi

# Display access information
echo ""
echo "🎉 Deployment completed!"
echo "========================"

if [[ -n "$DOMAIN" ]]; then
    echo "🌐 API Access URLs:"
    echo "   HTTP:  http://${DOMAIN}"
    if [[ "$SSL_ENABLED" == "true" ]]; then
        echo "   HTTPS: https://${DOMAIN}"
    fi
    echo "   Health: http://${DOMAIN}/health"
    echo "   Docs:   http://${DOMAIN}/docs"
else
    echo "🌐 API Access URLs (using server IP):"
    SERVER_IP=$(curl -s http://checkip.amazonaws.com || echo "YOUR_SERVER_IP")
    echo "   HTTP:  http://${SERVER_IP}"
    if [[ "$SSL_ENABLED" == "true" ]]; then
        echo "   HTTPS: https://${SERVER_IP}"
    fi
    echo "   Health: http://${SERVER_IP}/health"
    echo "   Docs:   http://${SERVER_IP}/docs"
fi

echo ""
echo "📊 Monitoring:"
echo "   Prometheus: http://localhost:9090"
echo ""
echo "🔧 Management:"
echo "   View logs: docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
echo "   Stop:      docker-compose -f docker-compose.yml -f docker-compose.prod.yml down"
echo "   Restart:   docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart"
echo ""
echo "📝 Next steps:"
echo "1. Update DNS records to point to this server"
echo "2. Configure firewall to allow ports 80, 443"
echo "3. Setup monitoring alerts"
echo "4. Configure backup schedules"
echo ""
echo "🔒 Security checklist:"
echo "- [ ] Firewall configured"
echo "- [ ] SSL certificates valid"
echo "- [ ] Environment variables secured"
echo "- [ ] Regular backups scheduled"
echo "- [ ] Monitoring alerts configured"
