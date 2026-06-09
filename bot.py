import os
import time
import requests

TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    requests.post(
        f"{API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )


def main():
    offset = 0

    while True:
        try:
            response = requests.get(
                f"{API_URL}/getUpdates",
                params={"offset": offset, "timeout": 30}
            )

            data = response.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "")

                if not chat_id:
                    continue

                if text == "/start":
                    send_message(
                        chat_id,
                        "👋 Biz Assistant работает!\n\n"
                        "Бот успешно запущен в Railway."
                    )
                else:
                    send_message(
                        chat_id,
                        "Я получил сообщение. Скоро добавим задачи и напоминания."
                    )

        except Exception as e:
            print("Error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
