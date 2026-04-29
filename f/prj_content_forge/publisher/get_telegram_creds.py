"""
Выводит credentials для локального использования.
"""
import wmill
import json

telegram_client_api = wmill.get_resource("u/theatmacreator/telegram_client_api")

print("CREDENTIALS:")
print(f"API_ID={telegram_client_api['api_id']}")
print(f"API_HASH={telegram_client_api['api_hash']}")
print(f"PHONE={telegram_client_api['phone']}")
