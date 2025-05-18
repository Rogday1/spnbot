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

# Загружаем переменные окружения
load_dotenv()

# Создаем роутер ТОЛЬКО для обработки команды admin
# Важно: задаем имя роутера и явный фильтр только для команды admin
router = Router(name="admin_commands")

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


@router.callback_query(AdminCallback.filter(F.action == "set_max_win"), AdminFilter())
async def set_max_win_callback(callback: CallbackQuery, callback_data: AdminCallback):
    """Обработчик нажатия на кнопку установки максимального выигрыша"""
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


@router.callback_query(AdminCallback.filter(F.action == "back_to_menu"), AdminFilter())
async def back_to_menu_callback(callback: CallbackQuery, callback_data: AdminCallback):
    """Обработчик возврата в главное меню админки"""
    await callback.answer()
    await callback.message.edit_text(
        "Панель администратора:",
        reply_markup=get_admin_keyboard()
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