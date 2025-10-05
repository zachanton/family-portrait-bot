# aiogram_bot_template/db/models.py
from sqlalchemy import (
    func, ForeignKey, JSON, text, BigInteger, Boolean, Column,
    DateTime, Integer, String, Text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(32), nullable=True)
    first_name = Column(String(255), nullable=False)
    language_code = Column(String(5), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="active", nullable=False, index=True)
    last_activity_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    referral_source = Column(String(100), nullable=True)
    has_used_free_trial = Column(Boolean, default=False, nullable=False, server_default=text("false"))

    requests = relationship("GenerationRequest", back_populates="user")
    payments = relationship("Payment", back_populates="user")


class GenerationRequest(Base):
    """Tracks a user's entire generation session, from start to finish."""
    __tablename__ = "generation_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True, default="started")
    request_parameters = Column(JSON, nullable=True)
    referral_source_at_creation = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="requests")
    generations = relationship("Generation", back_populates="request", cascade="all, delete-orphan", foreign_keys="[Generation.request_id]")
    source_images = relationship("GenerationSourceImage", back_populates="request", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="request", uselist=False)

class Generation(Base):
    """Stores the result of a single AI generation attempt."""
    __tablename__ = "generations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("generation_requests.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    quality_level = Column(Integer, nullable=True)
    trial_type = Column(String(50), nullable=True, index=True)
    seed = Column(BigInteger, nullable=True)
    style = Column(String(50), nullable=True)
    result_image_unique_id = Column(String, nullable=True)
    result_message_id = Column(BigInteger, nullable=True)
    result_file_id = Column(String, nullable=True)
    caption = Column(Text, nullable=True)
    control_message_id = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    generation_time_ms = Column(Integer, nullable=True)
    api_request_payload = Column(JSON, nullable=True)
    api_response_payload = Column(JSON, nullable=True)
    enhanced_prompt = Column(Text, nullable=True)
    sequence_index = Column(Integer, nullable=True, comment="The 0-indexed position of this image in a photoshoot sequence.")
    source_generation_id = Column(Integer, ForeignKey("generations.id"), nullable=True, comment="The ID of the previous generation in the sequence, used as a source.")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    request = relationship("GenerationRequest", back_populates="generations", foreign_keys=[request_id])
    source_generation = relationship("Generation", remote_side=[id], backref="derived_generations", uselist=False)


class GenerationSourceImage(Base):
    """Stores a source image for a specific generation request."""
    __tablename__ = "generation_source_images"
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("generation_requests.id"), nullable=False, index=True)
    file_unique_id = Column(String, nullable=False)
    file_id = Column(String, nullable=False)
    role = Column(String(50), nullable=False)

    request = relationship("GenerationRequest", back_populates="source_images")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    request_id = Column(Integer, ForeignKey("generation_requests.id"), unique=True, nullable=False, index=True)
    telegram_charge_id = Column(String, unique=True, nullable=False)
    provider_charge_id = Column(String, nullable=False)
    currency = Column(String(5), nullable=False)
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    invoice_payload = Column(JSON, nullable=True)

    user = relationship("User", back_populates="payments")
    request = relationship("GenerationRequest", back_populates="payment")