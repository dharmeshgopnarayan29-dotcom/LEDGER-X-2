from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from database import engine, SessionLocal
from models import Base, User, Budget
from schemas import FinanceCreate, FinanceResponse, UserCreate, UserResponse, BudgetCreate, BudgetResponse
import crud
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError
import os

Base.metadata.create_all(bind=engine)
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print("\n\n==================================================")
    print(" LEDGER-X SERVER STARTED SUCCESSFULLY ")
    print("==================================================\n\n")

SECRET_KEY = "your_secret_key_change_me_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

@app.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, form_data.username)
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/ledger/", response_model=FinanceResponse)
def create(data: FinanceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.create(db, data, user_id=current_user.id)

@app.get("/ledger/", response_model=list[FinanceResponse])
def get(category: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get(db, user_id=current_user.id, category=category)

@app.put("/ledger/{id}", response_model=FinanceResponse)
def update(id: int, data: FinanceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    updated = crud.update(db, id, data, user_id=current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Record not found")
    return updated

@app.delete("/ledger/{id}")
def delete(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    deleted = crud.delete(db, id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "Record deleted successfully"}

@app.get("/api/users/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/api/summary")
def get_monthly_summary(month: int, year: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get_monthly_summary(db, month, year, user_id=current_user.id)

@app.get("/api/category-expenses")
def get_category_expenses(month: int, year: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get_category_expenses(db, month, year, user_id=current_user.id)

@app.post("/api/budget", response_model=BudgetResponse)
def create_budget(budget: BudgetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.create_budget(db, budget, user_id=current_user.id)

@app.get("/api/budget", response_model=BudgetResponse | None)
def get_budget(month: int, year: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get_budget(db, month, year, user_id=current_user.id)

@app.get("/api/daily-spending")
def get_daily_spending(month: int, year: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get_daily_spending(db, month, year, user_id=current_user.id)

@app.get("/api/yearly-expenses")
def get_yearly_expenses(year: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get_yearly_expenses(db, year, user_id=current_user.id)

# TEMPORARY: Admin endpoint to reset DB in production
@app.get("/api/admin/reset-db-force")
def reset_database_force():
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    # Recreate all tables
    Base.metadata.create_all(bind=engine)
    return {"message": "Database has been reset successfully. All data deleted. New schema applied."}
