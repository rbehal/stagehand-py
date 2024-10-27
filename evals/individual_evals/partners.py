import os
from dataclasses import dataclass
from typing import Dict, Any, List

from utils.logger import EvalLogger

from stagehand import Stagehand

@dataclass
class Partner:
    name: str
    explanation: str

def extract_partners() -> Dict[str, Any]:
    logger = EvalLogger()
    
    stagehand = Stagehand(
        env=os.environ.get('ENVIRONMENT', 'LOCAL'),
        verbose=2,
        debug_dom=True,
        headless=os.environ.get('HEADLESS', 'true').lower() != 'false',
        logger=lambda message: logger.log(message['message'])
    )

    logger.init(stagehand)
    
    browser_info = stagehand.init(model_name="gpt-4")
    debug_url = browser_info.get("debug_url")
    session_url = browser_info.get("session_url")

    try:
        stagehand.driver.get("https://ramp.com")

        stagehand.act(action="Close the popup.")

        stagehand.act(action="Scroll down to the bottom of the page.")

        stagehand.act(
            action="Click on the link or button that leads to the partners page. If it's in a dropdown or hidden section, first interact with the element to reveal it, then click the link."
        )

        partners = stagehand.extract(
            instruction="""
            Extract the names of all partner companies mentioned on this page.
            These could be inside text, links, or images representing partner companies.
            If no specific partner names are found, look for any sections or categories of partners mentioned.
            Also, check for any text that explains why partner names might not be listed, if applicable.
            """,
            schema=List[Partner]
        )

        expected_partners = [
            "Accounting Partners",
            "Private Equity & Venture Capital Partners", 
            "Services Partners",
            "Affiliates"
        ]

        if partners.get("explanation"):
            logger.log(f"Explanation: {partners['explanation']}")

        found_partners = [p["name"].lower() for p in partners["partners"]]
        
        all_expected_found = all(
            p.lower() in found_partners for p in expected_partners
        )

        logger.log(f"All expected partners found: {all_expected_found}")
        logger.log(f"Expected: {expected_partners}")
        logger.log(f"Found: {found_partners}")

        return {
            "_success": all_expected_found,
            "partners": partners,
            "debug_url": debug_url,
            "session_url": session_url,
            "logs": logger.get_logs()
        }

    except Exception as error:
        logger.error(
            f"Error in extract_partners function: {str(error)}\nTrace: {error.__traceback__}"
        )
        return {
            "_success": False,
            "debug_url": debug_url,
            "session_url": session_url,
            "error": str(error),
            "logs": logger.get_logs()
        }

    finally:
        stagehand.driver.quit()
