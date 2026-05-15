from abc import ABC, abstractmethod
from backend.services.prompts.strategies import (
    DEFAULT_EXTRACTION_PROMPT, DEFAULT_SYNTHESIS_PROMPT,
    TECH_EXTRACTION_PROMPT, TECH_SYNTHESIS_PROMPT,
    EDUCATION_EXTRACTION_PROMPT, EDUCATION_SYNTHESIS_PROMPT,
    BUSINESS_EXTRACTION_PROMPT, BUSINESS_SYNTHESIS_PROMPT,
    CONTENT_CREATION_EXTRACTION_PROMPT, CONTENT_CREATION_SYNTHESIS_PROMPT
)

class AnalysisStrategy(ABC):
    @abstractmethod
    def get_extraction_prompt(self) -> str:
        pass
        
    @abstractmethod
    def get_synthesis_prompt(self, metadata: str, visual_observations: str, transcript: str, web_context: str) -> str:
        pass

class TechTutorialStrategy(AnalysisStrategy):
    def get_extraction_prompt(self) -> str:
        return TECH_EXTRACTION_PROMPT
        
    def get_synthesis_prompt(self, metadata: str, visual_observations: str, transcript: str, web_context: str) -> str:
        return TECH_SYNTHESIS_PROMPT.format(
            metadata=metadata,
            visual_observations=visual_observations,
            transcript=transcript,
            web_context=web_context
        )

class EducationStrategy(AnalysisStrategy):
    def get_extraction_prompt(self) -> str:
        return EDUCATION_EXTRACTION_PROMPT
        
    def get_synthesis_prompt(self, metadata: str, visual_observations: str, transcript: str, web_context: str) -> str:
        return EDUCATION_SYNTHESIS_PROMPT.format(
            metadata=metadata,
            visual_observations=visual_observations,
            transcript=transcript,
            web_context=web_context
        )

class BusinessStrategy(AnalysisStrategy):
    def get_extraction_prompt(self) -> str:
        return BUSINESS_EXTRACTION_PROMPT
        
    def get_synthesis_prompt(self, metadata: str, visual_observations: str, transcript: str, web_context: str) -> str:
        return BUSINESS_SYNTHESIS_PROMPT.format(
            metadata=metadata,
            visual_observations=visual_observations,
            transcript=transcript,
            web_context=web_context
        )

class ContentCreationStrategy(AnalysisStrategy):
    def get_extraction_prompt(self) -> str:
        return CONTENT_CREATION_EXTRACTION_PROMPT
        
    def get_synthesis_prompt(self, metadata: str, visual_observations: str, transcript: str, web_context: str) -> str:
        return CONTENT_CREATION_SYNTHESIS_PROMPT.format(
            metadata=metadata,
            visual_observations=visual_observations,
            transcript=transcript,
            web_context=web_context
        )

class DefaultStrategy(AnalysisStrategy):
    def get_extraction_prompt(self) -> str:
        return DEFAULT_EXTRACTION_PROMPT
        
    def get_synthesis_prompt(self, metadata: str, visual_observations: str, transcript: str, web_context: str) -> str:
        return DEFAULT_SYNTHESIS_PROMPT.format(
            metadata=metadata,
            visual_observations=visual_observations,
            transcript=transcript,
            web_context=web_context
        )

def get_strategy_for_category(category: str) -> AnalysisStrategy:
    """Return the specific prompt strategy for the given database category."""
    category = category.upper()
    if "TECHNOLOGY" in category:
        return TechTutorialStrategy()
    elif "AI & MACHINE LEARNING" in category or "AI AND MACHINE" in category:
        # AI tools used for BUILDING — use default (not tech tutorial, which expects code)
        return DefaultStrategy()
    elif "CONTENT CREATION" in category:
        return ContentCreationStrategy()
    elif "BUSINESS STRATEGY" in category or "MARKETING" in category:
        return BusinessStrategy()
    elif "SOCIAL MEDIA" in category:
        return BusinessStrategy()  # Close enough for social media creator content
    elif "EDUCATION" in category:
        return EducationStrategy()
    else:
        return DefaultStrategy()
