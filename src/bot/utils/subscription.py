from aiogram import Bot
from aiogram.types import User as TelegramUser
import logging
from typing import List, Dict, Tuple, Any, Optional

from src.config import settings

async def get_chat_info(bot: Bot, channel_identifier: str) -> Optional[Dict[str, Any]]:
    """
    Получает информацию о канале по его идентификатору.
    
    Args:
        bot (Bot): Экземпляр бота
        channel_identifier (str): Идентификатор канала (@username или t.me/username)
        
    Returns:
        Optional[Dict[str, Any]]: Информация о канале или None в случае ошибки
    """
    try:
        # Нормализуем идентификатор канала
        if channel_identifier.startswith('https://t.me/'):
            channel_identifier = '@' + channel_identifier.split('/')[-1]
        elif channel_identifier.startswith('t.me/'):
            channel_identifier = '@' + channel_identifier.split('/')[-1]
        elif not channel_identifier.startswith('@'):
            channel_identifier = '@' + channel_identifier
            
        # Получаем информацию о канале
        chat_info = await bot.get_chat(channel_identifier)
        return chat_info
    except Exception as e:
        logging.error(f"Ошибка при получении информации о канале {channel_identifier}: {e}")
        return None

async def check_user_subscription(bot: Bot, user_id: int, channel_identifier: str) -> bool:
    """
    Проверяет, подписан ли пользователь на указанный канал.
    
    Args:
        bot (Bot): Экземпляр бота
        user_id (int): ID пользователя
        channel_identifier (str): Идентификатор канала (@username или t.me/username)
        
    Returns:
        bool: True если пользователь подписан, иначе False
    """
    try:
        # Получаем информацию о канале
        chat_info = await get_chat_info(bot, channel_identifier)
        if not chat_info:
            logging.warning(f"Не удалось получить информацию о канале {channel_identifier}")
            return True  # В случае ошибки считаем, что пользователь подписан
            
        # Получаем статус пользователя в канале
        member = await bot.get_chat_member(chat_info.id, user_id)
        
        # Проверяем статус
        # Возможные статусы: 'creator', 'administrator', 'member', 'restricted', 'left', 'kicked'
        is_subscribed = member.status in ['creator', 'administrator', 'member', 'restricted']
        
        return is_subscribed
    except Exception as e:
        error_text = str(e).lower()
        # Проверяем типичные ошибки, которые могут возникнуть
        if "member list is inaccessible" in error_text:
            logging.warning(f"Бот не является администратором канала {channel_identifier} "
                           f"или не имеет прав на просмотр списка участников")
            return True  # Считаем пользователя подписанным
        elif "chat not found" in error_text:
            logging.warning(f"Канал {channel_identifier} не найден")
            return True  # Считаем пользователя подписанным
        elif "bot was kicked" in error_text:
            logging.warning(f"Бот был удален из канала {channel_identifier}")
            return True  # Считаем пользователя подписанным
        else:
            # Для других ошибок просто логируем и считаем, что пользователь подписан
            logging.error(f"Ошибка при проверке подписки пользователя {user_id} на канал {channel_identifier}: {e}")
            return True  # В случае ошибки считаем, что пользователь подписан

async def check_all_subscriptions(bot: Bot, user_id: int) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Проверяет подписку пользователя на все обязательные каналы.
    
    Args:
        bot (Bot): Экземпляр бота
        user_id (int): ID пользователя
        
    Returns:
        Tuple[bool, List[Dict[str, Any]]]: (все_подписки_активны, список_каналов_с_информацией)
    """
    # Если список обязательных каналов пуст, считаем что пользователь подписан на все
    if not settings.REQUIRED_CHANNELS:
        return True, []
        
    all_subscribed = True
    channels_info = []
    
    for channel_id in settings.REQUIRED_CHANNELS:
        try:
            # Получаем информацию о канале
            chat_info = await get_chat_info(bot, channel_id)
            if not chat_info:
                logging.warning(f"Не удалось получить информацию о канале {channel_id}")
                continue
                
            # Проверяем подписку
            is_subscribed = await check_user_subscription(bot, user_id, channel_id)
            
            # Добавляем информацию о канале в список
            channels_info.append({
                "chat_id": chat_info.id,
                "title": chat_info.title,
                "username": chat_info.username,
                "invite_link": chat_info.invite_link,
                "is_subscribed": is_subscribed
            })
            
            # Если хотя бы на один канал не подписан, результат будет False
            if not is_subscribed:
                all_subscribed = False
                
        except Exception as e:
            logging.error(f"Ошибка при проверке канала {channel_id}: {e}")
            continue
            
    return all_subscribed, channels_info 