#!/bin/bash
# =================================================================================
# Скрипт для настройки Nginx как реверс-прокси для Docker-приложения за Cloudflare
# =================================================================================
#
# Что он делает:
# 1. Читает конфигурацию (домен, порты) напрямую из файла .env.
# 2. Устанавливает и настраивает файрвол UFW.
# 3. Устанавливает Nginx.
# 4. Создает конфиг для Nginx, который правильно работает с Cloudflare (восстанавливает реальный IP).
# 5. Создает конфиг для вашего сайта, проксируя запросы к вебхукам и файловому кешу в Docker.
#
# Использование:
# Просто запустите из корня проекта:
# sudo bash setup_nginx.sh
#

# --- Начало скрипта ---

set -e

# 1. Проверка прав root
if [ "$(id -u)" -ne 0 ]; then
  echo "Пожалуйста, запустите этот скрипт от имени root или с помощью sudo."
  exit 1
fi

# 2. Проверка наличия .env файла и загрузка переменных
ENV_FILE="./.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "ОШИБКА: Файл .env не найден. Запустите скрипт из корневой папки проекта."
    exit 1
fi

# Загружаем переменные из .env файла надежным способом
set -a
source $ENV_FILE
set +a

# Проверяем, что необходимые переменные загрузились
if [ -z "$WEBHOOK__ADDRESS" ] || [ -z "$WEBHOOK__LISTENING_PORT" ] || [ -z "$PROXY__LISTENING_PORT" ]; then
    echo "ОШИБКА: Убедитесь, что в .env файле заданы WEBHOOK__ADDRESS, WEBHOOK__LISTENING_PORT и PROXY__LISTENING_PORT."
    exit 1
fi

# Извлекаем домен из полного адреса вебхука
DOMAIN=$(echo "$WEBHOOK__ADDRESS" | sed -e 's|^[^/]*//||' -e 's|/.*$||')

echo "--- Настройка Nginx для домена $DOMAIN (под Cloudflare) ---"
echo "Порт вебхуков: $WEBHOOK__LISTENING_PORT"
echo "Порт файлового прокси: $PROXY__LISTENING_PORT"

# 3. Установка Nginx и UFW
echo "[1/5] Установка Nginx..."
apt-get update -qq > /dev/null
apt-get install -y -qq nginx > /dev/null
echo "Nginx установлен."

echo "[2/5] Настройка файрвола UFW..."
ufw allow ssh > /dev/null
ufw allow 'Nginx HTTP' > /dev/null # Открываем ТОЛЬКО порт 80
ufw --force enable > /dev/null
echo "Файрвол настроен."

# 4. Настройка Nginx для работы с реальными IP от Cloudflare
echo "[3/5] Настройка получения реального IP от Cloudflare..."
CF_IP_FILE="/etc/nginx/conf.d/cloudflare.conf"
cat > $CF_IP_FILE <<EOF
# Cloudflare IP ranges
# Этот файл позволяет Nginx видеть реальный IP-адрес посетителя, а не IP Cloudflare.

set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;

real_ip_header CF-Connecting-IP;
EOF
echo "Файл с IP-адресами Cloudflare создан."

# 5. Создание основного конфигурационного файла и лимитов
echo "[4/5] Создание конфигурационного файла и лимитов для $DOMAIN..."
SITE_CONFIG_FILE="/etc/nginx/sites-available/$DOMAIN"

# Базовый rate-limit (в контексте http)
cat > /etc/nginx/conf.d/limits.conf <<'EOF_LIM'
limit_req_zone $binary_remote_addr zone=perip:10m rate=5r/s;
EOF_LIM

cat > $SITE_CONFIG_FILE <<EOF
server {
    listen 80;
    listen [::]:80;

    server_name $DOMAIN;

    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # Убираем экранирование у переменной $DOMAIN, чтобы bash подставил ее значение
    if (\$host != $DOMAIN) { return 444; }
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    # Путь для вебхуков Telegram
    location /tg/webhooks/ {
        # --- ИЗМЕНЕНИЕ: Упрощаем proxy_pass ---
        # Просто передаем на базовый адрес нашего aiohttp сервера.
        # Nginx автоматически добавит URI запроса (/tg/webhooks/bot/ID).
        proxy_pass http://127.0.0.1:$WEBHOOK__LISTENING_PORT;
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        if (\$request_method != POST) { return 405; }
        if (\$http_x_telegram_bot_api_secret_token != "$WEBHOOK__SECRET_TOKEN") { return 403; }

        limit_req zone=perip burst=10 nodelay;
        client_max_body_size 30m;
    }

    # Путь для нашего файлового кеша
    location /file_cache/ {
        proxy_pass http://127.0.0.1:$PROXY__LISTENING_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        if (\$request_method !~ ^(GET|HEAD)$) { return 405; }

        limit_req zone=perip burst=20 nodelay;
    }

    location / { return 444; }
}
EOF
echo "Конфигурационный файл сайта создан."

# 6. Активация конфигурации и перезапуск Nginx
echo "[5/5] Активация конфигурации и перезапуск Nginx..."
if [ -L /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
fi
ln -s -f $SITE_CONFIG_FILE /etc/nginx/sites-enabled/

nginx -t
if [ $? -eq 0 ]; then
    systemctl restart nginx
    echo "--- Настройка Nginx успешно завершена! ---"
else
    echo "ОШИБКА: Конфигурация Nginx содержит ошибки. Проверьте файлы."
    exit 1
fi
