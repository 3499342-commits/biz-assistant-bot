import os
import time
import json
import requests

TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"
TASKS_FILE = "tasks.json"


def load_tasks():
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except:
        return {}


def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as file:
        json.dump(tasks, file, ensure_ascii=False, indent=2)


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


def main():
    offset = 0

    while True:
        try:
            response = requests.get(
                f"{API_URL}/getUpdates",
                params={"offset": offset, "timeout": 30}
            )

            data = response.json()
            tasks = load_tasks()

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
                        "👋 Biz Assistant v1.0\n\n"
                        "Я помогу вести задачи.\n\n"
                        "Команды:\n"
                        "/add текст задачи — добавить задачу\n"
                        "/tasks — список задач\n"
                        "/done номер — выполнить задачу\n"
                        "/report — итог дня\n"
                        "/clear — очистить задачи"
                    )

                elif text.startswith("/add "):
                    task_text = text.replace("/add ", "", 1).strip()

                    if task_text:
                        user_tasks.append({
                            "text": task_text,
                            "done": False
                        })
                        save_tasks(tasks)
                        send_message(chat_id, f"✅ Задача добавлена:\n{task_text}")
                    else:
                        send_message(chat_id, "Напиши так:\n/add Купить продукты")

                elif text == "/tasks":
                    if not user_tasks:
                        send_message(chat_id, "📭 У тебя пока нет задач.")
                    else:
                        result = "📋 Твои задачи:\n\n"
                        for i, task in enumerate(user_tasks, start=1):
                            status = "✅" if task["done"] else "⬜"
                            result += f"{i}. {status} {task['text']}\n"
                        send_message(chat_id, result)

                elif text.startswith("/done "):
                    try:
                        number = int(text.replace("/done ", "", 1).strip())
                        if 1 <= number <= len(user_tasks):
                            user_tasks[number - 1]["done"] = True
                            save_tasks(tasks)
                            send_message(chat_id, f"✅ Задача выполнена:\n{user_tasks[number - 1]['text']}")
                        else:
                            send_message(chat_id, "Такой задачи нет.")
                    except:
                        send_message(chat_id, "Напиши так:\n/done 1")

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
                        "/tasks\n"
                        "/done номер\n"
                        "/report"
                    )

            save_tasks(tasks)

        except Exception as e:
            print("Error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
