from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .callback_data import AdminCallback


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает инлайн-клавиатуру для админ-панели
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура для админ-панели
    """
    # Создаем кнопки с соответствующими коллбэк-данными
    max_win_button = InlineKeyboardButton(
        text="💰 Назначить максимальный выигрыш за сутки",
        callback_data=AdminCallback(action="set_max_win").pack()
    )
    
    prizes_button = InlineKeyboardButton(
        text="🎁 Управление призами",
        callback_data=AdminCallback(action="manage_prizes").pack()
    )
    
    giveaways_button = InlineKeyboardButton(
        text="🎉 Управление розыгрышами",
        callback_data=AdminCallback(action="manage_giveaways").pack()
    )
    
    add_channel_button = InlineKeyboardButton(
        text="📢 Добавить канал в требуемые подписки",
        callback_data=AdminCallback(action="add_channel").pack()
    )
    
    list_channels_button = InlineKeyboardButton(
        text="📋 Список требуемых каналов",
        callback_data=AdminCallback(action="list_channels").pack()
    )
    
    stats_button = InlineKeyboardButton(
        text="📊 Статистика бота",
        callback_data=AdminCallback(action="bot_stats").pack()
    )
    
    webapp_button = InlineKeyboardButton(
        text="🌐 Настроить WebApp",
        callback_data=AdminCallback(action="setup_webapp").pack()
    )
    
    reload_button = InlineKeyboardButton(
        text="🔄 Перезагрузить настройки",
        callback_data=AdminCallback(action="reload_settings").pack()
    )
    
    # Собираем и возвращаем клавиатуру
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [max_win_button],
            [prizes_button],
            [giveaways_button],
            [add_channel_button],
            [list_channels_button],
            [stats_button],
            [webapp_button],
            [reload_button]
        ]
    )


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает инлайн-клавиатуру с кнопкой "Назад" для подразделов админ-панели
    
    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура с кнопкой "Назад"
    """
    back_button = InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=AdminCallback(action="back_to_menu").pack()
    )
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [back_button]
        ]
    ) 