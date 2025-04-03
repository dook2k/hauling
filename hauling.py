# Simplified Junk Hauling API Implementation (FastAPI + SQLModel + Admin Dashboard)

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Field, Session, SQLModel, create_engine, select
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import date
import shutil
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ------------------
# Database Setup
# ------------------

db_url = "sqlite:///./junk_hauling.db"
engine = create_engine(db_url, echo=True)

# Dependency


def get_session():
    with Session(engine) as session:
        yield session


# ------------------
# SQLModel Models
# ------------------


class Customer(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    phone: str
    email: str


class Quote(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    customer_id: UUID
    categories: str
    estimated_volume: float
    price_estimate: float
    accepted: bool = False
    photo_path: Optional[str] = None


class Booking(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    customer_id: UUID
    quote_id: UUID
    scheduled_date: date
    address: str
    categories: str


class Truck(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    capacity: float
    current_route: Optional[str] = None


class DisposalFacility(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    location: str
    accepted_categories: str


# ------------------
# Create DB Tables
# ------------------

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)

# ------------------
# Customer Endpoints
# ------------------


@app.get("/customers", response_model=List[Customer])
def list_customers(session: Session = Depends(get_session)):
    return session.exec(select(Customer)).all()


@app.post("/customers", response_model=Customer)
def create_customer(customer: Customer, session: Session = Depends(get_session)):
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


# ------------------
# Quote Endpoints
# ------------------


@app.post("/quotes", response_model=Quote)
def create_quote_with_photo(
    customer_id: UUID = Form(...),
    categories: str = Form(...),
    estimated_volume: float = Form(...),
    price_estimate: float = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    photo_path = f"uploads/{uuid4()}_{file.filename}"
    with open(photo_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    quote = Quote(
        customer_id=customer_id,
        categories=categories,
        estimated_volume=estimated_volume,
        price_estimate=price_estimate,
        photo_path=photo_path,
    )
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return quote


@app.post("/admin/quotes/{quote_id}/approve")
def approve_quote(quote_id: UUID, session: Session = Depends(get_session)):
    quote = session.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    quote.accepted = True
    session.add(quote)
    session.commit()
    return RedirectResponse(url="/admin/quotes", status_code=303)


@app.post("/admin/quotes/{quote_id}/convert")
def convert_quote_to_booking(
    quote_id: UUID,
    scheduled_date: date = Form(...),
    address: str = Form(...),
    session: Session = Depends(get_session),
):
    quote = session.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    booking = Booking(
        customer_id=quote.customer_id,
        quote_id=quote.id,
        scheduled_date=scheduled_date,
        address=address,
        categories=quote.categories,
    )
    session.add(booking)
    session.commit()
    return RedirectResponse(url="/admin/quotes", status_code=303)


# ------------------
# Admin Dashboard
# ------------------


@app.get("/admin/quotes", response_class=HTMLResponse)
def view_quotes(request: Request, session: Session = Depends(get_session)):
    quotes = session.exec(select(Quote)).all()
    customers = {c.id: c for c in session.exec(select(Customer)).all()}
    return templates.TemplateResponse(
        "quotes.html", {"request": request, "quotes": quotes, "customers": customers}
    )


@app.get("/admin/bookings", response_class=HTMLResponse)
def view_bookings(request: Request, session: Session = Depends(get_session)):
    bookings = session.exec(select(Booking)).all()
    customers = {c.id: c for c in session.exec(select(Customer)).all()}
    quotes = {q.id: q for q in session.exec(select(Quote)).all()}
    return templates.TemplateResponse(
        "bookings.html",
        {
            "request": request,
            "bookings": bookings,
            "customers": customers,
            "quotes": quotes,
        },
    )


# ------------------
# Booking Endpoints
# ------------------


@app.post("/bookings", response_model=Booking)
def create_booking(booking: Booking, session: Session = Depends(get_session)):
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


# ------------------
# Truck Endpoints
# ------------------


@app.post("/trucks", response_model=Truck)
def create_truck(truck: Truck, session: Session = Depends(get_session)):
    session.add(truck)
    session.commit()
    session.refresh(truck)
    return truck


# ------------------
# Disposal Facility Endpoints
# ------------------


@app.post("/disposal-facilities", response_model=DisposalFacility)
def create_facility(
    facility: DisposalFacility, session: Session = Depends(get_session)
):
    session.add(facility)
    session.commit()
    session.refresh(facility)
    return facility
