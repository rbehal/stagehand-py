from pydantic import BaseModel
from stagehand import Stagehand

class JobPosting(BaseModel):
    class Qualifications(BaseModel):
        degree: str
        yearsOfExperience: int

    applicationDeadline: str | None
    minimumQualifications: Qualifications | None
    preferredQualifications: Qualifications | None

def run_google_jobs_eval():
    stagehand = Stagehand(env="LOCAL")
    stagehand.init()
    
    try:
        stagehand.driver.get("https://www.google.com")

        stagehand.act("click on the about page")

        stagehand.act("click on the careers page")

        stagehand.act("input data scientist into role")

        stagehand.act("input new york city into location")

        stagehand.act("click on the search button")

        stagehand.act("click on the first job link")

        job_posting = stagehand.extract(
            instruction="Extract the following details from the job posting: application deadline, minimum qualifications (degree and years of experience), and preferred qualifications (degree and years of experience)",
            schema=JobPosting
        )

        print(f"Job Details: {job_posting}")
            
        return True
    except Exception as e:
        print(f"Error in google jobs eval: {str(e)}")
        return False
    finally:
        stagehand.page.close()
