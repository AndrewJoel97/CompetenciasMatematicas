from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from .database import Base, engine, get_db, SessionLocal
from .models import User
from .schemas import UserCreate, UserLogin, TokenResponse, UserOut, PromoteRole, UserUpdate
from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin
)

# Lifespan: se lo pasaremos a FastAPI al crear la app
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting lifespan")
    try:
        print("Creating tables")
        # Crear tablas (si no existen)
        Base.metadata.create_all(bind=engine)
        print("Seeding admin")
        # Seed admin
        db = SessionLocal()
        try:
            seed_admin(db)
        finally:
            db.close()
        print("Lifespan startup complete")
    except Exception as e:
        print(f"Error in startup: {e}")
        import traceback
        traceback.print_exc()
    yield
    print("Lifespan shutdown")

# Pasamos lifespan al crear la app para que se ejecute correctamente
app = FastAPI(title="Backend Competencias", version="1.0", lifespan=lifespan)

@app.get("/")
def root():
    print("Root endpoint called")
    return {"ok": True, "message": "API Competencias OK", "timestamp": "2026-01-10"}

# CORS para Angular (en desarrollo está bien usar "*", en producción limitar orígenes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== SEED ADMIN (solo si no existe) =====
def seed_admin(db: Session):
    admin_email = "admin@ug.edu.ec"
    admin_password = "Admin1234"

    # Buscar por nombre o correo
    exists = db.query(User).filter(
        (User.correo == admin_email) | (User.nombre == "Administrador")
    ).first()
    
    if not exists:
        admin = User(
            nombre="Administrador",
            correo=admin_email,
            password_hash=hash_password(admin_password),
            role="admin",
        )
        db.add(admin)
        db.commit()
        print("Admin seeded successfully")
    else:
        # Asegurar que tenga el correo correcto
        if exists.correo != admin_email:
            exists.correo = admin_email
            exists.password_hash = hash_password(admin_password)
            db.commit()
            print("Admin updated successfully")
        else:
            print("Admin already exists")

# ========= AUTH =========

@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.correo == payload.correo).first()
    if exists:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    # Validar dominio del correo
    if not payload.correo.endswith('@ug.edu.ec'):
        raise HTTPException(status_code=400, detail="El correo debe terminar en @ug.edu.ec")

    # ✅ por seguridad: siempre estudiante
    user = User(
        nombre=payload.nombre,
        correo=payload.correo,
        password_hash=hash_password(payload.password),
        role="estudiante"
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.post("/auth/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.correo == payload.correo).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no existe")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

# ========= ADMIN =========
@app.get("/admin/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).order_by(User.id.desc()).all()

# ===== NUEVO: Actualizar usuario completo (nombre, correo, rol) =====
@app.put("/admin/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """
    Actualiza datos del usuario (nombre, correo, rol)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Actualizar nombre
    if payload.nombre:
        user.nombre = payload.nombre
    
    # Actualizar correo
    if payload.correo:
        # Verificar que el correo no esté en uso
        existing = db.query(User).filter(User.correo == payload.correo, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="El correo ya está en uso")
        user.correo = payload.correo
    
    # Actualizar rol
    if payload.role:
        if payload.role not in ["docente", "admin", "estudiante"]:
            raise HTTPException(status_code=400, detail="Rol inválido")
        user.role = payload.role

    db.commit()
    db.refresh(user)
    return user

# ===== ALTERNATIVA: POST para actualizar (por si lo prefieres) =====
@app.post("/admin/users/{user_id}", response_model=UserOut)
def update_user_post(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """
    Alternativa POST para actualizar usuario
    """
    return update_user(user_id, payload, db, _)

# ===== CAMBIAR ROL (ahora acepta PUT, POST y PATCH) =====
@app.put("/admin/users/{user_id}/role", response_model=UserOut)
def change_role_put(user_id: int, payload: PromoteRole, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Cambiar rol vía PUT"""
    if payload.role not in ["docente", "admin", "estudiante"]:
        raise HTTPException(status_code=400, detail="Rol inválido")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user

@app.post("/admin/users/{user_id}/role", response_model=UserOut)
def change_role_post(user_id: int, payload: PromoteRole, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Cambiar rol vía POST"""
    return change_role_put(user_id, payload, db, _)

@app.patch("/admin/users/{user_id}/role", response_model=UserOut)
def change_role_patch(user_id: int, payload: PromoteRole, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Cambiar rol vía PATCH"""
    return change_role_put(user_id, payload, db, _)

@app.delete("/admin/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), current_admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # No permitir que se auto-elimine
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")
    
    db.delete(user)
    db.commit()
    return None