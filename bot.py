import os
import time
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Paris"))

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "data.json"


def now():
    return datetime.now(TZ)


def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "tasks": {},
            "notes": {},
            "clients": {},
            "finance": {},
            "chat": {}
        }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def user_bucket(data, section, chat_id, default):
    chat_id = str(chat_id)
    if section not in data:
        data[section] = {}
    if chat_id not in data[section]:
        data[section][chat_id] = default
    return data[section][chat_id]


def send_message(chat_id, text):
    requests.post(
        f"{API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )


def parse_reminder(text):
    lower = text.lower()
    words = text.split()

    if len(words) < 2:
        return text, None

    possible_time = words[-1]

    if ":" not in possible_time:
        return text, None

    try:
        hour, minute = map(int, possible_time.split(":"))
    except Exception:
        return text, None

    if "сегодня" in lower:
        date = now().date()
        clean_text = text.replace("сегодня", "").replace(possible_time, "").strip()
    elif "завтра" in lower:
        date = (now() + timedelta(days=1)).date()
        clean_text = text.replace("завтра", "").replace(possible_time, "").strip()
    else:
        return text, None

    reminder_time = datetime(
        date.year, date.month, date.day, hour, minute, tzinfo=TZ
    )

    return clean_text, reminder_time.isoformat()


def check_reminders(data):
    current = now()
    changed = False

    def biz_agent(chat_id, data):
        tasks = user_bucket(data, "tasks", chat_id, [])
        notes = user_bucket(data, "notes", chat_id, [])
        clients = user_bucket(data, "clients", chat_id, [])
        finance = user_bucket(data, "finance", chat_id, [])

    total_tasks = len(tasks)
    done_tasks = len([t for t in tasks if t.get("done")])
    active_tasks = total_tasks - done_tasks

    income = sum(
        item["amount"]
        for item in finance
        if item["type"] == "income"
    )

    spent = sum(
        item["amount"]
        for item in finance
        if item["type"] == "spent"
    )

    balance = income - spent

    deals_count = 0
    deals_sum = 0

    for client in clients:
        deals = client.get("deals", [])
        deals_count += len(deals)

        for deal in deals:
            deals_sum += deal.get("amount", 0)

    report = (
        "📊 Biz Director\n\n"
        f"📋 Задачи: {total_tasks}\n"
        f"✅ Выполнено: {done_tasks}\n"
        f"⏳ Осталось: {active_tasks}\n\n"
        f"👥 Клиентов: {len(clients)}\n"
        f"💼 Сделок: {deals_count}\n"
        f"💰 Сумма сделок: {deals_sum}\n\n"
        f"📈 Доходы: {income}\n"
        f"📉 Расходы: {spent}\n"
        f"💵 Баланс: {balance}\n\n"
    )

    if active_tasks > 0:
        report += "👉 Сегодня сначала закрой активные задачи.\n"

    if len(clients) == 0:
        report += "👉 Добавь новых клиентов в CRM.\n"

    if balance < 0:
        report += "👉 Расходы превышают доходы.\n"

    return report

    for chat_id, tasks in data.get("tasks", {}).items():
        for task in tasks:
            if task.get("done") or task.get("reminded"):
                continue

            reminder_at = task.get("reminder_at")
            if not reminder_at:
                continue

            try:
                reminder_time = datetime.fromisoformat(reminder_at)
            except Exception:
                continue

            if current.timestamp() >= reminder_time.timestamp():
                send_message(chat_id, f"🔔 Напоминание:\n{task['text']}")
                task["reminded"] = True
                changed = True

    if changed:
        save_data(data)
def biz_agent(chat_id, data):
    tasks = user_bucket(data, "tasks", chat_id, [])
    notes = user_bucket(data, "notes", chat_id, [])
    clients = user_bucket(data, "clients", chat_id, [])
    finance = user_bucket(data, "finance", chat_id, [])

    total_tasks = len(tasks)
    done_tasks = len([t for t in tasks if t.get("done")])
    active_tasks = total_tasks - done_tasks

    income = sum(item["amount"] for item in finance if item["type"] == "income")
    spent = sum(item["amount"] for item in finance if item["type"] == "spent")
    balance = income - spent

    deals_count = 0
    deals_sum = 0

    for client in clients:
        deals = client.get("deals", [])
        deals_count += len(deals)

        for deal in deals:
            deals_sum += deal.get("amount", 0)

    report = (
        "📊 Biz Director\n\n"
        "✅ Задачи:\n"
        f"Всего: {total_tasks}\n"
        f"Выполнено: {done_tasks}\n"
        f"Осталось: {active_tasks}\n\n"
        "👥 CRM:\n"
        f"Клиентов: {len(clients)}\n"
        f"Сделок: {deals_count}\n"
        f"Сумма сделок: {deals_sum}\n\n"
        "💰 Финансы:\n"
        f"Доходы: {income}\n"
        f"Расходы: {spent}\n"
        f"Баланс: {balance}\n\n"
        "📌 Рекомендации:\n"
    )

    if active_tasks > 0:
        report += "1. Сначала закрой активные задачи.\n"
    else:
        report += "1. Активных задач нет — добавь приоритет на сегодня.\n"

    if len(clients) == 0:
        report += "2. Добавь первых клиентов в CRM.\n"
    elif deals_count == 0:
        report += "2. Добавь сделки по текущим клиентам.\n"
    else:
        report += "2. Проверь клиентов со сделками и доведи их до оплаты.\n"

    if balance < 0:
        report += "3. Расходы выше доходов — сократи ненужные траты.\n"
    elif income == 0:
        report += "3. Добавь доходы или план продаж.\n"
    else:
        report += "3. Финансовая ситуация положительная — усиливай продажи.\n"

    if notes:
        report += "4. Просмотри последние заметки и преврати идеи в задачи.\n"
    else:
        report += "4. Добавь заметки с идеями, клиентами или планами.\n"

    return report

def ask_gpt(chat_id, prompt, data):
    if not OPENAI_API_KEY:
        return "❌ OPENAI_API_KEY не добавлен в Railway Variables."

    history = user_bucket(data, "chat", chat_id, [])

    messages_text = ""
    for item in history[-6:]:
        messages_text += f"{item['role']}: {item['content']}\n"

    full_prompt = (
        "Ты Biz Assistant — личный бизнес-помощник в Telegram. "
        "Отвечай кратко, практично и на русском языке.\n\n"
        f"История:\n{messages_text}\n"
        f"Пользователь: {prompt}"
    )

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "input": full_prompt,
            },
            timeout=60,
        )

        result = response.json()

        if "output_text" in result:
            answer = result["output_text"]
        else:
            answer = result.get("error", {}).get("message", "Не удалось получить ответ от ChatGPT.")

        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": answer})
        save_data(data)

        return answer

    except Exception as e:
        return f"❌ Ошибка ChatGPT: {e}"


