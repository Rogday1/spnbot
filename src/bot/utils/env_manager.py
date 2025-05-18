import os
import logging
from pathlib import Path
from typing import List, Optional
import re

from src.config import settings

def get_env_file_path() -> Path:
    """
    Получает путь к .env файлу.
    
    Returns:
        Path: Путь к .env файлу
    """
    return Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))) / '.env'

def read_env_file() -> str:
    """
    Читает содержимое .env файла.
    
    Returns:
        str: Содержимое .env файла или пустая строка в случае ошибки
    """
    try:
        env_path = get_env_file_path()
        if not env_path.exists():
            logging.warning(f"Файл .env не найден по пути {env_path}")
            return ""
            
        with open(env_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Ошибка при чтении .env файла: {e}")
        return ""

def write_env_file(content: str) -> bool:
    """
    Записывает содержимое в .env файл.
    
    Args:
        content (str): Новое содержимое .env файла
        
    Returns:
        bool: True если запись прошла успешно, иначе False
    """
    try:
        env_path = get_env_file_path()
        # Создаем резервную копию перед изменением
        if env_path.exists():
            backup_path = env_path.with_suffix('.env.bak')
            with open(env_path, 'r', encoding='utf-8') as src, open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            logging.info(f"Создана резервная копия .env файла: {backup_path}")
            
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"Файл .env успешно обновлен")
        return True
    except Exception as e:
        logging.error(f"Ошибка при записи в .env файл: {e}")
        return False

def add_channel_to_required(channel_id: str, channel_title: Optional[str] = None) -> bool:
    """
    Добавляет канал в список REQUIRED_CHANNELS в .env файле.
    
    Args:
        channel_id (str): ID или юзернейм канала (например, @channel или -10012345678)
        channel_title (Optional[str]): Название канала (для логов)
        
    Returns:
        bool: True если канал успешно добавлен, иначе False
    """
    try:
        # Нормализуем ID канала
        if channel_id.startswith('https://t.me/'):
            channel_id = '@' + channel_id.split('/')[-1]
        elif channel_id.startswith('t.me/'):
            channel_id = '@' + channel_id.split('/')[-1]
        elif channel_id.startswith('-100'):
            # Если это числовой ID, оставляем как есть
            pass
        elif not channel_id.startswith('@'):
            channel_id = '@' + channel_id
            
        # Получаем текущий список каналов
        current_channels = settings.REQUIRED_CHANNELS
        
        # Проверяем, есть ли уже этот канал в списке
        if channel_id in current_channels:
            logging.warning(f"Канал {channel_id} уже есть в списке обязательных подписок")
            return False
            
        # Добавляем канал в список
        new_channels = current_channels + [channel_id]
        
        # Обновляем .env файл
        env_content = read_env_file()
        required_channels_pattern = r'^REQUIRED_CHANNELS=(.*)$'
        
        # Если переменная REQUIRED_CHANNELS уже есть в .env
        if re.search(required_channels_pattern, env_content, re.MULTILINE):
            # Заменяем значение
            new_content = re.sub(
                required_channels_pattern,
                f'REQUIRED_CHANNELS={",".join(new_channels)}',
                env_content,
                flags=re.MULTILINE
            )
        else:
            # Добавляем новую переменную
            new_content = env_content.rstrip() + f'\nREQUIRED_CHANNELS={",".join(new_channels)}\n'
            
        # Записываем обновленное содержимое
        if write_env_file(new_content):
            # Обновляем переменную в текущем сеансе
            os.environ['REQUIRED_CHANNELS'] = ','.join(new_channels)
            # Обновляем настройки
            settings.REQUIRED_CHANNELS = new_channels
            
            channel_info = f"{channel_id} ({channel_title})" if channel_title else channel_id
            logging.info(f"Канал {channel_info} успешно добавлен в список обязательных подписок")
            return True
        else:
            return False
            
    except Exception as e:
        logging.error(f"Ошибка при добавлении канала {channel_id} в список обязательных подписок: {e}")
        return False

