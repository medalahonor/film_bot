"""Database models."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger, String, Integer, Text, DateTime, ForeignKey,
    UniqueConstraint, DECIMAL
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class SessionStatus(Base):
    """Session status model - possible session statuses."""
    __tablename__ = "session_statuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="status_obj", lazy="selectin")

    def __repr__(self) -> str:
        return f"<SessionStatus(code={self.code}, name={self.name})>"


class User(Base):
    """User model - participants of the film club."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="creator", lazy="selectin")
    movies: Mapped[List["Movie"]] = relationship("Movie", back_populates="proposer", lazy="selectin")
    votes: Mapped[List["Vote"]] = relationship("Vote", back_populates="user", lazy="selectin")
    ratings: Mapped[List["Rating"]] = relationship("Rating", back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class Group(Base):
    """Group model - authorized Telegram groups."""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="group", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Group(id={self.id}, name={self.name})>"


class Admin(Base):
    """Admin model - bot administrators."""
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Admin(id={self.id}, username={self.username})>"


class Session(Base):
    """Session model - film club sessions."""
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(
        ForeignKey("session_statuses.id"), 
        nullable=False
    )
    pinned_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    poll_slot1_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    poll_slot2_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    poll_slot1_id: Mapped[Optional[str]] = mapped_column(String(255))
    poll_slot2_id: Mapped[Optional[str]] = mapped_column(String(255))
    poll_slot1_movie_ids: Mapped[Optional[str]] = mapped_column(Text)
    poll_slot2_movie_ids: Mapped[Optional[str]] = mapped_column(Text)
    winner_slot1_id: Mapped[Optional[int]] = mapped_column(ForeignKey("movies.id"))
    winner_slot2_id: Mapped[Optional[int]] = mapped_column(ForeignKey("movies.id"))
    rating_msg_slot1_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    rating_msg_slot2_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    rating_scoreboard_msg_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    voting_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="sessions", lazy="selectin")
    creator: Mapped["User"] = relationship("User", back_populates="sessions", lazy="selectin")
    status_obj: Mapped["SessionStatus"] = relationship("SessionStatus", back_populates="sessions", lazy="selectin")
    movies: Mapped[List["Movie"]] = relationship(
        "Movie",
        back_populates="session",
        foreign_keys="Movie.session_id",
        lazy="selectin",
    )
    votes: Mapped[List["Vote"]] = relationship("Vote", back_populates="session", lazy="selectin")
    ratings: Mapped[List["Rating"]] = relationship("Rating", back_populates="session", lazy="selectin")
    winner_slot1: Mapped[Optional["Movie"]] = relationship(
        "Movie",
        foreign_keys=[winner_slot1_id],
        post_update=True,
        lazy="selectin",
    )
    winner_slot2: Mapped[Optional["Movie"]] = relationship(
        "Movie",
        foreign_keys=[winner_slot2_id],
        post_update=True,
        lazy="selectin",
    )

    @property
    def status(self) -> str:
        """Get status code for backward compatibility."""
        return self.status_obj.code if self.status_obj else "unknown"

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, status={self.status})>"


class Movie(Base):
    """Movie model - proposed movies."""
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2
    kinopoisk_url: Mapped[str] = mapped_column(String(500), nullable=False)
    kinopoisk_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    year: Mapped[Optional[int]] = mapped_column(Integer)
    genres: Mapped[Optional[str]] = mapped_column(Text)  # JSON or CSV
    description: Mapped[Optional[str]] = mapped_column(Text)
    poster_url: Mapped[Optional[str]] = mapped_column(String(1000))
    kinopoisk_rating: Mapped[Optional[float]] = mapped_column(DECIMAL(3, 1))
    club_rating: Mapped[Optional[float]] = mapped_column(DECIMAL(4, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="movies",
        foreign_keys=[session_id],
        lazy="selectin",
    )
    proposer: Mapped["User"] = relationship("User", back_populates="movies", lazy="selectin")
    votes: Mapped[List["Vote"]] = relationship("Vote", back_populates="movie", lazy="selectin")
    ratings: Mapped[List["Rating"]] = relationship("Rating", back_populates="movie", lazy="selectin")

    # Constraint: unique kinopoisk_id per session
    __table_args__ = (
        UniqueConstraint('session_id', 'kinopoisk_id', name='uq_session_kinopoisk'),
    )

    def __repr__(self) -> str:
        return f"<Movie(id={self.id}, title={self.title}, year={self.year})>"


class Vote(Base):
    """Vote model - votes in polls."""
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="votes", lazy="selectin")
    movie: Mapped["Movie"] = relationship("Movie", back_populates="votes", lazy="selectin")
    user: Mapped["User"] = relationship("User", back_populates="votes", lazy="selectin")

    # Constraint: one vote per user per movie per session
    __table_args__ = (
        UniqueConstraint('session_id', 'movie_id', 'user_id', name='uq_session_movie_user_vote'),
    )

    def __repr__(self) -> str:
        return f"<Vote(id={self.id}, session_id={self.session_id}, movie_id={self.movie_id}, user_id={self.user_id})>"


class Rating(Base):
    """Rating model - ratings after viewing."""
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-10
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="ratings", lazy="selectin")
    movie: Mapped["Movie"] = relationship("Movie", back_populates="ratings", lazy="selectin")
    user: Mapped["User"] = relationship("User", back_populates="ratings", lazy="selectin")

    # Constraint: one rating per user per movie per session
    __table_args__ = (
        UniqueConstraint('session_id', 'movie_id', 'user_id', name='uq_session_movie_user_rating'),
    )

    def __repr__(self) -> str:
        return f"<Rating(id={self.id}, session_id={self.session_id}, movie_id={self.movie_id}, rating={self.rating})>"
