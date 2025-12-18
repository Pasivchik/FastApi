from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from sqlalchemy.future import select

import models
import schemas
from database import engine, session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield
    # Clean up the ML models and release the resources
    await session.close()
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.get("/recipes/", response_model=List[schemas.RecipesOut])
async def recipes() -> List[models.Recipes]:
    query = select(models.Recipes).order_by(
        models.Recipes.views.desc(), models.Recipes.cooking_time.asc()
    )

    res = await session.execute(query)
    return res.scalars().all()


@app.get("/recipes/{recipe_id}", response_model=schemas.RecipesOut)
async def recipes(recipe_id: int) -> Optional[schemas.RecipesOut]:
    result = await session.execute(
        select(models.Recipes).where(models.Recipes.id == recipe_id)
    )
    recipe = result.scalar_one_or_none()

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe.views += 1

    try:
        await session.commit()
        await session.refresh(recipe)
    except Exception as e:
        await session.rollback()
        print(f"Error updating view count: {e}")

    return recipe


@app.post("/recipes/", response_model=schemas.RecipesOut)
async def add_recipes(recipe: schemas.RecipesIn) -> models.Recipes:
    new_recipe = models.Recipes(**recipe.model_dump())
    async with session.begin():
        session.add(new_recipe)
    return new_recipe
