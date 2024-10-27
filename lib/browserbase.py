import os
import httpx
from pydantic import BaseModel

class SessionResponse(BaseModel):
    id: str

class DebugResponse(BaseModel):
    debugger_fullscreen_url: str

class BrowserbaseError(Exception):
    pass

class Browserbase:
    def __init__(self):
        self.base_url = "https://www.browserbase.com/v1"
        self.api_key = os.getenv("BROWSERBASE_API_KEY")
        if not self.api_key:
            raise ValueError("BROWSERBASE_API_KEY environment variable is not set")

    def create_session(self) -> dict:
        """Create a new Browserbase session."""
        project_id = os.getenv("BROWSERBASE_PROJECT_ID")
        headers = {
            "x-bb-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {}
        if project_id:
            payload["projectId"] = project_id

        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/sessions",
                headers=headers,
                json=payload
            )
            
            data = response.json()
            if "error" in data:
                raise BrowserbaseError(data["error"])
            
            session = SessionResponse(**data)
            return {"sessionId": session.id}

    def retrieve_debug_connection_url(self, session_id: str) -> str:
        """Retrieve debug connection URL for a session."""
        headers = {
            "x-bb-api-key": self.api_key
        }

        with httpx.Client() as client:
            response = client.get(
                f"{self.base_url}/sessions/{session_id}/debug",
                headers=headers
            )
            
            data = response.json()
            debug_response = DebugResponse(**data)
            return debug_response.debugger_fullscreen_url
