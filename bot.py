import os
import time
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Paris")

TZ = ZoneInfo(TIMEZONE)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE = "data.json"


def now():
    return datetime.now(TZ)


def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    if "tasks" not in data:
        data["tasks"] = {}

    if "notes" not in data:
        data["notes"] = {}

    if "clients" not in data:
        data["clients"] = {}

    if "finance" not in data:
        data["finance"] = {}

    if "chat" not in data:
        data["chat"] = {}

    return data


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


def main_keyboard():
    return {
        "keyboard": [
    [{"text": "📋 Задачи"}, {"text": "📝 Заметки"}],
    [{"text": "👥 CRM"}, {"text": "💰 Финансы"}],
    [{"text": "🤖 AI Помощник"}, {"text": "📊 Biz Director"}],
    [{"text": "📈 Dashboard"}],
    [{"text": "ℹ️ Помощь"}]
],
        "resize_keyboard": True
    }


def send_message(chat_id, text):
    try:
        requests.post(
            f"{API_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": main_keyboard()
            },
            timeout=20
        )
    except Exception as e:
        print("Send message error:", e)


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
        date.year,
        date.month,
        date.day,
        hour,
        minute,
        tzinfo=TZ
    )

    return clean_text, reminder_time.isoformat()


def check_reminders(data):
    current = now()
    changed = False

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

def ask_gpt(chat_id, prompt, data):
    if not OPENAI_API_KEY:
        return (
            "❌ OPENAI_API_KEY не добавлен в Railway Variables.\n\n"
            "Бот работает без ChatGPT, но AI-функции пока недоступны."
        )

    history = user_bucket(data, "chat", chat_id, [])

    history_text = ""
    for item in history[-6:]:
        history_text += f"{item['role']}: {item['content']}\n"

    full_prompt = (
        "Ты Biz Assistant — личный бизнес-помощник в Telegram. "
        "Отвечай кратко, понятно, практично и на русском языке.\n\n"
        f"История:\n{history_text}\n\n"
        f"Пользователь: {prompt}"
    )

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENAI_MODEL,
                "input": full_prompt
            },
            timeout=60
        )

        result = response.json()

        if response.status_code == 429:
            return (
                "❌ Закончился лимит OpenAI API.\n"
                "Проверь Billing и баланс в OpenAI Platform."
            )

        if response.status_code >= 400:
            return result.get("error", {}).get("message", "❌ Ошибка OpenAI API.")

        answer = result.get("output_text", "Не удалось получить ответ от ChatGPT.")

        history.append({
            "role": "user",
            "content": prompt
        })

        history.append({
            "role": "assistant",
            "content": answer
        })

        save_data(data)

        return answer

    except Exception as e:
        return f"❌ Ошибка ChatGPT:\n{e}"


