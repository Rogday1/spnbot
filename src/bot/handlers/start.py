from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
import logging
import re
import time
import os
from aiogram.filters.command import CommandObject

from ..keyboards.inline import get_start_keyboard, get_subscription_keyboard
from ..utils.subscription import check_all_subscriptions
from src.config import settings
from src.database.repositories.user_repository import UserRepository
from src.database.db import get_session

# Создаем роутер только для обработки команд start и других общих сообщений
# Явно указываем имя роутера
router = Router(name="start_commands")

def escape_markdown(text):
    """
    Экранирование специальных символов для MarkdownV2.
    
    Args:
        text (str): Исходный текст
        
    Returns:
        str: Текст с экранированными спецсимволами
    """
    # Символы, которые нужно экранировать в MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    
    # Заменяем каждый специальный символ на экранированный вариант
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# Обработчик ТОЛЬКО команды /start
@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    """
    Обработчик команды /start.
    Проверяет подписку на обязательные каналы, отправляет приветственное сообщение.
    Также обрабатывает реферальную ссылку, если она есть.
    """
    logging.info(f"Получена команда /start от пользователя {message.from_user.id}")
    
    # Обработка реферальной ссылки (аргумента команды)
    arg = command.args
    user_id = message.from_user.id
    
    # Проверяем, есть ли у нас реферальный код
    if arg and arg.startswith('ref'):
        try:
            # Извлекаем ID реферера из аргумента
            referrer_id = int(arg[3:]) # убираем 'ref' из начала строки
            
            # Если ID не совпадает с текущим пользователем
            if referrer_id != user_id:
                logging.info(f"Пользователь {user_id} пришел по реферальной ссылке от пользователя {referrer_id}")
                
                # Создаем сессию и репозиторий для работы с БД
                async for session in get_session():
                    user_repo = UserRepository(session)
                    
                    # Проверяем, существует ли реферер
                    referrer = await user_repo.get_user(referrer_id)
                    
                    if referrer:
                        # Увеличиваем счетчик рефералов у реферера
                        current_refs = getattr(referrer, 'referral_count', 0)
                        
                        # Обновляем информацию о реферере (счетчик и добавляем билет)
                        await user_repo.update_user_batch(referrer_id, {
                            'referral_count': current_refs + 1,
                            'tickets': referrer.tickets + 1
                        })
                        
                        logging.info(f"Пользователю {referrer_id} начислен 1 билет за приглашение пользователя {user_id}")
                        
                        # Также сохраняем информацию о том, кто пригласил текущего пользователя
                        current_user = await user_repo.get_user(user_id)
                        if current_user and not current_user.referred_by:
                            await user_repo.update_user_batch(user_id, {'referred_by': referrer_id})
            else:
                logging.info(f"Пользователь {user_id} пытается использовать собственную реферальную ссылку")
        except (ValueError, Exception) as e:
            logging.error(f"Ошибка при обработке реферальной ссылки: {e}")
    
    # Проверяем подписку пользователя на обязательные каналы
    if settings.REQUIRED_CHANNELS:
        logging.info(f"Проверка подписок пользователя {user_id} на каналы")
        all_subscribed, channels_info = await check_all_subscriptions(message.bot, user_id)
        
        # Если пользователь не подписан на все каналы, отправляем требование подписаться
        if not all_subscribed:
            logging.info(f"Пользователь {user_id} не подписан на все обязательные каналы")
            text = (
                "⚠️ Для доступа к боту необходимо подписаться на все каналы ниже.\n\n"
                "После подписки нажмите кнопку \"🔄 Проверить подписки\"."
            )
            
            # Отправляем сообщение с кнопками подписки
            await message.answer(
                text=text,
                parse_mode=None,  # Отключаем парсинг разметки
                reply_markup=get_subscription_keyboard(channels_info)
            )
            return
    
    # Если пользователь подписан на все каналы или проверка не требуется, отправляем приветственное сообщение
    await send_welcome_message(message)

async def send_welcome_message(message: Message):
    """
    Отправляет приветственное сообщение с клавиатурой.
    
    Args:
        message (Message): Сообщение пользователя
    """
    # Получаем имя пользователя
    user_name = message.from_user.first_name
    
    # Приветственное сообщение без MarkdownV2 форматирования
    welcome_text = (
        f"👋 Привет, {user_name}!\n\n"
        f"Добро пожаловать в Spin Bot. "
        f"Здесь ты можешь играть и пополнять свой баланс.\n\n"
        f"Выбери действие из меню ниже:"
    )
    
    # Отправляем сообщение с клавиатурой
    logging.info("Отправляем приветственное сообщение...")
    await message.answer(
        text=welcome_text,
        parse_mode=None,  # Отключаем парсинг разметки
        reply_markup=get_start_keyboard()
    )
    
    logging.info(f"Пользователь {message.from_user.id} запустил бота, сообщение отправлено")

