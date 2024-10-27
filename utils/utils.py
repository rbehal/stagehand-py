from typing import Dict, Any
from pydantic import BaseModel

from selenium import webdriver
from selenium_stealth import stealth
from selenium.webdriver.chrome.options import Options

def get_json_response_format(schema: BaseModel, name: str) -> Dict[str, Any]:
    return {
        "type": "json_object", 
        "schema": schema.model_json_schema()
    }

def get_selenium_driver() -> webdriver.Chrome:
    """
    Creates and returns a selenium webdriver with stealth settings to avoid detection
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    return driver
