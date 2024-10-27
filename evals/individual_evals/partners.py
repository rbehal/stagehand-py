import os
from dataclasses import dataclass
from typing import Dict, Any, List

from stagehand import Stagehand

@dataclass
class Partner:
    name: str
    explanation: str

def run_partners_eval() -> Dict[str, Any]:
    stagehand = Stagehand()

    try:
        stagehand.goto("https://ramp.com")

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
            print(f"Explanation: {partners['explanation']}")

        found_partners = [p["name"].lower() for p in partners["partners"]]
        
        all_expected_found = all(
            p.lower() in found_partners for p in expected_partners
        )

        print(f"All expected partners found: {all_expected_found}")
        print(f"Expected: {expected_partners}")
        print(f"Found: {found_partners}")

    finally:
        stagehand.driver.quit()