def help_text():
    return (
        "👋 Biz Assistant v1.3\n\n"
        "Команды:\n\n"
        "🧠 ChatGPT:\n"
        "/ask вопрос — спросить ChatGPT\n"
        "/agent — Biz Director анализ\n\n"
        "✅ Задачи:\n"
        "/add текст задачи — добавить задачу\n"
        "/add задача сегодня 18:00 — задача с напоминанием\n"
        "/tasks — список задач\n"
        "/done номер — выполнить задачу\n"
        "/delete номер — удалить задачу\n"
        "/report — итог дня\n"
        "/clear — очистить задачи\n\n"
        "📝 Заметки:\n"
        "/note текст — добавить заметку\n"
        "/notes — список заметок\n"
        "/delnote номер — удалить заметку\n\n"
        "👥 CRM:\n"
        "/client Имя — добавить клиента\n"
        "/clients — список клиентов\n"
        "/deal Имя сумма описание — добавить сделку\n\n"
        "💰 Финансы:\n"
        "/spent сумма категория — расход\n"
        "/income сумма источник — доход\n"
        "/finance — финансовый отчет"
    )


def main():
    offset = 0

    while True:
        try:
            data = load_data()
            check_reminders(data)

            response = requests.get(
                f"{API_URL}/getUpdates",
                params={"offset": offset, "timeout": 20}
            )
            updates = response.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1

                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "").strip()

                if not chat_id or not text:
                    continue

                tasks = user_bucket(data, "tasks", chat_id, [])
                notes = user_bucket(data, "notes", chat_id, [])
                clients = user_bucket(data, "clients", chat_id, [])
                finance = user_bucket(data, "finance", chat_id, [])

                if text == "/start":
                    send_message(chat_id, help_text())

                elif text.startswith("/ask "):
                    prompt = text.replace("/ask ", "", 1).strip()
                    send_message(chat_id, "🧠 Думаю...")
                    answer = ask_gpt(chat_id, prompt, data)
                    send_message(chat_id, answer)

                elif text.startswith("/add "):
                    task_raw = text.replace("/add ", "", 1).strip()
                    task_text, reminder_at = parse_reminder(task_raw)

                    tasks.append({
                        "text": task_text,
                        "done": False,
                        "created_at": now().isoformat(),
                        "reminder_at": reminder_at,
                        "reminded": False
                    })

                    save_data(data)

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
                    if not tasks:
                        send_message(chat_id, "📭 У тебя пока нет задач.")
                    else:
                        result = "📋 Твои задачи:\n\n"
                        for i, task in enumerate(tasks, start=1):
                            status = "✅" if task["done"] else "⬜"
                            reminder = ""
                            if task.get("reminder_at"):
                                rt = datetime.fromisoformat(task["reminder_at"])
                                reminder = f" 🔔 {rt.strftime('%d.%m %H:%M')}"
                            result += f"{i}. {status} {task['text']}{reminder}\n"
                        send_message(chat_id, result)

                elif text.startswith("/done "):
                    try:
                        number = int(text.replace("/done ", "", 1).strip())
                        if 1 <= number <= len(tasks):
                            tasks[number - 1]["done"] = True
                            save_data(data)
                            send_message(chat_id, f"✅ Задача выполнена:\n{tasks[number - 1]['text']}")
                        else:
                            send_message(chat_id, "Такой задачи нет.")
                    except Exception:
                        send_message(chat_id, "Напиши так:\n/done 1")

                elif text.startswith("/delete "):
                    try:
                        number = int(text.replace("/delete ", "", 1).strip())
                        if 1 <= number <= len(tasks):
                            deleted = tasks.pop(number - 1)
                            save_data(data)
                            send_message(chat_id, f"🗑 Задача удалена:\n{deleted['text']}")
                        else:
                            send_message(chat_id, "Такой задачи нет.")
                    except Exception:
                        send_message(chat_id, "Напиши так:\n/delete 1")

               elif text == "/agent":
    send_message(chat_id, "📊 Анализирую твои данные...")
    result = biz_agent(chat_id, data)
    send_message(chat_id, result)

