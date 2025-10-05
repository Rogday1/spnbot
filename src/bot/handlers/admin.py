from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
import os
import re
import logging
import urllib.parse
from dotenv import load_dotenv

from src.bot.keyboards.admin import get_admin_keyboard, get_back_to_menu_keyboard
from src.bot.filters.admin import AdminFilter
from src.bot.keyboards.callback_data import AdminCallback
from src.bot.utils.env_manager import (
    add_channel_to_required, 
    get_required_channels, 
    remove_channel_from_required,
    set_max_win_per_day,
    get_max_win_per_day
)
from src.database.repositories.prize_repository import PrizeRepository
from src.database.db import get_session
from src.config import settings

# Загружаем переменные окружения
load_dotenv()

# Создаем роутер ТОЛЬКО для обработки команды admin
# Важно: задаем имя роутера и явный фильтр только для команды admin
router = Router(name="admin_commands")


# Вспомогательная функция для проверки прав администратора
async def check_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором
    
    Args:
        user_id (int): ID пользователя
        
    Returns:
        bool: True, если пользователь администратор
    """
    try:
        from src.database.db import get_session
        from src.database.repositories.user_repository import UserRepository
        
        async for session in get_session():
            user_repo = UserRepository(session)
            user = await user_repo.get_user(user_id)
            return user and user.is_admin
    except Exception as e:
        logging.error(f"Ошибка при проверке прав администратора: {e}")
        return False

# Этот обработчик должен срабатывать только на команду admin от админов
@router.message(Command("admin"), AdminFilter())
async def admin_command(message: Message):
    """Обработчик команды /admin"""
    logging.info(f"Вызвана административная панель пользователем {message.from_user.id}")
    await message.answer(
        "Панель администратора:",
        parse_mode=None,
        reply_markup=get_admin_keyboard()
    )


# ГЛАВНЫЙ обработчик для ВСЕХ admin callback
@router.callback_query(F.data.startswith("admin:"))
async def handle_admin_callbacks(callback: CallbackQuery):
    """Главный обработчик для всех admin callback"""
    logging.info(f"🎯 Получен admin callback: data={callback.data}, user={callback.from_user.id}")
    
    # Проверяем права администратора
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора!", show_alert=True)
        return
    
    # Парсим callback data
    try:
        logging.info(f"🎯 Пытаемся распарсить: {callback.data}")
        callback_data = AdminCallback.unpack(callback.data)
        action = callback_data.action
        value = callback_data.value
        logging.info(f"🎯 Распарсен callback: action={action}, value={value}")
    except Exception as e:
        logging.error(f"❌ Ошибка парсинга callback: {e}")
        import traceback
        logging.error(traceback.format_exc())
        await callback.answer("❌ Ошибка обработки запроса", show_alert=True)
        return
    
    # Обрабатываем разные действия
    logging.info(f"🎯 Обрабатываем действие: {action}")
    if action == "set_max_win":
        await set_max_win_handler(callback)
    elif action == "manage_prizes":
        await manage_prizes_handler(callback)
    elif action == "manage_giveaways":
        await manage_giveaways_handler(callback)
    elif action == "list_giveaways":
        await list_giveaways_handler(callback)
    elif action == "create_giveaway":
        await create_giveaway_handler(callback)
    elif action == "giveaway_details":
        logging.info(f"🎯 Вызываем giveaway_details_handler с value={value}")
        await giveaway_details_handler(callback, value)
    elif action == "activate_giveaway":
        await activate_giveaway_handler(callback, value)
    elif action == "finish_giveaway":
        await finish_giveaway_handler(callback, value)
    elif action == "bot_stats":
        await bot_stats_handler(callback)
    elif action == "back_to_menu":
        await back_to_menu_handler(callback)
    elif action == "add_channel":
        await add_channel_handler(callback)
    elif action == "list_channels":
        await list_channels_handler(callback)
    elif action == "list_prizes":
        await list_prizes_handler(callback)
    elif action == "prize_details":
        await prize_details_handler(callback, value)
    elif action == "toggle_prize":
        await toggle_prize_handler(callback, value)
    elif action == "setup_webapp":
        await setup_webapp_handler(callback)
    elif action == "reload_settings":
        await reload_settings_handler(callback)
    else:
        logging.warning(f"⚠️ Неизвестное действие: {action}")
        await callback.answer(f"⚠️ Действие {action} не реализовано", show_alert=True)


# Вспомогательные функции-обработчики
async def set_max_win_handler(callback: CallbackQuery):
    """Обработчик для установки максимального выигрыша"""
    await callback.answer()
    
    # Получаем текущее значение
    current_max_win = get_max_win_per_day()
    
    await callback.message.edit_text(
        f"Текущий максимальный выигрыш за сутки: **{current_max_win}**\n\n"
        f"Для изменения введите команду в формате:\n\n"
        f"/set_max_win 5000",
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.callback_query(AdminCallback.filter(F.action == "add_channel"), AdminFilter())
async def add_channel_callback(callback: CallbackQuery, callback_data: AdminCallback):
    """Обработчик нажатия на кнопку добавления канала для обязательной подписки"""
    await callback.answer()
    
    # Создаем клавиатуру с кнопкой назад
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=AdminCallback(action="list_channels").pack()
                )
            ]
        ]
    )
    
    await callback.message.edit_text(
        "Введите ссылку на Telegram канал в формате:\n\n"
        "https://t.me/test_channel\n\n"
        "Или в формате:\n\n"
        "@test_channel\n\n"
        "Бот ожидает вашего ответа в следующем сообщении.",
        parse_mode=None,  # Отключаем парсинг разметки
        reply_markup=keyboard
    )


async def back_to_menu_handler(callback: CallbackQuery):
    """Обработчик возврата в главное меню админки"""
    await callback.answer()
    await callback.message.edit_text(
        "Панель администратора:",
        reply_markup=get_admin_keyboard()
    )


async def add_channel_handler(callback: CallbackQuery):
    """Обработчик для добавления канала"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=AdminCallback(action="list_channels").pack()
            )]
        ]
    )
    
    await callback.message.edit_text(
        "📢 Добавление канала-спонсора\n\n"
        "Введите информацию о канале в формате:\n\n"
        "`@channel_name Название канала`\n\n"
        "Пример:\n"
        "`@masha_channel Канал Маши`\n\n"
        "Или используйте команду:\n"
        "`/add_channel @channel_name Название канала`",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def list_channels_handler(callback: CallbackQuery):
    """Обработчик для списка каналов"""
    await callback.answer()
    
    try:
        async for session in get_session():
            from src.database.repositories.sponsor_channel_repository import SponsorChannelRepository
            channel_repo = SponsorChannelRepository(session)
            channels = await channel_repo.get_all_channels()
            
            if not channels:
                message_text = "📋 Список каналов-спонсоров\n\nКаналы не найдены."
            else:
                message_text = "📋 Список каналов-спонсоров\n\n"
                for channel in channels:
                    status_icon = "🟢" if channel.is_active else "🔴"
                    required_icon = "✅" if channel.is_required else "❌"
                    message_text += f"{status_icon} {channel.channel_title}\n"
                    message_text += f"   ID: {channel.channel_id}\n"
                    message_text += f"   Обязательный: {required_icon}\n\n"
            
            keyboard_buttons = [
                [InlineKeyboardButton(
                    text="➕ Добавить канал",
                    callback_data=AdminCallback(action="add_channel").pack()
                )],
                [InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=AdminCallback(action="back_to_menu").pack()
                )]
            ]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении списка каналов: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке каналов. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


