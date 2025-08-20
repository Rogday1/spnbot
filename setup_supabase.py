#!/usr/bin/env python3
"""
Скрипт для настройки Supabase в проекте
"""

import os
import re

def create_env_file():
    """Создает файл .env с настройками для Supabase"""
    
    print("=== Настройка Supabase для Telegram Bot ===")
    print()
    
    # Запрашиваем данные у пользователя
    bot_token = input("Введите BOT_TOKEN от @BotFather: ").strip()
    
    print("\nДля WEBAPP_PUBLIC_URL:")
    print("1. Если у вас есть домен - введите его (например: https://mydomain.com)")
    print("2. Если нет - оставьте пустым (нажмите Enter)")
    webapp_url = input("WEBAPP_PUBLIC_URL: ").strip()
    
    print("\n=== Данные от Supabase ===")
    print("1. Откройте https://supabase.com/dashboard")
    print("2. Выберите ваш проект")
    print("3. Перейдите в Settings → Database")
    print("4. Скопируйте строку подключения из секции 'Connection string'")
    print()
    
    database_url = input("Вставьте строку подключения к Supabase: ").strip()
    
    # Создаем содержимое файла .env
    env_content = f"""# Telegram Bot Configuration
BOT_TOKEN={bot_token}

# WebApp Configuration
WEBAPP_PUBLIC_URL={webapp_url}

# Supabase Database Configuration
DATABASE_URL={database_url}

# Debug mode
DEBUG=false
"""
    
    # Записываем файл .env
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print("\n✅ Файл .env успешно создан!")
        print("\nСодержимое файла:")
        print("-" * 50)
        print(env_content)
        print("-" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при создании файла .env: {e}")
        return False

def update_existing_env():
    """Обновляет существующий файл .env"""
    
    if not os.path.exists('.env'):
        print("Файл .env не найден. Создаем новый...")
        return create_env_file()
    
    print("Файл .env найден. Обновляем DATABASE_URL...")
    
    # Читаем существующий файл
    with open('.env', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n=== Данные от Supabase ===")
    print("1. Откройте https://supabase.com/dashboard")
    print("2. Выберите ваш проект")
    print("3. Перейдите в Settings → Database")
    print("4. Скопируйте строку подключения из секции 'Connection string'")
    print()
    
    database_url = input("Вставьте строку подключения к Supabase: ").strip()
    
    # Обновляем или добавляем DATABASE_URL
    if 'DATABASE_URL=' in content:
        # Заменяем существующий
        new_content = re.sub(r'DATABASE_URL=.*', f'DATABASE_URL={database_url}', content)
    else:
        # Добавляем новый
        new_content = content + f'\nDATABASE_URL={database_url}'
    
    # Записываем обновленный файл
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("\n✅ Файл .env успешно обновлен!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при обновлении файла .env: {e}")
        return False

def main():
    """Основная функция"""
    
    print("🚀 Настройка Supabase для Telegram Bot")
    print("=" * 50)
    
    choice = input("Выберите действие:\n1. Создать новый файл .env\n2. Обновить существующий файл .env\nВведите 1 или 2: ").strip()
    
    if choice == '1':
        success = create_env_file()
    elif choice == '2':
        success = update_existing_env()
    else:
        print("Неверный выбор!")
        return
    
    if success:
        print("\n🎉 Настройка завершена!")
        print("\nСледующие шаги:")
        print("1. Убедитесь, что в файле .env указан правильный BOT_TOKEN")
        print("2. Проверьте, что DATABASE_URL от Supabase корректный")
        print("3. Запустите проект командой: python main.py")
        print("\nЕсли возникнут ошибки, проверьте:")
        print("- Правильность BOT_TOKEN")
        print("- Доступность базы данных Supabase")
        print("- Настройки сети (порт 6543 должен быть доступен)")

if __name__ == "__main__":
    main()
