from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_ip_hash,
    DUMMY_PASSWORD_HASH,
)
from app.db.session import get_db
from app.db.models import User, AuditLog
from app.schemas.auth import RegisterIn, LoginIn, UserOut, AuthOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


def _get_client_ip(request: Request) -> str:
    """Mengambil alamat IP klien dengan fallback aman."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def register(request: Request, payload: RegisterIn, db: Session = Depends(get_db)) -> AuthOut:
    """Mendaftarkan pengguna baru dengan rate limit 5 per jam per IP."""
    ip = _get_client_ip(request)
    ip_hash = generate_ip_hash(ip)

    # Periksa duplikasi email
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        # Catat audit kegagalan registrasi
        audit = AuditLog(
            user_id=None,
            action="register",
            status="failed",
            ip_hash=ip_hash,
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email sudah terdaftar",
        )

    # Hash password dengan bcrypt
    password_hashed = hash_password(payload.password)

    new_user = User(
        nama=payload.nama,
        email=payload.email,
        password_hash=password_hashed,
        role="user",
    )
    db.add(new_user)
    db.flush()

    # Catat audit keberhasilan registrasi
    audit = AuditLog(
        user_id=new_user.id,
        action="register",
        status="success",
        ip_hash=ip_hash,
    )
    db.add(audit)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(subject=str(new_user.id))
    user_out = UserOut(id=str(new_user.id), nama=new_user.nama, email=new_user.email)
    return AuthOut(user=user_out, token=token)


@router.post("/login", response_model=AuthOut)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginIn, db: Session = Depends(get_db)) -> AuthOut:
    """Autentikasi pengguna dengan mitigasi user enumeration dan rate limit 5 per menit per IP."""
    ip = _get_client_ip(request)
    ip_hash = generate_ip_hash(ip)

    user = db.query(User).filter(User.email == payload.email).first()

    # Jika email tidak ditemukan, tetap jalankan verifikasi hash dummy
    # agar waktu eksekusi identik dan tidak membocorkan keberadaan email (mitigasi timing attack)
    if not user:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        audit = AuditLog(
            user_id=None,
            action="login_failed",
            status="failed",
            ip_hash=ip_hash,
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau kata sandi salah",
        )

    if not verify_password(payload.password, user.password_hash):
        audit = AuditLog(
            user_id=user.id,
            action="login_failed",
            status="failed",
            ip_hash=ip_hash,
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau kata sandi salah",
        )

    # Catat login sukses
    audit = AuditLog(
        user_id=user.id,
        action="login_success",
        status="success",
        ip_hash=ip_hash,
    )
    db.add(audit)
    db.commit()

    token = create_access_token(subject=str(user.id))
    user_out = UserOut(id=str(user.id), nama=user.nama, email=user.email)
    return AuthOut(user=user_out, token=token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Mengembalikan data profil pengguna yang sedang login berdasarkan token JWT."""
    return UserOut(
        id=str(current_user.id),
        nama=current_user.nama,
        email=current_user.email,
    )