async def list_prizes_handler(callback: CallbackQuery):
    """Обработчик для списка призов"""
    await callback.answer()
    
    try:
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            prizes = await prize_repo.get_all_prizes()
            
            if not prizes:
                message_text = "📋 Список призов\n\nПризы не найдены."
            else:
                message_text = "📋 Список призов\n\n"
                for prize in prizes:
                    status = "✅ Активен" if prize.is_active else "❌ Неактивен"
                    message_text += f"🎁 {prize.name}\n"
                    message_text += f"💰 Стоимость: {prize.value} руб\n"
                    message_text += f"🎯 Вероятность: {prize.probability*100:.1f}%\n"
                    message_text += f"📊 Статус: {status}\n\n"
            
            keyboard_buttons = []
            
            for prize in prizes:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"🎁 {prize.name} ({prize.value} руб)",
                        callback_data=AdminCallback(action="prize_details", value=str(prize.id)).pack()
                    )
                ])
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=AdminCallback(action="manage_prizes").pack()
                )
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении списка призов: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке списка призов. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


async def prize_details_handler(callback: CallbackQuery, prize_id_str: str):
    """Обработчик для деталей приза"""
    await callback.answer()
    
    try:
        prize_id = int(prize_id_str)
        
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            prize = await prize_repo.get_prize(prize_id)
            
            if not prize:
                await callback.message.edit_text(
                    "❌ Приз не найден.",
                    reply_markup=get_back_to_menu_keyboard()
                )
                return
            
            stats = await prize_repo.get_prize_statistics(prize_id)
            
            message_text = f"🎁 Детали приза\n\n"
            message_text += f"📝 Название: {prize.name}\n"
            message_text += f"📄 Описание: {prize.description or 'Нет описания'}\n"
            message_text += f"💰 Стоимость: {prize.value} руб\n"
            message_text += f"🎯 Вероятность: {prize.probability*100:.1f}%\n"
            message_text += f"📊 Статус: {'✅ Активен' if prize.is_active else '❌ Неактивен'}\n"
            message_text += f"📈 Выигрышей: {stats['wins_count']}\n"
            message_text += f"💵 Общая сумма: {stats['total_value']} руб\n"
            message_text += f"📊 Средняя сумма: {stats['average_value']:.1f} руб\n"
            
            keyboard_buttons = [
                [InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=AdminCallback(action="edit_prize", value=str(prize_id)).pack()
                )],
                [InlineKeyboardButton(
                    text="🗑️ Удалить" if prize.is_active else "✅ Активировать",
                    callback_data=AdminCallback(action="toggle_prize", value=str(prize_id)).pack()
                )],
                [InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=AdminCallback(action="list_prizes").pack()
                )]
            ]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении деталей приза: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке деталей приза. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


async def toggle_prize_handler(callback: CallbackQuery, prize_id_str: str):
    """Обработчик для включения/отключения приза"""
    await callback.answer()
    
    try:
        prize_id = int(prize_id_str)
        
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            prize = await prize_repo.get_prize(prize_id)
            
            if not prize:
                await callback.message.edit_text(
                    "❌ Приз не найден.",
                    reply_markup=get_back_to_menu_keyboard()
                )
                return
            
            new_status = not prize.is_active
            success = await prize_repo.update_prize(prize_id, is_active=new_status)
            
            if success:
                status_text = "активирован" if new_status else "деактивирован"
                await callback.message.edit_text(
                    f"✅ Приз {prize.name} успешно {status_text}!",
                    reply_markup=get_back_to_menu_keyboard()
                )
            else:
                await callback.message.edit_text(
                    "❌ Не удалось изменить состояние приза.",
                    reply_markup=get_back_to_menu_keyboard()
                )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при переключении приза: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при изменении состояния приза.",
            reply_markup=get_back_to_menu_keyboard()
        )


def extract_channel_username(url_or_username):
    """
    Извлекает имя пользователя из различных форматов ссылок на канал.
    
    Args:
        url_or_username (str): URL или имя пользователя канала
        
    Returns:
        tuple: (username, encoded_url)
    """
    # Если это URL-адрес с протоколом https://
    if url_or_username.startswith('https://t.me/'):
        username = url_or_username.split('/')[-1]
    # Если это URL-адрес с протоколом t.me/
    elif url_or_username.startswith('t.me/'):
        username = url_or_username.split('/')[-1]
    # Если это имя пользователя с @
    elif url_or_username.startswith('@'):
        username = url_or_username[1:]
    # Если это просто имя пользователя без @
    else:
        username = url_or_username
    
    encoded_url = urllib.parse.quote_plus(url_or_username)
    return username, encoded_url


