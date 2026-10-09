"""OSINT Brasil Flow routes: every case and evidence read is user-scoped."""

from fastapi import Depends
from osintbr.api import build_router

from app.api.deps import get_current_user


def owner_id(user=Depends(get_current_user)):
    return str(user.id)


router = build_router(owner_id)
