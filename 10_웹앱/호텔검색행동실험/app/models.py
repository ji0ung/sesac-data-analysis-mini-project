from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_name: Mapped[str] = mapped_column(String(80))
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    signup_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Session(Base):
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class Hotel(Base):
    __tablename__ = "hotels"
    hotel_id: Mapped[str] = mapped_column(String, primary_key=True)
    hotel_name: Mapped[str] = mapped_column(String(120)); city_name: Mapped[str] = mapped_column(String(50), index=True)
    region_name: Mapped[str] = mapped_column(String(50)); grade: Mapped[int] = mapped_column(Integer)
    latitude: Mapped[float] = mapped_column(Float); longitude: Mapped[float] = mapped_column(Float)
    hotel_address: Mapped[str] = mapped_column(String(200)); hotel_rating: Mapped[float] = mapped_column(Float)
    accommodation_type: Mapped[str] = mapped_column(String(30)); price_per_night: Mapped[int] = mapped_column(Integer)
    review_count: Mapped[int] = mapped_column(Integer); amenities_json: Mapped[str] = mapped_column(Text)
    nearest_station: Mapped[str] = mapped_column(String(80)); station_distance_m: Mapped[int] = mapped_column(Integer)
    thumbnail_url: Mapped[str] = mapped_column(String(300)); description: Mapped[str] = mapped_column(Text)
    free_cancellation: Mapped[bool] = mapped_column(Boolean, default=False); pay_at_hotel: Mapped[bool] = mapped_column(Boolean, default=False)
    breakfast_included: Mapped[bool] = mapped_column(Boolean, default=False); pet_friendly: Mapped[bool] = mapped_column(Boolean, default=False)
    family_room: Mapped[bool] = mapped_column(Boolean, default=False); swimming_pool: Mapped[bool] = mapped_column(Boolean, default=False)
    spa: Mapped[bool] = mapped_column(Boolean, default=False); chain_name: Mapped[str | None] = mapped_column(String(50), nullable=True)

class Search(Base):
    __tablename__ = "searches"
    search_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True); session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), index=True)
    search_time: Mapped[datetime] = mapped_column(DateTime, default=now); query_text: Mapped[str] = mapped_column(String(100))
    checkin_date: Mapped[datetime] = mapped_column(Date); checkout_date: Mapped[datetime] = mapped_column(Date)
    guest_count: Mapped[int] = mapped_column(Integer); room_count: Mapped[int] = mapped_column(Integer, default=1)
    search_region: Mapped[str] = mapped_column(String(50)); sort_condition: Mapped[str] = mapped_column(String(30), default="recommended")
    total_result_count: Mapped[int] = mapped_column(Integer, default=0)
    parent_search_id: Mapped[str | None] = mapped_column(ForeignKey("searches.search_id"), nullable=True)
    filter: Mapped["SearchFilter"] = relationship(back_populates="search", uselist=False, cascade="all, delete-orphan")

class SearchFilter(Base):
    __tablename__ = "search_filters"
    search_filter_id: Mapped[str] = mapped_column(String, primary_key=True); search_id: Mapped[str] = mapped_column(ForeignKey("searches.search_id"), unique=True)
    accommodation_type: Mapped[str | None] = mapped_column(String, nullable=True); accommodation_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_rating: Mapped[float | None] = mapped_column(Float, nullable=True); min_price: Mapped[int | None] = mapped_column(Integer, nullable=True); max_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amenity_count: Mapped[int] = mapped_column(Integer, default=0); amenities_json: Mapped[str] = mapped_column(Text, default="[]")
    transport_condition: Mapped[str | None] = mapped_column(String, nullable=True); region: Mapped[str | None] = mapped_column(String, nullable=True)
    breakfast_required: Mapped[bool] = mapped_column(Boolean, default=False); parking_required: Mapped[bool] = mapped_column(Boolean, default=False)
    public_bath_required: Mapped[bool] = mapped_column(Boolean, default=False); free_wifi_required: Mapped[bool] = mapped_column(Boolean, default=False)
    max_station_distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    free_cancellation_required: Mapped[bool] = mapped_column(Boolean, default=False); pay_at_hotel_required: Mapped[bool] = mapped_column(Boolean, default=False)
    pet_friendly_required: Mapped[bool] = mapped_column(Boolean, default=False); family_room_required: Mapped[bool] = mapped_column(Boolean, default=False)
    swimming_pool_required: Mapped[bool] = mapped_column(Boolean, default=False); spa_required: Mapped[bool] = mapped_column(Boolean, default=False)
    chain_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    search: Mapped[Search] = relationship(back_populates="filter")

class Event(Base):
    __tablename__ = "events"; __table_args__ = (UniqueConstraint("search_id", "hotel_id", "event_name", name="uq_impression_guard"),)
    event_id: Mapped[str] = mapped_column(String, primary_key=True); user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), index=True); event_name: Mapped[str] = mapped_column(String(50), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, default=now, index=True); search_id: Mapped[str | None] = mapped_column(ForeignKey("searches.search_id"), nullable=True)
    search_filter_id: Mapped[str | None] = mapped_column(ForeignKey("search_filters.search_filter_id"), nullable=True); hotel_id: Mapped[str | None] = mapped_column(ForeignKey("hotels.hotel_id"), nullable=True)
    action_id: Mapped[str] = mapped_column(String, unique=True); page_name: Mapped[str] = mapped_column(String(50)); event_properties_json: Mapped[str] = mapped_column(Text, default="{}")

class Review(Base):
    __tablename__ = "reviews"
    review_id: Mapped[str] = mapped_column(String, primary_key=True); hotel_id: Mapped[str] = mapped_column(ForeignKey("hotels.hotel_id"), index=True); user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    rating: Mapped[float] = mapped_column(Float); review_created_at: Mapped[datetime] = mapped_column(DateTime, default=now); review_text: Mapped[str] = mapped_column(Text); review_image: Mapped[str | None] = mapped_column(String, nullable=True)

class Reservation(Base):
    __tablename__ = "reservations"
    reservation_id: Mapped[str] = mapped_column(String, primary_key=True); user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id")); hotel_id: Mapped[str] = mapped_column(ForeignKey("hotels.hotel_id")); search_id: Mapped[str] = mapped_column(ForeignKey("searches.search_id"))
    reservation_status: Mapped[str] = mapped_column(String, default="confirmed"); total_price: Mapped[int] = mapped_column(Integer); reservation_created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    checkin_date: Mapped[datetime] = mapped_column(Date); checkout_date: Mapped[datetime] = mapped_column(Date); guest_count: Mapped[int] = mapped_column(Integer); room_count: Mapped[int] = mapped_column(Integer)