@router.callback_query(AdminCallback.filter(F.action == "list_channels"), AdminFilter())
async def list_channels_callback(callback: CallbackQuery, callback_data: AdminCallback):
    """Обработчик для просмотра списка обязательных каналов"""
    await callback.answer()
    
    # Получаем список каналов
    channels = get_required_channels()
    
    if not channels:
        message_text = "В данный момент нет обязательных каналов для подписки."
    else:
        message_text = "Список обязательных каналов для подписки:\nВыберите канал для управления."
    
    # Создаем клавиатуру с кнопками каналов
    keyboard_buttons = []
    
    # Добавляем кнопки для каждого канала
    for channel in channels:
        # Извлекаем имя пользователя и кодируем URL для избежания проблем с callback_data
        username, _ = extract_channel_username(channel)
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"📢 {channel}",
                callback_data=AdminCallback(action="channel_details", value=username).pack()
            )
        ])
    
    # Добавляем кнопку для добавления нового канала
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить канал",
            callback_data=AdminCallback(action="add_channel").pack()
        )
    ])
    
    # Добавляем кнопку назад
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=AdminCallback(action="back_to_menu").pack()
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard
    )


@router.callback_query(AdminCallback.filter(F.action == "channel_details"), AdminFilter())
async def channel_details_callback(callback: CallbackQuery, callback_data: AdminCallback):
    """Обработчик для просмотра деталей канала и действий с ним"""
    await callback.answer()
    
    username = callback_data.value
    
    if not username:
        await callback.message.edit_text(
            "Ошибка: не указан идентификатор канала.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    
    # Получаем список каналов, чтобы найти полную ссылку
    channels = get_required_channels()
    channel_id = None
    
    # Ищем канал с соответствующим именем пользователя
    for channel in channels:
        ch_username, _ = extract_channel_username(channel)
        if ch_username == username:
            channel_id = channel
            break
    
    # Если канал не найден, используем username с @
    if channel_id is None:
        channel_id = f"@{username}"
    
    # Формируем клавиатуру с действиями для канала
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Удалить канал из требуемых подписок",
                    callback_data=AdminCallback(action="delete_channel", value=username).pack()
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=AdminCallback(action="list_channels").pack()
                )
            ]
        ]
    )
    
    await callback.message.edit_text(
        f"Канал: {channel_id}\n\nВыберите действие:",
        reply_markup=keyboard
    )


@router.callback_query(AdminCallback.filter(F.action == "delete_channel"), AdminFilter())
async def delete_channel_callback(callback: CallbackQuery, callback_data: AdminCallback):
    """Обработчик для удаления канала из списка обязательных подписок"""
    await callback.answer()
    
    username = callback_data.value
    
    if not username:
        await callback.message.edit_text(
            "Ошибка: не указан идентификатор канала для удаления.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    
    # Получаем список каналов, чтобы найти полную ссылку
    channels = get_required_channels()
    channel_id = None
    
    # Ищем канал с соответствующим именем пользователя
    for channel in channels:
        ch_username, _ = extract_channel_username(channel)
        if ch_username == username:
            channel_id = channel
            break
    
    # Если канал не найден, используем username с @
    if channel_id is None:
        channel_id = f"@{username}"
    
    # Удаляем канал из списка
    success = remove_channel_from_required(channel_id)
    
    if success:
        # Получаем обновленный список каналов
        channels = get_required_channels()
        
        if not channels:
            message_text = "Канал успешно удален! В данный момент нет обязательных каналов для подписки."
        else:
            # Формируем текст с информацией о каналах
            channels_list = "\n".join([f"• {channel}" for channel in channels])
            message_text = f"Канал {channel_id} успешно удален!\n\nОбновленный список каналов:\n\n{channels_list}"
        
        # Создаем клавиатуру с кнопкой для возврата к просмотру списка каналов
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 К списку каналов",
                        callback_data=AdminCallback(action="list_channels").pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="◀️ Назад в меню",
                        callback_data=AdminCallback(action="back_to_menu").pack()
                    )
                ]
            ]
        )
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            f"❌ Не удалось удалить канал {channel_id} из списка обязательных подписок.",
            reply_markup=get_back_to_menu_keyboard()
        )


@router.message(Command("set_max_win"), AdminFilter())
async def set_max_win_command(message: Message):
    """Обработчик команды установки максимального выигрыша"""
    try:
        # Получаем значение из текста сообщения
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.answer("Неверный формат команды. Правильный формат: /set_max_win 5000", parse_mode=None)
            return
        
        # Парсим значение
        try:
            max_win = int(command_parts[1])
            if max_win <= 0:
                await message.answer("Значение должно быть положительным числом.", parse_mode=None)
                return
        except ValueError:
            await message.answer("Значение должно быть числом.", parse_mode=None)
            return
        
        # Устанавливаем максимальный выигрыш
        success = set_max_win_per_day(max_win)
        
        if success:
            await message.answer(
                f"✅ Максимальный выигрыш за сутки установлен: {max_win}",
                parse_mode=None,
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                "❌ Не удалось установить максимальный выигрыш за сутки. Попробуйте позже.",
                parse_mode=None,
                reply_markup=get_admin_keyboard()
            )
    except Exception as e:
        logging.error(f"Ошибка при установке максимального выигрыша: {e}")
        await message.answer(f"Произошла ошибка: {str(e)}", parse_mode=None)


async def manage_prizes_handler(callback: CallbackQuery):
    """Обработчик для управления призами"""
    logging.info(f"🎯 Вызван manage_prizes_handler")
    await callback.answer()
    
    try:
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            prizes = await prize_repo.get_all_prizes()
            
            if not prizes:
                message_text = "🎁 Управление призами\n\nПризы не найдены. Добавьте первый приз!"
                keyboard_buttons = [
                    [InlineKeyboardButton(
                        text="➕ Добавить приз",
                        callback_data=AdminCallback(action="add_prize").pack()
                    )],
                    [InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data=AdminCallback(action="back_to_menu").pack()
                    )]
                ]
            else:
                message_text = "🎁 Управление призами\n\nВыберите действие:"
                keyboard_buttons = [
                    [InlineKeyboardButton(
                        text="➕ Добавить приз",
                        callback_data=AdminCallback(action="add_prize").pack()
                    )],
                    [InlineKeyboardButton(
                        text="📋 Список призов",
                        callback_data=AdminCallback(action="list_prizes").pack()
                    )],
                    [InlineKeyboardButton(
                        text="📊 Статистика призов",
                        callback_data=AdminCallback(action="prizes_stats").pack()
                    )],
                    [InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data=AdminCallback(action="back_to_menu").pack()
                    )]
                ]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении призов: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке призов. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


