"""
OBS WEBSOCKET LISTENER - слушатель событий OBS для Content Forge

ЧТО ДЕЛАЕТ:
- Подключается к OBS WebSocket серверу
- Слушает события RecordingStopped и StreamingStopped
- Запускает обработку контента при остановке записи/трансляции

ГДЕ ИСПОЛЬЗУЕТСЯ:
- Запускается как отдельный процесс/сервер
- Работает в паре с OBS Studio

ИСПОЛЬЗУЕТ:
- External: obswebsocket (pip install obs-websocket)
"""
import asyncio
import os
import sys
from pathlib import Path
from obswebsocket import obsws, events
from obswebsocket.core import exceptions

# OBS WebSocket настройки
OBS_HOST = os.getenv("OBS_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")

# Путь к обработчикам (для локального запуска)
HANDLER_PATH = Path(__file__).parent.parent.parent.parent / "Desktop" / "obs_recording_handler" / "main.py"


class OBSWebSocketListener:
    """Слушатель событий OBS WebSocket"""

    def __init__(self, host: str = OBS_HOST, port: int = OBS_PORT, password: str = OBS_PASSWORD):
        self.host = host
        self.port = port
        self.password = password
        self.ws = None

    async def connect(self) -> bool:
        """Подключается к OBS WebSocket"""
        try:
            if self.password:
                self.ws = obsws(self.host, self.port, self.password)
            else:
                self.ws = obsws(self.host, self.port)

            await self.ws.connect()
            print(f"✅ Подключено к OBS WebSocket: {self.host}:{self.port}")
            return True
        except exceptions.ConnectionFailure:
            print(f"❌ Не удалось подключиться к OBS: {self.host}:{self.port}")
            print("Убедитесь, что obs-websocket сервер запущен в OBS")
            return False
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False

    async def on_recording_stopped(self, event):
        """Обработчик остановки записи"""
        recording_path = getattr(event, 'recording_path', None) or getattr(event, 'output_recording_path', None)
        if recording_path:
            print(f"📹 Запись остановлена: {recording_path}")
            await self._run_handler('on_recording_stopped', recording_path)
        else:
            print("⚠️  Событие RecordingStopped получено, но путь к файлу отсутствует")

    async def on_streaming_stopped(self, event):
        """Обработчик остановки трансляции"""
        # StreamingStopped может содержать путь к записи трансляции
        recording_path = getattr(event, 'output_recording_path', None)
        if recording_path:
            print(f"🎬 Трансляция остановлена, запись: {recording_path}")
            await self._run_handler('on_streaming_stopped', recording_path)
        else:
            print("🎬 Трансляция остановлена (запись не найдена)")

    async def _run_handler(self, handler_name: str, recording_path: str):
        """Запускает обработчик в отдельном процессе"""
        import subprocess

        print(f"🚀 Запуск обработчика: {handler_name}")

        # Запускаем Python скрипт обработчика в отдельном процессе
        # Текстовый интерфейс будет запущен в новом терминале
        if sys.platform == "darwin":  # macOS
            # На macOS открываем новый терминальное окно
            cmd = [
                "osascript",
                "-e",
                f'tell application "Terminal" to do script "cd "{os.getcwd()}" && python3 "{HANDLER_PATH}" "{recording_path}" activate end script"'
            ]
            subprocess.Popen(cmd)
        elif sys.platform == "linux":
            # На Linux открываем новое окно терминала
            subprocess.Popen([
                "gnome-terminal",
                "--", "python3", str(HANDLER_PATH), recording_path
            ])
        else:
            # Windows или fallback - запускаем в фоне
            subprocess.Popen([
                sys.executable, str(HANDLER_PATH), recording_path
            ])

    async def listen(self):
        """Основной цикл прослушивания событий"""
        if not await self.connect():
            return

        # Регистрируем обработчики событий
        self.ws.register(self.on_recording_stopped, events.RecordingStopped)
        self.ws.register(self.on_streaming_stopped, events.StreamingStopped)

        print("🎧 Слушаю события OBS (RecordingStopped, StreamingStopped)...")
        print("Нажмите Ctrl+C для остановки")

        try:
            # Держим соединение активным
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Остановка слушателя...")
        finally:
            if self.ws:
                await self.ws.disconnect()


async def main():
    """Точка входа"""
    listener = OBSWebSocketListener()
    await listener.listen()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✋ Прервано пользователем")
