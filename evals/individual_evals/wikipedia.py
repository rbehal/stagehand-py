from typing import List
from pydantic import BaseModel
from stagehand import Stagehand

class WikipediaContent(BaseModel):
    title: str
    summary: str
    sections: List[str]

def run_wikipedia_eval():
    stagehand = Stagehand(env="LOCAL")
    stagehand.init()
    
    try:
        stagehand.driver.get("https://en.wikipedia.org/wiki/Baseball")
        
        stagehand.act("click the 'hit and run' link in this article")

        current_url = stagehand.driver.current_url
        expected_url = "https://en.wikipedia.org/wiki/Hit_and_run_(baseball)";
        
        print(f"Current URL is: {current_url}")
        print(f"Expected URL is: {expected_url}")
        
        return True
    except Exception as e:
        print(f"Error in wikipedia eval: {str(e)}")
        return False
    finally:
        stagehand.driver.quit()