@router.callback_query(AdminCallback.filter(F.action == "list_prizes"), AdminFilter())
async def list_prizes_callback(callback: CallbackQuery, callback_data: AdminCallback):
    """Обработчик для просмотра списка призов"""
    await callback.answer()
    
    try:
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            prizes = await prize_repo.get_all_prizes()
            
            if not prizes:
                message_text = "📋 Список призов\n\nПризы не найдены."
            else:
                message_text = "📋 Список призов\n\n"
                for prize in prizes:
                    status = "✅ Активен" if prize.is_active else "❌ Неактивен"
                    message_text += f"🎁 {prize.name}\n"
                    message_text += f"💰 Стоимость: {prize.value} руб\n"
                    message_text += f"🎯 Вероятность: {prize.probability*100:.1f}%\n"
                    message_text += f"📊 Статус: {status}\n\n"
            
            keyboard_buttons = []
            
            # Добавляем кнопки для каждого приза
            for prize in prizes:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"🎁 {prize.name} ({prize.value} руб)",
                        callback_data=AdminCallback(action="prize_details", value=str(prize.id)).pack()
                    )
                ])
            
            # Добавляем кнопку назад
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=AdminCallback(action="manage_prizes").pack()
                )
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении списка призов: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке списка призов. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


@router.callback_query(AdminCallback.filter(F.action == "prize_details"), AdminFilter())
async def prize_details_callback(callback: CallbackQuery, callback_data: AdminCallback):
    """Обработчик для детальной информации о призе"""
    await callback.answer()
    
    try:
        prize_id = int(callback_data.value)
        
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            prize = await prize_repo.get_prize(prize_id)
            
            if not prize:
                await callback.message.edit_text(
                    "❌ Приз не найден.",
                    reply_markup=get_back_to_menu_keyboard()
                )
                return
            
            # Получаем статистику приза
            stats = await prize_repo.get_prize_statistics(prize_id)
            
            message_text = f"🎁 Детали приза\n\n"
            message_text += f"📝 Название: {prize.name}\n"
            message_text += f"📄 Описание: {prize.description or 'Нет описания'}\n"
            message_text += f"💰 Стоимость: {prize.value} руб\n"
            message_text += f"🎯 Вероятность: {prize.probability*100:.1f}%\n"
            message_text += f"📊 Статус: {'✅ Активен' if prize.is_active else '❌ Неактивен'}\n"
            message_text += f"📈 Выигрышей: {stats['wins_count']}\n"
            message_text += f"💵 Общая сумма: {stats['total_value']} руб\n"
            message_text += f"📊 Средняя сумма: {stats['average_value']:.1f} руб\n"
            
            keyboard_buttons = [
                [InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=AdminCallback(action="edit_prize", value=str(prize_id)).pack()
                )],
                [InlineKeyboardButton(
                    text="🗑️ Удалить" if prize.is_active else "✅ Активировать",
                    callback_data=AdminCallback(action="toggle_prize", value=str(prize_id)).pack()
                )],
                [InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=AdminCallback(action="list_prizes").pack()
                )]
            ]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении деталей приза: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке деталей приза. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


@router.callback_query(AdminCallback.filter(F.action == "toggle_prize"), AdminFilter())
async def toggle_prize_callback(callback: CallbackQuery, callback_data: AdminCallback):
    """Обработчик для включения/отключения приза"""
    await callback.answer()
    
    try:
        prize_id = int(callback_data.value)
        
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            prize = await prize_repo.get_prize(prize_id)
            
            if not prize:
                await callback.message.edit_text(
                    "❌ Приз не найден.",
                    reply_markup=get_back_to_menu_keyboard()
                )
                return
            
            # Переключаем состояние
            new_status = not prize.is_active
            success = await prize_repo.update_prize(prize_id, is_active=new_status)
            
            if success:
                status_text = "активирован" if new_status else "деактивирован"
                await callback.message.edit_text(
                    f"✅ Приз {prize.name} успешно {status_text}!",
                    reply_markup=get_back_to_menu_keyboard()
                )
            else:
                await callback.message.edit_text(
                    "❌ Не удалось изменить состояние приза.",
                    reply_markup=get_back_to_menu_keyboard()
                )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при переключении приза: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при изменении состояния приза.",
            reply_markup=get_back_to_menu_keyboard()
        )


async def bot_stats_handler(callback: CallbackQuery):
    """Обработчик для просмотра статистики бота"""
    logging.info(f"🎯 bot_stats_handler вызван")
    await callback.answer()
    
    try:
        async for session in get_session():
            from src.database.repositories.user_repository import UserRepository
            from src.database.repositories.game_repository import GameRepository
            
            user_repo = UserRepository(session)
            game_repo = GameRepository(session)
            prize_repo = PrizeRepository(session)
            
            # Получаем статистику
            from sqlalchemy import select, func
            from src.database.models import User, Game
            
            # Всего пользователей
            total_users_result = await session.execute(select(func.count(User.id)))
            total_users = total_users_result.scalar() or 0
            
            # Всего игр
            total_games_result = await session.execute(select(func.count(Game.id)))
            total_games = total_games_result.scalar() or 0
            
            # Всего выигрышей
            total_wins_result = await session.execute(
                select(func.count(Game.id)).where(Game.is_win == True)
            )
            total_wins = total_wins_result.scalar() or 0
            
            # Общая сумма выигрышей
            total_winnings_result = await session.execute(
                select(func.sum(Game.win_amount)).where(Game.is_win == True)
            )
            total_winnings = total_winnings_result.scalar() or 0
            
            # Всего призов
            prizes = await prize_repo.get_all_prizes()
            total_prizes = len(prizes)
            active_prizes = len([p for p in prizes if p.is_active])
            
            message_text = "📊 Статистика бота\n\n"
            message_text += f"👥 Всего пользователей: {total_users}\n"
            message_text += f"🎮 Всего игр: {total_games}\n"
            message_text += f"🎁 Всего выигрышей: {total_wins}\n"
            message_text += f"💰 Общая сумма выигрышей: {total_winnings} руб\n"
            message_text += f"🎯 Всего призов: {total_prizes}\n"
            message_text += f"✅ Активных призов: {active_prizes}\n"
            
            if total_games > 0:
                win_rate = (total_wins / total_games) * 100
                message_text += f"📈 Процент выигрышей: {win_rate:.1f}%\n"
            
            await callback.message.edit_text(
                message_text,
                reply_markup=get_back_to_menu_keyboard()
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении статистики: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке статистики.",
            reply_markup=get_back_to_menu_keyboard()
        )


