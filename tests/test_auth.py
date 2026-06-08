import pytest
from httpx import AsyncClient


class TestAuth:
    async def test_register(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "user@test.com",
            "password": "secure123",
            "full_name": "Juan Perez",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_duplicate_email(self, client: AsyncClient):
        await client.post("/auth/register", json={
            "email": "dup@test.com",
            "password": "secure123",
            "full_name": "Dup User",
        })
        resp = await client.post("/auth/register", json={
            "email": "dup@test.com",
            "password": "secure123",
            "full_name": "Dup User 2",
        })
        assert resp.status_code == 409

    async def test_register_short_password(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "short@test.com",
            "password": "12345",
            "full_name": "Short Pwd",
        })
        assert resp.status_code == 422

    async def test_login(self, client: AsyncClient):
        await client.post("/auth/register", json={
            "email": "login@test.com",
            "password": "secure123",
            "full_name": "Login User",
        })
        resp = await client.post("/auth/login", json={
            "email": "login@test.com",
            "password": "secure123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post("/auth/register", json={
            "email": "wrong@test.com",
            "password": "secure123",
            "full_name": "Wrong Pwd",
        })
        resp = await client.post("/auth/login", json={
            "email": "wrong@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_me(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "me@test.com",
            "password": "secure123",
            "full_name": "Me User",
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp2 = await client.get("/auth/me", headers=headers)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["email"] == "me@test.com"
        assert data["full_name"] == "Me User"

    async def test_me_unauthorized(self, client: AsyncClient):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401
