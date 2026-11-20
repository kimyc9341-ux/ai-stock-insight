"""
api_server.py - Render.com 배포용 FastAPI 백엔드 서버
- Supabase(SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)가 설정되면 Supabase DB와 실시간 연동
- 미설정 시에도 로컬 SQLite(data/auth_audit.db)로 즉시 정상 동작 (이중 폴백)
"""

import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import stock_service

app = FastAPI(title="AI Stock Insight Auth & Audit API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def normalize_supabase_url(raw_url: str) -> str:
    cleaned = (raw_url or "").strip().rstrip("/")
    if not cleaned:
        return ""
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return cleaned

SUPABASE_URL = normalize_supabase_url(os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
ADMIN_API_SECRET = (os.environ.get("ADMIN_API_SECRET") or SUPABASE_KEY or "cpr-local-admin-secret").strip()
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "data", "auth_audit.db")


def create_admin_token(username: str, role: str) -> str:
    msg = f"{username}:{role}".encode("utf-8")
    sig = hmac.new(ADMIN_API_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{username}:{role}:{sig}"


def verify_admin_request(request: Request, require_master: bool = False) -> str:
    token = request.headers.get("x-admin-token", "").strip()
    if token:
        parts = token.split(":")
        if len(parts) == 3:
            username, role, sig = parts
            expected = hmac.new(ADMIN_API_SECRET.encode("utf-8"), f"{username}:{role}".encode("utf-8"), hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected):
                if require_master and role != "admin":
                    raise HTTPException(status_code=403, detail="Master admin privilege required")
                if role in ("admin", "evaluator"):
                    return username
    raise HTTPException(status_code=401, detail="Unauthorized admin request")


def is_supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def supabase_headers(prefer: str = "return=representation") -> Dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def sb_request(method: str, table: str, params: Optional[Dict[str, str]] = None, payload: Any = None) -> Any:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    resp = requests.request(
        method=method,
        url=url,
        headers=supabase_headers(),
        params=params,
        json=payload,
        timeout=10,
    )
    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=f"Supabase error: {resp.text}")
    if not resp.text:
        return []
    return resp.json()


def get_sqlite_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite() -> None:
    conn = get_sqlite_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            name TEXT DEFAULT '',
            birthdate TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            is_phone_verified INTEGER DEFAULT 0,
            email TEXT DEFAULT '',
            address TEXT DEFAULT '',
            referrer TEXT DEFAULT '없음',
            role TEXT NOT NULL DEFAULT 'user',
            status TEXT NOT NULL DEFAULT 'pending',
            allow_external_query INTEGER DEFAULT 1,
            api_key_enabled INTEGER DEFAULT 1,
            can_access_admin_panel INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_review_accounts (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            name TEXT DEFAULT '심사 담당자',
            note TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            can_access_admin_panel INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_audit_logs (
            id REAL PRIMARY KEY,
            username TEXT NOT NULL,
            ip TEXT DEFAULT '127.0.0.1',
            browser TEXT DEFAULT 'Chrome',
            os TEXT DEFAULT 'PC',
            device_type TEXT DEFAULT 'Desktop',
            action TEXT NOT NULL,
            meta TEXT DEFAULT '{}',
            client_time TEXT DEFAULT '',
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_user_portfolios (
            username TEXT PRIMARY KEY,
            favorites TEXT DEFAULT '[]',
            paper_account TEXT DEFAULT '{"cash":50000000,"holdings":{}}',
            updated_at TEXT
        )
    """)
    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT OR IGNORE INTO app_users
        (id, username, password, name, birthdate, phone, is_phone_verified, email, address, referrer, role, status, allow_external_query, api_key_enabled, can_access_admin_panel, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("usr-admin", "admin", "1234", "최고 관리자", "1990-01-01", "010-0000-0000", 1, "admin@myaccount.local", "서울특별시 영등포구 여의도동", "SYSTEM", "admin", "approved", 1, 1, 1, now_iso),
    )
    cur.execute(
        """
        INSERT OR IGNORE INTO app_review_accounts
        (username, password, name, note, is_active, can_access_admin_panel, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("admin2", "5678", "심사 담당자", "심사용 공식 계정", 1, 1, now_iso),
    )
    conn.commit()
    conn.close()


init_sqlite()


def row_to_user(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "name": row.get("name", ""),
        "birthdate": row.get("birthdate", ""),
        "phone": row.get("phone", ""),
        "isPhoneVerified": bool(row.get("is_phone_verified", False)),
        "email": row.get("email", ""),
        "address": row.get("address", ""),
        "referrer": row.get("referrer", "없음"),
        "role": row.get("role", "user"),
        "status": row.get("status", "pending"),
        "allowExternalQuery": bool(row.get("allow_external_query", True)),
        "apiKeyEnabled": bool(row.get("api_key_enabled", True)),
        "canAccessAdminPanel": bool(row.get("can_access_admin_panel", False)),
        "created_at": row.get("created_at", ""),
    }


def row_to_review(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "username": row["username"],
        "name": row.get("name", "심사 담당자"),
        "note": row.get("note", ""),
        "isActive": bool(row.get("is_active", True)),
        "canAccessAdminPanel": bool(row.get("can_access_admin_panel", True)),
        "created_at": row.get("created_at", ""),
    }


def row_to_log(row: Dict[str, Any]) -> Dict[str, Any]:
    meta_val = row.get("meta", {})
    if isinstance(meta_val, str):
        try:
            meta_val = json.loads(meta_val)
        except Exception:
            meta_val = {}
    return {
        "id": row["id"],
        "username": row["username"],
        "ip": row.get("ip", "127.0.0.1"),
        "browser": row.get("browser", "Chrome"),
        "os": row.get("os", "PC"),
        "deviceType": row.get("device_type", "Desktop"),
        "action": row["action"],
        "meta": meta_val,
        "time": row.get("client_time") or row.get("created_at", ""),
    }


def get_client_ip(request: Request, fallback_ip: str = "") -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if fallback_ip and "Local" not in fallback_ip:
        return fallback_ip
    return (request.client.host if request.client else "") or "127.0.0.1"


def insert_audit_log(entry: Dict[str, Any]) -> None:
    if is_supabase_enabled():
        sb_request(
            "POST",
            "app_audit_logs",
            payload={
                "id": entry["id"],
                "username": entry["username"],
                "ip": entry["ip"],
                "browser": entry["browser"],
                "os": entry["os"],
                "device_type": entry["deviceType"],
                "action": entry["action"],
                "meta": entry.get("meta", {}),
                "client_time": entry["time"],
            },
        )
        return

    conn = get_sqlite_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO app_audit_logs (id, username, ip, browser, os, device_type, action, meta, client_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["id"],
            entry["username"],
            entry["ip"],
            entry["browser"],
            entry["os"],
            entry["deviceType"],
            entry["action"],
            json.dumps(entry.get("meta", {}), ensure_ascii=False),
            entry["time"],
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


class LoginReq(BaseModel):
    username: str
    password: str
    fp: Optional[Dict[str, Any]] = None
    ip: Optional[str] = ""


class RegisterReq(BaseModel):
    username: str
    password: str
    name: str
    birthdate: str = ""
    phone: str = ""
    isPhoneVerified: bool = False
    email: str = ""
    address: str = ""
    referrer: str = "없음"
    fp: Optional[Dict[str, Any]] = None
    ip: Optional[str] = ""


class ProfileUpdateReq(BaseModel):
    username: str
    currentPw: str
    newPw: Optional[str] = ""
    name: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""
    fp: Optional[Dict[str, Any]] = None
    ip: Optional[str] = ""


class ReviewCreateReq(BaseModel):
    username: str
    password: str
    name: str = "심사위원"
    note: str = ""
    canAccessAdminPanel: bool = True


class ReviewToggleReq(BaseModel):
    username: str
    canAccessAdminPanel: Optional[bool] = None
    isActive: Optional[bool] = None


class UserStatusReq(BaseModel):
    userId: str
    status: str


class UserControlsReq(BaseModel):
    userId: str
    allowExternalQuery: Optional[bool] = None
    apiKeyEnabled: Optional[bool] = None


class AuditLogReq(BaseModel):
    id: Optional[float] = None
    username: str = "GUEST_USER"
    ip: str = ""
    browser: str = "Chrome"
    os: str = "PC"
    deviceType: str = "Desktop"
    action: str
    meta: Optional[Dict[str, Any]] = None
    time: str = ""


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "supabase": is_supabase_enabled()}


@app.get("/api/config")
def api_config() -> Dict[str, Any]:
    return {
        "backend": "render-fastapi",
        "database": "supabase" if is_supabase_enabled() else "sqlite-fallback",
        "supabaseConnected": is_supabase_enabled(),
        "dartConfigured": bool(os.environ.get("DART_API_KEY", "").strip()),
        "geminiConfigured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "kisConfigured": bool(os.environ.get("KIS_APP_KEY", "").strip()),
    }


def find_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    clean = username.strip().lower()
    if is_supabase_enabled():
        rows = sb_request("GET", "app_users", params={"username": f"eq.{clean}", "select": "*"})
        return rows[0] if rows else None
    conn = get_sqlite_conn()
    row = conn.execute("SELECT * FROM app_users WHERE lower(username) = ?", (clean,)).fetchone()
    conn.close()
    return dict(row) if row else None


@app.post("/api/auth/login")
def api_login(req: LoginReq, request: Request) -> Dict[str, Any]:
    user = find_user_by_username(req.username)
    fp = req.fp or {}
    client_ip = get_client_ip(request, req.ip or "")
    now_str = datetime.now().strftime("%p %I:%M:%S")

    if not user:
        return {"success": False, "message": "등록되지 않은 아이디입니다. 회원가입을 먼저 진행해 주세요."}

    if user["password"] != req.password:
        insert_audit_log({
            "id": time.time() * 1000,
            "username": user["username"],
            "ip": client_ip,
            "browser": fp.get("browser", "Chrome"),
            "os": fp.get("os", "PC"),
            "deviceType": fp.get("deviceType", "Desktop"),
            "action": "LOGIN_FAIL_PASSWORD",
            "time": now_str,
        })
        return {"success": False, "message": "비밀번호가 일치하지 않습니다. 다시 확인해 주세요."}

    if user["status"] == "pending":
        insert_audit_log({
            "id": time.time() * 1000,
            "username": user["username"],
            "ip": client_ip,
            "browser": fp.get("browser", "Chrome"),
            "os": fp.get("os", "PC"),
            "deviceType": fp.get("deviceType", "Desktop"),
            "action": "LOGIN_BLOCKED_PENDING",
            "time": now_str,
        })
        return {"success": False, "message": "가입 승인 심사 대기 중인 계정입니다. 관리자 승인 확인 후 로그인 가능합니다."}

    if user["status"] == "blocked":
        insert_audit_log({
            "id": time.time() * 1000,
            "username": user["username"],
            "ip": client_ip,
            "browser": fp.get("browser", "Chrome"),
            "os": fp.get("os", "PC"),
            "deviceType": fp.get("deviceType", "Desktop"),
            "action": "LOGIN_BLOCKED",
            "time": now_str,
        })
        return {"success": False, "message": "관리자에 의해 이용이 차단된 계정입니다."}

    insert_audit_log({
        "id": time.time() * 1000,
        "username": user["username"],
        "ip": client_ip,
        "browser": fp.get("browser", "Chrome"),
        "os": fp.get("os", "PC"),
        "deviceType": fp.get("deviceType", "Desktop"),
        "action": "LOGIN_SUCCESS",
        "time": now_str,
    })

    session = {
        "user": row_to_user(user),
        "device": fp,
        "ip": client_ip,
        "loggedInAt": datetime.now(timezone.utc).isoformat(),
    }
    if user.get("role") == "admin":
        session["adminToken"] = create_admin_token(user["username"], "admin")
    return {"success": True, "session": session}


@app.post("/api/auth/eval-login")
def api_eval_login(req: LoginReq, request: Request) -> Dict[str, Any]:
    clean = req.username.strip().lower()
    if is_supabase_enabled():
        rows = sb_request("GET", "app_review_accounts", params={"username": f"eq.{clean}", "select": "*"})
        target = rows[0] if rows else None
    else:
        conn = get_sqlite_conn()
        row = conn.execute("SELECT * FROM app_review_accounts WHERE lower(username) = ?", (clean,)).fetchone()
        conn.close()
        target = dict(row) if row else None

    fp = req.fp or {}
    client_ip = get_client_ip(request, req.ip or "")
    now_str = datetime.now().strftime("%p %I:%M:%S")

    if not target:
        return {"success": False, "message": "등록되지 않은 심사용 아이디입니다."}
    if target["password"] != req.password:
        insert_audit_log({
            "id": time.time() * 1000,
            "username": req.username,
            "ip": client_ip,
            "browser": fp.get("browser", "Chrome"),
            "os": fp.get("os", "PC"),
            "deviceType": fp.get("deviceType", "Desktop"),
            "action": "EVAL_LOGIN_FAIL_PW",
            "time": now_str,
        })
        return {"success": False, "message": "비밀번호가 일치하지 않습니다."}
    if not bool(target.get("is_active", True)):
        return {"success": False, "message": "이용이 중지된 심사용 계정입니다. 관리자에게 문의하세요."}

    insert_audit_log({
        "id": time.time() * 1000,
        "username": target["username"],
        "ip": client_ip,
        "browser": fp.get("browser", "Chrome"),
        "os": fp.get("os", "PC"),
        "deviceType": fp.get("deviceType", "Desktop"),
        "action": "EVAL_LOGIN_SUCCESS",
        "time": now_str,
    })

    session = {
        "user": {
            "id": f"eval-{target['username']}",
            "username": target["username"],
            "name": target.get("name", "심사평가자"),
            "role": "evaluator",
            "status": "approved",
            "allowExternalQuery": True,
            "apiKeyEnabled": True,
            "isReviewer": True,
            "canAccessAdminPanel": bool(target.get("can_access_admin_panel", True)),
        },
        "device": fp,
        "ip": client_ip,
        "loggedInAt": datetime.now(timezone.utc).isoformat(),
    }
    if bool(target.get("can_access_admin_panel", True)):
        session["adminToken"] = create_admin_token(target["username"], "evaluator")
    return {"success": True, "session": session, "message": "심사용 계정 로그인이 완료되었습니다."}


@app.post("/api/auth/register")
def api_register(req: RegisterReq, request: Request) -> Dict[str, Any]:
    clean = req.username.strip().lower()
    if len(clean) < 3:
        return {"success": False, "message": "아이디는 최소 3자리 이상 입력해 주세요."}
    if len(req.password) < 4:
        return {"success": False, "message": "비밀번호는 최소 4자리 이상 설정해 주세요."}
    if find_user_by_username(clean):
        return {"success": False, "message": "이미 사용 중인 아이디입니다."}

    user_id = f"usr-{int(time.time() * 1000)}"
    now_iso = datetime.now(timezone.utc).isoformat()
    if is_supabase_enabled():
        sb_request(
            "POST",
            "app_users",
            payload={
                "id": user_id,
                "username": clean,
                "password": req.password,
                "name": req.name.strip(),
                "birthdate": req.birthdate,
                "phone": req.phone.strip(),
                "is_phone_verified": req.isPhoneVerified,
                "email": req.email.strip(),
                "address": req.address.strip(),
                "referrer": (req.referrer or "없음").strip(),
                "role": "user",
                "status": "pending",
                "allow_external_query": True,
                "api_key_enabled": True,
                "can_access_admin_panel": False,
                "created_at": now_iso,
            },
        )
    else:
        conn = get_sqlite_conn()
        conn.execute(
            """
            INSERT INTO app_users
            (id, username, password, name, birthdate, phone, is_phone_verified, email, address, referrer, role, status, allow_external_query, api_key_enabled, can_access_admin_panel, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, clean, req.password, req.name.strip(), req.birthdate, req.phone.strip(), int(req.isPhoneVerified), req.email.strip(), req.address.strip(), (req.referrer or "없음").strip(), "user", "pending", 1, 1, 0, now_iso),
        )
        conn.commit()
        conn.close()

    fp = req.fp or {}
    insert_audit_log({
        "id": time.time() * 1000,
        "username": clean,
        "ip": get_client_ip(request, req.ip or ""),
        "browser": fp.get("browser", "Chrome"),
        "os": fp.get("os", "PC"),
        "deviceType": fp.get("deviceType", "Desktop"),
        "action": "REGISTER_SUBMITTED",
        "time": datetime.now().strftime("%p %I:%M:%S"),
    })
    return {"success": True, "message": "회원가입 신청이 성공적으로 접수되었습니다!\n관리자 승인 후 정식 서비스 이용이 가능합니다."}


@app.post("/api/auth/profile")
def api_update_profile(req: ProfileUpdateReq, request: Request) -> Dict[str, Any]:
    user = find_user_by_username(req.username)
    if not user:
        return {"success": False, "message": "사용자를 찾을 수 없습니다."}
    if user["password"] != req.currentPw:
        return {"success": False, "message": "현재 비밀번호가 올바르지 않습니다."}
    if req.newPw and len(req.newPw) < 4:
        return {"success": False, "message": "새 비밀번호는 4자리 이상이어야 합니다."}

    updates: Dict[str, Any] = {}
    if req.newPw:
        updates["password"] = req.newPw
    if req.name:
        updates["name"] = req.name.strip()
    if req.phone:
        updates["phone"] = req.phone.strip()
    if req.email:
        updates["email"] = req.email.strip()
    if req.address:
        updates["address"] = req.address.strip()

    if updates:
        if is_supabase_enabled():
            sb_request("PATCH", "app_users", params={"username": f"eq.{user['username']}"}, payload=updates)
        else:
            conn = get_sqlite_conn()
            cols = ", ".join([f"{k} = ?" for k in updates.keys()])
            conn.execute(f"UPDATE app_users SET {cols} WHERE username = ?", [*updates.values(), user["username"]])
            conn.commit()
            conn.close()

    updated = find_user_by_username(req.username) or user
    fp = req.fp or {}
    insert_audit_log({
        "id": time.time() * 1000,
        "username": user["username"],
        "ip": get_client_ip(request, req.ip or ""),
        "browser": fp.get("browser", "Chrome"),
        "os": fp.get("os", "PC"),
        "deviceType": fp.get("deviceType", "Desktop"),
        "action": "PASSWORD_CHANGED" if req.newPw else "PROFILE_UPDATED",
        "time": datetime.now().strftime("%p %I:%M:%S"),
    })
    return {"success": True, "user": row_to_user(updated), "message": "회원정보가 안전하게 업데이트되었습니다."}


@app.get("/api/admin/users")
def api_get_users(request: Request) -> List[Dict[str, Any]]:
    verify_admin_request(request)
    if is_supabase_enabled():
        rows = sb_request("GET", "app_users", params={"select": "*", "order": "created_at.desc"})
        return [row_to_user(r) for r in rows]
    conn = get_sqlite_conn()
    rows = conn.execute("SELECT * FROM app_users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [row_to_user(dict(r)) for r in rows]


@app.post("/api/admin/users/status")
def api_update_user_status(req: UserStatusReq, request: Request) -> Dict[str, Any]:
    verify_admin_request(request, require_master=True)
    if is_supabase_enabled():
        sb_request("PATCH", "app_users", params={"id": f"eq.{req.userId}"}, payload={"status": req.status})
    else:
        conn = get_sqlite_conn()
        conn.execute("UPDATE app_users SET status = ? WHERE id = ?", (req.status, req.userId))
        conn.commit()
        conn.close()
    return {"success": True}


@app.post("/api/admin/users/controls")
def api_update_user_controls(req: UserControlsReq, request: Request) -> Dict[str, Any]:
    verify_admin_request(request, require_master=True)
    updates: Dict[str, Any] = {}
    if req.allowExternalQuery is not None:
        updates["allow_external_query"] = req.allowExternalQuery if is_supabase_enabled() else int(req.allowExternalQuery)
    if req.apiKeyEnabled is not None:
        updates["api_key_enabled"] = req.apiKeyEnabled if is_supabase_enabled() else int(req.apiKeyEnabled)

    if updates:
        if is_supabase_enabled():
            sb_request("PATCH", "app_users", params={"id": f"eq.{req.userId}"}, payload=updates)
        else:
            conn = get_sqlite_conn()
            cols = ", ".join([f"{k} = ?" for k in updates.keys()])
            conn.execute(f"UPDATE app_users SET {cols} WHERE id = ?", [*updates.values(), req.userId])
            conn.commit()
            conn.close()
    return {"success": True}


@app.get("/api/admin/review-codes")
def api_get_review_codes(request: Request) -> List[Dict[str, Any]]:
    verify_admin_request(request)
    if is_supabase_enabled():
        rows = sb_request("GET", "app_review_accounts", params={"select": "*", "order": "created_at.desc"})
        return [row_to_review(r) for r in rows]
    conn = get_sqlite_conn()
    rows = conn.execute("SELECT * FROM app_review_accounts ORDER BY created_at DESC").fetchall()
    conn.close()
    return [row_to_review(dict(r)) for r in rows]


@app.post("/api/admin/review-codes")
def api_create_review_code(req: ReviewCreateReq, request: Request) -> Dict[str, Any]:
    verify_admin_request(request, require_master=True)
    clean = req.username.strip().lower()
    if len(clean) < 3:
        return {"success": False, "message": "아이디는 3자리 이상이어야 합니다."}
    if len(req.password) < 4:
        return {"success": False, "message": "비밀번호는 4자리 이상이어야 합니다."}

    now_iso = datetime.now(timezone.utc).isoformat()
    if is_supabase_enabled():
        existing = sb_request("GET", "app_review_accounts", params={"username": f"eq.{clean}", "select": "username"})
        if existing:
            return {"success": False, "message": "이미 존재하는 심사용 아이디입니다."}
        sb_request(
            "POST",
            "app_review_accounts",
            payload={
                "username": clean,
                "password": req.password,
                "name": req.name.strip() or "심사위원",
                "note": req.note,
                "is_active": True,
                "can_access_admin_panel": req.canAccessAdminPanel,
                "created_at": now_iso,
            },
        )
    else:
        conn = get_sqlite_conn()
        if conn.execute("SELECT 1 FROM app_review_accounts WHERE username = ?", (clean,)).fetchone():
            conn.close()
            return {"success": False, "message": "이미 존재하는 심사용 아이디입니다."}
        conn.execute(
            "INSERT INTO app_review_accounts (username, password, name, note, is_active, can_access_admin_panel, created_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
            (clean, req.password, req.name.strip() or "심사위원", req.note, int(req.canAccessAdminPanel), now_iso),
        )
        conn.commit()
        conn.close()

    return {"success": True, "message": f"신규 심사용 계정 [{clean}] 발급 완료!"}


@app.post("/api/admin/review-codes/toggle")
def api_toggle_review_code(req: ReviewToggleReq, request: Request) -> Dict[str, Any]:
    verify_admin_request(request, require_master=True)
    updates: Dict[str, Any] = {}
    if req.canAccessAdminPanel is not None:
        updates["can_access_admin_panel"] = req.canAccessAdminPanel if is_supabase_enabled() else int(req.canAccessAdminPanel)
    if req.isActive is not None:
        updates["is_active"] = req.isActive if is_supabase_enabled() else int(req.isActive)

    if updates:
        if is_supabase_enabled():
            sb_request("PATCH", "app_review_accounts", params={"username": f"eq.{req.username.lower()}"}, payload=updates)
        else:
            conn = get_sqlite_conn()
            cols = ", ".join([f"{k} = ?" for k in updates.keys()])
            conn.execute(f"UPDATE app_review_accounts SET {cols} WHERE lower(username) = ?", [*updates.values(), req.username.lower()])
            conn.commit()
            conn.close()
    return {"success": True}


@app.get("/api/audit-logs")
def api_get_audit_logs(request: Request, limit: int = 300) -> List[Dict[str, Any]]:
    verify_admin_request(request)
    if is_supabase_enabled():
        rows = sb_request("GET", "app_audit_logs", params={"select": "*", "order": "id.desc", "limit": str(limit)})
        return [row_to_log(r) for r in rows]
    conn = get_sqlite_conn()
    rows = conn.execute("SELECT * FROM app_audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [row_to_log(dict(r)) for r in rows]


@app.post("/api/audit-logs")
def api_post_audit_log(req: AuditLogReq, request: Request) -> Dict[str, Any]:
    entry = {
        "id": req.id if req.id is not None else time.time() * 1000,
        "username": req.username or "GUEST_USER",
        "ip": get_client_ip(request, req.ip or ""),
        "browser": req.browser or "Chrome",
        "os": req.os or "PC",
        "deviceType": req.deviceType or "Desktop",
        "action": req.action,
        "meta": req.meta or {},
        "time": req.time or datetime.now().strftime("%p %I:%M:%S"),
    }
    insert_audit_log(entry)
    return {"success": True, "entry": entry}


class PortfolioReq(BaseModel):
    username: str
    favorites: Optional[List[str]] = None
    paperAccount: Optional[Dict[str, Any]] = None


@app.get("/api/user/portfolio")
def api_get_portfolio(username: str) -> Dict[str, Any]:
    clean = username.strip().lower()
    if is_supabase_enabled():
        try:
            rows = sb_request("GET", "app_user_portfolios", params={"username": f"eq.{clean}", "select": "*"})
            if rows:
                r = rows[0]
                return {
                    "success": True,
                    "favorites": r.get("favorites", []),
                    "paperAccount": r.get("paper_account", {"cash": 50000000, "holdings": {}}),
                }
        except HTTPException:
            pass
    conn = get_sqlite_conn()
    row = conn.execute("SELECT * FROM app_user_portfolios WHERE username = ?", (clean,)).fetchone()
    conn.close()
    if row:
        return {
            "success": True,
            "favorites": json.loads(row["favorites"] or "[]"),
            "paperAccount": json.loads(row["paper_account"] or '{"cash":50000000,"holdings":{}}'),
        }
    return {"success": True, "favorites": None, "paperAccount": None}


@app.post("/api/user/portfolio")
def api_save_portfolio(req: PortfolioReq) -> Dict[str, Any]:
    clean = req.username.strip().lower()
    now_iso = datetime.now(timezone.utc).isoformat()
    current = api_get_portfolio(clean)
    favs = req.favorites if req.favorites is not None else (current.get("favorites") or [])
    acc = req.paperAccount if req.paperAccount is not None else (current.get("paperAccount") or {"cash": 50000000, "holdings": {}})

    if is_supabase_enabled():
        try:
            existing = sb_request("GET", "app_user_portfolios", params={"username": f"eq.{clean}", "select": "username"})
            if existing:
                sb_request("PATCH", "app_user_portfolios", params={"username": f"eq.{clean}"}, payload={"favorites": favs, "paper_account": acc, "updated_at": now_iso})
            else:
                sb_request("POST", "app_user_portfolios", payload={"username": clean, "favorites": favs, "paper_account": acc, "updated_at": now_iso})
            return {"success": True}
        except HTTPException:
            pass

    conn = get_sqlite_conn()
    conn.execute(
        "INSERT OR REPLACE INTO app_user_portfolios (username, favorites, paper_account, updated_at) VALUES (?, ?, ?, ?)",
        (clean, json.dumps(favs, ensure_ascii=False), json.dumps(acc, ensure_ascii=False), now_iso),
    )
    conn.commit()
    conn.close()
    return {"success": True}


@app.get("/api/proxy/naver")
def api_proxy_naver(url: str) -> Any:
    parsed = urlparse(url)
    allowed_hosts = {"m.stock.naver.com", "ac.stock.naver.com", "api.stock.naver.com", "finance.naver.com"}
    if parsed.scheme != "https" or parsed.netloc not in allowed_hosts:
        raise HTTPException(status_code=400, detail="Disallowed proxy target")
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        timeout=8,
    )
    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail="Upstream fetch error")
    return resp.json()


@app.get("/api/external/dart")
def api_external_dart(q: str, count: int = 5) -> Dict[str, Any]:
    items = stock_service.get_dart_disclosures(q, page_count=min(max(count, 1), 10))
    return {
        "success": True,
        "query": q,
        "live": bool(os.environ.get("DART_API_KEY", "").strip()),
        "items": items or [],
    }


class GeminiAnalyzeReq(BaseModel):
    name: str
    code: Optional[str] = ""


@app.post("/api/external/gemini-analyze")
def api_external_gemini_analyze(req: GeminiAnalyzeReq) -> Dict[str, Any]:
    code = (req.code or "").strip()
    name = req.name.strip()
    if not code:
        resolved_name, resolved_code = stock_service.resolve_stock_code(name)
        if resolved_code:
            name = resolved_name or name
            code = resolved_code

    price_info = stock_service.get_realtime_price(code) if code else None
    finance_info = stock_service.get_financial_summary(code) if code else None
    news_list = stock_service.get_recent_news(code, page_size=3) if code else []
    result = stock_service.analyze_with_gemini(name, price_info, finance_info, news_list)
    return {
        "success": True,
        "name": name,
        "code": code,
        "source": result.get("source", "AI 분석"),
        "analysis": result.get("analysis", ""),
    }
