#!/usr/bin/env python3
"""
로컬 SQLite 동기화 및 관리자 감사 뷰어 도구 (db_manager.py)
- 회원 상태(pending/approved/blocked) 조회 및 변경
- 기기/브라우저 접속 로그 확인
- API 키 및 외부조회 차단 스위치 제어
"""

import sqlite3
import os
import sys
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'auth_audit.db')

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 회원 프로필
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL DEFAULT 'user',
        status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, blocked
        created_at TEXT
    )
    ''')
    
    # 2. 기기/브라우저 접속 로그
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS access_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        email TEXT,
        ip_address TEXT,
        browser TEXT,
        os TEXT,
        device_type TEXT,
        action TEXT,
        timestamp TEXT
    )
    ''')
    
    # 3. API 키 및 외부조회 제어
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS api_controls (
        user_id TEXT PRIMARY KEY,
        allow_external_query INTEGER DEFAULT 0, -- 1: 허용, 0: 차단
        api_key_enabled INTEGER DEFAULT 0,
        api_key_custom TEXT,
        updated_at TEXT
    )
    ''')
    
    # 기본 관리자 계정 생성 (없는 경우)
    cursor.execute("SELECT id FROM profiles WHERE role = 'admin'")
    if not cursor.fetchone():
        admin_id = "admin-root-001"
        now = datetime.now().isoformat()
        cursor.execute("INSERT OR IGNORE INTO profiles VALUES (?, ?, ?, ?, ?)",
                       (admin_id, "admin@myaccount.local", "admin", "approved", now))
        cursor.execute("INSERT OR IGNORE INTO api_controls VALUES (?, 1, 1, 'MASTER_KEY_LOCAL', ?)",
                       (admin_id, now))
        cursor.execute("INSERT INTO access_logs (user_id, email, ip_address, browser, os, device_type, action, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (admin_id, "admin@myaccount.local", "127.0.0.1", "Chrome", "Linux", "Desktop", "INITIALIZE", now))
    
    conn.commit()
    conn.close()

def list_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.id, p.email, p.role, p.status, 
           COALESCE(c.allow_external_query, 0), COALESCE(c.api_key_enabled, 0)
    FROM profiles p
    LEFT JOIN api_controls c ON p.id = c.user_id
    ORDER BY p.created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*80)
    print(f"{'ID':<18} | {'이메일':<25} | {'역할':<7} | {'승인상태':<8} | {'외부조회':<6} | {'API키':<6}")
    print("="*80)
    for r in rows:
        ext = "허용" if r[4] == 1 else "차단"
        key = "활성" if r[5] == 1 else "비활성"
        print(f"{r[0]:<18} | {r[1]:<25} | {r[2]:<7} | {r[3]:<8} | {ext:<8} | {key:<6}")
    print("="*80 + "\n")

def list_logs(limit=15):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, email, ip_address, browser, os, device_type, action, timestamp
    FROM access_logs
    ORDER BY id DESC LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*95)
    print(f"{'번호':<4} | {'이메일':<22} | {'IP':<14} | {'브라우저':<10} | {'OS/기기':<14} | {'동작':<8} | {'시간'}")
    print("="*95)
    for r in rows:
        dev = f"{r[4]}/{r[5]}"
        print(f"{r[0]:<4} | {r[1]:<22} | {r[2]:<14} | {r[3]:<10} | {dev:<14} | {r[6]:<8} | {r[7]}")
    print("="*95 + "\n")

def set_user_status(email, status):
    if status not in ['approved', 'pending', 'blocked']:
        print("유효하지 않은 상태입니다. (approved, pending, blocked 중 선택)")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE profiles SET status = ? WHERE email = ?", (status, email))
    if cursor.rowcount == 0:
        print(f"해당 이메일({email})의 사용자를 찾을 수 없습니다.")
    else:
        conn.commit()
        print(f"✅ {email} 사용자의 상태가 [{status}] 로 변경되었습니다.")
    conn.close()

def toggle_external_query(email, allow):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE api_controls 
    SET allow_external_query = ?, updated_at = ?
    WHERE user_id = (SELECT id FROM profiles WHERE email = ?)
    ''', (1 if allow else 0, datetime.now().isoformat(), email))
    if cursor.rowcount == 0:
        print(f"사용자를 찾을 수 없거나 컨트롤 레코드가 없습니다: {email}")
    else:
        conn.commit()
        val = "허용(ON)" if allow else "차단(OFF)"
        print(f"✅ {email} 외부 조회 권한이 [{val}]으로 설정되었습니다.")
    conn.close()

if __name__ == '__main__':
    init_db()
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'users':
            list_users()
        elif cmd == 'logs':
            list_logs()
        elif cmd == 'approve' and len(sys.argv) > 2:
            set_user_status(sys.argv[2], 'approved')
        elif cmd == 'block' and len(sys.argv) > 2:
            set_user_status(sys.argv[2], 'blocked')
        elif cmd == 'toggle-query' and len(sys.argv) > 3:
            toggle_external_query(sys.argv[2], sys.argv[3].lower() in ['true', '1', 'on'])
        else:
            print("사용법:")
            print("  python db_manager.py users")
            print("  python db_manager.py logs")
            print("  python db_manager.py approve <email>")
            print("  python db_manager.py block <email>")
            print("  python db_manager.py toggle-query <email> <on/off>")
    else:
        print("💡 SQLite 감사 데이터베이스 초기화 완료: data/auth_audit.db")
        list_users()
        list_logs(5)
