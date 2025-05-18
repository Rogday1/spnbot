import asyncio
import logging
import sys
import argparse
import os
from alembic.config import Config
from alembic import command


def run_migrations(upgrade=True, revision=None, sql=False):
    """
    Запускает миграции базы данных с использованием Alembic.
    
    Args:
        upgrade (bool): True для применения миграций, False для отката
        revision (str): Версия миграции (по умолчанию 'head' для upgrade и '-1' для downgrade)
        sql (bool): Выводить SQL вместо выполнения миграций
    """
    try:
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        
        logging.info("Запуск миграций базы данных с Alembic...")
        
        # Получаем абсолютный путь к alembic.ini
        alembic_ini_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alembic.ini')
        
        if not os.path.exists(alembic_ini_path):
            logging.error(f"Файл alembic.ini не найден по пути: {alembic_ini_path}")
            return False
        
        # Создаем конфигурацию Alembic
        alembic_cfg = Config(alembic_ini_path)
        
        if upgrade:
            # Применяем миграции
            target_revision = revision or "head"
            logging.info(f"Применение миграций до версии: {target_revision}")
            
            if sql:
                # Только вывод SQL
                command.upgrade(alembic_cfg, target_revision, sql=True)
            else:
                # Выполнение миграций
                command.upgrade(alembic_cfg, target_revision)
                
            logging.info("Миграции успешно применены")
        else:
            # Откатываем миграции
            target_revision = revision or "-1"
            logging.info(f"Откат миграций на {target_revision} версий назад")
            
            if sql:
                # Только вывод SQL
                command.downgrade(alembic_cfg, target_revision, sql=True)
            else:
                # Выполнение отката
                command.downgrade(alembic_cfg, target_revision)
                
            logging.info("Миграции успешно откачены")
            
        return True
        
    except Exception as e:
        logging.error(f"Ошибка при выполнении миграций: {e}")
        return False


if __name__ == "__main__":
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description="Управление миграциями базы данных")
    parser.add_argument("--downgrade", action="store_true", help="Откатить миграции")
    parser.add_argument("--revision", help="Версия миграции (по умолчанию 'head' для upgrade и '-1' для downgrade)")
    parser.add_argument("--sql", action="store_true", help="Только вывести SQL без выполнения миграций")
    args = parser.parse_args()
    
    # Запуск миграций
    success = run_migrations(
        upgrade=not args.downgrade,
        revision=args.revision,
        sql=args.sql
    )
    
    # Выход с соответствующим кодом
    sys.exit(0 if success else 1) 