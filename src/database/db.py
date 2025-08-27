from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text, inspect
import logging
import os
from sqlalchemy.sql import select

from src.config import settings


# Создаем базовый класс для моделей
Base = declarative_base()

# Константа для тестового пользователя
TEST_USER_ID = 123456789

# Создаем асинхронный движок для работы с PostgreSQL
async_database_url = settings.DATABASE_URL.replace('postgresql:', 'postgresql+asyncpg:')

engine = create_async_engine(
    async_database_url,
    echo=settings.DEBUG,
    future=True,
    pool_size=20,  # Увеличиваем размер пула соединений
    max_overflow=40,  # Максимальное количество дополнительных соединений
    pool_timeout=30,  # Тайм-аут ожидания соединения из пула
    pool_pre_ping=True,  # Проверка соединения перед использованием
    # Важно для PgBouncer (pool_mode transaction/statement): отключаем prepared statements
    connect_args={
        "statement_cache_size": 0,
    },
)

# Создаем фабрику сессий
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # Отключаем автоматический flush для более предсказуемого поведения
)

async def init_db():
    """
    Инициализирует базу данных и создает необходимые таблицы.
    """
    try:
        logging.info(f"Инициализация базы данных {settings.DATABASE_URL}")
        
        # Создаем таблицы и индексы
        async with engine.begin() as conn:
            # Создаем таблицы
            await conn.run_sync(Base.metadata.create_all)
            
            # Создаем индексы для оптимизации запросов
            await create_indexes(conn)
        
        # Удаляем тестового пользователя, если он существует
        async with async_session() as session:
            await remove_test_user(session)
            
        logging.info("База данных инициализирована успешно")
        return async_session
    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {e}")
        return async_session

async def update_tables_structure(session: AsyncSession):
    """
    Проверяет и обновляет структуру таблиц в базе данных,
    добавляя новые колонки, которые были добавлены в модели.
    
    Args:
        session (AsyncSession): Сессия базы данных
    """
    try:
        # Проверяем наличие нужных колонок в таблице users
        try:
            # Универсальный код для проверки колонок
            inspector = await session.run_sync(lambda sync_conn: inspect(sync_conn))
            columns = await session.run_sync(lambda sync_conn: inspector.get_columns('users'))
            column_names = [col['name'] for col in columns]
            
            has_nickname = 'nickname' in column_names
            has_nickname_webapp = 'nickname_webapp' in column_names
            has_is_admin = 'is_admin' in column_names
            has_referral_count = 'referral_count' in column_names
            has_referred_by = 'referred_by' in column_names
            
            # Добавляем отсутствующие колонки
            if not has_nickname:
                logging.info("Добавление колонки 'nickname' в таблицу 'users'")
                await session.execute(text("ALTER TABLE users ADD COLUMN nickname TEXT"))
                await session.commit()
                logging.info("Колонка 'nickname' успешно добавлена")
            
            if not has_nickname_webapp:
                logging.info("Добавление колонки 'nickname_webapp' в таблицу 'users'")
                await session.execute(text("ALTER TABLE users ADD COLUMN nickname_webapp TEXT"))
                await session.commit()
                logging.info("Колонка 'nickname_webapp' успешно добавлена")
                
            if not has_is_admin:
                logging.info("Добавление колонки 'is_admin' в таблицу 'users'")
                await session.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
                await session.commit()
                logging.info("Колонка 'is_admin' успешно добавлена")
                
            if not has_referral_count:
                logging.info("Добавление колонки 'referral_count' в таблицу 'users'")
                await session.execute(text("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0"))
                await session.commit()
                logging.info("Колонка 'referral_count' успешно добавлена")
                
            if not has_referred_by:
                logging.info("Добавление колонки 'referred_by' в таблицу 'users'")
                await session.execute(text("ALTER TABLE users ADD COLUMN referred_by BIGINT"))
                await session.commit()
                logging.info("Колонка 'referred_by' успешно добавлена")
                
        except Exception as e:
            logging.error(f"Ошибка при проверке/обновлении структуры таблиц: {e}")
            await session.rollback()
            raise
    except Exception as e:
        logging.error(f"Ошибка при обновлении структуры таблиц: {e}")
        raise

async def create_indexes(conn):
    """
    Создает индексы в базе данных для оптимизации запросов
    """
    try:
        # Индексы для таблицы пользователей
        # Базовые индексы для поиска пользователей
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"))
        
        # Индексы для лидерборда
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_spins_count ON users(spins_count DESC)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_spins_count_id ON users(spins_count DESC, id)"))
        
        # Индекс с условием для исключения тестового пользователя
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_spins_count_excl_test ON users(spins_count DESC) WHERE id != 123456789"))
        
        # Индексы для реферальной системы
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_referral_count ON users(referral_count DESC)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_referred_by_id ON users(referred_by, id)"))
        
        # Индексы для системы билетов
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_tickets ON users(tickets)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_last_free_spin ON users(last_free_spin)"))
        
        # Индексы для таблицы игр 
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_games_user_id ON games(user_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_games_created_at ON games(created_at DESC)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_games_user_id_created_at ON games(user_id, created_at DESC)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_games_result ON games(result)"))
        
        # Индексы для таблицы ежедневной статистики
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_daily_stats_total_win ON daily_stats(total_wins)"))
        
        logging.info("Индексы базы данных созданы успешно")
    except Exception as e:
        logging.warning(f"Ошибка при создании индексов: {e}")

async def get_session() -> AsyncSession:
    """
    Получение сессии базы данных.
    
    Yields:
        AsyncSession: Сессия для работы с базой данных
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def optimize_database():
    """
    Оптимизирует базу данных.
    Для PostgreSQL выполняет VACUUM ANALYZE.
    """
    logging.info("Запуск оптимизации базы данных...")
    
    async with async_session() as session:
        try:
            # Для PostgreSQL используем VACUUM ANALYZE
            await session.execute(text("VACUUM ANALYZE"))
            logging.info("Оптимизация PostgreSQL базы данных завершена")
            
        except Exception as e:
            logging.error(f"Ошибка при оптимизации базы данных: {e}")
            raise

async def remove_test_user(session: AsyncSession):
    """
    Удаляет тестового пользователя из БД, если он существует.
    """
    from src.database.models import User
    
    try:
        test_user = await session.execute(
            select(User).where(User.id == TEST_USER_ID)
        )
        test_user = test_user.scalar_one_or_none()
        
        if test_user:
            await session.delete(test_user)
            await session.commit()
            logging.info(f"Тестовый пользователь (ID: {TEST_USER_ID}) удален из базы данных")
    except Exception as e:
        logging.error(f"Ошибка при удалении тестового пользователя: {e}")
        await session.rollback()
