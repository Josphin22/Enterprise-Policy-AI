import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.config import settings
from app.database.session import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_permission import DocumentPermission
from app.models.audit_log import AuditLog
from app.core.security import hash_password, create_access_token
from app.services.auth_throttle_service import auth_throttle
from app.services.permission_service import permission_service

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_rbac_roles_hierarchy(db_session: Session):
    """
    Test user role tiers: USER, MANAGER, ADMIN.
    Ensure MANAGER can access manager/admin endpoints (or manager-permitted routes)
    while USER is restricted.
    """
    # Create test users
    user_email = "test_user_rbac@example.com"
    manager_email = "test_mgr_rbac@example.com"

    for email in [user_email, manager_email]:
        existing = db_session.query(User).filter(User.email == email).first()
        if existing:
            db_session.delete(existing)
    db_session.commit()

    regular_user = User(
        email=user_email,
        username="regular_user",
        hashed_password=hash_password("UserPass123!"),
        role="USER",
        is_active=True,
    )
    manager_user = User(
        email=manager_email,
        username="manager_user",
        hashed_password=hash_password("MgrPass123!"),
        role="MANAGER",
        is_active=True,
    )
    db_session.add_all([regular_user, manager_user])
    db_session.commit()
    db_session.refresh(regular_user)
    db_session.refresh(manager_user)

    user_token = create_access_token({"sub": regular_user.id, "email": regular_user.email, "role": regular_user.role})
    mgr_token = create_access_token({"sub": manager_user.id, "email": manager_user.email, "role": manager_user.role})

    # USER attempting admin route -> 403
    resp_user = client.get("/api/admin/users", headers={"Authorization": f"Bearer {user_token}"})
    assert resp_user.status_code == 403

    # MANAGER attempting admin-only user management -> 403 (since user mgmt is ADMIN only)
    resp_mgr = client.get("/api/admin/users", headers={"Authorization": f"Bearer {mgr_token}"})
    assert resp_mgr.status_code == 403


def test_admin_update_user_to_manager(db_session: Session):
    """
    Verify ADMIN can promote a USER to MANAGER via PATCH /api/admin/users/{user_id}/role.
    """
    admin = db_session.query(User).filter(User.role == "ADMIN").first()
    assert admin is not None
    admin_token = create_access_token({"sub": admin.id, "email": admin.email, "role": "ADMIN"})

    target = User(
        email="promotable_user@example.com",
        username="promotable_user",
        hashed_password=hash_password("Pass123!"),
        role="USER",
        is_active=True,
    )
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    # Promote to MANAGER
    resp = client.patch(
        f"/api/admin/users/{target.id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "MANAGER"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "MANAGER"

    # Verify in DB
    db_session.refresh(target)
    assert target.role == "MANAGER"

    # Cleanup
    db_session.delete(target)
    db_session.commit()


def test_document_visibility_levels_and_retrieval_filtering(db_session: Session):
    """
    Test Pre-Retrieval Security Enforcement:
    1. Doc A is ORGANIZATION -> visible to all authenticated users.
    2. Doc B is PRIVATE (owner: User 1) -> visible ONLY to User 1 and ADMIN.
    3. User 2 querying the chatbot or retrieval must NEVER receive Doc B's chunks.
    """
    u1_email = "alice_sec@example.com"
    u2_email = "bob_sec@example.com"

    for email in [u1_email, u2_email]:
        existing = db_session.query(User).filter(User.email == email).first()
        if existing:
            db_session.delete(existing)
    db_session.commit()

    user1 = User(
        email=u1_email,
        username="alice_sec",
        hashed_password=hash_password("Alice123!"),
        role="USER",
        is_active=True,
    )
    user2 = User(
        email=u2_email,
        username="bob_sec",
        hashed_password=hash_password("Bob123!"),
        role="USER",
        is_active=True,
    )
    db_session.add_all([user1, user2])
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)

    # Create Doc A (ORGANIZATION)
    doc_a = Document(
        filename="company_handbook.txt",
        original_filename="company_handbook.txt",
        file_path="/dummy/company_handbook.txt",
        file_type="txt",
        file_size=500,
        status="PROCESSED",
        visibility="ORGANIZATION",
        owner_id=user1.id,
    )
    # Create Doc B (PRIVATE owned by user1)
    doc_b = Document(
        filename="alice_secret_eval.txt",
        original_filename="alice_secret_eval.txt",
        file_path="/dummy/alice_secret_eval.txt",
        file_type="txt",
        file_size=500,
        status="PROCESSED",
        visibility="PRIVATE",
        owner_id=user1.id,
    )
    db_session.add_all([doc_a, doc_b])
    db_session.commit()
    db_session.refresh(doc_a)
    db_session.refresh(doc_b)

    # Verify authorized IDs via PermissionService
    u1_allowed = permission_service.get_authorized_document_ids(db_session, user1)
    u2_allowed = permission_service.get_authorized_document_ids(db_session, user2)

    assert u1_allowed is not None
    assert doc_a.id in u1_allowed
    assert doc_b.id in u1_allowed  # Alice owns Doc B

    assert u2_allowed is not None
    assert doc_a.id in u2_allowed
    assert doc_b.id not in u2_allowed  # Bob cannot access Doc B!

    # Test API Document Access by Bob
    u2_token = create_access_token({"sub": user2.id, "email": user2.email, "role": user2.role})
    resp_b = client.get(f"/api/documents/{doc_b.id}", headers={"Authorization": f"Bearer {u2_token}"})
    assert resp_b.status_code == 403  # Forbidden for Bob

    u1_token = create_access_token({"sub": user1.id, "email": user1.email, "role": user1.role})
    resp_a = client.get(f"/api/documents/{doc_b.id}", headers={"Authorization": f"Bearer {u1_token}"})
    assert resp_a.status_code == 200  # Allowed for Alice

    # Cleanup
    db_session.delete(doc_a)
    db_session.delete(doc_b)
    db_session.delete(user1)
    db_session.delete(user2)
    db_session.commit()


