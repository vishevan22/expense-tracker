from sqlalchemy import func, extract
from datetime import date
from app.models import Category, Expense, CategoryBudget

def get_budget_overview(db, user_id):
    today = date.today()
    current_month = today.month
    current_year = today.year

    categories = db.query(Category).filter(
        ((Category.user_id == user_id) | (Category.user_id == None)) &
        (Category.type == "expense")
    ).all()

    budgets = db.query(CategoryBudget).filter_by(
        user_id=user_id,
        month=current_month,
        year=current_year
    ).all()
    budget_map = {b.category_id: b.budget for b in budgets}

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

    overview_data = []
    for cat in categories:
        budget = budget_map.get(cat.id)
        if budget:
            spent = spending_map.get(cat.id, 0)
            remaining = budget - spent
            percent = round((spent / budget) * 100, 2)
            overview_data.append({
                "id": cat.id,
                "name": cat.name,
                "budget": budget,
                "spent": spent,
                "remaining": remaining,
                "percent": percent
            })

    return overview_data
def get_budget_overview_comparison(db, user_id):
    today = date.today()
    this_month, this_year = today.month, today.year

    # Previous month logic
    if this_month == 1:
        prev_month, prev_year = 12, this_year - 1
    else:
        prev_month, prev_year = this_month - 1, this_year

    categories = db.query(Category).filter(
        ((Category.user_id == user_id) | (Category.user_id == None)) &
        (Category.type == "expense")
    ).all()

    # Get monthly budgets
    budgets = db.query(CategoryBudget).filter(
        CategoryBudget.user_id == user_id,
        ((CategoryBudget.month == this_month) & (CategoryBudget.year == this_year)) |
        ((CategoryBudget.month == prev_month) & (CategoryBudget.year == prev_year))
    ).all()
    budget_map = {(b.category_id, b.month, b.year): b.budget for b in budgets}

    # Spending data
    spending = db.query(
        Expense.category_id,
        extract('month', Expense.date).label('month'),
        extract('year', Expense.date).label('year'),
        func.sum(Expense.amount).label("spent")
    ).filter(
        Expense.user_id == user_id,
        Expense.type == "expense",
        extract('month', Expense.date).in_([this_month, prev_month]),
        extract('year', Expense.date).in_([this_year, prev_year])
    ).group_by(Expense.category_id, 'month', 'year').all()

    spending_map = {
        (int(row.category_id), int(row.month), int(row.year)): row.spent for row in spending
    }

    comparison_data = []
    for cat in categories:
        b_this = budget_map.get((cat.id, this_month, this_year))
        b_prev = budget_map.get((cat.id, prev_month, prev_year))
        if not b_this and not b_prev:
            continue

        spent_now = spending_map.get((cat.id, this_month, this_year), 0)
        spent_prev = spending_map.get((cat.id, prev_month, prev_year), 0)

        percent_now = round((spent_now / b_this) * 100, 2) if b_this else 0
        percent_prev = round((spent_prev / b_prev) * 100, 2) if b_prev else 0

        comparison_data.append({
            "id": cat.id,
            "name": cat.name,
            "budget": b_this or b_prev,
            "spent_now": spent_now,
            "spent_prev": spent_prev,
            "percent_now": percent_now,
            "percent_prev": percent_prev
        })

    return comparison_data

def get_category_monthly_spending_comparison(db, user_id, category_name):
    today = date.today()
    this_month = today.month
    this_year = today.year

    # Handle previous month/year edge case
    if this_month == 1:
        prev_month = 12
        prev_year = this_year - 1
    else:
        prev_month = this_month - 1
        prev_year = this_year

    # Get category ID
    category = db.query(Category).filter(
        Category.name == category_name,
        (Category.user_id == user_id) | (Category.user_id == None)
    ).first()
    if not category:
        return {}

    # Query daily spending for both months
    data = db.query(
        extract('day', Expense.date).label("day"),
        extract('month', Expense.date).label("month"),
        extract('year', Expense.date).label("year"),
        func.sum(Expense.amount).label("spent")
    ).filter(
        Expense.user_id == user_id,
        Expense.category_id == category.id,
        Expense.type == "expense",
        extract('month', Expense.date).in_([this_month, prev_month]),
        extract('year', Expense.date).in_([this_year, prev_year])
    ).group_by("day", "month", "year").all()

    # Organize into day→amount map
    current_month_data = {}
    prev_month_data = {}
    for row in data:
        day = int(row.day)
        month = int(row.month)
        year = int(row.year)
        amount = float(row.spent)

        if month == this_month and year == this_year:
            current_month_data[day] = amount
        elif month == prev_month and year == prev_year:
            prev_month_data[day] = amount

    # Build aligned series (e.g., days 1 to 31)
    max_day = 31
    labels = list(range(1, max_day + 1))
    current_series = [current_month_data.get(day, 0) for day in labels]
    prev_series = [prev_month_data.get(day, 0) for day in labels]

    return {
        "labels": labels,
        "this_month": current_series,
        "prev_month": prev_series,
        "this_month_label": today.strftime("%B"),
        "prev_month_label": date(today.year, prev_month, 1).strftime("%B"),
    }
    
def get_line_chart_data_for_category(db, user_id, category_name):
    if not category_name:
        return {}

    from datetime import date, timedelta
    from sqlalchemy import extract, func
    from app.models import Expense, Category

    today = date.today()
    current_month = today.month
    current_year = today.year

    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year

    # Get category id
    category = db.query(Category).filter(
        Category.name == category_name,
        (Category.user_id == user_id) | (Category.user_id == None)
    ).first()
    if not category:
        return {}

    # Day labels for 1–31
    labels = [str(day) for day in range(1, 32)]

    def fetch_month_data(month, year):
        result = db.query(
            extract('day', Expense.date).label("day"),
            func.sum(Expense.amount)
        ).filter(
            Expense.user_id == user_id,
            Expense.category_id == category.id,
            Expense.type == "expense",
            extract('month', Expense.date) == month,
            extract('year', Expense.date) == year
        ).group_by("day").all()
        day_map = {int(r[0]): float(r[1]) for r in result}
        return [day_map.get(day, 0) for day in range(1, 32)]

    return {
        "labels": labels,
        "this_month": fetch_month_data(current_month, current_year),
        "last_month": fetch_month_data(prev_month, prev_year)
    }
