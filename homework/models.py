from sqlalchemy import Column, String, Integer, Time
from database import Base


class Recipes(Base):
    __tablename__ = "Recipes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    views = Column(Integer, default=0)
    cooking_time = Column(Time, index=True)
    list_of_ingredients = Column(String, index=True)
    description = Column(String, index=True)
