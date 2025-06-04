# Инструкция по деплою Spin Bot v2.6.0 на VDS сервер

## Требования

- VDS сервер с Ubuntu 20.04 или выше
- Python 3.11 или выше
- PostgreSQL 12 или выше
- Nginx
- Certbot для SSL сертификатов

## Подготовка сервера

1. Обновите систему:

```bash
sudo apt update && sudo apt upgrade -y
```

2. Установите необходимые пакеты:

```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip git nginx postgresql postgresql-contrib ufw
```

3. Установите uv (Astral):

```bash
pip install uv
```

4. Настройте брандмауэр:

```bash
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

5. Установите Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

## Клонирование репозитория

1. Клонируйте репозиторий в домашнюю директорию:

```bash
cd ~
git clone https://github.com/your-username/spin-bot.git
cd spin-bot
```

## Настройка окружения

1. Создайте виртуальное окружение и активируйте его:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

2. Установите зависимости:

```bash
uv pip install -e .
```

3. Создайте файл .env:

```bash
cp .env.example .env
nano .env
```

4. Отредактируйте файл .env, установив правильные значения:

```
# Основные настройки
DEBUG=False
BOT_TOKEN=your_bot_token_here
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=8000
WEBAPP_PUBLIC_URL=https://your-domain.com

# Настройки базы данных
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/spin_bot

# Настройки безопасности
SECRET_KEY=your_random_secret_key

# Настройки логирования
LOG_LEVEL=INFO
LOG_FILE=/var/log/spinbot.log

# Настройки игры
FREE_SPIN_INTERVAL=86400
INITIAL_TICKETS=1
MAX_WIN_PER_DAY=5000

# Обязательные каналы для подписки (через запятую)
REQUIRED_CHANNELS=@channel1,@channel2
```

## Настройка базы данных

1. Переключитесь на пользователя postgres:

```bash
sudo -i -u postgres
```

2. Создайте базу данных и пользователя:

```bash
createdb spin_bot
psql -c "CREATE USER postgres WITH PASSWORD 'your_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE spin_bot TO postgres;"
exit
```

3. Примените миграции:

```bash
python run_migrations.py
```

## Настройка systemd

1. Создайте файл службы systemd:

```bash
sudo nano /etc/systemd/system/spinbot.service
```

2. Вставьте следующую конфигурацию (замените пути и пользователя на свои):

```ini
[Unit]
Description=Spin Bot v2.6.0
After=network.target postgresql.service
Wants=postgresql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/spin-bot
ExecStart=/home/ubuntu/spin-bot/.venv/bin/python /home/ubuntu/spin-bot/main.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=/home/ubuntu/spin-bot

# Настройка логирования
StandardOutput=append:/var/log/spinbot.log
StandardError=append:/var/log/spinbot.error.log

# Ограничения ресурсов
CPUQuota=80%
MemoryLimit=1G

# Тайм-аут остановки
TimeoutStopSec=20

# Настройки безопасности
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
```

3. Создайте лог-файлы и установите права:

```bash
sudo touch /var/log/spinbot.log /var/log/spinbot.error.log
sudo chown ubuntu:ubuntu /var/log/spinbot.log /var/log/spinbot.error.log
```

4. Включите и запустите службу:

```bash
sudo systemctl daemon-reload
sudo systemctl enable spinbot.service
sudo systemctl start spinbot.service
```

## Настройка Nginx

1. Создайте конфигурационный файл Nginx:

```bash
sudo nano /etc/nginx/sites-available/spinbot.conf
```

2. Вставьте следующую конфигурацию (замените example.com на ваш домен):

```nginx
server {
    listen 80;
    server_name example.com;
    
    # Редирект на HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
    
    # Настройки для Let's Encrypt
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}

server {
    listen 443 ssl http2;
    server_name example.com;
    
    # SSL настройки (будут заполнены Certbot)
    # ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    
    # Оптимизация SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    
    # HSTS (Строгая транспортная безопасность HTTP)
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    
    # Другие заголовки безопасности
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-XSS-Protection "1; mode=block";
    
    # Проксирование запросов к FastAPI приложению
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Настройки WebSocket (если используются)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Тайм-ауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Настройки для статических файлов
    location /static/ {
        alias /home/ubuntu/spin-bot/src/webapp/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
        access_log off;
        
        # Gzip сжатие
        gzip on;
        gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript image/svg+xml;
        gzip_comp_level 6;
        gzip_min_length 1000;
    }
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 10M;
    
    # Логи
    access_log /var/log/nginx/spinbot-access.log;
    error_log /var/log/nginx/spinbot-error.log;
}
```

3. Создайте символическую ссылку и проверьте конфигурацию:

```bash
sudo ln -s /etc/nginx/sites-available/spinbot.conf /etc/nginx/sites-enabled/
sudo nginx -t
```

4. Если конфигурация корректна, перезапустите Nginx:

```bash
sudo systemctl restart nginx
```

## Настройка SSL с помощью Certbot

1. Получите SSL-сертификат:

```bash
sudo certbot --nginx -d example.com
```

2. Следуйте инструкциям Certbot для завершения настройки.

## Проверка работоспособности

1. Проверьте статус службы:

```bash
sudo systemctl status spinbot.service
```

2. Проверьте логи:

```bash
tail -f /var/log/spinbot.log
```

3. Откройте ваш домен в браузере и убедитесь, что веб-приложение работает.

## Обновление бота

1. Остановите службу:

```bash
sudo systemctl stop spinbot.service
```

2. Перейдите в директорию проекта и обновите код:

```bash
cd ~/spin-bot
git pull
```

3. Активируйте виртуальное окружение и обновите зависимости:

```bash
source .venv/bin/activate
uv pip install -e .
```

4. Примените миграции:

```bash
python run_migrations.py
```

5. Запустите службу:

```bash
sudo systemctl start spinbot.service
```

## Автоматическое обновление SSL-сертификатов

Certbot автоматически добавляет задание в cron для обновления сертификатов. Вы можете проверить это с помощью команды:

```bash
sudo systemctl status certbot.timer
```

## Резервное копирование

Регулярно создавайте резервные копии базы данных:

```bash
pg_dump -U postgres spin_bot > spin_bot_backup_$(date +%Y%m%d).sql
```

Также рекомендуется настроить автоматическое резервное копирование с помощью cron.

## Мониторинг

Для мониторинга производительности и доступности можно использовать такие инструменты, как:

- UptimeRobot для мониторинга доступности
- Prometheus + Grafana для мониторинга производительности
- Sentry для отслеживания ошибок

## Устранение неполадок

### Проблемы с запуском службы

Проверьте логи:

```bash
sudo journalctl -u spinbot.service
```

### Проблемы с Nginx

Проверьте логи Nginx:

```bash
sudo tail -f /var/log/nginx/error.log
```

### Проблемы с базой данных

Проверьте логи PostgreSQL:

```bash
sudo tail -f /var/log/postgresql/postgresql-*.log
``` 