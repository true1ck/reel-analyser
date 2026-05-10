import json

from backend.services.prompts.router_prompt import ROUTER_PROMPT

class VideoRouter:
    @staticmethod
    def classify(transcript: str, metadata: dict) -> str:
        """Classify the video type based on metadata and transcript snippet."""
        
        # Grab just enough transcript to know what the video is about (first 500 chars)
        transcript_snippet = transcript[:500] if transcript else "(No transcript)"
        
        # Format the prompt
        prompt = ROUTER_PROMPT.format(
            metadata=json.dumps(metadata, indent=2),
            transcript_snippet=transcript_snippet
        )
        
        try:
            from backend.services.analyzer import _run_text_pass
            # Ask the LLM (this is a fast text-only pass)
            category_response = _run_text_pass(prompt).strip().upper()
            
            # Clean up the response just in case the LLM added punctuation
            valid_categories = {
                "TECHNOLOGY": "Technology",
                "AI & MACHINE LEARNING": "AI & Machine Learning",
                "BUSINESS STRATEGY": "Business Strategy",
                "MARKETING": "Marketing",
                "SOCIAL MEDIA": "Social Media",
                "EDUCATION": "Education",
                "UNCATEGORIZED": "Uncategorized"
            }
            for valid_upper, valid_exact in valid_categories.items():
                if valid_upper in category_response:
                    return valid_exact
                    
            return "Uncategorized"
            
        except Exception as e:
            print(f"Router classification failed, falling back to Uncategorized: {e}")
            return "Uncategorized"
