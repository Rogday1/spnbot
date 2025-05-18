from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging
import os

from src.config import settings

def get_start_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт инлайн клавиатуру для стартового сообщения.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками "Открыть игру" и "Реферальная ссылка"
    """
    builder = InlineKeyboardBuilder()
    
    # Получаем URL для веб-приложения
    # Приоритет: 1. Переменная окружения 2. Настройки в settings
    game_url = os.environ.get('WEBAPP_PUBLIC_URL', '')
    
    # Если URL получен из переменной окружения, добавляем /game
    if game_url and game_url.strip():
        game_url = game_url.strip().rstrip('/')
        game_url = f"{game_url}/game"
    else:
        # Если в переменной окружения нет URL, проверяем в настройках
        try:
            if hasattr(settings, 'WEBAPP_PUBLIC_URL') and settings.WEBAPP_PUBLIC_URL:
                game_url = settings.WEBAPP_PUBLIC_URL.strip().rstrip('/')
                game_url = f"{game_url}/game"
                logging.info(f"URL получен из настроек: {game_url}")
            else:
                logging.error("URL для WebApp не найден в настройках и переменных окружения")
                game_url = ""
        except Exception as e:
            logging.error(f"Ошибка при получении URL из настроек: {e}")
            game_url = ""
    
    # Для отладки выведем URL
    logging.info(f"URL для WebApp: {game_url}")
    
    # Проверяем, что URL начинается с https://
    if not game_url or not game_url.startswith("https://"):
        logging.error(f"❌ ОШИБКА: URL должен начинаться с https://, получен: {game_url}")
        
        # В режиме отладки всё равно создаем кнопку для тестирования
        logging.warning(f"⚠️ Создание кнопки с неправильным URL для тестирования: {game_url}")
        
        # Используем callback_data вместо WebApp, чтобы показать ошибку
        builder.add(InlineKeyboardButton(
            text="🎮 Открыть игру",
            callback_data="game_unavailable"
        ))
    else:
        # URL корректен, создаем кнопку WebApp
        logging.info(f"✅ Создание WebApp кнопки с URL: {game_url}")
        builder.add(InlineKeyboardButton(
            text="🎮 Открыть игру",
            web_app=WebAppInfo(url=game_url)
        ))
    
    # Кнопка "Реферальная ссылка"
    builder.add(InlineKeyboardButton(
        text="🔗 Реферальная ссылка",
        callback_data="get_referral_link"
    ))
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup() 

def get_subscription_keyboard(channels_info: list) -> InlineKeyboardMarkup:
    """
    Создаёт инлайн клавиатуру с кнопками для подписки на каналы и кнопкой проверки.
    
    Args:
        channels_info (list): Список словарей с информацией о каналах
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками подписки и проверки
    """
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для каждого канала
    for channel in channels_info:
        # Получаем ссылку на канал
        channel_link = channel.get('invite_link')
        if not channel_link and channel.get('username'):
            channel_link = f"https://t.me/{channel['username']}"
        
        if not channel_link:
            continue
            
        # Добавляем маркер статуса подписки
        status = "✅" if channel.get('is_subscribed', False) else "❌"
        
        # Создаем кнопку с названием канала
        builder.add(InlineKeyboardButton(
            text=f"{status} {channel.get('title', 'Канал')}",
            url=channel_link
        ))
    
    # Кнопка для проверки подписок
    builder.add(InlineKeyboardButton(
        text="🔄 Проверить подписки",
        callback_data="check_subscriptions"
    ))
    
    # Кнопка "Вернуться назад"
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back_to_main_menu"
    ))
    
    # Размещаем кнопки в одну колонку
    builder.adjust(1)
    
    return builder.as_markup() 