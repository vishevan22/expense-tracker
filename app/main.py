# app/main.py

from fastapi import FastAPI, Request, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import extract, func
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from . import auth, crud
from .database import engine, get_db
from sqlalchemy.orm import Session
from .models import Base, Category
import os
from datetime import date, datetime, timedelta
import calendar
from dotenv import load_dotenv
import os
from fastapi.responses import HTMLResponse
from fastapi import Form
from .budget_utils import get_budget_progress
from .budget_overview_util import get_budget_overview,get_budget_overview_comparison,get_category_monthly_spending_comparison,get_line_chart_data_for_category
from .category_utils import get_all_categories_with_budget, upsert_category_budget
from fastapi import Query


from app import models


app = FastAPI()

load_dotenv()

# Create tables if not already created
Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


# Session Middleware (use a secure secret key in production!)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

#app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Jinja2 template directory
templates = Jinja2Templates(directory="app/templates")

# Include auth routes (login/register/logout)
app.include_router(auth.router)


# Dependency to get logged-in user
def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return user_id

@app.get("/")
def home():
    return RedirectResponse("/login")

@app.get("/dashboard")
def dashboard(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    type: str = "expense",  # income / expense / all
    period: str = "month",  # day / week / month / year
    category: str = None,  # NEW: category filter
    date: str = None,
    week: str = None,
    month: str = None,
    year: str = None,
):
    if not user_id:
        return RedirectResponse("/login")

    today = datetime.today().date()
    from_date = to_date = today
    period_label = f"Today, {today.strftime('%d %B')}"

    if period == "week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        from_date, to_date = start, end
        period_label = f"{start.strftime('%d %b')} – {end.strftime('%d %b')}"
    elif period == "month":
        from_date = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        to_date = today.replace(day=last_day)
        period_label = today.strftime("%B %Y")
    elif period == "year":
        from_date = today.replace(month=1, day=1)
        to_date = today.replace(month=12, day=31)
        period_label = today.strftime("%Y")

    if date:
        dt = datetime.strptime(date, "%Y-%m-%d").date()
        from_date = to_date = dt
        period_label = f"{dt.strftime('%A')}, {dt.strftime('%d %B')}"
    elif week:
        year_, week_ = map(int, week.split("-W"))
        start = datetime.strptime(f"{year_}-W{week_}-1", "%Y-W%W-%w").date()
        end = start + timedelta(days=6)
        from_date, to_date = start, end
        period_label = f"{start.strftime('%d %b')} – {end.strftime('%d %b')}"
    elif month:
        dt = datetime.strptime(month, "%Y-%m")
        from_date = dt.replace(day=1).date()
        last_day = calendar.monthrange(dt.year, dt.month)[1]
        to_date = dt.replace(day=last_day).date()
        period_label = dt.strftime("%B %Y")
    elif year:
        from_date = datetime.strptime(year, "%Y").replace(month=1, day=1).date()
        to_date = datetime.strptime(year, "%Y").replace(month=12, day=31).date()
        period_label = year

    # Filter transactions with optional category
    transactions = crud.get_filtered_transactions(user_id, type, from_date, to_date, db)
    if category:
        transactions = [txn for txn in transactions if txn.category.name == category]

    income, expense, profit = crud.get_stats(user_id, db)
    total_amount = income - expense

    if type in ["income", "expense"]:
        pie = crud.get_pie_chart_data_filtered(user_id, type, from_date, to_date, db)
        labels = pie["labels"]
        values = pie["data"]
    else:
        labels, values = [], []

    progress_data = get_budget_progress(db, user_id)
    all_categories = crud.get_all_categories(user_id, db)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "transactions": transactions,
            "labels": labels,
            "values": values,
            "type": type,
            "period": period,
            "period_label": period_label,
            "total_amount": total_amount,
            "progress_data": progress_data,
            "selected_category": category,
            "all_categories": all_categories,
        },
    )

