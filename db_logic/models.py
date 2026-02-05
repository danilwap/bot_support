from typing import Type

from sqlalchemy import create_engine, Column, Integer, String, BigInteger, DateTime, func, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from db_logic.database import Base


# Создаем таблицу SupportTickets
class SupportTickets(Base):
    __tablename__ = 'support_tickets'

    id = Column(Integer, primary_key=True, autoincrement=True)  # <-- номер тикета 1..N
    tg_id = Column(BigInteger, nullable=False)  # если 1 активный тикет на юзера
    thread_id = Column(Integer, nullable=False)  # topic/thread id
    chat_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    status = Column(String(10), nullable=False, default="open")
    closed_at = Column(DateTime, nullable=True)




class User(Base):
    __tablename__ = "users"

    tg_id = Column(Integer, primary_key=True)

    privacy_accepted = Column(Boolean, nullable=False, default=False)
    privacy_accepted_at = Column(DateTime(timezone=True), nullable=True)
    privacy_version = Column(String(32), nullable=True)

    marketing_accepted = Column(Boolean, nullable=False, default=False)
    marketing_accepted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)