def biz_agent(chat_id, data):
    tasks = user_bucket(data, "tasks", chat_id, [])
    notes = user_bucket(data, "notes", chat_id, [])
    clients = user_bucket(data, "clients", chat_id, [])
    finance = user_bucket(data, "finance", chat_id, [])

    total_tasks = len(tasks)
    done_tasks = len([task for task in tasks if task.get("done")])
    active_tasks = total_tasks - done_tasks

    active_task_list = [
        task.get("text", "")
        for task in tasks
        if not task.get("done")
    ]

    income = sum(
        item.get("amount", 0)
        for item in finance
        if item.get("type") == "income"
    )

    spent = sum(
        item.get("amount", 0)
        for item in finance
        if item.get("type") == "spent"
    )

    balance = income - spent

    deals_count = 0
    deals_sum = 0

    for client in clients:
        deals = client.get("deals", [])
        deals_count += len(deals)
        deals_sum += sum(deal.get("amount", 0) for deal in deals)

    report = "📊 Biz Director\n\n"

    report += "✅ Задачи:\n"
    report += f"Всего: {total_tasks}\n"
    report += f"Выполнено: {done_tasks}\n"
    report += f"Осталось: {active_tasks}\n\n"

    report += "👥 CRM:\n"
    report += f"Клиентов: {len(clients)}\n"
    report += f"Сделок: {deals_count}\n"
    report += f"Сумма сделок: {deals_sum}\n\n"

    report += "💰 Финансы:\n"
    report += f"Доходы: {income}\n"
    report += f"Расходы: {spent}\n"
    report += f"Баланс: {balance}\n\n"

    report += "🎯 Главный фокус:\n"

    if active_tasks > 0:
        report += f"Закрой первую активную задачу: {active_task_list[0]}\n\n"
    elif len(clients) == 0:
        report += "Добавь первых клиентов в CRM.\n\n"
    elif deals_count == 0:
        report += "Добавь сделки по клиентам.\n\n"
    else:
        report += "Усиль продажи и доведи сделки до оплаты.\n\n"

    report += "📌 Рекомендации:\n"

    if active_tasks == 0:
        report += "1. Добавь 1 главную задачу на сегодня.\n"
    elif active_tasks <= 3:
        report += "1. У тебя нормальная нагрузка — закрой задачи по порядку.\n"
    else:
        report += "1. Задач много — выбери 3 самые важные.\n"

    if len(clients) == 0:
        report += "2. Добавь клиентов командой /client Имя.\n"
    elif deals_count == 0:
        report += "2. Добавь сделки командой /deal Имя сумма описание.\n"
    else:
        report += "2. Проверь клиентов и сделай следующий контакт.\n"

    if income == 0:
        report += "3. Запиши доход или поставь цель по продажам.\n"
    elif balance < 0:
        report += "3. Расходы выше доходов — сократи лишнее.\n"
    else:
        report += "3. Баланс положительный — продолжай фиксировать деньги.\n"

    if len(notes) > 0:
        report += "4. Проверь заметки и преврати важные идеи в задачи.\n"
    else:
        report += "4. Добавь идеи или планы через /note.\n"

    report += "\n🚀 Следующий шаг:\n"

    if active_tasks > 0:
        report += f"Сейчас сделай: {active_task_list[0]}"
    elif len(clients) == 0:
        report += "Напиши: /client Иван"
    elif deals_count == 0:
        report += "Напиши: /deal Иван 500 консультация"
    elif income == 0:
        report += "Напиши: /income 1000 клиент"
    else:
        report += "Напиши клиенту и продвинь сделку к оплате."

    return report