#to add transaction
@app.get("/add")
def add_expense_form(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user_id:
        return RedirectResponse("/login")
    
    categories = db.query(Category).filter(Category.user_id == user_id).all()

    return templates.TemplateResponse(
        "add.html",
        {"request": request, "categories": categories}
    )

#for adding transaction in homepage
@app.post("/add")
async def add_expense(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    if not user_id:
        return RedirectResponse("/login")

    form = await request.form()
    crud.add_expense(
        user_id=user_id,
        date=form["date"],
        category_id=int(form["category"]),
        amount=float(form["amount"]),
        description=form["description"],
        type=form["type"],
        db=db,
    )

    return RedirectResponse("/dashboard", status_code=302)


@app.get("/edit/{txn_id}", response_class=HTMLResponse)
def edit_transaction(
    txn_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
):
    txn = crud.get_transaction_by_id(db, txn_id, user_id)  # Pass user_id here
    categories = crud.get_categories(db, user_id)
    return templates.TemplateResponse("edit_transaction.html", {
        "request": request,
        "txn": txn,
        "categories": categories
    })



@app.post("/edit/{txn_id}")
def update_transaction(
    txn_id: int,
    request: Request,
    date: str = Form(...),
    type: str = Form(...),
    category: int = Form(...),
    amount: float = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    crud.update_transaction(db, txn_id, date, type, category, amount, description)
    return RedirectResponse("/dashboard", status_code=302)



@app.post("/delete/{txn_id}")
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    crud.delete_transaction(db, txn_id)
    return RedirectResponse("/dashboard", status_code=302)



@app.get("/charts")
def charts(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    period: str = "month",
    tab: str = "general",
    category: str = None,
):
    from_date, to_date = None, None
    today = datetime.today().date()

    # Prepare label ranges
    def get_last_years(n=5):
        return [str(today.year - i) for i in reversed(range(n))]

    def get_last_months(n=5):
        labels = []
        for i in range(n-1, -1, -1):
            month = (today.month - i - 1) % 12 + 1
            year = today.year - ((today.month - i - 1) // 12 < 0)
            labels.append(datetime(year, month, 1).strftime("%b"))
        return labels
    
    def get_last_weeks(n=5):
        return [(today - timedelta(days=today.weekday()) - timedelta(weeks=i)).strftime("%Y-%m-%d")
                for i in reversed(range(n))]


    def get_last_days(n=5):
        days = []
        for i in reversed(range(n)):
            d = today - timedelta(days=i)
            days.append(d.strftime("%Y-%m-%d"))  # full ISO format
        return days, today.strftime("%B %Y")
        

    # Generate x-axis labels
    if period == "year":
        labels = get_last_years()
    elif period == "month":
        labels = get_last_months()
    elif period == "week":
        labels = get_last_weeks()
    elif period == "day":
        labels, month_label = get_last_days()
    else:
        labels = []
        month_label = ""

    # Get actual chart data from DB
    summary = crud.get_summary_by_period(user_id, period, category, db)
    label_map = {row[0]: (row[1], row[2]) for row in summary}

    income_data, expense_data, profit_data, loss_data = [], [], [], []

    for label in labels:
        income = label_map.get(label, (0, 0))[0]
        expense = label_map.get(label, (0, 0))[1]
        profit = max(income - expense, 0)
        loss = max(expense - income, 0)

        income_data.append(income)
        expense_data.append(expense)
        profit_data.append(profit)
        loss_data.append(loss)

    # Overall totals
    income, expense, profit = crud.get_stats(user_id, db)

    return templates.TemplateResponse("charts.html", {
        "request": request,
        "labels": labels,
        "income_data": income_data,
        "expense_data": expense_data,
        "profit_data": profit_data,
        "loss_data": loss_data,
        "income": income,
        "expense": expense,
        "profit": profit,
        "tab": tab,
        "period": period,
        "month_label": month_label if period == "day" else "",
        "categories": crud.get_all_categories(user_id, db),
        "selected_category": category  # pass selected
    })

#for categories - categories.html

@app.get("/categories", response_class=HTMLResponse)
def view_categories(request: Request, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user_id:
        return RedirectResponse("/login")

    categories = get_all_categories_with_budget(db, user_id)
    return templates.TemplateResponse("categories.html", {"request": request, "categories": categories})


@app.post("/categories/add")
def add_category(
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    budget: float = Form(None),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user_id:
        return RedirectResponse("/login")

    # Add new category (user-owned)
    new_category = crud.add_category(db=db, user_id=user_id, name=name, type=type)

    # Save budget for current month
    if budget:
        upsert_category_budget(db, new_category.id, user_id, budget)

    return RedirectResponse("/categories", status_code=302)


@app.post("/categories/update/{category_id}")
def update_category(
    request: Request,
    category_id: int,
    name: str = Form(...),
    budget: float = Form(None),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user_id:
        return RedirectResponse("/login")

    crud.update_category(category_id=category_id, name=name, user_id=user_id, db=db)
    upsert_category_budget(db, category_id, user_id, budget)

    referer = request.headers.get("referer", "/categories")
    return RedirectResponse(referer, status_code=302)


@app.post("/categories/delete/{category_id}")
def delete_category(
    request: Request,
    category_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user_id:
        return RedirectResponse("/login")

    crud.delete_category(category_id=category_id, user_id=user_id, db=db)
    return RedirectResponse("/categories", status_code=302)


#for budget overview - budget_overview.html
from fastapi import Query

@app.get("/budget_overview", response_class=HTMLResponse)
def budget_overview(
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    selected_category: str = Query(None, alias="category")
):
    if not user_id:
        return RedirectResponse("/login")

    all_categories = db.query(models.Category).filter(
        ((models.Category.user_id == user_id) | (models.Category.user_id == None)) &
        (models.Category.type == "expense")
    ).all()

    overview_data = get_budget_overview(db, user_id)
    comparison_data = get_budget_overview_comparison(db, user_id)
    chart_data = get_line_chart_data_for_category(db, user_id, selected_category)

    labels = chart_data.get("labels", [])
    this_month_data = chart_data.get("this_month", [])
    last_month_data = chart_data.get("last_month", [])

    return templates.TemplateResponse("budget_overview.html", {
        "request": request,
        "overview_data": overview_data,
        "comparison_data": comparison_data,
        "all_expense_categories": all_categories,
        "selected_category": selected_category,
        "line_labels": labels,
        "this_month_data": this_month_data,
        "last_month_data": last_month_data
    })
import csv
from fastapi.responses import StreamingResponse
from io import StringIO

@app.get("/export/csv")
def export_csv(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    transactions = crud.get_all_transactions(user_id=user_id, db=db)

    def generate():
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(["Date", "Type", "Category", "Amount", "Description"])
        for txn in transactions:
            writer.writerow([txn.date, txn.type, txn.category.name, txn.amount, txn.description])
        data.seek(0)
        return data

    return StreamingResponse(generate(), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=transactions.csv"
    })
