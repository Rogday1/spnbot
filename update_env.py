#!/usr/bin/env python3
"""
Скрипт для обновления DATABASE_URL в файле .env
"""

import os
import re

def update_env_file():
    """Обновляет DATABASE_URL в файле .env"""
    env_file = '.env'
    
    if not os.path.exists(env_file):
        print(f"Файл {env_file} не найден!")
        return False
    
    # Читаем содержимое файла
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем DATABASE_URL на SQLite
    old_pattern = r'DATABASE_URL=.*'
    new_line = 'DATABASE_URL=sqlite+aiosqlite:///./spin_bot.db'
    
    if re.search(old_pattern, content):
        new_content = re.sub(old_pattern, new_line, content)
        print(f"Обновлен DATABASE_URL: {new_line}")
    else:
        # Если строка не найдена, добавляем её
        new_content = content + f'\n{new_line}'
        print(f"Добавлен DATABASE_URL: {new_line}")
    
    # Записываем обновленное содержимое
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Файл .env успешно обновлен!")
    return True

if __name__ == "__main__":
    update_env_file()
