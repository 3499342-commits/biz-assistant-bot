import os
import time
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TOKEN = os.getenv("BOT_TOKEN")
TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Kyiv"))

API_URL = f"https://api.telegram.org/bot{TOKEN}"
TASKS_FILE = "tasks.json"


def load_tasks():
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def send_message(chat_id, text):
    requests.post(
        f"{API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )


def get_user_tasks(tasks, chat_id):
    chat_id = str(chat_id)
    if chat_id not in tasks:
        tasks[chat_id] = []
    return tasks[chat_id]


def parse_reminder(text):
    now = datetime.now(TZ)
    lower = text.lower()

    words = text.split()
    if len(words) < 2:
        return text, None

    possible_time = words[-1]

    if ":" not in possible_time:
        return text, None

    try:
        hour, minute = map(int, possible_time.split(":"))
    except:
        return text, None

    if "сегодня" in lower:
        date = now.date()
        clean_text = text.replace("сегодня", "").replace(possible_time, "").strip()
    elif "завтра" in lower:
        date = (now + timedelta(days=1)).date()
        clean_text = text.replace("завтра", "").replace(possible_time, "").strip()
    else:
        return text, None

    reminder_time = datetime(
        date.year, date.month, date.day, hour, minute, tzinfo=TZ
    )

    return clean_text, reminder_time.isoformat()


def check_reminders(tasks):
    now = datetime.now(TZ)

    for chat_id, user_tasks in tasks.items():
        for task in user_tasks:
            if task.get("done"):
                continue

            if task.get("reminded"):
                continue

            reminder_at = task.get("reminder_at")
            if not reminder_at:
                continue

            try:
                reminder_time = datetime.fromisoformat(reminder_at)
            except:
                continue

            if now >= reminder_time:
                send_message(
                    chat_id,
                    f"🔔 Напоминание:\n{task['text']}"
                )
                task["reminded"] = True

    save_tasks(tasks)


def main():
    offset = 0

    while True:
        try:
            tasks = load_tasks()
            check_reminders(tasks)

            response = requests.get(
                f"{API_URL}/getUpdates",
                params={"offset": offset, "timeout": 20}
            )

            data = response.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "").strip()

                if not chat_id:
                    continue

                user_tasks = get_user_tasks(tasks, chat_id)

                if text == "/start":
                    send_message(
                        chat_id,
                        "👋 Biz Assistant v1.1\n\n"
                        "Я помогу вести задачи и напоминания.\n\n"
                        "Команды:\n"
                        "/add текст задачи — добавить задачу\n"
                        "/add задача сегодня 22:30 — задача с напоминанием\n"
                        "/add задача завтра 18:00 — задача с напоминанием\n"
                        "/tasks — список задач\n"
                        "/done номер — выполнить задачу\n"
                        "/delete номер — удалить задачу\n"
                        "/report — итог дня\n"
                        "/clear — очистить задачи"
                    )

                elif text.startswith("/add "):
                    task_raw = text.replace("/add ", "", 1).strip()

                    if not task_raw:
                        send_message(chat_id, "Напиши так:\n/add Купить продукты")
                        continue

                    task_text, reminder_at = parse_reminder(task_raw)

                    user_tasks.append({
                        "text": task_text,
                        "done": False,
                        "created_at": datetime.now(TZ).isoformat(),
                        "reminder_at": reminder_at,
                        "reminded": False
                    })

                    save_tasks(tasks)

                    if reminder_at:
                        reminder_time = datetime.fromisoformat(reminder_at)
                        send_message(
                            chat_id,
                            f"✅ Задача добавлена:\n{task_text}\n\n"
                            f"🔔 Напомню: {reminder_time.strftime('%d.%m.%Y %H:%M')}"
                        )
                    else:
                        send_message(chat_id, f"✅ Задача добавлена:\n{task_text}")

                elif text == "/tasks":
                    if not user_tasks:
                        send_message(chat_id, "📭 У тебя пока нет задач.")
                    else:
                        result = "📋 Твои задачи:\n\n"
                        for i, task in enumerate(user_tasks, start=1):
                            status = "✅" if task["done"] else "⬜"
                            reminder = ""

                            if task.get("reminder_at"):
                                reminder_time = datetime.fromisoformat(task["reminder_at"])
                                reminder = f" 🔔 {reminder_time.strftime('%d.%m %H:%M')}"

                            result += f"{i}. {status} {task['text']}{reminder}\n"

                        send_message(chat_id, result)

                elif text.startswith("/done "):
                    try:
                        number = int(text.replace("/done ", "", 1).strip())

                        if 1 <= number <= len(user_tasks):
                            user_tasks[number - 1]["done"] = True
                            save_tasks(tasks)
                            send_message(
                                chat_id,
                                f"✅ Задача выполнена:\n{user_tasks[number - 1]['text']}"
                            )
                        else:
                            send_message(chat_id, "Такой задачи нет.")
                    except:
                        send_message(chat_id, "Напиши так:\n/done 1")

                elif text.startswith("/delete "):
                    try:
                        number = int(text.replace("/delete ", "", 1).strip())

                        if 1 <= number <= len(user_tasks):
                            deleted = user_tasks.pop(number - 1)
                            save_tasks(tasks)
                            send_message(
                                chat_id,
                                f"🗑 Задача удалена:\n{deleted['text']}"
                            )
                        else:
                            send_message(chat_id, "Такой задачи нет.")
                    except:
                        send_message(chat_id, "Напиши так:\n/delete 1")

                elif text == "/report":
                    total = len(user_tasks)
                    done = len([t for t in user_tasks if t["done"]])
                    active = total - done

                    send_message(
                        chat_id,
                        "📈 Итог дня:\n\n"
                        f"Всего задач: {total}\n"
                        f"Выполнено: {done}\n"
                        f"Осталось: {active}"
                    )

                elif text == "/clear":
                    tasks[str(chat_id)] = []
                    save_tasks(tasks)
                    send_message(chat_id, "🗑 Все задачи очищены.")

                else:
                    send_message(
                        chat_id,
                        "Я пока понимаю команды:\n"
                        "/add задача\n"
                        "/add задача сегодня 22:30\n"
                        "/add задача завтра 18:00\n"
                        "/tasks\n"
                        "/done номер\n"
                        "/delete номер\n"
                        "/report"
                    )

            save_tasks(tasks)

        except Exception as e:
            print("Error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