# === ОБРАБОТЧИКИ РОЗЫГРЫШЕЙ ===

async def manage_giveaways_handler(callback: CallbackQuery):
    """Обработчик для управления розыгрышами"""
    logging.info(f"🎯 manage_giveaways_handler вызван")
    await callback.answer()
    
    try:
        async for session in get_session():
            from src.database.repositories.giveaway_repository import GiveawayRepository
            giveaway_repo = GiveawayRepository(session)
            giveaways = await giveaway_repo.list_all()
            
            message_text = "🎉 Управление розыгрышами\n\nВыберите действие:"
            keyboard_buttons = [
                [InlineKeyboardButton(
                    text="➕ Создать розыгрыш",
                    callback_data=AdminCallback(action="create_giveaway").pack()
                )],
                [InlineKeyboardButton(
                    text="📋 Список розыгрышей",
                    callback_data=AdminCallback(action="list_giveaways").pack()
                )],
                [InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=AdminCallback(action="back_to_menu").pack()
                )]
            ]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении розыгрышей: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке розыгрышей. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


async def list_giveaways_handler(callback: CallbackQuery):
    """Обработчик для списка розыгрышей"""
    await callback.answer()
    
    try:
        async for session in get_session():
            from src.database.repositories.giveaway_repository import GiveawayRepository
            giveaway_repo = GiveawayRepository(session)
            giveaways = await giveaway_repo.list_all()
            
            if not giveaways:
                message_text = "📋 Список розыгрышей\n\nРозыгрыши не найдены."
            else:
                message_text = "📋 Список розыгрышей\n\n"
                for giveaway in giveaways:
                    status_emoji = "🟢" if giveaway.status == "active" else "🟡" if giveaway.status == "draft" else "🔴"
                    message_text += f"{status_emoji} {giveaway.title}\n"
                    message_text += f"🎁 Приз: {giveaway.prize}\n"
                    message_text += f"📊 Статус: {giveaway.status}\n\n"
            
            keyboard_buttons = []
            
            for giveaway in giveaways:
                status_emoji = "🟢" if giveaway.status == "active" else "🟡" if giveaway.status == "draft" else "🔴"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{status_emoji} {giveaway.title}",
                        callback_data=AdminCallback(action="giveaway_details", value=str(giveaway.id)).pack()
                    )
                ])
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=AdminCallback(action="manage_giveaways").pack()
                )
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении списка розыгрышей: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке списка розыгрышей. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


async def create_giveaway_handler(callback: CallbackQuery):
    """Обработчик для создания розыгрыша"""
    await callback.answer()
    
    await callback.message.edit_text(
        "➕ Создание розыгрыша\n\n"
        "Используйте команду в формате:\n\n"
        "/create_giveaway \"Название\" \"Описание\" \"Приз\"\n\n"
        "Пример:\n"
        "/create_giveaway \"Новогодний розыгрыш\" \"Выиграй iPhone 15!\" \"iPhone 15 Pro\"",
        reply_markup=get_back_to_menu_keyboard()
    )


async def giveaway_details_handler(callback: CallbackQuery, giveaway_id_str: str):
    """Обработчик для деталей розыгрыша"""
    logging.info(f"🎯 giveaway_details_handler вызван с giveaway_id_str: {giveaway_id_str}")
    await callback.answer()
    
    try:
        if not giveaway_id_str or giveaway_id_str == "None":
            logging.warning(f"⚠️ Неверный giveaway_id_str: {giveaway_id_str}")
            await callback.message.edit_text(
                "❌ Неверный ID розыгрыша.",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
            
        giveaway_id = int(giveaway_id_str)
        logging.info(f"🎯 Обрабатываем розыгрыш ID: {giveaway_id}")
        
        async for session in get_session():
            from src.database.repositories.giveaway_repository import GiveawayRepository, GiveawayEntryRepository
            giveaway_repo = GiveawayRepository(session)
            entry_repo = GiveawayEntryRepository(session)
            giveaway = await giveaway_repo.get_by_id(giveaway_id)
            
            if not giveaway:
                await callback.message.edit_text(
                    "❌ Розыгрыш не найден.",
                    reply_markup=get_back_to_menu_keyboard()
                )
                return
            
            # Получаем количество участников
            entries_count = await entry_repo.count_entries(giveaway_id)
            
            status_text = {
                "draft": "📝 Черновик",
                "active": "🟢 Активен",
                "finished": "🔴 Завершен"
            }.get(giveaway.status, giveaway.status)
            
            message_text = f"🎉 Детали розыгрыша\n\n"
            message_text += f"📝 Название: {giveaway.title}\n"
            message_text += f"📄 Описание: {giveaway.description or 'Нет описания'}\n"
            message_text += f"🎁 Приз: {giveaway.prize}\n"
            message_text += f"📊 Статус: {status_text}\n"
            message_text += f"👥 Участников: {entries_count}\n"
            
            if giveaway.starts_at:
                message_text += f"🕐 Начало: {giveaway.starts_at.strftime('%d.%m.%Y %H:%M')}\n"
            if giveaway.ends_at:
                message_text += f"🕐 Конец: {giveaway.ends_at.strftime('%d.%m.%Y %H:%M')}\n"
            
            if giveaway.winner_id:
                message_text += f"🏆 Победитель: {giveaway.winner_username or giveaway.winner_id}\n"
            
            keyboard_buttons = []
            
            if giveaway.status == "draft":
                keyboard_buttons.append([InlineKeyboardButton(
                    text="▶️ Активировать",
                    callback_data=AdminCallback(action="activate_giveaway", value=str(giveaway_id)).pack()
                )])
            elif giveaway.status == "active":
                keyboard_buttons.append([InlineKeyboardButton(
                    text="🏁 Завершить и выбрать победителя",
                    callback_data=AdminCallback(action="finish_giveaway", value=str(giveaway_id)).pack()
                )])
            
            keyboard_buttons.append([InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=AdminCallback(action="list_giveaways").pack()
            )])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при получении деталей розыгрыша: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке деталей розыгрыша. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