def remove_channel_from_required(channel_id: str) -> bool:
    """
    Удаляет канал из списка REQUIRED_CHANNELS в .env файле.
    
    Args:
        channel_id (str): ID или юзернейм канала (например, @channel или -10012345678)
        
    Returns:
        bool: True если канал успешно удален, иначе False
    """
    try:
        # Нормализуем ID канала
        if channel_id.startswith('https://t.me/'):
            channel_id = '@' + channel_id.split('/')[-1]
        elif channel_id.startswith('t.me/'):
            channel_id = '@' + channel_id.split('/')[-1]
        elif channel_id.startswith('-100'):
            # Если это числовой ID, оставляем как есть
            pass
        elif not channel_id.startswith('@'):
            channel_id = '@' + channel_id
            
        # Получаем текущий список каналов
        current_channels = settings.REQUIRED_CHANNELS
        
        # Проверяем, есть ли канал в списке
        if channel_id not in current_channels:
            logging.warning(f"Канал {channel_id} не найден в списке обязательных подписок")
            return False
            
        # Удаляем канал из списка
        new_channels = [ch for ch in current_channels if ch != channel_id]
        
        # Обновляем .env файл
        env_content = read_env_file()
        required_channels_pattern = r'^REQUIRED_CHANNELS=(.*)$'
        
        # Заменяем значение
        new_content = re.sub(
            required_channels_pattern,
            f'REQUIRED_CHANNELS={",".join(new_channels)}' if new_channels else 'REQUIRED_CHANNELS=',
            env_content,
            flags=re.MULTILINE
        )
            
        # Записываем обновленное содержимое
        if write_env_file(new_content):
            # Обновляем переменную в текущем сеансе
            os.environ['REQUIRED_CHANNELS'] = ','.join(new_channels)
            # Обновляем настройки
            settings.REQUIRED_CHANNELS = new_channels
            
            logging.info(f"Канал {channel_id} успешно удален из списка обязательных подписок")
            return True
        else:
            return False
            
    except Exception as e:
        logging.error(f"Ошибка при удалении канала {channel_id} из списка обязательных подписок: {e}")
        return False

def get_required_channels() -> List[str]:
    """
    Получает список обязательных каналов для подписки.
    
    Returns:
        List[str]: Список ID каналов
    """
    return settings.REQUIRED_CHANNELS

def set_max_win_per_day(max_win: int) -> bool:
    """
    Устанавливает максимальный выигрыш за сутки в .env файле.
    
    Args:
        max_win (int): Максимальный выигрыш
        
    Returns:
        bool: True если значение успешно установлено, иначе False
    """
    try:
        if max_win <= 0:
            logging.error("Максимальный выигрыш должен быть положительным числом")
            return False
            
        # Обновляем .env файл
        env_content = read_env_file()
        max_win_pattern = r'^MAX_WIN_PER_DAY=(.*)$'
        
        # Если переменная MAX_WIN_PER_DAY уже есть в .env
        if re.search(max_win_pattern, env_content, re.MULTILINE):
            # Заменяем значение
            new_content = re.sub(
                max_win_pattern,
                f'MAX_WIN_PER_DAY={max_win}',
                env_content,
                flags=re.MULTILINE
            )
        else:
            # Добавляем новую переменную
            new_content = env_content.rstrip() + f'\nMAX_WIN_PER_DAY={max_win}\n'
            
        # Записываем обновленное содержимое
        if write_env_file(new_content):
            # Обновляем переменную в текущем сеансе
            os.environ['MAX_WIN_PER_DAY'] = str(max_win)
            
            # Добавляем значение в настройки, если его там еще нет
            if not hasattr(settings, 'MAX_WIN_PER_DAY'):
                setattr(settings, 'MAX_WIN_PER_DAY', max_win)
            else:
                settings.MAX_WIN_PER_DAY = max_win
                
            logging.info(f"Максимальный выигрыш за сутки установлен: {max_win}")
            return True
        else:
            return False
            
    except Exception as e:
        logging.error(f"Ошибка при установке максимального выигрыша за сутки: {e}")
        return False

def get_max_win_per_day() -> int:
    """
    Получает максимальный выигрыш за сутки из настроек.
    
    Returns:
        int: Максимальный выигрыш за сутки или 5000 по умолчанию
    """
    default_value = 5000  # Значение по умолчанию
    
    try:
        # Проверяем, есть ли переменная в настройках
        if hasattr(settings, 'MAX_WIN_PER_DAY'):
            return int(settings.MAX_WIN_PER_DAY)
            
        # Проверяем, есть ли переменная в окружении
        max_win_str = os.getenv('MAX_WIN_PER_DAY')
        if max_win_str:
            try:
                return int(max_win_str)
            except ValueError:
                logging.error(f"Некорректное значение MAX_WIN_PER_DAY в переменных окружения: {max_win_str}")
                
        return default_value
    except Exception as e:
        logging.error(f"Ошибка при получении максимального выигрыша за сутки: {e}")
        return default_value 