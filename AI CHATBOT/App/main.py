"""FastAPI application for Sage - AI Mental Health Support Chatbot."""
import sqlite3
from pathlib import Path

from fastapi import HTTPException, Request  # type: ignore[import-untyped]
from fastapi import FastAPI  # type: ignore[import-untyped]
from fastapi.responses import FileResponse  # type: ignore[import-untyped]
from fastapi.staticfiles import StaticFiles  # type: ignore[import-untyped]

from app.auth import create_token, decode_token, hash_password, verify_password
from app.database import get_connection, init_db
from app.models import ChatMessage, ChatResponse, UserLogin, UserRegister
from app.chat_service import get_chat_response

app = FastAPI(
    title="Sage",
    description="AI-powered mental health support chatbot",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent

static_path = BASE_DIR / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


def get_current_user(request: Request) -> str | None:
    """Get username from Authorization header or cookie."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return decode_token(auth[7:])
    token = request.cookies.get("sage_token")
    if token:
        return decode_token(token)
    return None


def require_auth(request: Request) -> str:
    """Require authenticated user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# Initialize DB on startup
@app.on_event("startup")
def startup():
    init_db()


# --- Auth routes ---

@app.post("/api/register")
async def register(data: UserRegister):
    print("PASSWORD TYPE:", type(data.password))
    print("PASSWORD LENGTH:", len(data.password))
    print("PASSWORD VALUE:", data.password)

    """Register a new user."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (data.username.lower(), data.email.lower(), hash_password(data.password)),
        )
        conn.commit()
        token = create_token(data.username.lower())
        return {"access_token": token, "token_type": "bearer"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    finally:
        conn.close()


@app.post("/api/login")
async def login(data: UserLogin):
    """Login and return JWT."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT username, password_hash FROM users WHERE username = ?",
            (data.username.lower(),),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(row["username"])
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/logout")
async def logout():
    """Logout - client should clear token."""
    return {"ok": True}


# --- Page routes ---

@app.get("/")
async def root():
    """Redirect to chat or login."""
    return FileResponse(BASE_DIR / "templates" / "index.html")


@app.get("/login")
async def login_page():
    return FileResponse(BASE_DIR / "templates" / "login.html")


@app.get("/register")
async def register_page():
    return FileResponse(BASE_DIR / "templates" / "register.html")


@app.get("/history")
async def history_page():
    return FileResponse(BASE_DIR / "templates" / "history.html")


# --- API routes ---

@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage, request: Request):
    """Process chat message and return Sage's response."""
    username = require_auth(request)
    response, suggestions = await get_chat_response(message.message)

    # Save to history
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cur.fetchone()
        if user_row:
            user_id = user_row["id"]
            conn.execute(
                "INSERT INTO chat_sessions (user_id) VALUES (?)",
                (user_id,),
            )
            session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, "user", message.message),
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, "assistant", response),
            )
            conn.commit()
    finally:
        conn.close()

    return ChatResponse(response=response, suggestions=suggestions)


@app.get("/api/history")
async def get_history(request: Request):
    """Get user's chat history."""
    username = require_auth(request)
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT s.id, s.created_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) as msg_count
            FROM chat_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE u.username = ?
            ORDER BY s.created_at DESC
            LIMIT 50
            """,
            (username,),
        )
        sessions = [dict(zip(row.keys(), row)) for row in cur.fetchall()]
    finally:
        conn.close()
    return {"sessions": sessions}


@app.get("/api/history/{session_id}")
async def get_session_messages(session_id: int, request: Request):
    """Get messages for a session."""
    username = require_auth(request)
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT m.role, m.content, m.created_at
            FROM messages m
            JOIN chat_sessions s ON m.session_id = s.id
            JOIN users u ON s.user_id = u.id
            WHERE s.id = ? AND u.username = ?
            ORDER BY m.created_at
            """,
            (session_id, username),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": [dict(zip(r.keys(), r)) for r in rows]}


@app.get("/api/me")
async def me(request: Request):
    """Get current user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"username": user}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Sage"}
