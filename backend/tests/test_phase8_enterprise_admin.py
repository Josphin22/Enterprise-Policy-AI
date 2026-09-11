import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.config import settings
from app.database.session import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.chat import ChatSession, ChatMessage
from app.models.feedback import Feedback
from app.models.audit_log import AuditLog
from app.models.chat_metric import ChatMetric
from app.core.security import hash_password, create_access_token

client = TestClient(app)


@pytest.fixture
def db_session():
    from app.services.auth_throttle_service import auth_throttle
    auth_throttle._attempts.clear()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        auth_throttle._attempts.clear()


def test_admin_default_seeding_and_login(db_session: Session):
    """
    Verify default administrator is seeded automatically and can authenticate to receive JWT.
    """
    # 1. Verify admin exists in DB
    admin = db_session.query(User).filter(User.role == "ADMIN").first()
    assert admin is not None
    assert admin.email == settings.ADMIN_EMAIL

    # 2. Login with correct credentials
    login_resp = client.post(
        "/api/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
    data = login_resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["email"] == settings.ADMIN_EMAIL

    # 3. Login with bad password
    bad_login = client.post(
        "/api/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": "WrongPassword123!"},
    )
    assert bad_login.status_code == 401


def test_rbac_admin_route_protection(db_session: Session):
    """
    Verify /api/admin/* strictly enforces 401 for unauthenticated and 403 for non-admin users.
    """
    # 1. Unauthenticated request -> 401
    resp = client.get("/api/admin/dashboard")
    assert resp.status_code == 401

    # 2. Register normal user -> role 'USER'
    user_email = "employee_test@enterprise.com"
    existing = db_session.query(User).filter(User.email == user_email).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    reg_resp = client.post(
        "/api/auth/register",
        json={
            "email": user_email,
            "username": "Employee Test",
            "password": "Password123!",
        },
    )
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    user_token = user_data["access_token"]
    assert user_data["user"]["role"] == "USER"

    # 3. Non-admin request to admin dashboard -> 403 Forbidden
    forbidden_resp = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden_resp.status_code == 403
    assert "Administrative privileges required" in forbidden_resp.json()["detail"]


def test_admin_dashboard_metrics(db_session: Session):
    """
    Verify admin dashboard endpoint returns authentic database and system stats.
    """
    # Login as admin
    login_resp = client.post(
        "/api/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    admin_token = login_resp.json()["access_token"]

    dash_resp = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert dash_resp.status_code == 200
    data = dash_resp.json()

    assert "metrics" in data
    assert "system_status" in data
    assert "recent_activity" in data

    metrics = data["metrics"]
    assert "total_documents" in metrics
    assert "total_chunks" in metrics
    assert "total_users" in metrics
    assert "total_conversations" in metrics
    assert "total_messages" in metrics
    assert "storage_used_bytes" in metrics
    assert "feedback" in metrics


def test_admin_user_management(db_session: Session):
    """
    Test user listing, role modification, status toggling, and safety checks.
    """
    # Login as admin
    login_resp = client.post(
        "/api/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    admin_token = login_resp.json()["access_token"]
    admin_user = login_resp.json()["user"]

    # 1. List users
    users_resp = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert users_resp.status_code == 200
    users_list = users_resp.json()["items"]
    assert len(users_list) >= 1

    # Find or create a target user
    target_email = "target_emp@enterprise.com"
    target = db_session.query(User).filter(User.email == target_email).first()
    if not target:
        target = User(
            email=target_email,
            username="Target Employee",
            hashed_password=hash_password("Pass123!"),
            role="USER",
            is_active=True,
        )
        db_session.add(target)
        db_session.commit()
        db_session.refresh(target)

    # 2. Promote target user to ADMIN
    promote_resp = client.patch(
        f"/api/admin/users/{target.id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "ADMIN"},
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["role"] == "ADMIN"

    # 3. Demote target user back to USER
    demote_resp = client.patch(
        f"/api/admin/users/{target.id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "USER"},
    )
    assert demote_resp.status_code == 200
    assert demote_resp.json()["role"] == "USER"

    # 4. Attempt to deactivate own admin account -> should fail with 400
    self_deact_resp = client.patch(
        f"/api/admin/users/{admin_user['id']}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert self_deact_resp.status_code == 400
    assert "cannot deactivate your own" in self_deact_resp.json()["detail"].lower()

    # 5. Toggle target user active status
    deact_target = client.patch(
        f"/api/admin/users/{target.id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert deact_target.status_code == 200
    assert deact_target.json()["is_active"] is False

    # Reactivate target user
    react_target = client.patch(
        f"/api/admin/users/{target.id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": True},
    )
    assert react_target.status_code == 200
    assert react_target.json()["is_active"] is True


def test_system_health_diagnostic(db_session: Session):
    """
    Test GET /api/admin/system-health diagnostic endpoint.
    """
    login_resp = client.post(
        "/api/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    admin_token = login_resp.json()["access_token"]

    health_resp = client.get(
        "/api/admin/system-health",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert health_resp.status_code == 200
    data = health_resp.json()

    assert "database" in data
    assert data["database"]["connected"] is True
    assert "latency_ms" in data["database"]

    assert "ollama" in data
    assert "endpoint" in data["ollama"]
    assert "configured_model" in data["ollama"]

    assert "vector_store" in data
    assert "storage" in data
    assert data["storage"]["writable"] is True


def test_analytics_and_audit_logs(db_session: Session):
    """
    Test analytics query calculations and audit trail query.
    """
    login_resp = client.post(
        "/api/auth/login",
        json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    admin_token = login_resp.json()["access_token"]

    # 1. Analytics
    analytics_resp = client.get(
        "/api/admin/analytics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert analytics_resp.status_code == 200
    analytics_data = analytics_resp.json()
    assert "summary" in analytics_data
    assert "questions_timeline" in analytics_data
    assert "total_queries" in analytics_data["summary"]

    # 2. Audit Logs
    audit_resp = client.get(
        "/api/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert "items" in audit_data
    assert "total" in audit_data
    assert audit_data["total"] >= 1
    # Verify actions were recorded
    actions = [item["action"] for item in audit_data["items"]]
    assert any("LOGIN" in a or "ROLE" in a or "STATUS" in a for a in actions)


def test_path_traversal_upload_rejection():
    """
    Verify security protection against malicious directory traversal uploads.
    """
    fake_content = b"Confidential system information."
    traversal_filenames = [
        "../../etc/passwd.txt",
        "..\\..\\windows\\win.ini.txt",
        "nested/../../secret.txt",
    ]

    for bad_name in traversal_filenames:
        resp = client.post(
            "/api/documents/upload",
            files={"file": (bad_name, io.BytesIO(fake_content), "text/plain")},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "INVALID_FILE_TYPE" or "directory traversal" in str(data).lower()