# Добавим также простой обработчик текстовых сообщений для проверки работы бота
# Указываем что этот обработчик НЕ должен обрабатывать команды
@router.message(~F.text.startswith('/'))
async def echo_message(message: Message):
    """
    Простой обработчик для эхо-ответа на сообщения.
    Нужен для проверки работы бота.
    
    Обрабатывает только сообщения без команд (не начинающиеся с "/").
    """
    logging.info(f"Получено текстовое сообщение от пользователя {message.from_user.id}: {message.text}")
    
    await message.answer(
        f"Вы отправили: {message.text}",
        parse_mode=None
    )
    
    logging.info("Эхо-ответ отправлен")

@router.callback_query(F.data == "get_referral_link")
async def process_referral_link(callback: CallbackQuery):
    """
    Обработчик нажатия на кнопку "Реферальная ссылка".
    Отправляет пользователю его реферальную ссылку.
    """
    logging.info(f"Получен callback_query 'get_referral_link' от пользователя {callback.from_user.id}")
    
    user_id = callback.from_user.id
    bot_username = (await callback.bot.get_me()).username
    
    # Создаем реферальную ссылку
    referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
    
    # Отвечаем на колбэк
    await callback.answer()
    
    # Отправляем сообщение с реферальной ссылкой без разметки
    await callback.message.answer(
        text=f"🔗 Твоя реферальная ссылка:\n\n{referral_link}\n\n"
             f"Поделись ею с друзьями и получи +1 билет за каждого приглашенного пользователя!",
        parse_mode=None,
        disable_web_page_preview=True
    )
    
    logging.info(f"Пользователь {user_id} запросил реферальную ссылку, ссылка отправлена")

@router.callback_query(F.data == "game_unavailable")
async def process_game_unavailable(callback: CallbackQuery):
    """
    Обработчик нажатия на кнопку игры, когда она недоступна.
    """
    logging.info(f"Пользователь {callback.from_user.id} нажал на кнопку недоступной игры")
    
    # Диагностика URL
    env_url = os.environ.get('WEBAPP_PUBLIC_URL', 'Не задан')
    settings_url = settings.WEBAPP_PUBLIC_URL if hasattr(settings, 'WEBAPP_PUBLIC_URL') else 'Не доступен'
    
    # Проверяем наличие файла .env
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), '.env')
    env_exists = os.path.exists(env_path)
    
    # Проверяем содержимое .env
    env_content = "Не удалось прочитать"
    if env_exists:
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
                env_content = '\n'.join([line for line in env_lines if 'WEBAPP_PUBLIC_URL' in line])
        except Exception as e:
            env_content = f"Ошибка чтения: {e}"
    
    # Формируем сообщение диагностики без экранирования
    diagnostic_text = (
        f"🔍 Диагностика URL\n\n"
        f"• Файл .env: {'✅ Найден' if env_exists else '❌ Не найден'}\n"
        f"• В файле .env: {env_content}\n"
        f"• В переменной окружения: {env_url}\n"
        f"• В настройках приложения: {settings_url}\n\n"
        f"📋 Инструкция:\n"
        f"1. Запустите сервис туннелирования:\n"
        f"   lt --port 8000\n\n"
        f"2. Скопируйте полученный URL в файл .env:\n"
        f"   WEBAPP_PUBLIC_URL=https://ваш-url-здесь\n\n"
        f"3. Важно: URL должен начинаться с https://\n\n"
        f"4. Перезапустите бота"
    )
    
    # Отвечаем на callback
    await callback.answer("Для запуска мини-приложения требуется корректный HTTPS URL")
    
    # Отправляем сообщение с диагностикой без разметки
    await callback.message.answer(
        text=diagnostic_text,
        parse_mode=None
    )
    
    logging.info(f"Отправлена диагностика URL. Текущий URL: {env_url}")

