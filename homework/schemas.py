from datetime import time
from pydantic import BaseModel
from pydantic import ConfigDict


class BaseRecipes(BaseModel):
    name: str
    cooking_time: time
    list_of_ingredients: str
    description: str


class RecipesIn(BaseRecipes):
    pass


class RecipesOut(BaseRecipes):
    id: int
    views: int

    model_config = ConfigDict(from_attributes=True)
