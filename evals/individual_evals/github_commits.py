from pydantic import BaseModel
from stagehand import Stagehand

class Commit(BaseModel):
    message: str
    author: str
    date: str
    hash: str | None

def run_github_commits_eval():
    stagehand = Stagehand(env="LOCAL")
    stagehand.init()
    
    try:
        stagehand.driver.get("https://github.com/facebook/react")

        stagehand.act("find commit history, generally described by the number of commits")
        
        commits = stagehand.extract(
            instruction="Extract the last 20 commits with their messages, authors, and dates",
            schema=Commit
        )
        
        print(f"Successfully extracted {len(commits)} commits")
        for commit in commits[:5]:
            print(f"{commit.date}: {commit.message} by {commit.author}")
            
        return True
    except Exception as e:
        print(f"Error in github commits eval: {str(e)}")
        return False
    finally:
        stagehand.driver.quit()
