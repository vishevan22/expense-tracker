from sqlalchemy.orm import Session
from .models import Expense, Category
from sqlalchemy import  func, case
from datetime import datetime, timedelta
from app.models import Expense
from .models import CategoryBudget
from app import models

def add_expense(user_id: int, date, category_id: int, amount: float, description: str, type: str, db: Session):
    expense = Expense(
        user_id=user_id,
        date=date,
        category_id=category_id,
        amount=amount,
        description=description,
        type=type
    )
    db.add(expense)
    db.commit()

def get_transaction_by_id(db: Session, txn_id: int, user_id: int):
    return db.query(Expense).filter(Expense.id == txn_id, Expense.user_id == user_id).first()

def update_transaction(db: Session, txn_id: int, date, type, category_id, amount, description):
    txn = db.query(models.Expense).filter(models.Expense.id == txn_id).first()
    if txn:
        txn.date = date
        txn.type = type
        txn.category_id = category_id
        txn.amount = amount
        txn.description = description
        db.commit()
        
def delete_transaction(db: Session, txn_id: int):
    txn = db.query(models.Expense).filter(models.Expense.id == txn_id).first()
    if txn:
        db.delete(txn)
        db.commit()



def get_filtered_transactions(user_id: int, type: str, from_date, to_date, db: Session):
    query = db.query(Expense).filter(
        Expense.user_id == user_id,
        Expense.date >= from_date,
        Expense.date <= to_date
    ).join(Category)

    if type in ["income", "expense"]:
        query = query.filter(Expense.type == type)

    return query.order_by(Expense.date.desc()).all()

def get_stats(user_id: int, db: Session):
    income = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.user_id == user_id, Expense.type == "income"
    ).scalar()

    expense = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.user_id == user_id, Expense.type == "expense"
    ).scalar()

    profit = income - expense
    return income, expense, profit

def get_pie_chart_data_filtered(user_id: int, type: str, from_date, to_date, db: Session):
    results = db.query(Category.name, func.sum(Expense.amount)).join(Category).filter(
        Expense.user_id == user_id,
        Expense.type == type,
        Expense.date >= from_date,
        Expense.date <= to_date
    ).group_by(Category.name).all()

    labels = [r[0] for r in results]
    data = [r[1] for r in results]

    return {"labels": labels, "data": data}

def get_all_categories(user_id: int, db: Session):
    return db.query(Category).filter(Category.user_id == user_id).all()

def create_category(name: str, type: str, budget: float, user_id: int, db: Session):
    category = Category(name=name, type=type, budget=budget, user_id=user_id)
    db.add(category)
    db.commit()

def get_categories(db: Session, user_id: int):
    return db.query(Category).filter(Category.user_id == user_id).all()

def get_summary_by_period(user_id: int, period: str, category: str, db: Session):
    today = datetime.today().date()

    if period == "year":
        label_format = 'YYYY'
        start_date = today.replace(year=today.year - 4, month=1, day=1)

    elif period == "month":
        label_format = 'Mon'
        month = today.month
        year = today.year
        if month <= 5:
            year -= 1
            month += 12
        start_date = datetime(year, month - 4, 1).date()

    elif period == "week":
        label_format = 'YYYY-MM-DD'   # week label = start of week
        start_date = today - timedelta(weeks=4)

    elif period == "day":
        label_format = 'YYYY-MM-DD'   # exact dates for last 5 days
        start_date = today - timedelta(days=4)

    else:
        label_format = 'Mon'
        start_date = today - timedelta(days=30)

    query = db.query(
        func.to_char(Expense.date, label_format).label("label"),
        func.sum(case((Expense.type == "income", Expense.amount), else_=0)).label("income"),
        func.sum(case((Expense.type == "expense", Expense.amount), else_=0)).label("expense")
    ).join(Category).filter(
        Expense.user_id == user_id,
        Expense.date >= start_date
    )

    if category:
        query = query.filter(Category.name == category)

    return query.group_by("label").order_by("label").limit(5).all()

#for categories page
# Get category by ID
def get_category_by_id(db: Session, category_id: int):
    return db.query(Category).filter(Category.id == category_id).first()

# Add new category (always user-specific)
def add_category(db: Session, user_id: int, name: str, type: str, budget: float = None):
    new_cat = Category(name=name, type=type, budget=budget, user_id=user_id)
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

# Update category (clone default if editing default)
def update_category(db: Session, category_id: int, user_id: int, name: str, budget: float = None):
    category = get_category_by_id(db, category_id)

    # If default, create a copy for user
    if category.user_id is None:
        # Check if user already has a custom copy of this name/type
        existing = db.query(Category).filter_by(name=name, type=category.type, user_id=user_id).first()
        if existing:
            existing.budget = budget
            db.commit()
            return existing
        # Otherwise create a new personal copy
        new_cat = Category(name=name, type=category.type, budget=budget, user_id=user_id)
        db.add(new_cat)
        db.commit()
        db.refresh(new_cat)
        return new_cat

    # If user-owned category
    if category.user_id == user_id:
        category.name = name
        category.budget = budget
        db.commit()
        return category
    return None

# Delete user-created category only
def delete_category(db: Session, category_id: int, user_id: int):
    category = get_category_by_id(db, category_id)
    if category and category.user_id == user_id:
        db.delete(category)
        db.commit()
        return True
    return False

   
# Set or update monthly budget for a category
def set_or_update_monthly_budget(db: Session, category_id: int, user_id: int, month: str, amount: float):
    budget = db.query(CategoryBudget).filter_by(
        category_id=category_id,
        user_id=user_id,
        month=month
    ).first()

    if budget:
        budget.amount = amount
    else:
        budget = CategoryBudget(
            category_id=category_id,
            user_id=user_id,
            month=month,
            amount=amount
        )
        db.add(budget)
    
    db.commit()


# Get budget for a specific category + month
def get_budget_for_category_month(db: Session, category_id: int, user_id: int, month: str):
    return db.query(CategoryBudget).filter_by(
        category_id=category_id,
        user_id=user_id,
        month=month
    ).first()


# Get all monthly budgets for a user (optional for categories.html)
def get_all_monthly_budgets_for_user(db: Session, user_id: int):
    return db.query(CategoryBudget).filter_by(user_id=user_id).all()

#for exporting data - download
def get_all_transactions(user_id: int, db: Session):
    return db.query(models.Expense).join(models.Category).filter(
        models.Expense.user_id == user_id
    ).order_by(models.Expense.date.desc()).all()
