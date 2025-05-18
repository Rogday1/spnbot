import logging
from typing import Any, Dict, Optional, Union

def format_log_message(message: str, extra: Optional[Dict[str, Any]] = None) -> str:
    """
    Форматирует сообщение для логирования с дополнительными параметрами.
    
    Args:
        message (str): Основное сообщение
        extra (Optional[Dict[str, Any]]): Дополнительные параметры
        
    Returns:
        str: Отформатированное сообщение для лога
    """
    if extra:
        return f"{message} | {' | '.join([f'{k}={v}' for k, v in extra.items()])}"
    return message

def safe_get(data: Dict[str, Any], keys: Union[str, list], default: Any = None) -> Any:
    """
    Безопасно извлекает значение из вложенного словаря.
    
    Args:
        data (Dict[str, Any]): Исходный словарь
        keys (Union[str, list]): Ключ или список ключей для доступа к вложенным словарям
        default (Any): Значение по умолчанию, если ключ не найден
        
    Returns:
        Any: Извлеченное значение или значение по умолчанию
    """
    if isinstance(keys, str):
        return data.get(keys, default)
    
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    
    return current