async def activate_giveaway_handler(callback: CallbackQuery, giveaway_id_str: str):
    """Обработчик для активации розыгрыша"""
    await callback.answer()
    
    try:
        giveaway_id = int(giveaway_id_str)
        
        async for session in get_session():
            from src.database.repositories.giveaway_repository import GiveawayRepository
            giveaway_repo = GiveawayRepository(session)
            success = await giveaway_repo.set_status(giveaway_id, "active")
            
            if success:
                await callback.message.edit_text(
                    "✅ Розыгрыш успешно активирован!",
                    reply_markup=get_back_to_menu_keyboard()
                )
            else:
                await callback.message.edit_text(
                    "❌ Не удалось активировать розыгрыш.",
                    reply_markup=get_back_to_menu_keyboard()
                )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при активации розыгрыша: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при активации розыгрыша.",
            reply_markup=get_back_to_menu_keyboard()
        )


async def finish_giveaway_handler(callback: CallbackQuery, giveaway_id_str: str):
    """Обработчик для завершения розыгрыша"""
    await callback.answer()
    
    try:
        giveaway_id = int(giveaway_id_str)
        
        async for session in get_session():
            from src.database.repositories.giveaway_repository import GiveawayRepository
            giveaway_repo = GiveawayRepository(session)
            result = await giveaway_repo.finish_and_draw(giveaway_id, winners_count=1)
            
            if result and result.get('winners'):
                winners = result['winners']
                total = result['total']
                await callback.message.edit_text(
                    f"✅ Розыгрыш успешно завершен!\n\n"
                    f"🏆 Победитель ID: {winners[0]}\n"
                    f"👥 Всего участников: {total}",
                    reply_markup=get_back_to_menu_keyboard()
                )
            else:
                await callback.message.edit_text(
                    "❌ Не удалось завершить розыгрыш. Возможно, нет участников.",
                    reply_markup=get_back_to_menu_keyboard()
                )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при завершении розыгрыша: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при завершении розыгрыша.",
            reply_markup=get_back_to_menu_keyboard()
        )


# Команды для управления призами
@router.message(Command("add_prize"), AdminFilter())
async def add_prize_command(message: Message):
    """Обработчик команды добавления приза"""
    try:
        # Формат: /add_prize "Название" "Описание" 1000 0.1
        command_parts = message.text.split('"')
        if len(command_parts) < 5:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Правильный формат:\n"
                "/add_prize \"Название приза\" \"Описание\" 1000 0.1\n\n"
                "Где:\n"
                "• Название приза - название приза\n"
                "• Описание - описание приза\n"
                "• 1000 - стоимость в рублях\n"
                "• 0.1 - вероятность (0.0-1.0)",
                parse_mode=None
            )
            return
        
        name = command_parts[1].strip()
        description = command_parts[3].strip()
        
        # Парсим стоимость и вероятность
        try:
            value_prob = command_parts[4].strip().split()
            if len(value_prob) != 2:
                raise ValueError()
            
            value = int(value_prob[0])
            probability = float(value_prob[1])
            
            if value <= 0:
                await message.answer("❌ Стоимость должна быть положительным числом.", parse_mode=None)
                return
                
            if not 0.0 <= probability <= 1.0:
                await message.answer("❌ Вероятность должна быть от 0.0 до 1.0.", parse_mode=None)
                return
                
        except (ValueError, IndexError):
            await message.answer(
                "❌ Неверный формат стоимости или вероятности.\n"
                "Пример: /add_prize \"iPhone\" \"Новый iPhone\" 50000 0.05",
                parse_mode=None
            )
            return
        
        # Создаем приз
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            prize = await prize_repo.create_prize(
                name=name,
                description=description,
                value=value,
                probability=probability
            )
            
            await message.answer(
                f"✅ Приз успешно добавлен!\n\n"
                f"🎁 Название: {prize.name}\n"
                f"📄 Описание: {prize.description}\n"
                f"💰 Стоимость: {prize.value} руб\n"
                f"🎯 Вероятность: {prize.probability*100:.1f}%",
                parse_mode=None,
                reply_markup=get_admin_keyboard()
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при добавлении приза: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)}", parse_mode=None)


@router.message(Command("edit_prize"), AdminFilter())
async def edit_prize_command(message: Message):
    """Обработчик команды редактирования приза"""
    try:
        # Формат: /edit_prize 1 "Новое название" "Новое описание" 2000 0.2
        command_parts = message.text.split('"')
        if len(command_parts) < 5:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Правильный формат:\n"
                "/edit_prize 1 \"Новое название\" \"Новое описание\" 2000 0.2\n\n"
                "Где 1 - ID приза",
                parse_mode=None
            )
            return
        
        try:
            prize_id = int(command_parts[0].split()[-1])
        except (ValueError, IndexError):
            await message.answer("❌ Неверный ID приза.", parse_mode=None)
            return
        
        name = command_parts[1].strip()
        description = command_parts[3].strip()
        
        # Парсим стоимость и вероятность
        try:
            value_prob = command_parts[4].strip().split()
            if len(value_prob) != 2:
                raise ValueError()
            
            value = int(value_prob[0])
            probability = float(value_prob[1])
            
            if value <= 0:
                await message.answer("❌ Стоимость должна быть положительным числом.", parse_mode=None)
                return
                
            if not 0.0 <= probability <= 1.0:
                await message.answer("❌ Вероятность должна быть от 0.0 до 1.0.", parse_mode=None)
                return
                
        except (ValueError, IndexError):
            await message.answer(
                "❌ Неверный формат стоимости или вероятности.",
                parse_mode=None
            )
            return
        
        # Обновляем приз
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            success = await prize_repo.update_prize(
                prize_id=prize_id,
                name=name,
                description=description,
                value=value,
                probability=probability
            )
            
            if success:
                await message.answer(
                    f"✅ Приз успешно обновлен!\n\n"
                    f"🎁 Название: {name}\n"
                    f"📄 Описание: {description}\n"
                    f"💰 Стоимость: {value} руб\n"
                    f"🎯 Вероятность: {probability*100:.1f}%",
                    parse_mode=None,
                    reply_markup=get_admin_keyboard()
                )
            else:
                await message.answer(
                    "❌ Не удалось обновить приз. Проверьте ID приза.",
                    parse_mode=None
                )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при редактировании приза: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)}", parse_mode=None)


