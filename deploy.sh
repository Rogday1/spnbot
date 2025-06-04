#!/bin/bash
set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ОШИБКА: $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ВНИМАНИЕ: $1${NC}"
}

# Установка uv
install_uv() {
    log "Установка uv (Astral)..."
    
    if command -v uv &> /dev/null; then
        log "uv уже установлен."
    else
        log "Скачивание и установка uv..."
        curl -sSf https://astral.sh/uv/install.sh | sh
        
        # Добавление uv в PATH для текущей сессии
        export PATH="$HOME/.cargo/bin:$PATH"
        
        if ! command -v uv &> /dev/null; then
            error "Не удалось установить uv. Пожалуйста, установите его вручную: https://astral.sh/uv"
        fi
    fi
    
    log "uv успешно установлен."
}

# Установка Python 3.11 с использованием uv
install_python() {
    log "Установка Python 3.11 с использованием uv..."
    
    # Проверка наличия Python 3.11
    if command -v python3.11 &> /dev/null; then
        log "Python 3.11 уже установлен."
    else
        # Установка Python 3.11 с помощью uv
        uv pip install python==3.11
        
        if ! command -v python3.11 &> /dev/null; then
            warning "Не удалось установить Python 3.11 через uv. Попытка установки через системный пакетный менеджер..."
            
            # Определение дистрибутива
            if [ -f /etc/debian_version ]; then
                # Debian/Ubuntu
                sudo apt update
                sudo apt install -y python3.11 python3.11-venv python3.11-dev
            elif [ -f /etc/redhat-release ]; then
                # CentOS/RHEL
                sudo dnf install -y python3.11 python3.11-devel
            else
                error "Не удалось определить дистрибутив Linux. Пожалуйста, установите Python 3.11 вручную."
            fi
        fi
    fi
    
    # Проверка версии Python
    if ! command -v python3.11 &> /dev/null; then
        error "Python 3.11 не установлен. Пожалуйста, установите его вручную."
    fi
    
    log "Python 3.11 успешно установлен."
}

# Проверка наличия необходимых утилит
check_requirements() {
    log "Проверка наличия необходимых утилит..."
    
    for cmd in git systemctl nginx; do
        if ! command -v $cmd &> /dev/null; then
            error "Команда '$cmd' не найдена. Пожалуйста, установите необходимое ПО."
        fi
    done
    
    # Проверка наличия PostgreSQL
    if ! command -v psql &> /dev/null; then
        warning "PostgreSQL не найден. Будет выполнена попытка его установки..."
        
        # Определение дистрибутива
        if [ -f /etc/debian_version ]; then
            # Debian/Ubuntu
            sudo apt update
            sudo apt install -y postgresql postgresql-contrib
        elif [ -f /etc/redhat-release ]; then
            # CentOS/RHEL
            sudo dnf install -y postgresql-server postgresql-contrib
            sudo postgresql-setup --initdb
            sudo systemctl enable postgresql
            sudo systemctl start postgresql
        else
            error "Не удалось определить дистрибутив Linux. Пожалуйста, установите PostgreSQL вручную."
        fi
    fi
    
    log "Все базовые утилиты установлены или будут установлены."
}

# Настройка переменных окружения
setup_env() {
    log "Настройка переменных окружения..."
    
    if [ ! -f .env ]; then
        if [ ! -f .env.example ]; then
            warning "Файл .env.example не найден. Создаю базовый .env файл."
            cat > .env << EOF
# Основные настройки
DEBUG=False
BOT_TOKEN=your_bot_token_here
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=8000
WEBAPP_PUBLIC_URL=https://your-domain.com

# Настройки базы данных
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/spin_bot

# Настройки безопасности
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Настройки игры
FREE_SPIN_INTERVAL=86400
INITIAL_TICKETS=1
MAX_WIN_PER_DAY=5000

# Обязательные каналы для подписки (через запятую)
REQUIRED_CHANNELS=@channel1,@channel2
EOF
            warning "Создан базовый .env файл. Пожалуйста, отредактируйте его и установите правильные значения."
            warning "Особенно важно установить BOT_TOKEN и WEBAPP_PUBLIC_URL."
            exit 1
        else
            cp .env.example .env
            warning "Файл .env создан из .env.example. Пожалуйста, отредактируйте его и установите правильные значения."
            warning "Особенно важно установить BOT_TOKEN и WEBAPP_PUBLIC_URL."
            exit 1
        fi
    else
        log "Файл .env уже существует."
    fi
}

# Установка зависимостей
install_dependencies() {
    log "Установка зависимостей проекта..."
    
    # Создание виртуального окружения, если его нет
    if [ ! -d .venv ]; then
        log "Создание виртуального окружения..."
        python3 -m venv .venv
    fi
    
    # Активация виртуального окружения
    source .venv/bin/activate
    
    # Установка зависимостей с использованием uv для ускорения
    log "Установка зависимостей с использованием uv..."
    uv pip install -e .
    
    log "Зависимости успешно установлены."
}

