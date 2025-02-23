from typing import Type

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Создаем объект базы данных SQLite
engine = create_engine('sqlite:///support.db')

# Создаем базовый класс для определения моделей
Base = declarative_base()

# Создаем сессию для взаимодействия с базой данных
Session = sessionmaker(bind=engine)


# Создаем таблицу SupportTickets
class SupportTickets(Base):
    __tablename__ = 'support_tickets'

    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer)
    message_thread_id = Column(Integer)

    @classmethod
    def create_ticket(cls, tg_id: int, message_thread_id: int) -> None:
        if cls.get_ticket_by_tg_id(tg_id):
            cls.delete_ticket_by_tg_id(tg_id)

        session = Session()
        ticket = cls(tg_id=tg_id, message_thread_id=message_thread_id)
        session.add(ticket)
        session.commit()
        session.close()

    @classmethod
    def get_ticket_by_message_thread_id(cls, message_thread_id: int) -> Type['SupportTickets'] | None:
        session = Session()
        ticket = session.query(cls).filter_by(message_thread_id=message_thread_id).first()
        session.close()
        return ticket

    @classmethod
    def get_ticket_by_tg_id(cls, tg_id: int) -> Type['SupportTickets'] | None:
        session = Session()
        ticket = session.query(cls).filter_by(tg_id=tg_id).first()
        session.close()
        return ticket

    @classmethod
    def delete_ticket(cls, message_thread_id: int) -> None:
        session = Session()
        ticket = session.query(cls).filter_by(message_thread_id=message_thread_id).first()
        session.delete(ticket)
        session.commit()
        session.close()

    @classmethod
    def delete_ticket_by_tg_id(cls, tg_id: int) -> None:
        session = Session()
        ticket = session.query(cls).filter_by(tg_id=tg_id).first()
        session.delete(ticket)
        session.commit()
        session.close()

# Для списка всех тикетов и установки им порядковых номеров, нужны две функции, создание нового и получание последнего
class AllTickets(Base):
    __tablename__ = 'all_tickets'

    id = Column(Integer, primary_key=True)
    user_id_tg = Column(Integer)

    @classmethod
    def create_ticket(cls, user_id_tg: int) -> None:
        session = Session()
        ticket = cls(user_id_tg=user_id_tg)
        session.add(ticket)
        session.commit()
        session.close()

    @classmethod
    def get_ticket_by_tg_id(cls, user_id_tg: int) -> Type['SupportTickets'] | None:
        session = Session()
        ticket = session.query(cls).filter_by(user_id_tg=user_id_tg).order_by(cls.id.desc()).first()
        session.close()
        return ticket



# Создаем таблицу в базе данных, если она не существует
Base.metadata.create_all(engine)
