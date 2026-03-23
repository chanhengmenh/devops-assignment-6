from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="DevSecOps API", version="1.0.0")

# In-memory data store
users = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
    {"id": 2, "name": "Bob",   "email": "bob@example.com",   "role": "user"},
]


# ---------- Request / Response schemas ----------

class UserCreate(BaseModel):
    name: str
    email: str
    role: Optional[str] = "user"


# ---------- Routes ----------

@app.get("/")
def health_check():
    return {"status": "ok", "message": "DevSecOps API is running!"}


@app.get("/api/users")
def get_users():
    return {"users": users, "count": len(users)}


@app.get("/api/users/{user_id}")
def get_user(user_id: int):
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/users", status_code=201)
def create_user(body: UserCreate):
    new_user = {
        "id": len(users) + 1,
        "name": body.name,
        "email": body.email,
        "role": body.role,
    }
    users.append(new_user)
    return new_user


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int):
    global users
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    users = [u for u in users if u["id"] != user_id]
    return {"message": f"User {user_id} deleted successfully"}