@router.callback_query(F.data == "open_game")
async def process_open_game(callback: CallbackQuery):
    """
    Обработчик нажатия на кнопку "Открыть игру".
    Проверяет подписку на обязательные каналы и запускает игру.
    """
    # Этот обработчик больше не нужен, так как теперь используем WebApp напрямую
    # Сохраняем его для обратной совместимости со старыми сообщениями
    logging.info(f"Пользователь {callback.from_user.id} нажал устаревшую кнопку 'Открыть игру'")
    
    # Проверяем подписку на обязательные каналы
    if settings.REQUIRED_CHANNELS:
        all_subscribed, channels_info = await check_all_subscriptions(callback.bot, callback.from_user.id)
        
        if not all_subscribed:
            logging.info(f"Пользователь {callback.from_user.id} не подписан на все обязательные каналы")
            
            # Отправляем сообщение с требованием подписаться
            text = (
                "⚠️ Для доступа к игре необходимо подписаться на все каналы ниже.\n\n"
                "После подписки нажмите кнопку \"🔄 Проверить подписки\"."
            )
            
            # Отправляем сообщение с кнопками подписки
            await callback.message.answer(
                text=text,
                parse_mode=None,  # Отключаем парсинг разметки
                reply_markup=get_subscription_keyboard(channels_info)
            )
            
            # Отвечаем на callback
            await callback.answer("Требуется подписка на обязательные каналы")
            return
    
    # Если подписан или проверка не требуется - отправляем новое сообщение с корректной клавиатурой
    await callback.answer("Открываем игру!")
    await send_welcome_message(callback.message)

@router.callback_query(F.data == "check_subscriptions")
async def process_check_subscriptions(callback: CallbackQuery):
    """
    Обработчик нажатия на кнопку "Проверить подписки".
    Проверяет подписку пользователя, удаляет текущее сообщение и 
    при успехе отправляет стартовое меню.
    """
    user_id = callback.from_user.id
    bot = callback.bot
    
    # Проверяем подписки
    all_subscribed, channels_info = await check_all_subscriptions(bot, user_id)
    
    if all_subscribed:
        # Если пользователь подписан на все каналы, удаляем текущее сообщение с кнопками подписки
        await callback.answer("✅ Все подписки проверены! Доступ открыт!", show_alert=True)
        
        try:
            # Удаляем сообщение с требованием подписаться
            await callback.message.delete()
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения: {e}")
        
        # Отправляем новое стартовое сообщение
        # Получаем имя пользователя
        user_name = callback.from_user.first_name
        
        # Приветственное сообщение без MarkdownV2 форматирования
        welcome_text = (
            f"👋 Привет, {user_name}!\n\n"
            f"Спасибо за подписку! Теперь у тебя есть доступ к боту.\n\n"
            f"Выбери действие из меню ниже:"
        )
        
        # Отправляем сообщение с основной клавиатурой
        await callback.message.answer(
            text=welcome_text,
            parse_mode=None,  # Отключаем парсинг разметки
            reply_markup=get_start_keyboard()
        )
    else:
        # Если не подписан на все каналы, показываем обновленное меню подписок
        await callback.answer("⚠️ Вы подписаны не на все каналы", show_alert=True)
        
        # Получаем текущий текст и разметку
        current_text = callback.message.text
        current_markup = callback.message.reply_markup
        
        # Создаем новый текст и разметку для обновления
        new_text = (
            "⚠️ Для доступа к боту необходимо подписаться на все каналы ниже.\n\n"
            "После подписки нажмите кнопку \"🔄 Проверить подписки\"."
        )
        new_markup = get_subscription_keyboard(channels_info)
        
        # Проверяем, изменилась ли информация о подписках
        try:
            # Проверяем, различаются ли текущая и новая клавиатуры
            if current_text != new_text or str(current_markup) != str(new_markup):
                # Обновляем сообщение только если данные изменились
                await callback.message.edit_text(
                    text=new_text,
                    parse_mode=None,  # Отключаем парсинг разметки
                    reply_markup=new_markup
                )
            else:
                # Просто отвечаем на callback без изменения сообщения
                logging.info("Информация о подписках не изменилась, пропускаем обновление сообщения")
        except Exception as e:
            logging.error(f"Ошибка при обновлении сообщения: {e}")
            # Отправляем новое сообщение вместо редактирования
            await callback.message.answer(
                text=new_text,
                parse_mode=None,  # Отключаем парсинг разметки
                reply_markup=new_markup
            )

@router.callback_query(F.data == "back_to_main_menu")
async def process_back_to_main_menu(callback: CallbackQuery):
    """
    Обработчик нажатия на кнопку "Назад".
    Показывает основное меню.
    """
    # Получаем имя пользователя
    user_name = callback.from_user.first_name
    
    # Приветственное сообщение без MarkdownV2 форматирования
    welcome_text = (
        f"👋 Привет, {user_name}!\n\n"
        f"Добро пожаловать в Spin Bot. "
        f"Здесь ты можешь играть и пополнять свой баланс.\n\n"
        f"Выбери действие из меню ниже:"
    )
    
    # Отправляем сообщение с основной клавиатурой
    await callback.message.edit_text(
        text=welcome_text,
        parse_mode=None,  # Отключаем парсинг разметки
        reply_markup=get_start_keyboard()
    )
    
    await callback.answer() 