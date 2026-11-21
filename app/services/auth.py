"""Authentication and authorization service."""
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.models import User, Officer


# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user


def create_user(
    db: Session,
    email: str,
    password: str,
    full_name: str,
    role: str,
    phone: Optional[str] = None,
    officer_id: Optional[int] = None
) -> User:
    """Create a new user account."""
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise ValueError("Email already registered")
    
    # Hash password
    password_hash = hash_password(password)
    
    # Create user
    user = User(
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        role=role,
        phone=phone,
        officer_id=officer_id,
        is_active=True,
        is_verified=False if role == "citizen" else True  # Officers pre-verified
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


def get_current_user(db: Session, token: str) -> Optional[User]:
    """Get current user from JWT token."""
    payload = decode_access_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    return user


def require_role(user: User, allowed_roles: list[str]) -> bool:
    """Check if user has required role."""
    return user.role in allowed_roles


def can_access_ticket(user: User, ticket, db: Session) -> bool:
    """Check if user can access a specific ticket."""
    # Citizens can only access their own tickets
    if user.role == "citizen":
        return ticket.reported_by_user_id == user.id
    
    # Officers can access tickets in their ward or assigned to them
    if user.role == "officer" and user.officer_id:
        officer = db.query(Officer).filter(Officer.id == user.officer_id).first()
        if officer:
            # Can access if in same ward or assigned
            if ticket.ward_id == officer.ward_id:
                return True
            if ticket.assigned_officer_id == officer.id:
                return True
            if ticket.escalated_to_officer_id == officer.id:
                return True
    
    # Admins can access everything
    if user.role == "admin":
        return True
    
    return False


def get_user_permissions(user: User) -> list[str]:
    """Get list of permissions for a user."""
    permissions = []
    
    if user.role == "citizen":
        permissions = [
            "create_ticket",
            "view_own_tickets",
            "provide_feedback",
        ]
    elif user.role == "officer":
        permissions = [
            "view_assigned_tickets",
            "view_ward_tickets",
            "assign_tickets",
            "resolve_tickets",
            "request_clock_stop",
            "escalate_tickets",
        ]
    elif user.role == "admin":
        permissions = [
            "view_all_tickets",
            "manage_users",
            "manage_officers",
            "manage_wards",
            "manage_contractors",
            "approve_clock_stop",
            "view_analytics",
            "export_data",
        ]
    
    return permissions
