"""
Security utilities for Legal AI Agent
- JWT secret validation
- Log sanitization
- Rate limiting
- Password validation
"""
import os
import re
import hmac
import warnings
from typing import Optional
from collections import defaultdict
import time

# ============================================
# FIX 1: JWT Secret Validation
# ============================================

def validate_jwt_secret() -> str:
    """Validate JWT secret and reject weak defaults"""
    JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
    
    if not JWT_SECRET or "change-in-production" in JWT_SECRET or len(JWT_SECRET) < 32:
        warnings.warn("⚠️ JWT_SECRET is weak or not set! Set SUPABASE_JWT_SECRET in .env")
        
        # In production, should raise error. For dev, generate random:
        if os.getenv("ENV", "development") == "production":
            raise ValueError("CRITICAL: Set a strong SUPABASE_JWT_SECRET in production!")
        
        # For development, warn but allow (don't break local dev)
        if not JWT_SECRET:
            JWT_SECRET = "dev-secret-key-" + os.urandom(16).hex()
            warnings.warn(f"⚠️ Using temporary development JWT secret")
    
    return JWT_SECRET


# ============================================
# FIX 7: Log Sanitization
# ============================================

def sanitize_log(msg: str) -> str:
    """Remove API keys, JWTs, and secrets from log messages"""
    import re
    
    # Redact API keys (OpenAI, Anthropic, custom)
    msg = re.sub(r'(sk-[a-zA-Z0-9]{20,})', '[REDACTED_API_KEY]', msg)
    msg = re.sub(r'(lak_[a-f0-9]{40,})', '[REDACTED_KEY]', msg)
    
    # Redact JWTs
    msg = re.sub(r'(eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)', '[REDACTED_JWT]', msg)
    
    # Redact passwords in form data
    msg = re.sub(r'(password["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', r'\1[REDACTED]', msg, flags=re.IGNORECASE)
    
    # Redact tokens
    msg = re.sub(r'(token["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', r'\1[REDACTED]', msg, flags=re.IGNORECASE)
    
    return msg


# ============================================
# FIX 8: Rate Limiting
# ============================================

class RateLimiter:
    """In-memory rate limiter with sliding window"""
    
    def __init__(self):
        self._requests = defaultdict(list)
    
    def check(self, key: str, max_req: int, window_sec: int) -> bool:
        """
        Check if key is within rate limit.
        Returns True if allowed, False if limit exceeded.
        """
        now = time.time()
        
        # Clean old requests outside window
        self._requests[key] = [t for t in self._requests[key] if t > now - window_sec]
        
        # Check if limit exceeded
        if len(self._requests[key]) >= max_req:
            return False
        
        # Add current request
        self._requests[key].append(now)
        return True
    
    def reset(self, key: str):
        """Reset rate limit for a key"""
        if key in self._requests:
            del self._requests[key]
    
    def get_remaining(self, key: str, max_req: int, window_sec: int) -> int:
        """Get remaining requests in current window"""
        now = time.time()
        self._requests[key] = [t for t in self._requests[key] if t > now - window_sec]
        return max(0, max_req - len(self._requests[key]))


# Global rate limiter instance
rate_limiter = RateLimiter()


# ============================================
# FIX 9: Password Policy
# ============================================

def validate_password(password: str) -> None:
    """
    Validate password strength.
    Raises HTTPException if password is weak.
    """
    from fastapi import HTTPException
    
    if len(password) < 10:
        raise HTTPException(400, "Password must be at least 10 characters")
    
    if not re.search(r'[A-Z]', password):
        raise HTTPException(400, "Password must contain an uppercase letter")
    
    if not re.search(r'[a-z]', password):
        raise HTTPException(400, "Password must contain a lowercase letter")
    
    if not re.search(r'[0-9]', password):
        raise HTTPException(400, "Password must contain a number")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise HTTPException(400, "Password must contain a special character")
    
    # Check common weak passwords
    weak_passwords = {
        'password123', 'admin123', 'welcome123', '12345678', 
        'qwerty123', 'letmein123', 'password1', 'abc123456'
    }
    if password.lower() in weak_passwords:
        raise HTTPException(400, "Password is too common. Choose a stronger one.")


