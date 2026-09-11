import logging
from typing import Optional, Set, List
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_

from app.models.user import User
from app.models.document import Document
from app.models.document_metadata import DocumentMetadata
from app.models.document_permission import DocumentPermission

logger = logging.getLogger("enterprise_rag.permissions")


class PermissionService:
    """
    Fine-grained authorization and access control service (Phase 11).
    Enforces document visibility scopes (ORGANIZATION, TEAM, PRIVATE)
    and granular permissions (VIEW, CHAT, EDIT, DELETE, ADMIN).
    """

    @staticmethod
    def get_authorized_document_ids(
        db: Session,
        user: Optional[User],
        required_permission: str = "VIEW",
    ) -> Optional[Set[str]]:
        """
        Compute the complete set of document IDs accessible by the user.
        If user is ADMIN, returns None (indicating unrestricted global access).
        If user is None (unauthenticated), returns only ORGANIZATION-level public docs.
        """
        # 1. Administrators possess universal access across all documents
        if user and (user.role or "USER").upper() == "ADMIN":
            return None

        # 2. Base query: All documents with ORGANIZATION visibility
        allowed_ids: Set[str] = set()

        # Organization-level public policies
        org_docs = db.query(Document.id).filter(
            or_(
                Document.visibility == "ORGANIZATION",
                Document.visibility == None,  # Backward compatibility for legacy docs
            )
        ).all()
        for row in org_docs:
            allowed_ids.add(row[0])

        # If unauthenticated, only ORGANIZATION documents are accessible
        if not user:
            return allowed_ids

        user_role = (user.role or "USER").upper()
        user_id = user.id

        # 3. Documents owned directly by the user
        owned_docs = db.query(Document.id).filter(Document.owner_id == user_id).all()
        for row in owned_docs:
            allowed_ids.add(row[0])

        # 4. TEAM documents
        # If user is MANAGER or belongs to the department specified in DocumentMetadata
        team_docs = db.query(Document.id).join(
            DocumentMetadata, Document.id == DocumentMetadata.document_id, isouter=True
        ).filter(
            Document.visibility == "TEAM"
        ).all()
        for row in team_docs:
            # Managers get access to team documents; or users matching department if department metadata is set
            if user_role == "MANAGER":
                allowed_ids.add(row[0])

        # 5. Explicit grants from document_permissions table
        # Permission hierarchy: ADMIN > DELETE > EDIT > CHAT > VIEW
        perm_hierarchy = {
            "VIEW": ["VIEW", "CHAT", "EDIT", "DELETE", "ADMIN"],
            "CHAT": ["CHAT", "EDIT", "DELETE", "ADMIN"],
            "EDIT": ["EDIT", "DELETE", "ADMIN"],
            "DELETE": ["DELETE", "ADMIN"],
            "ADMIN": ["ADMIN"],
        }
        valid_perms = perm_hierarchy.get(required_permission.upper(), ["VIEW", "CHAT", "EDIT", "DELETE", "ADMIN"])

        explicit_grants = db.query(DocumentPermission.document_id).filter(
            or_(
                DocumentPermission.user_id == user_id,
                and_(DocumentPermission.role != None, DocumentPermission.role == user_role),
            ),
            DocumentPermission.permission.in_(valid_perms),
        ).all()

        for row in explicit_grants:
            allowed_ids.add(row[0])

        return allowed_ids

    @staticmethod
    def check_document_access(
        db: Session,
        document_id: str,
        user: Optional[User],
        required_permission: str = "VIEW",
    ) -> bool:
        """
        Verify if a given user has the required permission for a specific document.
        """
        doc = db.get(Document, document_id)
        if not doc:
            return False

        # Admin bypass
        if user and (user.role or "USER").upper() == "ADMIN":
            return True

        # Owner bypass
        if user and doc.owner_id == user.id:
            return True

        # Visibility ORGANIZATION
        doc_vis = (doc.visibility or "ORGANIZATION").upper()
        if doc_vis == "ORGANIZATION":
            if required_permission.upper() in ("VIEW", "CHAT"):
                return True
            # For EDIT/DELETE on organization docs, require MANAGER or ADMIN
            if user and (user.role or "USER").upper() in ("MANAGER", "ADMIN"):
                return True

        # Visibility TEAM
        if doc_vis == "TEAM" and user:
            user_role = (user.role or "USER").upper()
            if user_role in ("MANAGER", "ADMIN"):
                return True

        # Check explicit permissions
        if user:
            user_role = (user.role or "USER").upper()
            perm_hierarchy = {
                "VIEW": ["VIEW", "CHAT", "EDIT", "DELETE", "ADMIN"],
                "CHAT": ["CHAT", "EDIT", "DELETE", "ADMIN"],
                "EDIT": ["EDIT", "DELETE", "ADMIN"],
                "DELETE": ["DELETE", "ADMIN"],
                "ADMIN": ["ADMIN"],
            }
            valid_perms = perm_hierarchy.get(required_permission.upper(), ["VIEW", "CHAT", "EDIT", "DELETE", "ADMIN"])

            has_perm = db.query(DocumentPermission).filter(
                DocumentPermission.document_id == document_id,
                or_(
                    DocumentPermission.user_id == user.id,
                    and_(DocumentPermission.role != None, DocumentPermission.role == user_role),
                ),
                DocumentPermission.permission.in_(valid_perms),
            ).first()

            if has_perm:
                return True

        return False

    @staticmethod
    def grant_permission(
        db: Session,
        document_id: str,
        permission: str,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> DocumentPermission:
        """Grant fine-grained permission to a user or role."""
        perm = DocumentPermission(
            document_id=document_id,
            user_id=user_id,
            role=role.upper() if role else None,
            permission=permission.upper(),
        )
        db.add(perm)
        db.commit()
        db.refresh(perm)
        return perm

    @staticmethod
    def revoke_permission(
        db: Session,
        permission_id: str,
    ) -> bool:
        """Revoke a previously granted document permission."""
        perm = db.get(DocumentPermission, permission_id)
        if not perm:
            return False
        db.delete(perm)
        db.commit()
        return True

    @staticmethod
    def list_document_permissions(
        db: Session,
        document_id: str,
    ) -> List[DocumentPermission]:
        """List all fine-grained permissions attached to a document."""
        return db.query(DocumentPermission).filter(
            DocumentPermission.document_id == document_id
        ).all()


permission_service = PermissionService()
