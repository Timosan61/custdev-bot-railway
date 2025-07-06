# Agents module

# Import factory functions
from .factory import create_researcher_agent, create_respondent_agent, create_agents

# For backward compatibility - keep the original imports
# This way existing code that imports the classes directly will still work
from .researcher_agent import ResearcherAgent
from .respondent_agent import RespondentAgent

__all__ = [
    'ResearcherAgent', 
    'RespondentAgent',
    'create_researcher_agent',
    'create_respondent_agent',
    'create_agents'
]