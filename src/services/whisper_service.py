import os
import io
from typing import Optional
from openai import AsyncOpenAI
from pydub import AudioSegment
from loguru import logger

class WhisperService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set")
        
        self.client = AsyncOpenAI(api_key=api_key)
        logger.info("Whisper service initialized")
    
    async def transcribe(self, audio_file: io.BytesIO) -> Optional[str]:
        try:
            # Convert OGG to MP3 (Whisper prefers standard formats)
            audio = AudioSegment.from_ogg(audio_file)
            mp3_buffer = io.BytesIO()
            audio.export(mp3_buffer, format="mp3")
            mp3_buffer.seek(0)
            
            # Transcribe with Whisper
            transcription = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.mp3", mp3_buffer, "audio/mp3"),
                language="ru"
            )
            
            logger.info(f"Transcribed: {transcription.text[:50]}...")
            return transcription.text
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None