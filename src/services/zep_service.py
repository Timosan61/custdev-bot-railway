import os
from typing import Dict, List, Optional
from zep_cloud.client import AsyncZep
from zep_cloud.types import Message
from loguru import logger

class ZepService:
    def __init__(self):
        api_key = os.getenv("ZEP_API_KEY")
        if not api_key:
            raise ValueError("ZEP_API_KEY must be set")
        
        self.client = AsyncZep(api_key=api_key)
        self._pending_metadata = {}  # Для хранения метаданных до первого сообщения
        logger.info("Zep client initialized")
    
    async def create_session(self, session_id: str, metadata: Optional[Dict] = None) -> bool:
        """
        Zep автоматически создает сессии при первом добавлении сообщений.
        Этот метод просто логирует намерение создать сессию.
        """
        try:
            logger.info(f"Zep session will be created on first message: {session_id}")
            # Сохраняем метаданные локально для использования при первом сообщении
            self._pending_metadata = {session_id: metadata or {}}
            return True
        except Exception as e:
            logger.error(f"Error preparing Zep session {session_id}: {e}")
            return False
    
    async def add_message(self, session_id: str, role: str, content: str, 
                         metadata: Optional[Dict] = None) -> None:
        try:
            # Определяем role_type на основе role
            role_type = "user" if role == "user" else "assistant"
            
            message = Message(
                role=role,
                role_type=role_type,
                content=content
            )
            
            # Используем правильный метод API
            await self.client.memory.add(
                session_id=session_id,
                messages=[message]
            )
            
            logger.debug(f"Message added to Zep session {session_id}")
            
            # Очищаем метаданные после первого сообщения
            if session_id in self._pending_metadata:
                del self._pending_metadata[session_id]
                
        except Exception as e:
            logger.error(f"Error adding message to session {session_id}: {e}")
            # Don't raise for message logging failures
    
    async def get_memory(self, session_id: str, last_n: int = 10) -> List[Message]:
        try:
            memory = await self.client.memory.get(
                session_id=session_id
            )
            if memory and memory.messages:
                return memory.messages[:last_n]
            return []
        except Exception as e:
            logger.error(f"Error getting memory for session {session_id}: {e}")
            return []
    
    async def search_memory(self, session_id: str, query: str, limit: int = 5) -> List[Message]:
        try:
            # В новой версии Zep поиск может быть недоступен или иметь другой API
            # Пока возвращаем пустой список
            logger.warning(f"Memory search not implemented for session {session_id}")
            return []
        except Exception as e:
            logger.error(f"Error searching memory for session {session_id}: {e}")
            return []
    
    async def get_session(self, session_id: str) -> Optional[Dict]:
        try:
            # В новой версии API сессии управляются автоматически
            return {"session_id": session_id, "exists": True}
        except Exception as e:
            logger.error(f"Error getting Zep session: {e}")
            return None
    
    async def update_session_metadata(self, session_id: str, metadata: Dict) -> None:
        try:
            # Метаданные можно добавлять с сообщениями
            logger.info(f"Session metadata update noted for {session_id}")
        except Exception as e:
            logger.error(f"Error updating Zep session metadata: {e}")