import logging

from kombu.exceptions import OperationalError

from app.tasks.orders import generate_order_pdf, send_order_email, send_order_sms


logger = logging.getLogger(__name__)


class CeleryOrderNotifications:
    def enqueue_order_created(self, order_id: int, email: str, phone: str | None):
        try:
            generate_order_pdf.delay(order_id)
            send_order_email.delay(order_id, email)
            send_order_sms.delay(order_id, phone)
        except OperationalError:
            logger.exception("Не удалось отправить задачу заказа %s в Celery", order_id)
