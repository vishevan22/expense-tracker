from datetime import date
from sqlalchemy.orm import Session
from app.models import Category, CategoryBudget


def get_all_categories_with_budget(db: Session, user_id: int):
    """Get all categories and their budget for the current month"""
    today = date.today()
    current_month, current_year = today.month, today.year

    categories = db.query(Category).filter(
        (Category.user_id == user_id) | (Category.user_id == None)
    ).all()

    budgets = db.query(CategoryBudget).filter(
        CategoryBudget.user_id == user_id,
        CategoryBudget.month == current_month,
        CategoryBudget.year == current_year
    ).all()
    budget_map = {b.category_id: b.budget for b in budgets}

    for cat in categories:
        cat.budget = budget_map.get(cat.id)

    return categories


def upsert_category_budget(db: Session, category_id: int, user_id: int, budget: float):
    """Insert or update the budget for the current month"""
    today = date.today()
    current_month, current_year = today.month, today.year

    existing = db.query(CategoryBudget).filter_by(
        category_id=category_id,
        user_id=user_id,
        month=current_month,
        year=current_year
    ).first()

    if existing:
        existing.budget = budget
    else:
        new = CategoryBudget(
            category_id=category_id,
            user_id=user_id,
            month=current_month,
            year=current_year,
            budget=budget
        )
        db.add(new)
    db.commit()
