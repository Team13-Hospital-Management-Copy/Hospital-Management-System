import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.roles import RECEPTIONIST
from app.security import hash_password

TEST_DATABASE_URL = "sqlite://"


@pytest.fixture()
def db_session():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


@pytest.fixture()
def seed_user(db_session):
    def _seed(
        username: str = "receptionist1",
        password: str = "CorrectHorseBattery9!",
        role: str = RECEPTIONIST,
    ):
        user = User(username=username, password_hash=hash_password(password), role=role)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _seed


@pytest.fixture()
def login_token(client):
    def _login(username: str, password: str = "CorrectHorseBattery9!") -> str:
        response = client.post("/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.text
        return response.json()["token"]

    return _login