# Настройка базы данных PostgreSQL
setup_database() {
    log "Настройка базы данных PostgreSQL..."
    
    # Получение параметров подключения из .env
    source <(grep -v '^#' .env | sed -E 's/(.*)=(.*)/\1="\2"/')
    
    # Извлечение параметров из DATABASE_URL
    if [[ $DATABASE_URL =~ postgresql://([^:]+):([^@]+)@([^:]+):([^/]+)/(.+) ]]; then
        DB_USER="${BASH_REMATCH[1]}"
        DB_PASS="${BASH_REMATCH[2]}"
        DB_HOST="${BASH_REMATCH[3]}"
        DB_PORT="${BASH_REMATCH[4]}"
        DB_NAME="${BASH_REMATCH[5]}"
        
        # Проверка существования базы данных
        if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
            log "База данных $DB_NAME уже существует."
        else
            log "Создание базы данных $DB_NAME..."
            sudo -u postgres createdb "$DB_NAME"
            log "База данных $DB_NAME создана."
        fi
        
        # Проверка существования пользователя
        if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
            log "Пользователь $DB_USER уже существует."
        else
            log "Создание пользователя $DB_USER..."
            sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
            log "Пользователь $DB_USER создан."
        fi
        
        # Назначение прав
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
        log "Права на базу данных $DB_NAME назначены пользователю $DB_USER."
    else
        error "Некорректный формат DATABASE_URL в .env файле."
    fi
}

# Применение миграций базы данных
run_migrations() {
    log "Применение миграций базы данных..."
    
    # Активация виртуального окружения
    source .venv/bin/activate
    
    # Запуск миграций
    python run_migrations.py
    
    log "Миграции успешно применены."
}

# Настройка systemd службы
setup_systemd() {
    log "Настройка systemd службы..."
    
    # Получение текущего пути
    CURRENT_DIR=$(pwd)
    
    # Создание файла службы
    sudo tee /etc/systemd/system/spinbot.service > /dev/null << EOF
[Unit]
Description=Spin Bot v2.6.0
After=network.target postgresql.service
Wants=postgresql.service

[Service]
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/.venv/bin/python $CURRENT_DIR/main.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=$CURRENT_DIR

# Настройка логирования
StandardOutput=append:/var/log/spinbot.log
StandardError=append:/var/log/spinbot.error.log

# Ограничения ресурсов
CPUQuota=80%
MemoryLimit=2G

[Install]
WantedBy=multi-user.target
EOF
    
    # Перезагрузка конфигурации systemd
    sudo systemctl daemon-reload
    
    # Включение автозапуска службы
    sudo systemctl enable spinbot.service
    
    log "Служба systemd настроена. Для запуска выполните: sudo systemctl start spinbot.service"
}

# Настройка Nginx
setup_nginx() {
    log "Настройка Nginx..."
    
    # Получение домена из .env
    source <(grep -v '^#' .env | sed -E 's/(.*)=(.*)/\1="\2"/')
    
    if [[ $WEBAPP_PUBLIC_URL =~ https://([^/]+) ]]; then
        DOMAIN="${BASH_REMATCH[1]}"
    else
        warning "Не удалось извлечь домен из WEBAPP_PUBLIC_URL. Используется значение по умолчанию: example.com"
        DOMAIN="example.com"
    fi
    
    # Создание конфигурации Nginx
    sudo tee /etc/nginx/sites-available/spinbot.conf > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name $DOMAIN;
    
    # SSL настройки будут добавлены Certbot
    
    location / {
        proxy_pass http://localhost:$WEBAPP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Настройки для статических файлов
    location /static/ {
        alias $CURRENT_DIR/src/webapp/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 10M;
}
EOF
    
    # Создание символической ссылки
    if [ ! -L /etc/nginx/sites-enabled/spinbot.conf ]; then
        sudo ln -s /etc/nginx/sites-available/spinbot.conf /etc/nginx/sites-enabled/
    fi
    
    # Проверка конфигурации Nginx
    sudo nginx -t
    
    # Перезапуск Nginx
    sudo systemctl restart nginx
    
    log "Nginx настроен. Теперь можно получить SSL-сертификат с помощью Certbot:"
    log "sudo certbot --nginx -d $DOMAIN"
}

# Основная функция
main() {
    log "Начало процесса деплоя Spin Bot v2.6.0..."
    
    check_requirements
    install_uv
    install_python
    setup_env
    install_dependencies
    setup_database
    run_migrations
    setup_systemd
    setup_nginx
    
    log "Деплой успешно завершен!"
    log "Для запуска бота выполните: sudo systemctl start spinbot.service"
    log "Для проверки статуса: sudo systemctl status spinbot.service"
    log "Для получения SSL-сертификата: sudo certbot --nginx -d your-domain.com"
}

# Запуск основной функции
main 