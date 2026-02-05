from datetime import datetime, timezone
from typing import Optional, TypedDict
from db_logic.session import session_scope
from db_logic.models import SupportTickets, User
from sqlalchemy import select, delete, update


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TicketDTO(TypedDict):
    id: int
    thread_id: int
    chat_id: int
    tg_id: int
    status: str
    closed_at: object | None

class SupportTicketsRepo:

    @staticmethod
    def create_ticket(tg_id: int, thread_id: int, chat_id: int) -> int:
        """Создаёт НОВЫЙ тикет со статусом open. Возвращает ticket_id."""
        SupportTicketsRepo.close_by_tg_id(tg_id)
        with session_scope() as session:
            ticket = SupportTickets(
                tg_id=tg_id,
                thread_id=thread_id,
                chat_id=chat_id,
                status="open",
            )
            session.add(ticket)
            session.flush()
            return ticket.id

    @staticmethod
    def get_open_by_tg_id(tg_id: int) -> Optional[TicketDTO]:
        with session_scope() as session:
            row = session.execute(
                select(
                    SupportTickets.id,
                    SupportTickets.thread_id,
                    SupportTickets.chat_id,
                    SupportTickets.tg_id,
                    SupportTickets.status,
                    SupportTickets.closed_at,
                )
                .where(SupportTickets.tg_id == tg_id)
                .where(SupportTickets.status == "open")
                .order_by(SupportTickets.id.desc())
            ).first()
            if not row:
                return None
            return {
                "id": row[0],
                "thread_id": row[1],
                "chat_id": row[2],
                "tg_id": row[3],
                "status": row[4],
                "closed_at": row[5],
            }

    @staticmethod
    def get_open_by_thread_id(thread_id: int) -> Optional[TicketDTO]:
        with session_scope() as session:
            row = session.execute(
                select(
                    SupportTickets.id,
                    SupportTickets.thread_id,
                    SupportTickets.chat_id,
                    SupportTickets.tg_id,
                    SupportTickets.status,
                    SupportTickets.closed_at,
                )
                .where(SupportTickets.thread_id == thread_id)
                .where(SupportTickets.status == "open")
            ).first()
            if not row:
                return None
            return {
                "id": row[0],
                "thread_id": row[1],
                "chat_id": row[2],
                "tg_id": row[3],
                "status": row[4],
                "closed_at": row[5],
            }

    @staticmethod
    def close_by_thread_id(thread_id: int) -> None:
        with session_scope() as session:
            session.execute(
                update(SupportTickets)
                .where(SupportTickets.thread_id == thread_id)
                .where(SupportTickets.status == "open")
                .values(status="closed", closed_at=datetime.now(timezone.utc))  # closed_at лучше поставить временем (ниже)
            )

    @staticmethod
    def close_by_tg_id(tg_id: int) -> None:
        with session_scope() as session:
            session.execute(
                update(SupportTickets)
                .where(SupportTickets.tg_id == tg_id)
                .where(SupportTickets.status == "open")
                .values(status="closed", closed_at=datetime.now(timezone.utc))
                # closed_at лучше поставить временем (ниже)
            )

    @staticmethod
    def update_thread_id(ticket_id: int, new_thread_id: int) -> bool:
        """
        Обновляет thread_id у тикета.
        Возвращает True если обновили, False если тикет не найден/закрыт.
        НЕ кидает исключение в штатных кейсах.
        """
        with session_scope() as session:
            ticket = session.execute(
                select(SupportTickets).where(
                    SupportTickets.id == ticket_id,
                    SupportTickets.closed_at.is_(None),  # если у тебя другой признак "открыт" — подставь
                )
            ).scalar_one_or_none()

            if not ticket:
                return False

            ticket.thread_id = new_thread_id
            session.add(ticket)
            return True



class UsersRepo:
    @staticmethod
    def get(tg_id: int) -> Optional[User]:
        with session_scope() as session:
            return session.execute(
                select(User).where(User.tg_id == tg_id)
            ).scalar_one_or_none()

    @staticmethod
    def get_or_create(tg_id: int) -> User:
        """
        Возвращает User. Если пользователя нет — создаёт.
        Идемпотентно: повторные вызовы не создают дублей.
        """
        with session_scope() as session:
            user = session.execute(
                select(User).where(User.tg_id == tg_id)
            ).scalar_one_or_none()

            if user is None:
                user = User(tg_id=tg_id)
                session.add(user)
                session.flush()

            return user

    @staticmethod
    def has_privacy(tg_id: int) -> bool:
        with session_scope() as session:
            val = session.execute(
                select(User.privacy_accepted).where(User.tg_id == tg_id)
            ).scalar_one_or_none()
            return bool(val)

    @staticmethod
    def has_marketing(tg_id: int) -> bool:
        with session_scope() as session:
            val = session.execute(
                select(User.marketing_accepted).where(User.tg_id == tg_id)
            ).scalar_one_or_none()
            return bool(val)

    @staticmethod
    def accept_privacy(tg_id: int, version: str) -> bool:
        """
        Ставит согласие на privacy.
        Возвращает True, если статус реально изменился (False -> True).
        """
        with session_scope() as session:
            user = session.execute(
                select(User).where(User.tg_id == tg_id)
            ).scalar_one_or_none()

            if user is None:
                user = User(tg_id=tg_id)
                session.add(user)
                session.flush()

            if user.privacy_accepted:
                # можно оставить как есть; но полезно заполнить версию если пустая
                if not user.privacy_version:
                    user.privacy_version = version
                return False

            user.privacy_accepted = True
            user.privacy_accepted_at = utcnow()
            user.privacy_version = version
            return True

    @staticmethod
    def accept_marketing(tg_id: int) -> bool:
        """
        Ставит согласие на marketing.
        Возвращает True, если статус реально изменился (False -> True).
        """
        with session_scope() as session:
            user = session.execute(
                select(User).where(User.tg_id == tg_id)
            ).scalar_one_or_none()

            if user is None:
                user = User(tg_id=tg_id)
                session.add(user)
                session.flush()

            if user.marketing_accepted:
                return False

            user.marketing_accepted = True
            user.marketing_accepted_at = utcnow()
            return True

    @staticmethod
    def revoke_marketing(tg_id: int) -> bool:
        """
        Опционально: отзыв маркетингового согласия.
        Возвращает True, если реально изменилось (True -> False).
        """
        with session_scope() as session:
            user = session.execute(
                select(User).where(User.tg_id == tg_id)
            ).scalar_one_or_none()

            if user is None or not user.marketing_accepted:
                return False

            user.marketing_accepted = False
            return True