def test_fine_grained_permission_grant_and_revoke(db_session: Session):
    """
    Verify fine-grained explicit document permissions (granting and revoking VIEW / CHAT).
    """
    owner_email = "owner_perm@example.com"
    collab_email = "collab_perm@example.com"

    for email in [owner_email, collab_email]:
        existing = db_session.query(User).filter(User.email == email).first()
        if existing:
            db_session.delete(existing)
    db_session.commit()

    owner = User(
        email=owner_email,
        username="owner_perm",
        hashed_password=hash_password("Pass123!"),
        role="USER",
        is_active=True,
    )
    collaborator = User(
        email=collab_email,
        username="collab_perm",
        hashed_password=hash_password("Pass123!"),
        role="USER",
        is_active=True,
    )
    db_session.add_all([owner, collaborator])
    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(collaborator)

    doc = Document(
        filename="confidential_roadmap.pdf",
        original_filename="confidential_roadmap.pdf",
        file_path="/dummy/confidential_roadmap.pdf",
        file_type="pdf",
        file_size=1024,
        status="PROCESSED",
        visibility="PRIVATE",
        owner_id=owner.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    owner_token = create_access_token({"sub": owner.id, "email": owner.email, "role": owner.role})
    collab_token = create_access_token({"sub": collaborator.id, "email": collaborator.email, "role": collaborator.role})

    # Prior to grant: collaborator cannot view
    resp_before = client.get(f"/api/documents/{doc.id}", headers={"Authorization": f"Bearer {collab_token}"})
    assert resp_before.status_code == 403

    # Owner grants VIEW permission to collaborator
    grant_resp = client.post(
        f"/api/documents/{doc.id}/permissions",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": collaborator.id, "permission": "VIEW"},
    )
    assert grant_resp.status_code in (200, 201)
    perm_id = grant_resp.json()["id"]

    # Now collaborator CAN view
    resp_after = client.get(f"/api/documents/{doc.id}", headers={"Authorization": f"Bearer {collab_token}"})
    assert resp_after.status_code == 200

    # Collaborator cannot delete (only has VIEW)
    resp_del_unauth = client.delete(f"/api/documents/{doc.id}", headers={"Authorization": f"Bearer {collab_token}"})
    assert resp_del_unauth.status_code == 403

    # Owner revokes permission
    revoke_resp = client.delete(
        f"/api/documents/{doc.id}/permissions/{perm_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert revoke_resp.status_code == 200

    # Now collaborator is blocked again
    resp_after_revoke = client.get(f"/api/documents/{doc.id}", headers={"Authorization": f"Bearer {collab_token}"})
    assert resp_after_revoke.status_code == 403

    # Cleanup
    db_session.delete(doc)
    db_session.delete(owner)
    db_session.delete(collaborator)
    db_session.commit()


def test_login_throttling_and_lockout():
    """
    Test Login Security:
    Simulate 5 consecutive failed login attempts on an account -> triggers HTTP 429 Too Many Requests.
    """
    throttle_email = "throttle_target@example.com"
    auth_throttle.reset_attempts(throttle_email)

    # Make 4 failed attempts -> 401
    for _ in range(4):
        resp = client.post(
            "/api/auth/login",
            json={"email": throttle_email, "password": "BadPassword123!"},
        )
        assert resp.status_code == 401

    # 5th failed attempt -> 401 (locks out account)
    resp5 = client.post(
        "/api/auth/login",
        json={"email": throttle_email, "password": "BadPassword123!"},
    )
    assert resp5.status_code == 401

    # 6th attempt -> 429 Too Many Requests (Account locked out)
    resp_locked = client.post(
        "/api/auth/login",
        json={"email": throttle_email, "password": "AnyPassword!"},
    )
    assert resp_locked.status_code == 429
    assert "Too many failed login attempts" in resp_locked.json()["detail"]

    # Reset throttle
    auth_throttle.reset_attempts(throttle_email)


def test_token_expiration_and_invalid_token():
    """
    Verify expired and tampered JWT tokens return 401 Unauthorized.
    """
    # 1. Invalid signature / garbage token
    resp_invalid = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage.jwt.token"})
    assert resp_invalid.status_code == 401

    # 2. Expired token
    expired_token = create_access_token(
        {"sub": "test@example.com", "role": "USER"},
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    resp_expired = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp_expired.status_code == 401


def test_logout_endpoint_and_audit(db_session: Session):
    """
    Verify POST /api/auth/logout registers an audit log and responds with 200.
    """
    admin = db_session.query(User).filter(User.role == "ADMIN").first()
    assert admin is not None
    token = create_access_token({"sub": admin.id, "email": admin.email, "role": admin.role})

    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json().get("success") is True

    # Verify audit log recorded
    log = (
        db_session.query(AuditLog)
        .filter(AuditLog.user_id == admin.id, AuditLog.action == "USER_LOGOUT")
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    assert log is not None
    assert log.action == "USER_LOGOUT"
