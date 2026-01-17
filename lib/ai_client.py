"""
AI Client for Google Gemini API (using new google.genai SDK)
"""
import os
from typing import Optional
from datetime import datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class AIClient:
    """Client for interacting with Google Gemini API"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-pro", verbose: bool = True):
        self.model_name = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.client = None
        self.chat = None
        self.verbose = verbose
        
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. Please set it:\n"
                "  export GEMINI_API_KEY='your-api-key'\n"
                "Get free key at: https://aistudio.google.com"
            )
        
        if genai is None:
            raise ImportError(
                "google-genai not installed. Run:\n"
                "  pip install google-genai"
            )
        
        self._initialize()
    
    def _initialize(self):
        """Initialize the Gemini API with new SDK"""
        self.client = genai.Client(api_key=self.api_key)
        self.chat = self.client.chats.create(model=self.model_name)
    
    def _log(self, message: str):
        """Log message if verbose mode is on"""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 🔵 {message}")
    
    def send_message(self, message: str) -> str:
        """Send a message and get a response (maintains chat history)"""
        try:
            # Log the full prompt being sent
            prompt_lines = message.split('\n')
            self._log(f"Sending prompt ({len(message):,} chars, {len(prompt_lines)} lines)")
            self._log("=" * 60)
            self._log("PROMPT MESSAGE:")
            self._log("=" * 60)
            print(message)  # Print full prompt
            self._log("=" * 60)
            
            start_time = datetime.now()
            response = self.chat.send_message(message)
            elapsed = (datetime.now() - start_time).total_seconds()
            
            self._log(f"Response received ({len(response.text):,} chars) in {elapsed:.1f}s")
            
            return response.text
        except Exception as e:
            self._log(f"ERROR: {str(e)}")
            return f"Error from AI: {str(e)}"
    
    def generate_once(self, prompt: str) -> str:
        """One-shot generation without chat history"""
        try:
            self._log(f"One-shot generation ({len(prompt):,} chars)")
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"Error from AI: {str(e)}"
    
    def reset_chat(self):
        """Reset the chat history"""
        self._log("Resetting chat history")
        self.chat = self.client.chats.create(model=self.model_name)


if __name__ == "__main__":
    # Test the client
    client = AIClient()
    response = client.send_message("Hello! Can you help me write tests?")
    print(response)
