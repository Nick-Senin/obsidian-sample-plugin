"""
Test script to fetch genre data from Baserow
"""
import wmill
import requests


def main() -> dict:
    """Получает данные из таблицы жанров Baserow."""
    baserow = wmill.get_resource("u/theatmacreator/baserow_api")

    # URL таблицы жанров (table/747)
    url = "https://content.nicksenin.com/api/database/rows/table/747/?user_field_names=true"

    headers = {
        "Authorization": f"Token {baserow['token']}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()
    return {"results": data.get("results", [])}
