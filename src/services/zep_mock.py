"""Mock Zep service for testing without Zep Cloud"""
from typing import Dict, List, Optional
from loguru import logger

class Message:
    def __init__(self, role: str, content: str, metadata: Dict = None):
        self.role = role
        self.content = content
        self.metadata = metadata or {}

class Session:
    def __init__(self, session_id: str, metadata: Dict = None):
        self.session_id = session_id
        self.metadata = metadata or {}

class ZepService:
    def __init__(self):
        logger.info("Zep mock service initialized")
        self.sessions = {}
        self.messages = {}
    
    async def create_session(self, session_id: str, metadata: Optional[Dict] = None) -> Optional[Session]:
        try:
            session = Session(session_id, metadata)
            self.sessions[session_id] = session
            self.messages[session_id] = []
            logger.info(f"Mock Zep session created: {session_id}")
            return session
        except Exception as e:
            logger.error(f"Error in mock Zep session: {e}")
            return None
    
    async def add_message(self, session_id: str, role: str, content: str, 
                         metadata: Optional[Dict] = None) -> None:
        try:
            if session_id not in self.messages:
                self.messages[session_id] = []
            
            message = Message(role, content, metadata)
            self.messages[session_id].append(message)
            logger.debug(f"Message added to session {session_id}")
        except Exception as e:
            logger.error(f"Error adding message to mock session: {e}")
    
    async def get_memory(self, session_id: str, last_n: int = 10) -> List[Message]:
        if session_id in self.messages:
            return self.messages[session_id][-last_n:]
        return []
    
    async def search_memory(self, session_id: str, query: str, limit: int = 5) -> List[Message]:
        # Simple mock search
        if session_id in self.messages:
            results = []
            for msg in self.messages[session_id]:
                if query.lower() in msg.content.lower():
                    results.append(msg)
                    if len(results) >= limit:
                        break
            return results
        return []
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)
    
    async def update_session_metadata(self, session_id: str, metadata: Dict) -> None:
        if session_id in self.sessions:
            self.sessions[session_id].metadata.update(metadata)