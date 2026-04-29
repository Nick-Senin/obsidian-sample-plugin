#!/bin/bash
# OBS WebSocket Listener - запуск скрипта

# Перейти в директорию скрипта
cd "$(dirname "$0")"

# Активировать виртуальное окружение если есть
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Установить зависимости если нужно
if ! python3 -c "import obswebsocket" 2>/dev/null; then
    echo "📦 Установка obswebsocket..."
    pip3 install obswebsocket
fi

# Запустить слушателя
echo "🎬 Запуск OBS WebSocket Listener..."
python3 listener.py "$@"
