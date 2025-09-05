# tasks.py
import uuid
from celery import shared_task, group
from .telegram import _send_tg
from celery.utils.log import get_task_logger

log = get_task_logger(__name__)

@shared_task(bind=True, max_retries=0)
def tg_broadcast_chunk(self, chat_ids: list[int], text: str, reply_markup: dict | None = None):
    sent = failed = 0
    for i, cid in enumerate(chat_ids, 1):
        try:
            _send_tg(cid, text, reply_markup)
            sent += 1
        except Exception as e:
            failed += 1
            log.warning("tg send fail cid=%s err=%s", cid, e)
        if i % 25 == 0:
            import time; time.sleep(1)
    result = {"task_id": self.request.id, "sent": sent, "failed": failed, "total": len(chat_ids)}
    log.info("tg_broadcast_chunk result=%s", result)
    return result

def start_broadcast(chat_ids: list[int], text: str, reply_markup: dict | None = None,
                    chunk: int = 200, burst: int = 25):
    """
    Планировщик: режем список на чанки и равномерно растягиваем по времени.
    burst — сообщений в секунду (примерно).
    """
    sigs = []
    for off in range(0, len(chat_ids), chunk):
        # равномерно: каждые burst адресатов — +1 сек задержки
        delay = (off // burst)
        sigs.append(
            tg_broadcast_chunk.s(chat_ids[off:off+chunk], text, reply_markup)
              .set(countdown=delay)
        )
    return group(sigs).delay()