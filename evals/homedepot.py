from pydantic import BaseModel
from stagehand import Stagehand

class ProductSpecs(BaseModel):
    burnerBTU: str | None

def run_homedepot_eval():
    stagehand = Stagehand(env="LOCAL")
    stagehand.init()
    
    try:
        stagehand.driver.get("https://www.homedepot.com/")

        stagehand.act("search for gas grills")

        stagehand.act("click on the best selling gas grill")

        stagehand.act("click on the Product Details")

        stagehand.act("find the Primary Burner BTU")

        productSpecs = stagehand.extract(
            instruction="Extract the Primary exact Burner BTU of the product",
            schema=ProductSpecs
        )
        
        print(f"The gas grill primary burner BTU is {productSpecs.burnerBTU}")

        return True
    except Exception as e:
        print(f"Error in Home Depot eval: {str(e)}")
        return False
    finally:
        stagehand.page.close()
