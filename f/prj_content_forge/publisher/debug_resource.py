"""
Проверяет содержимое ресурса telegram_client_api
"""
import wmill

def main() -> dict:
    """Отладка ресурса"""
    telegram_client_api = wmill.get_resource("u/theatmacreator/telegram_client_api")
    
    result = {
        "keys": list(telegram_client_api.keys()),
        "api_id": telegram_client_api.get('api_id'),
        "phone": telegram_client_api.get('phone'),
        "has_session_data": 'session_data' in telegram_client_api,
    }
    
    if 'session_data' in telegram_client_api:
        session_data = telegram_client_api['session_data']
        result['session_length'] = len(session_data)
        result['session_start'] = session_data[:100] if session_data else None
    else:
        result['error'] = "session_data not found in resource"
    
    return result
