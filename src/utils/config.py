import os
from typing import Optional
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    # Telegram
    telegram_bot_token: str
    
    # OpenAI
    openai_api_key: str
    
    # Zep Cloud
    zep_api_key: str
    
    # Supabase
    supabase_url: str
    supabase_key: str
    
    # Bot Settings
    bot_environment: str = "development"
    log_level: str = "INFO"
    max_message_length: int = 4096
    
    # LangChain Settings
    langchain_model: str = "gpt-4o"
    langchain_temperature: float = 0.7
    langchain_max_tokens: int = 2000
    
    class Config:
        env_file = ".env"
        case_sensitive = False

def get_config() -> Config:
    return Config()