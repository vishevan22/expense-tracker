# app/auth.py

from fastapi import APIRouter, Request, Form, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from starlette.responses import RedirectResponse
from .database import SessionLocal
from .models import User, Category
from .default_categories import DEFAULT_CATEGORIES
from fastapi.templating import Jinja2Templates
import re

emplates = Jinja2Templates(directory="app/templates")

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_valid_email(email: str) -> bool:
    pattern = r"^[\w\.-]+@[\w\.-]+\.(com)$"
    return re.match(pattern, email) is not None


# Register (Signup)
@router.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if not is_valid_email(email):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Invalid email format (e.g. name@gmail.com).",
            },
        )

    user = db.query(User).filter(User.email == email).first()
    if user:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": "Email already registered."}
        )

    hashed_password = bcrypt.hash(password)
    new_user = User(name=name, email=email, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Add default categories for new user
    for cat in DEFAULT_CATEGORIES:
        category = Category(
            name=cat["name"],
            type=cat["type"],
            user_id=new_user.id
        )
        db.add(category)
    db.commit()

    return RedirectResponse("/login", status_code=302)


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not bcrypt.verify(password, user.password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid email or password."}
        )

    request.session["user_id"] = user.id
    request.session["name"] = user.name
    return RedirectResponse("/dashboard", status_code=302)


# Logout
@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)
