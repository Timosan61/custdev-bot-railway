"""
Модуль для обработки голосовых сообщений в Telegram боте

Основные функции:
- Скачивание голосовых файлов через Telegram Bot API
- Конвертация аудио форматов (OGG → MP3) с graceful fallback
- Автоматическая транскрибация через OpenAI Whisper API
- Обработка ошибок и таймаутов

Требования:
- Python 3.8+
- aiohttp, aiofiles для асинхронных операций
- pydub (опционально) для конвертации аудио
- openai для транскрибации
- FFmpeg (опционально) для конвертации аудио
"""

import os
import logging
import tempfile
import asyncio
from typing import Optional, Dict, Any, Union
import aiohttp
import aiofiles
from pathlib import Path

# Настройка логгера для данного модуля
logger = logging.getLogger(__name__)

class VoiceProcessingError(Exception):
    """Кастомное исключение для ошибок обработки голосовых сообщений"""
    pass

class VoiceMessageHandler:
    """
    Обработчик голосовых сообщений из Telegram
    
    Обеспечивает полный цикл обработки:
    1. Скачивание файла с Telegram серверов
    2. Конвертация аудио формата (опционально)
    3. Транскрибация через OpenAI Whisper
    
    Пример использования:
    ```python
    handler = VoiceMessageHandler(bot_token="your_token", openai_api_key="your_key")
    result = await handler.process_voice_message(file_id="voice_file_id", duration=10)
    if result["success"]:
        transcription = result["transcription"]
    ```
    """
    
    def __init__(self, bot_token: str, openai_api_key: Optional[str] = None):
        """
        Инициализирует обработчик голосовых сообщений
        
        Args:
            bot_token: Токен Telegram бота
            openai_api_key: API ключ OpenAI (опционально, можно в .env)
            
        Raises:
            ValueError: При отсутствии обязательных параметров
        """
        if not bot_token:
            raise ValueError("Отсутствует bot_token")
            
        self.bot_token = bot_token
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.telegram_api_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Константы для оптимизации
        self.MAX_FILE_SIZE_MB = 20  # Максимальный размер файла
        self.DOWNLOAD_TIMEOUT = 30  # Таймаут скачивания
        self.TRANSCRIPTION_TIMEOUT = 60  # Таймаут транскрибации
        
        # Проверка зависимостей
        self._check_dependencies()
        
    def _check_dependencies(self) -> None:
        """
        Проверяет наличие всех необходимых зависимостей
        и устанавливает флаги доступности
        """
        self.pydub_available = False
        self.openai_available = False
        
        # Проверка pydub для конвертации аудио
        try:
            from pydub import AudioSegment
            self.pydub_available = True
            logger.info("✅ pydub доступен для обработки аудио")
        except ImportError:
            logger.warning("⚠️  pydub не установлен. Конвертация аудио будет ограничена")
            
        # Проверка OpenAI для транскрибации
        try:
            from openai import OpenAI
            if self.openai_api_key:
                self.openai_available = True
                logger.info("✅ OpenAI доступен для транскрибации")
            else:
                logger.warning("⚠️  OpenAI API ключ не найден. Транскрибация недоступна")
        except ImportError:
            logger.warning("⚠️  Библиотека openai не установлена. Транскрибация недоступна")
        
        # Логируем общую информацию о возможностях
        if not self.openai_available:
            logger.error("❌ Отсутствуют критические зависимости для транскрибации")
    
    async def download_voice_file(self, file_id: str) -> Optional[bytes]:
        """Download voice file from Telegram servers"""
        try:
            # Get file path from Telegram
            async with aiohttp.ClientSession() as session:
                file_info_url = f"{self.telegram_api_url}/getFile?file_id={file_id}"
                async with session.get(file_info_url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to get file info: {resp.status}")
                        return None
                    
                    data = await resp.json()
                    if not data.get("ok"):
                        logger.error(f"Telegram API error: {data}")
                        return None
                    
                    file_path = data["result"]["file_path"]
                
                # Download the file
                download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                async with session.get(download_url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to download file: {resp.status}")
                        return None
                    
                    return await resp.read()
                    
        except Exception as e:
            logger.error(f"Error downloading voice file: {e}")
            return None
    
    async def convert_ogg_to_mp3(self, ogg_data: bytes) -> Optional[bytes]:
        """Convert OGG audio to MP3 format"""
        if not self.pydub_available:
            logger.warning("pydub not available, returning original OGG data")
            return ogg_data
        
        try:
            from pydub import AudioSegment
            
            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_file:
                ogg_path = ogg_file.name
                await self._write_file(ogg_path, ogg_data)
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
                mp3_path = mp3_file.name
            
            # Convert OGG to MP3
            audio = AudioSegment.from_ogg(ogg_path)
            audio.export(mp3_path, format="mp3")
            
            # Read the converted file
            async with aiofiles.open(mp3_path, 'rb') as f:
                mp3_data = await f.read()
            
            # Clean up temporary files
            os.unlink(ogg_path)
            os.unlink(mp3_path)
            
            return mp3_data
            
        except Exception as e:
            logger.error(f"Error converting audio: {e}")
            # Если конвертация не удалась, возвращаем оригинальные данные
            logger.warning("Conversion failed, returning original OGG data for direct transcription")
            return ogg_data
    
    async def transcribe_audio(self, audio_data: bytes, language: str = "ru") -> Optional[str]:
        """Transcribe audio using OpenAI Whisper API"""
        if not self.openai_available:
            logger.warning("OpenAI not available for transcription")
            return None
        
        try:
            from openai import OpenAI
            # Настраиваем клиент с таймаутом и меньшим количеством попыток
            client = OpenAI(
                api_key=self.openai_api_key,
                timeout=60.0,  # 60 секунд таймаут
                max_retries=1   # Только 1 повторная попытка
            )
            
            # Save audio to temporary file (OGG is fine for Whisper)
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                temp_path = temp_file.name
                await self._write_file(temp_path, audio_data)
            
            # Transcribe using Whisper with new API
            with open(temp_path, "rb") as audio_file:
                transcript = await asyncio.to_thread(
                    client.audio.transcriptions.create,
                    model="whisper-1",
                    file=audio_file,
                    language=language
                )
            
            # Clean up
            os.unlink(temp_path)
            
            return transcript.text.strip() if transcript.text else None
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None
    
    async def process_voice_message(self, file_id: str, duration: int = 0) -> Dict[str, Any]:
        """Process a complete voice message from Telegram"""
        result = {
            "success": False,
            "file_id": file_id,
            "duration": duration,
            "transcription": None,
            "error": None
        }
        
        try:
            # Download voice file
            logger.info(f"Downloading voice file: {file_id}")
            ogg_data = await self.download_voice_file(file_id)
            if not ogg_data:
                result["error"] = "Failed to download voice file"
                return result
            
            # Convert to MP3 (optional, fallback to OGG if fails)
            logger.info("Converting OGG to MP3 (optional)")
            mp3_data = await self.convert_ogg_to_mp3(ogg_data)
            if not mp3_data:
                logger.warning("Audio conversion failed, using original OGG")
                mp3_data = ogg_data
            
            # Transcribe audio (works with both MP3 and OGG)
            logger.info("Transcribing audio")
            transcription = await self.transcribe_audio(mp3_data)
            if transcription:
                result["success"] = True
                result["transcription"] = transcription
                logger.info(f"Transcription successful: {transcription[:50]}...")
            else:
                result["error"] = "Failed to transcribe audio"
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing voice message: {e}")
            result["error"] = str(e)
            return result
    
    async def _write_file(self, path: str, data: bytes):
        """Helper to write data to file asynchronously"""
        async with aiofiles.open(path, 'wb') as f:
            await f.write(data)