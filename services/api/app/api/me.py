from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.models import User
from app.schemas import UserResponse


router = APIRouter(tags=["identity"])


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
