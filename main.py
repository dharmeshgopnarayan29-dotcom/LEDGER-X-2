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

Base.metadata.create_all(bind=engine)
app = FastAPI()

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
    return {"access_token": user.username, "token_type": "bearer"}

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/ledger/", response_model=FinanceResponse)
def create(data: FinanceCreate, db: Session = Depends(get_db)):
    return crud.create(db, data)

@app.get("/ledger/", response_model=list[FinanceResponse])
def get(category: str | None = None, db: Session = Depends(get_db)):
    return crud.get(db, category)

@app.put("/ledger/{id}", response_model=FinanceResponse)
def update(id: int, data: FinanceCreate, db: Session = Depends(get_db)):
    updated = crud.update(db, id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Record not found")
    return updated

@app.delete("/ledger/{id}")
def delete(id: int, db: Session = Depends(get_db)):
    deleted = crud.delete(db, id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "Record deleted successfully"}

@app.get("/api/users/me", response_model=UserResponse)
def read_users_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user

@app.get("/api/summary")
def get_monthly_summary(month: int, year: int, db: Session = Depends(get_db)):
    return crud.get_monthly_summary(db, month, year)

@app.get("/api/category-expenses")
def get_category_expenses(month: int, year: int, db: Session = Depends(get_db)):
    return crud.get_category_expenses(db, month, year)

@app.post("/api/budget", response_model=BudgetResponse)
def create_budget(budget: BudgetCreate, db: Session = Depends(get_db)):
    return crud.create_budget(db, budget)

@app.get("/api/budget", response_model=BudgetResponse | None)
def get_budget(month: int, year: int, db: Session = Depends(get_db)):
    return crud.get_budget(db, month, year)

@app.get("/api/daily-spending")
def get_daily_spending(month: int, year: int, db: Session = Depends(get_db)):
    return crud.get_daily_spending(db, month, year)

@app.get("/api/yearly-expenses")
def get_yearly_expenses(year: int, db: Session = Depends(get_db)):
    return crud.get_yearly_expenses(db, year)
