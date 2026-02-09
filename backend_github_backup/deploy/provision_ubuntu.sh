#!/bin/bash
# Script de provisionamento para servidor Ubuntu
# Executa como root (sudo)

set -e

# Atualizar sistema
apt update && apt upgrade -y

# Instalar dependências básicas
apt install -y python3 python3-venv python3-pip git nginx ufw fail2ban certbot python3-certbot-nginx

# Configurar firewall
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# Clonar projeto (ajuste para seu repo)
# git clone https://github.com/seuusuario/easya-agenda.git /opt/easya-backend
# cd /opt/easya-backend/Backend

# Criar e ativar virtualenv
python3 -m venv /opt/easya-backend/venv
source /opt/easya-backend/venv/bin/activate

# Instalar dependências Python
pip install --upgrade pip
pip install -r /opt/easya-backend/Backend/requirements.txt

# Configurar Nginx (templates no repositório)
# - API:   Backend/deploy/nginx_api.conf
# - APP:   Backend/deploy/nginx_app_frontend.conf
#
# Exemplo (ajuste YOUR_DOMAIN_HERE dentro dos arquivos):
# cp /opt/easya-backend/Backend/deploy/nginx_api.conf /etc/nginx/sites-available/easya-api.conf
# ln -s /etc/nginx/sites-available/easya-api.conf /etc/nginx/sites-enabled/
#
# cp /opt/easya-backend/Backend/deploy/nginx_app_frontend.conf /etc/nginx/sites-available/easya-app.conf
# ln -s /etc/nginx/sites-available/easya-app.conf /etc/nginx/sites-enabled/
#
# nginx -t && systemctl restart nginx

# Obter certificado TLS (subdomínios recomendados: app.* e api.*)
# certbot --nginx -d app.seudominio.com
# certbot --nginx -d api.seudominio.com

# Configurar serviço systemd
# Importante: em produção defina ENV=production e um SECRET_KEY forte
# Veja Backend/.env.production.example
# cp /opt/easya-backend/Backend/deploy/easya-backend.service /etc/systemd/system/
# systemctl daemon-reload
# systemctl enable easya-backend
# systemctl start easya-backend

# Configurar fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# Pronto! Backend provisionado com segurança e pronto para deploy.