elif text == "/report":
                    total = len(tasks)
                    done = len([t for t in tasks if t["done"]])
                    active = total - done
                    send_message(
                        chat_id,
                        f"📈 Итог дня:\n\nВсего задач: {total}\nВыполнено: {done}\nОсталось: {active}"
                    )

                elif text == "/clear":
                    data["tasks"][str(chat_id)] = []
                    save_data(data)
                    send_message(chat_id, "🗑 Все задачи очищены.")

                elif text.startswith("/note "):
                    note = text.replace("/note ", "", 1).strip()
                    notes.append({
                        "text": note,
                        "created_at": now().isoformat()
                    })
                    save_data(data)
                    send_message(chat_id, f"📝 Заметка сохранена:\n{note}")

                elif text == "/notes":
                    if not notes:
                        send_message(chat_id, "📭 Заметок пока нет.")
                    else:
                        result = "📝 Твои заметки:\n\n"
                        for i, note in enumerate(notes, start=1):
                            result += f"{i}. {note['text']}\n"
                        send_message(chat_id, result)

                elif text.startswith("/delnote "):
                    try:
                        number = int(text.replace("/delnote ", "", 1).strip())
                        if 1 <= number <= len(notes):
                            deleted = notes.pop(number - 1)
                            save_data(data)
                            send_message(chat_id, f"🗑 Заметка удалена:\n{deleted['text']}")
                        else:
                            send_message(chat_id, "Такой заметки нет.")
                    except Exception:
                        send_message(chat_id, "Напиши так:\n/delnote 1")

                elif text.startswith("/client "):
                    name = text.replace("/client ", "", 1).strip()
                    clients.append({
                        "name": name,
                        "deals": [],
                        "created_at": now().isoformat()
                    })
                    save_data(data)
                    send_message(chat_id, f"👤 Клиент добавлен:\n{name}")

                elif text == "/clients":
                    if not clients:
                        send_message(chat_id, "📭 Клиентов пока нет.")
                    else:
                        result = "👥 Клиенты:\n\n"
                        for i, client in enumerate(clients, start=1):
                            deals_sum = sum([d.get("amount", 0) for d in client.get("deals", [])])
                            result += f"{i}. {client['name']} — сделок: {len(client.get('deals', []))}, сумма: {deals_sum}\n"
                        send_message(chat_id, result)

                elif text.startswith("/deal "):
                    raw = text.replace("/deal ", "", 1).strip()
                    parts = raw.split()

                    if len(parts) < 2:
                        send_message(chat_id, "Напиши так:\n/deal Иван 500 сайт")
                        continue

                    name = parts[0]

                    try:
                        amount = float(parts[1].replace(",", "."))
                    except Exception:
                        send_message(chat_id, "Сумма должна быть числом:\n/deal Иван 500 сайт")
                        continue

                    description = " ".join(parts[2:]) if len(parts) > 2 else "Сделка"

                    client = None
                    for c in clients:
                        if c["name"].lower() == name.lower():
                            client = c
                            break

                    if client is None:
                        client = {
                            "name": name,
                            "deals": [],
                            "created_at": now().isoformat()
                        }
                        clients.append(client)

                    client["deals"].append({
                        "amount": amount,
                        "description": description,
                        "created_at": now().isoformat()
                    })

                    save_data(data)
                    send_message(chat_id, f"💼 Сделка добавлена:\n{name} — {amount}\n{description}")

                elif text.startswith("/spent "):
                    raw = text.replace("/spent ", "", 1).strip()
                    parts = raw.split()

                    try:
                        amount = float(parts[0].replace(",", "."))
                    except Exception:
                        send_message(chat_id, "Напиши так:\n/spent 50 кофе")
                        continue

                    category = " ".join(parts[1:]) if len(parts) > 1 else "расход"

                    finance.append({
                        "type": "spent",
                        "amount": amount,
                        "category": category,
                        "created_at": now().isoformat()
                    })

                    save_data(data)
                    send_message(chat_id, f"💸 Расход записан:\n{amount} — {category}")

                elif text.startswith("/income "):
                    raw = text.replace("/income ", "", 1).strip()
                    parts = raw.split()

                    try:
                        amount = float(parts[0].replace(",", "."))
                    except Exception:
                        send_message(chat_id, "Напиши так:\n/income 1000 клиент")
                        continue

                    source = " ".join(parts[1:]) if len(parts) > 1 else "доход"

                    finance.append({
                        "type": "income",
                        "amount": amount,
                        "category": source,
                        "created_at": now().isoformat()
                    })

                    save_data(data)
                    send_message(chat_id, f"💰 Доход записан:\n{amount} — {source}")

                elif text == "/finance":
                    income = sum(i["amount"] for i in finance if i["type"] == "income")
                    spent = sum(i["amount"] for i in finance if i["type"] == "spent")
                    balance = income - spent

                    send_message(
                        chat_id,
                        f"💰 Финансы:\n\nДоходы: {income}\nРасходы: {spent}\nБаланс: {balance}"
                    )

                else:
                    send_message(chat_id, "Я пока понимаю команды:\n/start\n/ask\n/add\n/tasks\n/note\n/client\n/spent\n/income")

                save_data(data)

        except Exception as e:
            print("Error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
