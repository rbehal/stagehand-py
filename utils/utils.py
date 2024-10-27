import os
import json
import tempfile
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Any, Callable

from selenium import webdriver
from selenium_stealth import stealth
from selenium.webdriver.chrome.options import Options

from .logger import get_default_logger

def get_json_response_format(schema: BaseModel, name: str) -> Dict[str, Any]:
    return {
        "type": "json_object", 
        "schema": schema.model_json_schema()
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
        # Note: Implementation for Browserbase would need their Python SDK
        raise NotImplementedError("Browserbase integration not yet implemented for Python")
    
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