@router.message(Command("delete_prize"), AdminFilter())
async def delete_prize_command(message: Message):
    """Обработчик команды удаления приза"""
    try:
        # Формат: /delete_prize 1
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Правильный формат: /delete_prize 1\n"
                "Где 1 - ID приза",
                parse_mode=None
            )
            return
        
        try:
            prize_id = int(command_parts[1])
        except ValueError:
            await message.answer("❌ Неверный ID приза.", parse_mode=None)
            return
        
        # Удаляем приз
        async for session in get_session():
            prize_repo = PrizeRepository(session)
            success = await prize_repo.delete_prize(prize_id)
            
            if success:
                await message.answer(
                    f"✅ Приз {prize_id} успешно удален!",
                    parse_mode=None,
                    reply_markup=get_admin_keyboard()
                )
            else:
                await message.answer(
                    "❌ Не удалось удалить приз. Проверьте ID приза.",
                    parse_mode=None
                )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при удалении приза: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)}", parse_mode=None)

async def reload_settings_handler(callback: CallbackQuery):
    """Обработчик для перезагрузки настроек"""
    try:
        # Принудительно перезагружаем настройки
        new_url = settings.reload_settings()
        
        await callback.message.edit_text(
            f"✅ Настройки перезагружены!\n\n"
            f"🔗 Новый URL: {new_url}\n"
            f"📱 Теперь можно настроить WebApp\n\n"
            f"Нажмите '🌐 Настроить WebApp' для применения изменений",
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode=None
        )
        
    except Exception as e:
        logging.error(f"Ошибка при перезагрузке настроек: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при перезагрузке настроек: {str(e)}",
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode=None
        )

async def setup_webapp_handler(callback: CallbackQuery):
    """Обработчик для настройки WebApp"""
    try:
        from aiogram import Bot
        bot = Bot(token=settings.BOT_TOKEN)
        
        # Настраиваем WebApp URL
        webapp_url = f"{settings.WEBAPP_PUBLIC_URL}/static/game/spin_wheel.html"
        
        await bot.set_web_app_menu_button(
            menu_button={
                "type": "web_app",
                "text": "🎰 Играть",
                "web_app": {
                    "url": webapp_url
                }
            }
        )
        
        await callback.message.edit_text(
            f"✅ WebApp настроен успешно!\n\n"
            f"🔗 URL: {webapp_url}\n"
            f"📱 Кнопка '🎰 Играть' добавлена в меню бота\n\n"
            f"Теперь пользователи смогут открыть игру прямо из бота!",
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode=None
        )
        
        await bot.session.close()
        
    except Exception as e:
        logging.error(f"Ошибка при настройке WebApp: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при настройке WebApp: {str(e)}",
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode=None
        )

# === КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ КАНАЛАМИ ===

@router.message(Command("reload_settings"))
async def reload_settings_command(message: Message):
    """Обработчик команды перезагрузки настроек"""
    # Проверяем права администратора
    if not await check_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора!", show_alert=True)
        return
    
    try:
        # Принудительно перезагружаем настройки
        new_url = settings.reload_settings()
        
        await message.answer(
            f"✅ Настройки перезагружены!\n\n"
            f"🔗 Новый URL: {new_url}\n"
            f"📱 Теперь можно настроить WebApp",
            parse_mode=None
        )
        
    except Exception as e:
        logging.error(f"Ошибка при перезагрузке настроек: {e}")
        await message.answer(f"❌ Ошибка при перезагрузке настроек: {str(e)}", parse_mode=None)

@router.message(Command("setup_webapp"))
async def setup_webapp_command(message: Message):
    """Обработчик команды настройки WebApp"""
    # Проверяем права администратора
    if not await check_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора!", show_alert=True)
        return
    
    try:
        from aiogram import Bot
        bot = Bot(token=settings.BOT_TOKEN)
        
        # Настраиваем WebApp URL
        webapp_url = f"{settings.WEBAPP_PUBLIC_URL}/static/game/spin_wheel.html"
        
        await bot.set_web_app_menu_button(
            menu_button={
                "type": "web_app",
                "text": "🎰 Играть",
                "web_app": {
                    "url": webapp_url
                }
            }
        )
        
        await message.answer(
            f"✅ WebApp настроен успешно!\n\n"
            f"🔗 URL: {webapp_url}\n"
            f"📱 Кнопка '🎰 Играть' добавлена в меню бота",
            parse_mode=None
        )
        
        await bot.session.close()
        
    except Exception as e:
        logging.error(f"Ошибка при настройке WebApp: {str(e)}")
        await message.answer(f"❌ Ошибка при настройке WebApp: {str(e)}", parse_mode=None)

@router.message(Command("add_channel"))
async def add_channel_command(message: Message):
    """Обработчик команды добавления канала"""
    # Проверяем права администратора
    if not await check_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора!", show_alert=True)
        return
    
    try:
        # Формат: /add_channel @channel_name Название канала
        command_parts = message.text.split(' ', 2)
        if len(command_parts) < 3:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Правильный формат:\n"
                "/add_channel @channel_name Название канала\n\n"
                "Пример:\n"
                "/add_channel @masha_channel Канал Маши",
                parse_mode=None
            )
            return
        
        channel_id = command_parts[1].strip()
        channel_title = command_parts[2].strip()
        
        if not channel_id.startswith('@'):
            await message.answer("❌ ID канала должен начинаться с @", parse_mode=None)
            return
        
        # Создаем канал
        async for session in get_session():
            from src.database.repositories.sponsor_channel_repository import SponsorChannelRepository
            channel_repo = SponsorChannelRepository(session)
            
            # Проверяем, не существует ли уже такой канал
            existing_channel = await channel_repo.get_channel(channel_id)
            if existing_channel:
                await message.answer(
                    f"❌ Канал {channel_id} уже существует!",
                    parse_mode=None
                )
                return
            
            channel = await channel_repo.create_channel(
                channel_id=channel_id,
                channel_title=channel_title,
                channel_url=f"https://t.me/{channel_id[1:]}",
                is_required=True,
                created_by=message.from_user.id
            )
            
            await message.answer(
                f"✅ Канал успешно добавлен!\n\n"
                f"📢 Название: {channel.channel_title}\n"
                f"🆔 ID: {channel.channel_id}\n"
                f"🔗 URL: {channel.channel_url}\n"
                f"✅ Обязательный: Да",
                parse_mode=None
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при добавлении канала: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)}", parse_mode=None)


# === КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ РОЗЫГРЫШАМИ ===

@router.message(Command("create_giveaway"))
async def create_giveaway_command(message: Message):
    """Обработчик команды создания розыгрыша"""
    # Проверяем права администратора
    if not await check_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора!", show_alert=True)
        return
    
    try:
        # Формат: /create_giveaway "Название" "Описание" "Приз"
        command_parts = message.text.split('"')
        if len(command_parts) < 6:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Правильный формат:\n"
                "/create_giveaway \"Название\" \"Описание\" \"Приз\"\n\n"
                "Пример:\n"
                "/create_giveaway \"Новогодний розыгрыш\" \"Выиграй iPhone!\" \"iPhone 15 Pro\"",
                parse_mode=None
            )
            return
        
        title = command_parts[1].strip()
        description = command_parts[3].strip()
        prize = command_parts[5].strip()
        
        if not title or not prize:
            await message.answer("❌ Название и приз обязательны.", parse_mode=None)
            return
        
        # Создаем розыгрыш
        async for session in get_session():
            from src.database.repositories.giveaway_repository import GiveawayRepository
            giveaway_repo = GiveawayRepository(session)
            giveaway = await giveaway_repo.create(
                title=title,
                description=description,
                prize=prize,
                created_by=message.from_user.id
            )
            
            await message.answer(
                f"✅ Розыгрыш успешно создан!\n\n"
                f"🎉 Название: {giveaway.title}\n"
                f"📄 Описание: {giveaway.description}\n"
                f"🎁 Приз: {giveaway.prize}\n"
                f"📊 Статус: Черновик\n\n"
                f"Используйте кнопку 'Управление розыгрышами' для активации.",
                parse_mode=None,
                reply_markup=get_back_to_menu_keyboard()
            )
            break
            
    except Exception as e:
        logging.error(f"Ошибка при создании розыгрыша: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)}", parse_mode=None)


@router.message(Command("add_channel"), AdminFilter())
async def add_channel_command(message: Message):
    """Обработчик команды добавления канала для обязательной подписки"""
    try:
        # Получаем значение из текста сообщения
        command_parts = message.text.split(maxsplit=2)
        if len(command_parts) != 3:
            await message.answer(
                "Неверный формат команды. Правильный формат:\n"
                "/add_channel @username Название канала\n"
                "или\n"
                "/add_channel -1001234567890 Название канала",
                parse_mode=None
            )
            return
        
        channel_id = command_parts[1]
        channel_name = command_parts[2]
        
        # Проверка валидности канала
        if not (channel_id.startswith('@') or channel_id.startswith('-100')):
            await message.answer("ID канала должен начинаться с @ или -100", parse_mode=None)
            return
        
        # Добавляем канал в список обязательных подписок
        success = add_channel_to_required(channel_id, channel_name)
        
        if success:
            # Получаем обновленный список каналов
            channels_list = get_required_channels()
            channels_text = '\n'.join([f"- {channel}" for channel in channels_list])
            
            await message.answer(
                f"✅ Канал успешно добавлен в список обязательных подписок:\n\n"
                f"ID: {channel_id}\n"
                f"Название: {channel_name}\n\n"
                f"Текущий список каналов:\n{channels_text}",
                parse_mode=None,
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                "❌ Не удалось добавить канал в список обязательных подписок.\n"
                "Возможно, канал уже есть в списке или произошла ошибка при обновлении файла конфигурации.",
                parse_mode=None,
                reply_markup=get_admin_keyboard()
            )
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}", parse_mode=None)


# Обработчик для добавления канала через сообщение с ссылкой
# Отфильтровываем команды, чтобы этот обработчик не перехватывал их
@router.message(AdminFilter(), ~F.text.startswith('/'))
async def process_channel_link(message: Message):
    """Обрабатывает сообщение с ссылкой на канал для добавления в список обязательных подписок"""
    # Проверяем, что сообщение содержит ссылку на телеграм канал
    text = message.text
    if not text:
        return
    
    # Проверяем разные форматы ссылок на канал
    channel_id = None
    
    # Проверка формата https://t.me/username
    https_pattern = r'https://t\.me/([a-zA-Z0-9_]+)'
    match_https = re.match(https_pattern, text)
    
    # Проверка формата @username
    username_pattern = r'@([a-zA-Z0-9_]+)'
    match_username = re.match(username_pattern, text)
    
    if match_https:
        # Используем полный URL как channel_id
        channel_id = text
    elif match_username:
        # Используем @username как channel_id
        channel_id = text
    
    if not channel_id:
        # Если сообщение не соответствует формату ссылки на канал
        # Проверяем, не является ли это командой (начинается с "/")
        if text.startswith('/'):
            return  # Пропускаем обработку команд
        
        # Сообщаем об ошибке формата
        await message.answer(
            "Некорректный формат ссылки. Введите ссылку в одном из форматов:\n\n"
            "- https://t.me/test_channel\n"
            "- @test_channel",
            parse_mode=None,  # Отключаем парсинг разметки
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="◀️ Вернуться в меню",
                            callback_data=AdminCallback(action="list_channels").pack()
                        )
                    ]
                ]
            )
        )
        return
    
    # Добавляем канал в список обязательных подписок
    success = add_channel_to_required(channel_id)
    
    if success:
        # Получаем обновленный список каналов
        channels_list = get_required_channels()
        
        await message.answer(
            f"✅ Канал успешно добавлен в список обязательных подписок:\n\n"
            f"ID: {channel_id}\n\n"
            f"Текущее количество каналов: {len(channels_list)}",
            parse_mode=None,  # Отключаем парсинг разметки
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📋 К списку каналов",
                            callback_data=AdminCallback(action="list_channels").pack()
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="◀️ Вернуться в меню",
                            callback_data=AdminCallback(action="back_to_menu").pack()
                        )
                    ]
                ]
            )
        )
    else:
        await message.answer(
            "❌ Не удалось добавить канал в список обязательных подписок.\n"
            "Возможно, канал уже есть в списке или произошла ошибка при обновлении конфигурации.",
            parse_mode=None,  # Отключаем парсинг разметки
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="◀️ Вернуться в меню",
                            callback_data=AdminCallback(action="list_channels").pack()
                        )
                    ]
                ]
            )
        )

