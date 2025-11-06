# app/models.py

from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    expenses = relationship("Expense", back_populates="owner")


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'income' or 'expense'
    budget = Column(Float)
    user_id = Column(Integer, ForeignKey("users.id"))

    expenses = relationship("Expense", back_populates="category") 

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    date = Column(Date, nullable=False)
    type = Column(String, nullable=False, default="expense")
    amount = Column(Float, nullable=False)
    description = Column(String)
    

    owner = relationship("User", back_populates="expenses")
    category = relationship("Category", back_populates="expenses")  # ← this must match


class CategoryBudget(Base):
    __tablename__ = "category_budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    month = Column(Integer, nullable=False)  # 1 to 12
    year = Column(Integer, nullable=False)
    budget = Column(Float, nullable=False)