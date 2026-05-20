import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db

SQLALCHEMY_TEST_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_register():
    res = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "securepass123",
        "first_name": "Test",
        "last_name": "User",
    })
    assert res.status_code == 201
    assert "access_token" in res.json()


def test_login():
    client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "securepass123",
        "first_name": "Login",
        "last_name": "User",
    })
    res = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "securepass123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password():
    client.post("/api/v1/auth/register", json={
        "email": "wrong@example.com",
        "password": "correct",
        "first_name": "A",
        "last_name": "B",
    })
    res = client.post("/api/v1/auth/login", json={"email": "wrong@example.com", "password": "wrong"})
    assert res.status_code == 401


def test_me():
    reg = client.post("/api/v1/auth/register", json={
        "email": "me@example.com",
        "password": "pass123",
        "first_name": "Me",
        "last_name": "User",
    })
    token = reg.json()["access_token"]
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "me@example.com"
