import os
import re
import time
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()

PACHCA_TOKEN   = os.environ["PACHCA_TOKEN"]
PACHCA_CHAT_ID = os.environ["PACHCA_CHAT_ID"]
TG_BOT_TOKEN   = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID     = os.environ["TG_CHAT_ID"]

POLL_INTERVAL  = int(os.environ.get("POLL_INTERVAL", "15"))

seen_ids: set[int] = set()


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=3, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

SESSION = make_session()


def get_messages() -> list[dict]:
    resp = SESSION.get(
        "https://api.pachca.com/api/shared/v1/messages",
        headers={"Authorization": f"Bearer {PACHCA_TOKEN}"},
        params={"chat_id": PACHCA_CHAT_ID, "per": 20},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def send_telegram(text: str):
    for attempt in range(1, 4):
        try:
            SESSION.post(
                f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"},
                timeout=15
            ).raise_for_status()
            return
        except Exception as e:
            print(f"   ⚠ Попытка {attempt}/3: {e}")
            if attempt < 3:
                time.sleep(5 * attempt)
    print("   ❌ Сообщение не отправлено после 3 попыток")


def format_message(content: str) -> str | None:
    low = content.lower()

    if "новые заказы" in low:
        order_ids = re.findall(r"RU\d{6}-\d{6}", content)
        times     = re.findall(r"🕒\s*(\d{2}:\d{2})", content)
        store     = re.search(r"г\.\s*Санкт-Петербург[^\n📦⚡]*", content)
        store_str = store.group(0).strip() if store else "—"

        orders = "\n".join(
            f"  📦 <code>{oid}</code>  🕒 {t}"
            for oid, t in zip(order_ids, times + [""] * len(order_ids))
        )
        return (
            f"⚡ <b>Новые заказы!</b>\n"
            f"🏪 {store_str}\n\n"
            f"{orders}\n\n"
            f"⏰ <b>Соберите за 30 минут!</b>"
        )

    elif "просроченные заказы" in low:
        order_ids   = re.findall(r"RU\d{6}-\d{6}", content)
        times       = re.findall(r"🕒\s*(\d{2}:\d{2})", content)
        overdue_min = re.findall(r"(\d+)\s*мин", content)
        store       = re.search(r"г\.\s*Санкт-Петербург[^\n📦🕒]*", content)
        store_str   = store.group(0).strip() if store else "—"
        total       = re.search(r"Всего:\s*(\d+\s*заказов[^\n]*)", content)
        total_str   = total.group(1).strip() if total else ""

        orders = "\n".join(
            f"  📦 <code>{oid}</code>  🕒 {t}"
            for oid, t in zip(order_ids, times + [""] * len(order_ids))
        )
        overdue_str = overdue_min[0] + " мин" if overdue_min else "?"
        return (
            f"🚨 <b>ПРОСРОЧЕННЫЕ ЗАКАЗЫ!</b>\n"
            f"🏪 {store_str}\n\n"
            f"{orders}\n\n"
            f"⌛ Просрочено: <b>{overdue_str}</b>\n"
            + (f"📊 Итого: {total_str}\n" if total_str else "")
            + f"❗ Срочно свяжитесь с сотрудниками!"
        )

    return None


def main():
    print(f"🚀 Запущен. Опрашиваю Пачку каждые {POLL_INTERVAL} сек...")

    try:
        for msg in get_messages():
            seen_ids.add(msg["id"])
        print(f"   Запомнено {len(seen_ids)} старых сообщений. Слежу за новыми.")
    except Exception as e:
        print(f"   Ошибка при старте: {e}")

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            messages = get_messages()
            for msg in reversed(messages):
                msg_id = msg["id"]
                if msg_id in seen_ids:
                    continue

                seen_ids.add(msg_id)

                content = msg.get("content", "")
                formatted = format_message(content)
                if formatted:
                    send_telegram(formatted)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Отправлено (id={msg_id})")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏭ Пропущено (id={msg_id})")

        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Ошибка: {e}")


if __name__ == "__main__":
    main()