# ============================================
# FIX 3: Path Traversal Prevention
# ============================================

ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.xlsx', '.xls', '.jpg', '.jpeg', '.png'}

def sanitize_filename(filename: str) -> tuple:
    """
    Sanitize uploaded filename to prevent path traversal.
    Returns (unique_name, extension)
    """
    import uuid
    from fastapi import HTTPException
    
    # Remove path components and dangerous characters
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
    
    # Extract extension
    ext = os.path.splitext(safe_name)[1].lower()
    
    # Validate extension
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type {ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Generate unique name with UUID
    unique_name = f"{uuid.uuid4()}{ext}"
    
    return unique_name, ext


def validate_file_path(file_path, company_dir):
    """
    Validate that file_path is within company_dir (prevent path traversal).
    Raises HTTPException if path is invalid.
    """
    from pathlib import Path
    from fastapi import HTTPException
    
    # Resolve to absolute paths
    file_path_resolved = Path(file_path).resolve()
    company_dir_resolved = Path(company_dir).resolve()
    
    # Check if file_path is within company_dir
    try:
        file_path_resolved.relative_to(company_dir_resolved)
    except ValueError:
        raise HTTPException(400, "Invalid file path")
    
    return file_path_resolved


# ============================================
# FIX 5: File Upload DoS Prevention
# ============================================

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def check_content_length(request, max_size: int = MAX_FILE_SIZE):
    """
    Check Content-Length header BEFORE reading file.
    Raises HTTPException if file is too large.
    """
    from fastapi import HTTPException, Request
    
    content_length = request.headers.get("content-length")
    
    if content_length and int(content_length) > max_size:
        raise HTTPException(
            413, 
            f"File too large. Maximum size: {max_size // (1024*1024)}MB"
        )


# ============================================
# FIX 12: API Key Storage with HMAC
# ============================================

SERVER_SECRET = os.getenv("API_KEY_SECRET")
if not SERVER_SECRET:
    SERVER_SECRET = os.urandom(32).hex()
    warnings.warn("⚠️ API_KEY_SECRET not set. Using random secret (will change on restart)")

def hash_api_key(key: str) -> str:
    """Hash API key with HMAC for secure storage"""
    return hmac.new(SERVER_SECRET.encode(), key.encode(), 'sha256').hexdigest()


def verify_api_key_hash(key: str, stored_hash: str) -> bool:
    """Verify API key against stored HMAC hash"""
    computed_hash = hash_api_key(key)
    return hmac.compare_digest(computed_hash, stored_hash)


# ============================================
# FIX 2: SQL Injection Prevention Helpers
# ============================================

# Whitelist of allowed column names for dynamic UPDATE queries
ALLOWED_UPDATE_COLUMNS = {
    "plan", "monthly_quota", "metadata", "name", "status", 
    "is_active", "role", "notes", "description", "title",
    "content", "doc_type", "contract_type", "parties",
    "start_date", "end_date", "value"
}

def validate_column_name(column: str) -> str:
    """
    Validate column name against whitelist.
    Prevents SQL injection in dynamic queries.
    """
    from fastapi import HTTPException
    
    if column not in ALLOWED_UPDATE_COLUMNS:
        raise HTTPException(400, f"Invalid column name: {column}")
    
    return column


# ============================================
# FIX 14: JWT Improvements
# ============================================

# Reduced token lifetimes
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Was 60, now 15 minutes
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Was 30, now 7 days

def create_jwt_with_jti(data: dict, token_type: str = "access") -> str:
    """
    Create JWT with jti (JWT ID) for future revocation support.
    """
    import jwt
    import uuid
    from datetime import datetime, timedelta
    
    to_encode = data.copy()
    
    # Add jti (JWT ID) for revocation
    to_encode["jti"] = str(uuid.uuid4())
    to_encode["type"] = token_type
    
    # Set expiration based on token type
    if token_type == "access":
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    elif token_type == "refresh":
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire = datetime.utcnow() + timedelta(hours=1)
    
    to_encode["exp"] = expire
    
    # Get validated JWT secret
    secret = validate_jwt_secret()
    
    return jwt.encode(to_encode, secret, algorithm="HS256")
