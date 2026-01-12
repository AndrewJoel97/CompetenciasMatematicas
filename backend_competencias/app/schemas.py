from pydantic import BaseModel, EmailStr, Field
from pydantic.config import ConfigDict

# ===== AUTH INPUTS =====
class UserCreate(BaseModel):
    nombre: str = Field(min_length=2)
    correo: EmailStr
    password: str = Field(min_length=4)

class UserLogin(BaseModel):
    correo: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ===== OUTPUTS =====
class UserOut(BaseModel):
    id: int
    nombre: str
    correo: EmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)

# ===== ADMIN INPUT =====
class PromoteRole(BaseModel):
    role: str  # "docente" o "admin"
