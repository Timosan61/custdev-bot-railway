import os
from typing import Dict, List, Optional
from uuid import UUID
from supabase import create_client, Client
from loguru import logger
from postgrest.exceptions import APIError

class SupabaseService:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self.client: Client = create_client(url, key)
        logger.info("Supabase client initialized")
    
    def create_interview(self, fields: Dict) -> Optional[Dict]:
        """Create a new interview with the provided fields"""
        try:
            # Extract researcher_telegram_id if provided
            researcher_id = fields.pop("researcher_telegram_id", None)
            
            data = {
                "status": "draft",
                "fields": fields
            }
            
            # Add researcher_telegram_id at top level
            if researcher_id:
                data["researcher_telegram_id"] = researcher_id
            
            logger.info(f"Creating interview with data: {data}")
            
            result = self.client.table("interviews").insert(data).execute()
            return result.data[0] if result.data else None
        except APIError as e:
            logger.error(f"Supabase API error creating interview: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating interview: {e}")
            raise
    
    def update_interview(self, interview_id: str, data: Dict) -> Optional[Dict]:
        try:
            logger.info(f"Updating interview {interview_id} with data keys: {list(data.keys())}")
            result = self.client.table("interviews").update(data).eq(
                "id", interview_id
            ).execute()
            logger.info(f"Interview {interview_id} updated successfully")
            return result.data[0] if result.data else None
        except APIError as e:
            logger.error(f"Supabase API error updating interview {interview_id}: {e.message}")
            logger.error(f"Error details: {e.json if hasattr(e, 'json') else str(e)}")
            # Более детальная информация об ошибке
            if hasattr(e, 'code'):
                logger.error(f"Error code: {e.code}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating interview {interview_id}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            raise
    
    def get_interview(self, interview_id: str) -> Optional[Dict]:
        try:
            result = self.client.table("interviews").select("*").eq(
                "id", interview_id
            ).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting interview: {e}")
            return None
    
    def create_session(self, user_id: int, session_type: str, 
                           interview_id: Optional[str] = None) -> Optional[Dict]:
        try:
            data = {
                "user_id": user_id,
                "session_type": session_type,
                "state": {}
            }
            if interview_id:
                data["interview_id"] = interview_id
            
            logger.info(f"Creating session for user {user_id} with type {session_type}")
            result = self.client.table("user_sessions").insert(data).execute()
            return result.data[0] if result.data else None
        except APIError as e:
            logger.error(f"Supabase API error creating session for user {user_id}: {e.message}")
            logger.error(f"Error details: {e.json if hasattr(e, 'json') else str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating session for user {user_id}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            raise
    
    def update_session(self, session_id: str, state_update: Dict) -> Optional[Dict]:
        try:
            # Получаем текущую сессию
            current = self.client.table("user_sessions").select("*").eq("id", session_id).execute()
            if not current.data:
                logger.error(f"Session {session_id} not found")
                return None
            
            # Обновляем state, объединяя с существующим
            current_state = current.data[0].get("state", {})
            current_state.update(state_update)
            
            result = self.client.table("user_sessions").update({
                "state": current_state
            }).eq("id", session_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            raise
    
    def get_active_session(self, user_id: int) -> Optional[Dict]:
        try:
            result = self.client.table("user_sessions").select("*").eq(
                "user_id", user_id
            ).order("created_at", desc=True).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def save_answer(self, interview_id: str, user_id: int, 
                         question: str, answer: str) -> Optional[Dict]:
        """Save respondent's answer to the database
        
        Note: Currently not used as answers are stored in user_sessions.answers
        """
        try:
            logger.info(f"Saving answer for interview {interview_id}, user {user_id}")
            result = self.client.table("respondent_answers").insert({
                "interview_id": interview_id,
                "user_id": user_id,
                "question_text": question,
                "answer_text": answer
            }).execute()
            logger.info(f"Answer saved successfully for interview {interview_id}")
            return result.data[0] if result.data else None
        except APIError as e:
            logger.error(f"Supabase API error saving answer for interview {interview_id}: {e.message}")
            logger.error(f"Error details: {e.json if hasattr(e, 'json') else str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving answer for interview {interview_id}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            raise
    
    def get_interview_answers(self, interview_id: str) -> List[Dict]:
        try:
            result = self.client.table("respondent_answers").select("*").eq(
                "interview_id", interview_id
            ).order("created_at").execute()
            return result.data
        except Exception as e:
            logger.error(f"Error getting answers: {e}")
            return []
    
