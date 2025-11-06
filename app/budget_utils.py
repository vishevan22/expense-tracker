from sqlalchemy import func, extract
from datetime import date
from app.models import Category, Expense, CategoryBudget

def get_budget_progress(db, user_id):
    today = date.today()
    current_month = today.month
    current_year = today.year

    # 1. Fetch all categories (default + user-defined)
    categories = db.query(Category).filter(
        (Category.user_id == user_id) | (Category.user_id == None)
    ).all()

    # 2. Fetch user budgets set for current month
    budgets = db.query(CategoryBudget).filter(
        CategoryBudget.user_id == user_id,
        CategoryBudget.month == current_month,
        CategoryBudget.year == current_year
    ).all()
    budget_map = {b.category_id: b.budget for b in budgets}

    # 3. Fetch expenses for current month
    spending = db.query(
        Expense.category_id,
        func.sum(Expense.amount).label("spent")
    ).filter(
        Expense.user_id == user_id,
        Expense.type == "expense",
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).group_by(Expense.category_id).all()
    spending_map = {row.category_id: row.spent for row in spending}

    # 4. Merge to build progress data
    progress_data = []
    for cat in categories:
        budget = budget_map.get(cat.id)
        if budget is not None:  # Show only categories with budget set
            spent = spending_map.get(cat.id, 0)
            percent = round((spent / budget) * 100, 2) if budget else 0
            progress_data.append({
                "category": cat.name,
                "spent": spent,
                "budget": budget,
                "percent": percent
            })

    return progress_data