def help_text():
    return (
        "👋 Biz Assistant v1.4\n\n"
        "Кнопки:\n"
        "📋 Задачи\n"
        "📝 Заметки\n"
        "👥 CRM\n"
        "💰 Финансы\n"
        "🤖 AI Помощник\n"
        "📊 Biz Director\n\n"
        "Команды:\n\n"
        "🧠 ChatGPT:\n"
        "/ask вопрос — спросить ChatGPT\n"
        "/agent — бизнес-анализ\n\n"
        "✅ Задачи:\n"
        "/add текст задачи — добавить задачу\n"
        "/add задача сегодня 18:00 — задача с напоминанием\n"
        "/add задача завтра 10:00 — задача с напоминанием\n"
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
                params={
                    "offset": offset,
                    "timeout": 20
                },
                timeout=30
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

                if text == "/start" or text == "ℹ️ Помощь":
                    send_message(chat_id, help_text())

                elif text == "📋 Задачи":
                    send_message(
                        chat_id,
                        "📋 Задачи\n\n"
                        "/add Купить продукты\n"
                        "/add Позвонить клиенту сегодня 18:00\n"
                        "/add Проверить оплату завтра 10:00\n"
                        "/tasks\n"
                        "/done 1\n"
                        "/delete 1\n"
                        "/report\n"
                        "/clear"
                    )

                elif text == "📝 Заметки":
                    send_message(
                        chat_id,
                        "📝 Заметки\n\n"
                        "/note Купить домен\n"
                        "/notes\n"
                        "/delnote 1"
                    )

                elif text == "👥 CRM":
                    send_message(
                        chat_id,
                        "👥 CRM\n\n"
                        "/client Иван\n"
                        "/deal Иван 500 сайт\n"
                        "/clients"
                    )

                elif text == "💰 Финансы":
                    send_message(
                        chat_id,
                        "💰 Финансы\n\n"
                        "/income 1000 клиент\n"
                        "/spent 50 кофе\n"
                        "/finance"
                    )

                elif text == "🤖 AI Помощник":
                    send_message(
                        chat_id,
                        "🤖 Напиши вопрос обычным сообщением.\n\n"
                        "Например:\n"
                        "Как найти клиентов для Telegram-ботов?"
                    )
                elif text == "📈 Dashboard":
                    total_tasks = len(tasks)
                    done_tasks = len([t for t in tasks if t.get("done")])
                    active_tasks = total_tasks - done_tasks

                    total_clients = len(clients)

                    deals_count = 0
                    deals_sum = 0

                    for client in clients:
                        client_deals = client.get("deals", [])
                        deals_count += len(client_deals)
                        deals_sum += sum(deal.get("amount", 0) for deal in client_deals)

                    income = sum(item.get("amount", 0) for item in finance if item.get("type") == "income")
                    spent = sum(item.get("amount", 0) for item in finance if item.get("type") == "spent")
                    balance = income - spent

                    next_task = "Нет активных задач"

                    for task in tasks:
                        if not task.get("done"):
                            next_task = task.get("text", "Без названия")
                            break

                    result = (
                        "📈 Biz Dashboard\n\n"
                        f"📋 Задачи: {total_tasks}\n"
                        f"✅ Выполнено: {done_tasks}\n"
                        f"🔥 Активные: {active_tasks}\n\n"
                        f"👥 Клиенты: {total_clients}\n"
                        f"🤝 Сделки: {deals_count}\n"
                        f"💼 Потенциал сделок: {deals_sum}\n\n"
                        f"💵 Доходы: {income}\n"
                        f"📉 Расходы: {spent}\n"
                        f"🏦 Баланс: {balance}\n\n"
                        f"🎯 Главный фокус:\n{next_task}"
                    )

                    send_message(chat_id, result)
                    
                elif text == "📊 Biz Director" or text == "/agent":
                    send_message(chat_id, "📊 Анализирую твои данные...")
                    result = biz_agent(chat_id, data)
                    send_message(chat_id, result)                
                                 
                elif text.startswith("/ask "):
                    prompt = text.replace("/ask ", "", 1).strip()

                    if not prompt:
                        send_message(chat_id, "Напиши так:\n/ask Как найти клиентов?")
                        continue

                    send_message(chat_id, "🧠 Думаю...")
                    answer = ask_gpt(chat_id, prompt, data)
                    send_message(chat_id, answer)

                elif text.startswith("/add "):
                    task_raw = text.replace("/add ", "", 1).strip()

                    if not task_raw:
                        send_message(chat_id, "Напиши так:\n/add Купить продукты")
                        continue

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
                            status = "✅" if task.get("done") else "⬜"
                            reminder = ""

                            if task.get("reminder_at"):
                                reminder_time = datetime.fromisoformat(task["reminder_at"])
                                reminder = f" 🔔 {reminder_time.strftime('%d.%m %H:%M')}"

                            result += f"{i}. {status} {task['text']}{reminder}\n"

                        send_message(chat_id, result)

                elif text.startswith("/done "):
                    try:
                        number = int(text.replace("/done ", "", 1).strip())

                        if 1 <= number <= len(tasks):
                            tasks[number - 1]["done"] = True
                            save_data(data)

                            send_message(
                                chat_id,
                                f"✅ Задача выполнена:\n{tasks[number - 1]['text']}"
                            )
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

                            send_message(
                                chat_id,
                                f"🗑 Задача удалена:\n{deleted['text']}"
                            )
                        else:
                            send_message(chat_id, "Такой задачи нет.")

                    except Exception:
                        send_message(chat_id, "Напиши так:\n/delete 1")

                elif text == "/report":
                    total = len(tasks)
                    done = len([task for task in tasks if task.get("done")])
                    active = total - done

                    send_message(
                        chat_id,
                        f"📈 Итог дня:\n\n"
                        f"Всего задач: {total}\n"
                        f"Выполнено: {done}\n"
                        f"Осталось: {active}"
                    )

                elif text == "/clear":
                    data["tasks"][str(chat_id)] = []
                    save_data(data)
                    send_message(chat_id, "🗑 Все задачи очищены.")

                elif text.startswith("/note "):
                    note_text = text.replace("/note ", "", 1).strip()

                    if not note_text:
                        send_message(chat_id, "Напиши так:\n/note Купить домен")
                        continue

                    notes.append({
                        "text": note_text,
                        "created_at": now().isoformat()
                    })

                    save_data(data)
                    send_message(chat_id, f"📝 Заметка сохранена:\n{note_text}")

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

                    if not name:
                        send_message(chat_id, "Напиши так:\n/client Иван")
                        continue

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
                            deals = client.get("deals", [])
                            deals_sum = sum(deal.get("amount", 0) for deal in deals)

                            result += (
                                f"{i}. {client['name']} — "
                                f"сделок: {len(deals)}, сумма: {deals_sum}\n"
                            )

                        send_message(chat_id, result)
                elif text.startswith("/status "):
                    raw = text.replace("/status ", "", 1).strip()

                    parts = raw.split(maxsplit=1)

                    if len(parts) < 2:
                       send_message(chat_id, "Напиши так:\n/status Иван Оплатил")
                       continue

                    name = parts[0]
                    status = parts[1]

                    found = False

                    for client in clients:
                        if client["name"].lower() == name.lower():
                           client["status"] = status
                           found = True
                           break

                    if found:
                        save_data(data)
                        send_message(chat_id, f"✅ Статус клиента обновлен:\n{name} → {status}")
                    else:
                        send_message(chat_id, "Клиент не найден.")
                elif text == "/pipeline":
                    if not clients:
                        send_message(chat_id, "📭 Клиентов пока нет.")
                        continue

                    result = "📊 Воронка продаж\n\n"
                    groups = {}

                    for client in clients:
                        status = client.get("status", "Новый")

                        if status not in groups:
                            groups[status] = []

                        groups[status].append(client["name"])

                    for status, names in groups.items():
                        result += f"📌 {status} ({len(names)})\n"

                        for name in names:
                            result += f"• {name}\n"

                        result += "\n"

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

                    for item in clients:
                        if item["name"].lower() == name.lower():
                            client = item
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

                    send_message(
                        chat_id,
                        f"💼 Сделка добавлена:\n{name} — {amount}\n{description}"
                    )

                elif text.startswith("/spent "):
                    raw = text.replace("/spent ", "", 1).strip()
                    parts = raw.split()

                    if not parts:
                        send_message(chat_id, "Напиши так:\n/spent 50 кофе")
                        continue

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

                    if not parts:
                        send_message(chat_id, "Напиши так:\n/income 1000 клиент")
                        continue

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
                    income = sum(
                        item.get("amount", 0)
                        for item in finance
                        if item.get("type") == "income"
                    )

                    spent = sum(
                        item.get("amount", 0)
                        for item in finance
                        if item.get("type") == "spent"
                    )

                    balance = income - spent

                    send_message(
                        chat_id,
                        f"💰 Финансы:\n\n"
                        f"Доходы: {income}\n"
                        f"Расходы: {spent}\n"
                        f"Баланс: {balance}"
                    )
                elif text == "/dashboard":
                    total_tasks = len(tasks)
                    done_tasks = len([t for t in tasks if t.get("done")])
                    active_tasks = total_tasks - done_tasks

                    total_clients = len(clients)

                    deals_count = 0
                    deals_sum = 0

                    for client in clients:
                        client_deals = client.get("deals", [])
                        deals_count += len(client_deals)
                        deals_sum += sum(deal.get("amount", 0) for deal in client_deals)

                    income = sum(
                        item.get("amount", 0)
                        for item in finance
                        if item.get("type") == "income"
                    )

                    spent = sum(
                        item.get("amount", 0)
                        for item in finance
                        if item.get("type") == "spent"
                    )

                    balance = income - spent

                    next_task = "Нет активных задач"

                    for task in tasks:
                        if not task.get("done"):
                            next_task = task.get("text", "Без названия")
                            break

                    result = (
                        "📈 Biz Dashboard\n\n"
                        f"📋 Задачи: {total_tasks}\n"
                        f"✅ Выполнено: {done_tasks}\n"
                        f"🔥 Активные: {active_tasks}\n\n"
                        f"👥 Клиенты: {total_clients}\n"
                        f"🤝 Сделки: {deals_count}\n"
                        f"💼 Потенциал сделок: {deals_sum}\n\n"
                        f"💵 Доходы: {income}\n"
                        f"📉 Расходы: {spent}\n"
                        f"🏦 Баланс: {balance}\n\n"
                        f"🎯 Главный фокус:\n{next_task}"
                    )

                    send_message(chat_id, result)
                else:
                    send_message(chat_id, "🧠 Думаю...")
                    answer = ask_gpt(chat_id, text, data)
                    send_message(chat_id, answer)

                save_data(data)

        except Exception as e:
            print("Error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
