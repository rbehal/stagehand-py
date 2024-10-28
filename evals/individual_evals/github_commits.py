import traceback

from typing import List
from pydantic import BaseModel
from stagehand import Stagehand

class Commit(BaseModel):
    message: str
    author: str
    date: str
    hash: str | None

def run_github_commits_eval():
    stagehand = Stagehand(env="LOCAL")
    
    try:
        stagehand.goto("https://github.com/facebook/react")

        stagehand.act("go to commit history, generally described by the number of commits")
        
        commits = stagehand.extract(
            instruction="Extract the last 20 commits with their messages, authors, and dates",
            schema=List[Commit],
            use_vision=True
        )
        
        print(f"Successfully extracted {len(commits)} commits")
        for commit in commits:
            print(f"{commit['date']}: {commit['message']} by {commit['author']}")
            
        return True
    except Exception as e:
        print(f"Error in github commits eval: {str(e)}")
        print(f"Stacktrace:\n{traceback.format_exc()}")
        return False
    finally:
        stagehand.driver.quit()
