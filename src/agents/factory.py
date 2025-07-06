import os
from typing import Union
from loguru import logger

from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService
from src.agents.base import BaseResearcherAgent, BaseRespondentAgent
from src.agents.direct import DirectResearcherAgent, DirectRespondentAgent


def create_researcher_agent(
    supabase: SupabaseService, 
    zep: ZepService,
    mode: str = None
) -> BaseResearcherAgent:
    """
    Factory function to create ResearcherAgent based on mode.
    
    Args:
        supabase: Supabase service instance
        zep: Zep service instance
        mode: Agent mode ("direct" or "n8n"). If None, reads from env
        
    Returns:
        ResearcherAgent instance
    """
    if mode is None:
        mode = os.getenv("AGENT_MODE", "direct").lower()
    
    logger.info(f"Creating ResearcherAgent in mode: {mode}")
    
    if mode == "direct":
        return DirectResearcherAgent(supabase, zep)
    elif mode == "n8n":
        # Lazy import to avoid circular dependencies
        from src.agents.n8n import N8nResearcherAgent
        return N8nResearcherAgent(supabase, zep)
    elif mode == "ai":
        # AI-powered n8n agent
        from src.agents.n8n.ai_researcher_agent import AIResearcherAgent
        return AIResearcherAgent(supabase, zep)
    else:
        logger.warning(f"Unknown agent mode: {mode}. Falling back to direct mode.")
        return DirectResearcherAgent(supabase, zep)


def create_respondent_agent(
    supabase: SupabaseService, 
    zep: ZepService,
    mode: str = None
) -> BaseRespondentAgent:
    """
    Factory function to create RespondentAgent based on mode.
    
    Args:
        supabase: Supabase service instance
        zep: Zep service instance
        mode: Agent mode ("direct" or "n8n"). If None, reads from env
        
    Returns:
        RespondentAgent instance
    """
    if mode is None:
        mode = os.getenv("AGENT_MODE", "direct").lower()
    
    logger.info(f"Creating RespondentAgent in mode: {mode}")
    
    if mode == "direct":
        return DirectRespondentAgent(supabase, zep)
    elif mode == "n8n":
        # Lazy import to avoid circular dependencies
        from src.agents.n8n import N8nRespondentAgent
        return N8nRespondentAgent(supabase, zep)
    elif mode == "ai":
        # AI-powered n8n agent
        from src.agents.n8n.ai_respondent_agent import AIRespondentAgent
        return AIRespondentAgent(supabase, zep)
    else:
        logger.warning(f"Unknown agent mode: {mode}. Falling back to direct mode.")
        return DirectRespondentAgent(supabase, zep)


# For backward compatibility - these will use the default mode from env
def create_agents(supabase: SupabaseService, zep: ZepService) -> tuple:
    """
    Create both agents using the default mode from environment.
    
    Returns:
        Tuple of (ResearcherAgent, RespondentAgent)
    """
    return (
        create_researcher_agent(supabase, zep),
        create_respondent_agent(supabase, zep)
    )