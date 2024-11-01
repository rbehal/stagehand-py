import os
import json
import tempfile
import requests
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from typing import Callable, Optional, Dict, Any, get_origin, get_args

from langchain_core.utils.function_calling import convert_pydantic_to_openai_function as langchain_convert_pydantic_to_openai_function

from selenium import webdriver
from selenium_stealth import stealth
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.remote_connection import RemoteConnection

from .logger import get_default_logger

def is_list_of_basemodel(type_hint) -> bool:
    """Check if a type hint is List[BaseModel]"""
    origin = get_origin(type_hint)
    if origin is not None and origin is list:
        args = get_args(type_hint)
        if len(args) == 1 and isinstance(args[0], type) and issubclass(args[0], BaseModel):
            return True
    return False

def convert_pydantic_to_openai_function(
    model: type,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    rm_titles: bool = True,
):
    # Handle List[BaseModel] case
    if is_list_of_basemodel(model):
        base_model = get_args(model)[0]
        # Convert the base model first
        base_schema = convert_pydantic_to_openai_function(
            base_model,
            name=name,
            description=description,
            rm_titles=rm_titles
        )
        
        # Create array schema
        array_schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": base_schema["parameters"]
                }
            },
            "required": ["items"],
            "additionalProperties": False
        }
        
        return {
            "name": name or base_model.__name__,
            "description": description or f"List of {base_model.__name__} objects",
            "parameters": array_schema
        }
    
    # Original case for single BaseModel
    langchain_response = langchain_convert_pydantic_to_openai_function(
        model,
        name=name,
        description=description,
        rm_titles=rm_titles
    )
    
    # OpenAI does not support 'default' kwarg, which is present in langchain converted schema
    def remove_defaults(obj):
        if isinstance(obj, dict):
            if "default" in obj:
                del obj["default"]
            for value in obj.values():
                remove_defaults(value)
        elif isinstance(obj, list):
            for item in obj:
                remove_defaults(item)
        return obj
    
    openai_function = remove_defaults(langchain_response)
    
    # Add required fields
    required_fields = list(openai_function['parameters']["properties"].keys())
    openai_function['parameters']["required"] = required_fields
    
    # Add additional properties
    openai_function['parameters']['additionalProperties'] = False
    
    return openai_function

def get_json_response_format(schema: type, name: str) -> Dict[str, Any]:
    openai_function_parameters = convert_pydantic_to_openai_function(schema)["parameters"]
    
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": openai_function_parameters,
            "strict": True
        }
    }

def get_browser(
    env: str = "LOCAL",
    headless: bool = False,
    logger: Callable = get_default_logger('browser')
) -> Dict[str, Any]:
    """Initialize and return a browser instance based on environment settings."""
    
    if env == "BROWSERBASE":
        if not os.getenv("BROWSERBASE_API_KEY"):
            logger.warning("BROWSERBASE_API_KEY is required to use BROWSERBASE env. Defaulting to LOCAL.")
            env = "LOCAL"
            
        if not os.getenv("BROWSERBASE_PROJECT_ID"):
            logger.warning("BROWSERBASE_PROJECT_ID is required to use BROWSERBASE env. Defaulting to LOCAL.")
            env = "LOCAL"

    if env == "BROWSERBASE":
        response = requests.post(
            "https://www.browserbase.com/v1/sessions",
            headers={
                "x-bb-api-key": os.environ.get('BROWSERBASE_API_KEY'),
                "Content-Type": "application/json",
            },
            json={"projectId": os.environ.get('BROWSERBASE_PROJECT_ID')},
        )

        session = response.json()

        class BrowserbaseRemoteConnection(RemoteConnection):
            def get_remote_connection_headers(self, parsed_url, keep_alive=False):
                # Call the super method to get the default headers
                headers = super().get_remote_connection_headers(parsed_url, keep_alive)

                # Add the Browserbase headers
                headers["session-id"] = session["id"] 
                headers["x-bb-api-key"] = os.environ.get('BROWSERBASE_API_KEY')
                headers["enable-proxy"] = "true"

                return headers

        # This is needed to direct the Webdriver at the correct browser port
        options = webdriver.ChromeOptions()
        options.debugger_address = "localhost:9223"
        # Create Browserbase remote driver
        driver = webdriver.Remote(
            command_executor=BrowserbaseRemoteConnection("http://connect.browserbase.com/webdriver"),
            options=options,
        )

        return {"driver": driver}
    
    else:
        logger.info(f"Launching local browser in {'headless' if headless else 'headed'} mode")

        # Setup Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        
        chrome_options.add_argument("--window-size=1250,800")
        chrome_options.add_argument("--enable-webgl")
        chrome_options.add_argument("--use-gl=swiftshader")
        chrome_options.add_argument("--enable-accelerated-2d-canvas")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Create temp directory for user data
        tmp_dir = tempfile.mkdtemp(prefix="selenium_test")
        user_data_dir = Path(tmp_dir) / "userdir"
        user_data_dir.mkdir(parents=True)
        
        # Set default preferences
        default_preferences = {
            "plugins": {
                "always_open_pdf_externally": True
            }
        }
        
        prefs_path = user_data_dir / "Default"
        prefs_path.mkdir(parents=True)
        with open(prefs_path / "Preferences", "w") as f:
            json.dump(default_preferences, f)

        # Setup downloads directory
        downloads_path = Path.cwd() / "downloads"
        downloads_path.mkdir(exist_ok=True)
        
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        
        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Apply stealth scripts
        stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        
        logger.info("Local browser started successfully.")
        
        return {"driver": driver}
