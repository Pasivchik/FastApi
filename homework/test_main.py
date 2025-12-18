import pytest
import pytest_asyncio
from datetime import time
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from routers import app
from database import Base
import models

# Тестовая база данных в памяти
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_db():
    """Создание тестовой базы данных для каждого теста"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_db, monkeypatch):
    """HTTP клиент для тестирования"""
    # Подменяем глобальную сессию на тестовую
    monkeypatch.setattr("routers.session", test_db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def sample_recipes(test_db):
    """Создание тестовых рецептов"""
    recipes = [
        models.Recipes(
            name="Паста Карбонара",
            cooking_time=time(0, 30, 0),
            list_of_ingredients="паста, яйца, бекон, пармезан, перец",
            description="Классический итальянский рецепт",
            views=100,
        ),
        models.Recipes(
            name="Борщ",
            cooking_time=time(1, 30, 0),
            list_of_ingredients="свекла, капуста, картофель, мясо, морковь",
            description="Традиционный украинский суп",
            views=200,
        ),
        models.Recipes(
            name="Омлет",
            cooking_time=time(0, 10, 0),
            list_of_ingredients="яйца, молоко, соль, масло",
            description="Быстрый завтрак",
            views=50,
        ),
    ]

    for recipe in recipes:
        test_db.add(recipe)
    await test_db.commit()

    return recipes


class TestGetRecipes:
    """Тесты для получения списка рецептов"""

    @pytest.mark.asyncio
    async def test_get_recipes_empty(self, client):
        """Тест получения пустого списка рецептов"""
        response = await client.get("/recipes/")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_recipes_with_data(self, client, sample_recipes):
        """Тест получения списка рецептов с данными"""
        response = await client.get("/recipes/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_recipes_sorted_by_views_and_time(self, client, sample_recipes):
        """Тест сортировки рецептов по просмотрам (desc) и времени (asc)"""
        response = await client.get("/recipes/")
        assert response.status_code == 200
        data = response.json()

        # Проверяем порядок: сначала по убыванию просмотров
        assert data[0]["name"] == "Борщ"  # 200 просмотров
        assert data[1]["name"] == "Паста Карбонара"  # 100 просмотров
        assert data[2]["name"] == "Омлет"  # 50 просмотров


class TestGetRecipeById:
    """Тесты для получения рецепта по ID"""

    @pytest.mark.asyncio
    async def test_get_recipe_by_id_success(self, client, sample_recipes):
        """Тест успешного получения рецепта по ID"""
        response = await client.get("/recipes/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Паста Карбонара"
        assert "cooking_time" in data
        assert "list_of_ingredients" in data

    @pytest.mark.asyncio
    async def test_get_recipe_by_id_not_found(self, client):
        """Тест получения несуществующего рецепта"""
        response = await client.get("/recipes/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Recipe not found"

    @pytest.mark.asyncio
    async def test_get_recipe_increments_views(self, client, sample_recipes, test_db):
        """Тест увеличения счетчика просмотров"""
        # Первый запрос
        response1 = await client.get("/recipes/1")
        assert response1.status_code == 200
        initial_views = response1.json()["views"]

        # Второй запрос
        response2 = await client.get("/recipes/1")
        assert response2.status_code == 200
        updated_views = response2.json()["views"]

        assert updated_views == initial_views + 1

    @pytest.mark.asyncio
    async def test_multiple_views_increment(self, client, sample_recipes):
        """Тест множественного увеличения просмотров"""
        initial_response = await client.get("/recipes/1")
        initial_views = initial_response.json()["views"]

        # Делаем 5 запросов
        for _ in range(5):
            await client.get("/recipes/1")

        final_response = await client.get("/recipes/1")
        final_views = final_response.json()["views"]

        assert final_views == initial_views + 6  # +5 за цикл + 1 за финальный запрос


class TestCreateRecipe:
    """Тесты для создания рецептов"""

    @pytest.mark.asyncio
    async def test_create_recipe_success(self, client):
        """Тест успешного создания рецепта"""
        new_recipe = {
            "name": "Салат Цезарь",
            "cooking_time": "00:20:00",
            "list_of_ingredients": "салат, курица, пармезан, соус, гренки",
            "description": "Классический салат с курицей",
        }

        response = await client.post("/recipes/", json=new_recipe)
        assert response.status_code == 200
        data = response.json()

        assert data["name"] == new_recipe["name"]
        assert data["cooking_time"] == new_recipe["cooking_time"]
        assert data["views"] == 0  # По умолчанию
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_recipe_missing_fields(self, client):
        """Тест создания рецепта с отсутствующими полями"""
        incomplete_recipe = {
            "name": "Неполный рецепт",
            "cooking_time": "00:15:00",
            # Отсутствуют list_of_ingredients и description
        }

        response = await client.post("/recipes/", json=incomplete_recipe)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_recipe_invalid_time_format(self, client):
        """Тест создания рецепта с неверным форматом времени"""
        invalid_recipe = {
            "name": "Тест",
            "cooking_time": "invalid_time",
            "list_of_ingredients": "тест",
            "description": "тест",
        }

        response = await client.post("/recipes/", json=invalid_recipe)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_created_recipe_appears_in_list(self, client):
        """Тест что созданный рецепт появляется в списке"""
        new_recipe = {
            "name": "Пицца Маргарита",
            "cooking_time": "00:25:00",
            "list_of_ingredients": "тесто, томаты, моцарелла, базилик",
            "description": "Итальянская пицца",
        }

        # Создаем рецепт
        create_response = await client.post("/recipes/", json=new_recipe)
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]

        # Проверяем что он есть в списке
        list_response = await client.get("/recipes/")
        recipes = list_response.json()

        assert any(recipe["id"] == created_id for recipe in recipes)
        created_recipe = next(r for r in recipes if r["id"] == created_id)
        assert created_recipe["name"] == new_recipe["name"]


class TestRecipeModel:
    """Тесты модели рецепта"""

    @pytest.mark.asyncio
    async def test_recipe_default_views(self, test_db):
        """Тест значения views по умолчанию"""
        recipe = models.Recipes(
            name="Тест",
            cooking_time=time(0, 15, 0),
            list_of_ingredients="тест",
            description="тест",
        )
        test_db.add(recipe)
        await test_db.commit()
        await test_db.refresh(recipe)

        assert recipe.views == 0

    @pytest.mark.asyncio
    async def test_recipe_custom_views(self, test_db):
        """Тест установки кастомного значения views"""
        recipe = models.Recipes(
            name="Тест",
            cooking_time=time(0, 15, 0),
            list_of_ingredients="тест",
            description="тест",
            views=42,
        )
        test_db.add(recipe)
        await test_db.commit()
        await test_db.refresh(recipe)

        assert recipe.views == 42


class TestEdgeCases:
    """Тесты граничных случаев"""

    @pytest.mark.asyncio
    async def test_recipe_with_long_description(self, client):
        """Тест рецепта с длинным описанием"""
        long_description = "А" * 1000
        recipe = {
            "name": "Тест",
            "cooking_time": "00:30:00",
            "list_of_ingredients": "тест",
            "description": long_description,
        }

        response = await client.post("/recipes/", json=recipe)
        assert response.status_code == 200
        assert len(response.json()["description"]) == 1000

    @pytest.mark.asyncio
    async def test_recipe_with_zero_cooking_time(self, client):
        """Тест рецепта с нулевым временем приготовления"""
        recipe = {
            "name": "Мгновенный рецепт",
            "cooking_time": "00:00:00",
            "list_of_ingredients": "ничего",
            "description": "Не требует приготовления",
        }

        response = await client.post("/recipes/", json=recipe)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_recipe_with_special_characters(self, client):
        """Тест рецепта со спецсимволами"""
        recipe = {
            "name": "Рецепт № 1 (новый!) & <специальный>",
            "cooking_time": "00:45:00",
            "list_of_ingredients": 'ингредиент №1, "особый" ингредиент',
            "description": "Описание с символами: @#$%^&*()",
        }

        response = await client.post("/recipes/", json=recipe)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == recipe["name"]
