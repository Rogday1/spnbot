from sqlalchemy import select, func, update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging
import asyncio
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError, StatementError

from src.database.models import User
from src.utils.cache import cached, cache
from src.config import settings


class UserRepository:
    """
    Репозиторий для работы с данными пользователей.
    Включает кэширование и оптимизированные запросы.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Инициализирует репозиторий с заданной сессией базы данных.
        
        Args:
            session (AsyncSession): Асинхронная сессия SQLAlchemy
        """
        self.session = session
        self.max_retries = 3  # Максимальное количество повторных попыток при ошибках
        self.retry_delay = 0.5  # Задержка между повторными попытками в секундах
    
    async def get_user(self, user_id: int) -> User:
        """
        Получает пользователя по ID или создает нового, если не существует.
        Также объединяет дублирующиеся записи с одинаковым ID.
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            User: Объект пользователя
        """
        # Пытаемся получить пользователя из кэша
        cache_key = f"user:{user_id}"
        cached_user = await cache.get(cache_key)
        
        if cached_user:
            return cached_user
        
        # Если нет в кэше, запрашиваем из БД и объединяем дублирующиеся записи
        retry_count = 0
        last_error = None
        
        while retry_count < self.max_retries:
            try:
                # Ищем все записи с указанным ID
                query = select(User).where(User.id == user_id)
                result = await self.session.execute(query)
                users = result.scalars().all()
                
                # Если нет ни одной записи, создаем нового пользователя
                if not users:
                    user = User(id=user_id)
                    # Устанавливаем начальное количество билетов из настроек
                    user.tickets = settings.INITIAL_TICKETS
                    self.session.add(user)
                    await self.session.commit()
                    await self.session.refresh(user)
                    
                    # Кэшируем нового пользователя на короткое время
                    await cache.set(cache_key, user, ttl=10)
                    
                    return user
                
                # Если есть несколько записей, объединяем данные
                if len(users) > 1:
                    logging.warning(f"Обнаружено {len(users)} дублирующихся записей для пользователя {user_id}")
                    
                    # Используем первую запись как основу и обновляем ее данными из других записей
                    main_user = users[0]
                    
                    # Собираем данные со всех записей
                    for user in users[1:]:
                        # Предпочитаем никнейм, установленный пользователем в Telegram
                        if user.nickname and not main_user.nickname:
                            main_user.nickname = user.nickname
                        
                        # Предпочитаем никнейм, установленный пользователем в веб-приложении
                        if user.nickname_webapp and not main_user.nickname_webapp:
                            main_user.nickname_webapp = user.nickname_webapp
                        
                        # Объединяем информацию о пользователе
                        if not main_user.first_name and user.first_name:
                            main_user.first_name = user.first_name
                        
                        if not main_user.last_name and user.last_name:
                            main_user.last_name = user.last_name
                        
                        if not main_user.username and user.username:
                            main_user.username = user.username
                        
                        # Берем максимальное количество прокрутов
                        main_user.spins_count = max(main_user.spins_count, user.spins_count)
                        
                        # Добавляем билеты, если они есть на других записях
                        main_user.tickets += user.tickets
                        
                        # Используем самое раннее время последнего бесплатного прокрута
                        if user.last_free_spin < main_user.last_free_spin:
                            main_user.last_free_spin = user.last_free_spin
                        
                        # Удаляем дублирующуюся запись
                        await self.session.delete(user)
                    
                    # Сохраняем объединенную запись
                    await self.update_user(main_user)
                    
                    # Кэшируем объединенного пользователя на короткое время
                    await cache.set(cache_key, main_user, ttl=10)
                    
                    return main_user
                
                # Если есть только одна запись, кэшируем и возвращаем ее
                user = users[0]
                await cache.set(cache_key, user, ttl=30)
                return user
                
            except (SQLAlchemyError, OperationalError) as e:
                last_error = e
                retry_count += 1
                logging.warning(f"Попытка {retry_count}/{self.max_retries} получения пользователя {user_id} завершилась ошибкой: {e}")
                
                # Сбрасываем сессию и ждем перед следующей попыткой
                await self.session.rollback()
                await asyncio.sleep(self.retry_delay * retry_count)  # Экспоненциальная задержка
                
            except Exception as e:
                logging.exception(f"Критическая ошибка при получении пользователя {user_id}: {e}")
                raise
        
        # Если все попытки завершились неудачей
        logging.error(f"Не удалось получить пользователя {user_id} после {self.max_retries} попыток: {last_error}")
        raise last_error or RuntimeError(f"Не удалось получить пользователя {user_id}")
    
    @cached(ttl=30)
    async def get_user_by_id(self, user_id: int) -> User:
        """
        Получает пользователя по ID с кэшированием результата.
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            User: Объект пользователя
        """
        return await self.get_user(user_id)
    
    async def update_user(self, user: User) -> User:
        """
        Обновляет данные пользователя в БД и инвалидирует кэш.
        Включает обработку конкурентных обновлений и повторные попытки при ошибках.
        
        Args:
            user (User): Объект пользователя для обновления
            
        Returns:
            User: Обновленный объект пользователя
        """
        retry_count = 0
        last_error = None
        
        while retry_count < self.max_retries:
            try:
                # Сохраняем версию данных перед обновлением
                old_tickets = user.tickets
                old_spins_count = user.spins_count
                
                # Обновляем пользователя
                self.session.add(user)
                await self.session.commit()
                await self.session.refresh(user)
                
                # Если обновление прошло успешно и данные изменились, инвалидируем кэш
                if old_tickets != user.tickets or old_spins_count != user.spins_count:
                    # Инвалидируем кэш для этого пользователя
                    cache_key = f"user:{user.id}"
                    await cache.delete(cache_key)
                    
                    # Также очищаем кэш для методов, которые могли кэшировать данного пользователя
                    cache_keys = [
                        f"get_user_by_id:{user.id}",
                        f"get_time_until_free_spin:{user.id}"
                    ]
                    
                    for key in cache_keys:
                        await cache.delete(key)
                    
                    # Очищаем кэш лидеров, так как данные пользователя могли измениться
                    await cache.delete("get_leaders")
                
                return user
                
            except IntegrityError as e:
                # Ошибка целостности данных (например, дублирование уникального ключа)
                logging.error(f"Ошибка целостности данных при обновлении пользователя {user.id}: {e}")
                await self.session.rollback()
                
                # В случае ошибки целостности, пытаемся получить свежую версию пользователя и слить изменения
                try:
                    # Получаем свежую версию пользователя из БД
                    fresh_query = select(User).where(User.id == user.id)
                    fresh_result = await self.session.execute(fresh_query)
                    fresh_user = fresh_result.scalar_one_or_none()
                    
                    if fresh_user:
                        # Сохраняем важные измененные данные
                        changed_data = {
                            'tickets': user.tickets,
                            'spins_count': user.spins_count,
                            'last_free_spin': user.last_free_spin,
                            'nickname': user.nickname,
                            'nickname_webapp': user.nickname_webapp
                        }
                        
                        # Обновляем только изменившиеся поля
                        for field, value in changed_data.items():
                            # Обновляем только если значение изменилось
                            if getattr(fresh_user, field) != value:
                                setattr(fresh_user, field, value)
                        
                        # Пытаемся сохранить слитые изменения
                        self.session.add(fresh_user)
                        await self.session.commit()
                        await self.session.refresh(fresh_user)
                        
                        # Инвалидируем кэш
                        await cache.delete(f"user:{user.id}")
                        return fresh_user
                    
                except Exception as inner_e:
                    logging.error(f"Ошибка при попытке слить изменения пользователя {user.id}: {inner_e}")
                
                # Если не удалось слить изменения, пробуем еще раз обновить исходного пользователя
                retry_count += 1
                await asyncio.sleep(self.retry_delay * retry_count)
                
            except (OperationalError, StatementError) as e:
                # Ошибки базы данных, которые можно повторить (блокировки, таймауты и т.д.)
                last_error = e
                retry_count += 1
                
                logging.warning(f"Попытка {retry_count}/{self.max_retries} обновления пользователя {user.id} завершилась ошибкой: {e}")
                await self.session.rollback()
                await asyncio.sleep(self.retry_delay * retry_count)
                
            except Exception as e:
                # Другие неожиданные ошибки
                logging.exception(f"Критическая ошибка при обновлении пользователя {user.id}: {e}")
                await self.session.rollback()
                raise
        
        # Если все попытки завершились неудачей
        logging.error(f"Не удалось обновить пользователя {user.id} после {self.max_retries} попыток: {last_error}")
        
        # Пытаемся восстановить исходное состояние пользователя
        try:
            # Получаем текущее состояние из БД, чтобы избежать рассинхронизации объекта
            query = select(User).where(User.id == user.id)
            result = await self.session.execute(query)
            db_user = result.scalar_one_or_none()
            
            if db_user:
                # Копируем состояние из БД в объект user
                user.tickets = db_user.tickets
                user.spins_count = db_user.spins_count
                user.nickname = db_user.nickname
                user.nickname_webapp = db_user.nickname_webapp
                user.last_free_spin = db_user.last_free_spin
        except Exception as e:
            logging.error(f"Ошибка при попытке восстановить состояние пользователя {user.id}: {e}")
        
        # Вызываем исключение с информацией об ошибке
        raise RuntimeError(f"Не удалось обновить пользователя {user.id} после нескольких попыток")
    
    async def update_user_batch(self, user_id: int, updates: dict) -> bool:
        """
        Обновляет данные пользователя, используя одну операцию SQL UPDATE.
        Это более эффективно для частичных обновлений, чем полная загрузка и сохранение объектов.
        Включает повторные попытки при ошибках базы данных.
        
        Args:
            user_id (int): ID пользователя
            updates (dict): Словарь с обновляемыми полями
            
        Returns:
            bool: True, если обновление выполнено успешно, иначе False
        """
        retry_count = 0
        last_error = None
        
        while retry_count < self.max_retries:
            try:
                # Проверяем корректность обновляемых полей
                valid_fields = {'username', 'first_name', 'last_name', 'nickname', 
                                'nickname_webapp', 'is_admin', 'spins_count', 'tickets', 
                                'last_free_spin', 'referral_count', 'referred_by'}
                
                # Фильтруем только допустимые поля
                valid_updates = {k: v for k, v in updates.items() if k in valid_fields}
                
                # Если нет допустимых полей для обновления, возвращаем False
                if not valid_updates:
                    logging.warning(f"Нет допустимых полей для обновления у пользователя {user_id}")
                    return False
                
                # Выполняем обновление
                stmt = update(User).where(User.id == user_id).values(**valid_updates)
                result = await self.session.execute(stmt)
                await self.session.commit()
                
                # Инвалидируем кэш для этого пользователя
                await cache.delete(f"user:{user_id}")
                await cache.delete(f"get_user_by_id:{user_id}")
                await cache.delete(f"get_time_until_free_spin:{user_id}")
                await cache.delete("get_leaders")
                
                return result.rowcount > 0
                
            except (OperationalError, StatementError) as e:
                last_error = e
                retry_count += 1
                
                logging.warning(f"Попытка {retry_count}/{self.max_retries} пакетного обновления пользователя {user_id} завершилась ошибкой: {e}")
                await self.session.rollback()
                await asyncio.sleep(self.retry_delay * retry_count)
                
            except Exception as e:
                logging.exception(f"Критическая ошибка при пакетном обновлении пользователя {user_id}: {e}")
                await self.session.rollback()
                return False
        
        # Если все попытки завершились неудачей
        logging.error(f"Не удалось выполнить пакетное обновление пользователя {user_id} после {self.max_retries} попыток: {last_error}")
        return False
    
    async def add_free_spin(self, user_id: int) -> bool:
        """
        Добавляет бесплатный прокрут пользователю, если он может его получить.
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            bool: True, если прокрут был добавлен, иначе False
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return False
            
            if user.can_get_free_spin():
                user.add_ticket()
                user.reset_free_spin_timer()
                await self.update_user(user)
                return True
            
            return False
            
        except Exception as e:
            logging.exception(f"Ошибка при добавлении бесплатного прокрута пользователю {user_id}: {e}")
            return False
    
    async def use_spin(self, user_id: int, win_value: int = 0) -> bool:
        """
        Использует прокрут, если у пользователя есть билет.
        
        Args:
            user_id (int): ID пользователя
            win_value (int): Выигранное значение, которое будет добавлено к балансу
            
        Returns:
            bool: True, если прокрут был успешно выполнен, иначе False
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user or not user.can_spin():
                return False
            
            # Сохраняем старые значения для фиксации в логах
            old_tickets = user.tickets
            old_spins_count = user.spins_count
            
            success = user.use_ticket(win_value)
            if success:
                try:
                    await self.update_user(user)
                    logging.info(f"Пользователь {user_id} использовал прокрут: билеты {old_tickets}->{user.tickets}, счет {old_spins_count}->{user.spins_count}")
                    return True
                except Exception as e:
                    logging.error(f"Ошибка при сохранении результатов прокрута для пользователя {user_id}: {e}")
                    # Восстанавливаем исходное состояние пользователя
                    user.tickets = old_tickets
                    user.spins_count = old_spins_count
                    return False
            
            return False
        
        except Exception as e:
            logging.exception(f"Ошибка при использовании прокрута пользователем {user_id}: {e}")
            return False
    
    @cached(ttl=10)
    async def get_time_until_free_spin(self, user_id: int) -> str:
        """
        Возвращает время до следующего бесплатного прокрута с кэшированием.
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            str: Время до следующего бесплатного прокрута в формате ЧЧ:ММ
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return "00:00"
        
        return user.get_time_until_free_spin()
        
    # Вспомогательная функция для получения отображаемого имени пользователя
    def _get_display_name(self, user_id, nickname_webapp, nickname, first_name):
        """
        Получает отображаемое имя пользователя.
        
        Args:
            user_id (int): ID пользователя
            nickname_webapp (str): Никнейм из веб-приложения
            nickname (str): Никнейм из Telegram
            first_name (str): Имя пользователя
            
        Returns:
            str: Отображаемое имя пользователя
        """
        # Используем никнейм из веб-приложения, если есть, иначе никнейм из Telegram или имя или ID
        return nickname_webapp or nickname or first_name or f"User{user_id}"

    async def get_leaders(self, limit: int = 10, current_user_id: int = None) -> list[dict]:
        """
        Получает список лидеров по количеству прокрутов (баланс).
        
        Args:
            limit (int): Максимальное количество лидеров
            current_user_id (int, optional): ID текущего пользователя, чтобы добавить его в список
            
        Returns:
            list[dict]: Список лидеров с их рангом, именем и счетом
        """
        # Для оптимизации кэшируем базовый список лидеров без текущего пользователя
        try:
            # Кэш только для базового списка лидеров (без текущего пользователя)
            cache_key = f"leaders_base:{limit}"
            leaders = None
            
            if not current_user_id:
                # Если не нужно добавлять текущего пользователя, можем использовать кэш напрямую
                cached_leaders = await cache.get(cache_key)
                if cached_leaders:
                    return cached_leaders
                
            # Запрос для получения топа пользователей
            query = select(
                User.id,
                func.max(User.spins_count).label("max_spins"),
                func.max(User.nickname_webapp).label("nickname_webapp"),
                func.max(User.nickname).label("nickname"),
                func.max(User.first_name).label("first_name")
            ).where(
                User.id != 123456789  # Исключаем тестовый ID из результатов
            ).group_by(User.id).order_by(func.max(User.spins_count).desc()).limit(limit)
            
            result = await self.session.execute(query)
            top_users = result.all()
            
            # Формируем список лидеров
            leaders = []
            
            # Отслеживаем, вошел ли текущий пользователь в топ
            current_user_in_top = False
            
            for idx, (user_id, spins_count, nickname_webapp, nickname, first_name) in enumerate(top_users, 1):
                # Если это текущий пользователь, отмечаем что он в топе
                if current_user_id and user_id == current_user_id:
                    current_user_in_top = True
                
                # Получаем отображаемое имя пользователя
                display_name = self._get_display_name(user_id, nickname_webapp, nickname, first_name)
                
                leaders.append({
                    "rank": idx,
                    "name": display_name,
                    "score": spins_count
                })
            
            # Если не запрашивали конкретного пользователя, кэшируем базовый список
            if not current_user_id:
                await cache.set(cache_key, leaders, ttl=60)  # Кэшируем на 1 минуту
                return leaders
            
            # Если текущий пользователь не вошел в топ, но его ID указан,
            # добавляем его в конец списка с его реальной позицией
            if current_user_id and not current_user_in_top:
                try:
                    # Получаем информацию о текущем пользователе
                    current_user = await self.get_user(current_user_id)
                    
                    if current_user:
                        # Считаем позицию пользователя в общем рейтинге
                        rank_query = select(func.count()).where(
                            User.spins_count > current_user.spins_count,
                            User.id != 123456789  # Исключаем тестовый ID
                        )
                        result = await self.session.execute(rank_query)
                        rank = result.scalar() + 1  # +1 потому что позиции начинаются с 1
                        
                        # Получаем отображаемое имя пользователя
                        display_name = self._get_display_name(
                            current_user_id, 
                            current_user.nickname_webapp, 
                            current_user.nickname, 
                            current_user.first_name
                        )
                        
                        # Добавляем пользователя в конец списка
                        leaders.append({
                            "rank": rank,
                            "name": display_name,
                            "score": current_user.spins_count
                        })
                except Exception as e:
                    logging.error(f"Ошибка при получении информации о текущем пользователе: {e}")
            
            return leaders
            
        except Exception as e:
            logging.exception(f"Ошибка при получении списка лидеров: {e}")
            return []
        
    async def update_nickname(self, user_id: int, nickname: str) -> bool:
        """
        Обновляет никнейм пользователя в веб-приложении.
        Включает валидацию данных для защиты от некорректного ввода.
        Использует оптимизированный запрос SQL UPDATE вместо загрузки и сохранения объектов.
        
        Args:
            user_id (int): ID пользователя
            nickname (str): Новый никнейм
            
        Returns:
            bool: True, если обновление выполнено успешно, иначе False
        """
        try:
            # Проверка на None или пустую строку
            if nickname is None or not nickname.strip():
                logging.warning(f"Попытка установить пустой никнейм для пользователя {user_id}")
                return False
            
            # Валидация данных - ограничение длины
            nickname = nickname.strip()
            if len(nickname) < 2:
                logging.warning(f"Никнейм слишком короткий для пользователя {user_id}: {nickname}")
                return False
            
            if len(nickname) > 32:
                # Обрезаем никнейм, если он слишком длинный
                nickname = nickname[:32]
                logging.warning(f"Никнейм был слишком длинный и обрезан для пользователя {user_id}")
            
            # Проверка на недопустимые символы (разрешаем буквы, цифры, подчеркивание, дефис и пробелы)
            import re
            if not re.match(r'^[\w\d\s\-\.]+$', nickname):
                # Очищаем от недопустимых символов
                nickname = re.sub(r'[^\w\d\s\-\.]', '', nickname)
                if not nickname:  # Если после очистки ничего не осталось
                    logging.warning(f"Никнейм содержал только недопустимые символы для пользователя {user_id}")
                    return False
                logging.warning(f"Никнейм содержал недопустимые символы и был очищен для пользователя {user_id}")
            
            # Дополнительная защита от SQL-инъекций (хотя ORM уже защищает)
            # Экранируем кавычки как дополнительная мера безопасности
            nickname = nickname.replace("'", "''").replace('"', '""')
            
            # Используем более эффективный запрос UPDATE
            stmt = update(User).where(User.id == user_id).values(nickname_webapp=nickname)
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            # Инвалидируем кэш для этого пользователя
            await cache.delete(f"user:{user_id}")
            await cache.delete(f"get_user_by_id:{user_id}")
            await cache.delete("get_leaders")
            
            logging.info(f"Никнейм пользователя {user_id} успешно обновлен на '{nickname}'")
            return result.rowcount > 0
            
        except Exception as e:
            logging.exception(f"Ошибка при обновлении никнейма пользователя {user_id}: {e}")
            await self.session.rollback()
            return False
        
    async def check_and_clean_duplicates(self) -> int:
        """
        Проверяет и объединяет дублирующиеся записи пользователей.
        Полезно для периодической очистки базы данных.
        
        Returns:
            int: Количество удаленных дублирующихся записей
        """
        try:
            # Получаем список ID пользователей с дублирующимися записями
            duplicate_query = select(User.id).group_by(User.id).having(func.count() > 1)
            result = await self.session.execute(duplicate_query)
            duplicate_ids = [row[0] for row in result]
            
            total_removed = 0
            
            # Для каждого ID с дубликатами вызываем метод get_user, который объединит записи
            for user_id in duplicate_ids:
                user = await self.get_user(user_id)
                if user:
                    # get_user уже выполнил объединение и вернул обновленного пользователя
                    total_removed += 1
            
            if total_removed > 0:
                logging.info(f"Очищено {total_removed} дублирующихся записей пользователей")
            
            return total_removed
            
        except Exception as e:
            logging.exception(f"Ошибка при очистке дубликатов пользователей: {e}")
            return 0

    async def get_referrals(self, user_id: int, limit: int = 10, offset: int = 0) -> list[dict]:
        """
        Получает список рефералов пользователя (пользователей, которых он пригласил)
        
        Args:
            user_id (int): ID пользователя
            limit (int, optional): Максимальное количество рефералов для получения
            offset (int, optional): Смещение для пагинации
            
        Returns:
            list[dict]: Список рефералов с их именем и датой регистрации
        """
        try:
            # Кэш для списка рефералов
            cache_key = f"referrals:{user_id}:{limit}:{offset}"
            cached_referrals = await cache.get(cache_key)
            
            if cached_referrals:
                return cached_referrals
            
            # Запрос для получения рефералов пользователя
            query = select(
                User.id,
                User.nickname_webapp,
                User.nickname,
                User.first_name,
                User.spins_count
            ).where(
                User.referred_by == user_id
            ).order_by(
                User.spins_count.desc()  # Сортируем по количеству спинов (балансу)
            ).limit(limit).offset(offset)
            
            result = await self.session.execute(query)
            referrals_data = result.all()
            
            # Формируем список рефералов
            referrals = []
            for ref_id, nickname_webapp, nickname, first_name, spins_count in referrals_data:
                # Получаем отображаемое имя пользователя
                display_name = self._get_display_name(ref_id, nickname_webapp, nickname, first_name)
                
                referrals.append({
                    "id": ref_id,
                    "name": display_name,
                    "balance": spins_count
                })
            
            # Кэшируем результат на короткое время
            await cache.set(cache_key, referrals, ttl=30)
            
            return referrals
            
        except Exception as e:
            logging.exception(f"Ошибка при получении рефералов пользователя {user_id}: {e}")
            return []

    async def count_referrals(self, user_id: int) -> int:
        """
        Подсчитывает общее количество рефералов пользователя
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            int: Общее количество рефералов
        """
        try:
            # Используем значение из кэша, если есть
            cache_key = f"referral_count:{user_id}"
            cached_count = await cache.get(cache_key)
            
            if cached_count is not None:
                return cached_count
            
            # Иначе делаем запрос к БД
            query = select(func.count()).where(User.referred_by == user_id)
            result = await self.session.execute(query)
            count = result.scalar() or 0
            
            # Кэшируем результат
            await cache.set(cache_key, count, ttl=60)
            
            return count
            
        except Exception as e:
            logging.exception(f"Ошибка при подсчете рефералов пользователя {user_id}: {e}")
            return 0

    async def get_referrer(self, user_id: int) -> dict:
        """
        Получает информацию о пользователе, который пригласил указанного пользователя
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            dict: Информация о реферере или None, если пользователь не был приглашен
        """
        try:
            # Получаем текущего пользователя
            user = await self.get_user(user_id)
            if not user or not user.referred_by:
                return None
            
            # Получаем информацию о реферере
            referrer_id = user.referred_by
            referrer = await self.get_user(referrer_id)
            
            if not referrer:
                return None
            
            # Формируем и возвращаем информацию о реферере
            return {
                "id": referrer.id,
                "name": self._get_display_name(
                    referrer.id, 
                    referrer.nickname_webapp, 
                    referrer.nickname, 
                    referrer.first_name
                )
            }
            
        except Exception as e:
            logging.exception(f"Ошибка при получении информации о реферере пользователя {user_id}: {e}")
            return None

    async def get_referral_stats(self, user_id: int) -> dict:
        """
        Получает статистику по рефералам для указанного пользователя
        
        Args:
            user_id (int): ID пользователя
            
        Returns:
            dict: Статистика по рефералам
        """
        try:
            # Используем кэш для статистики
            cache_key = f"referral_stats:{user_id}"
            cached_stats = await cache.get(cache_key)
            
            if cached_stats:
                return cached_stats
            
            # Получаем общее количество рефералов
            total_referrals = await self.count_referrals(user_id)
            
            # Получаем пять самых прибыльных рефералов (с наибольшим балансом)
            top_referrals_query = select(
                User.id,
                User.spins_count,
                User.nickname_webapp,
                User.nickname,
                User.first_name
            ).where(
                User.referred_by == user_id
            ).order_by(
                User.spins_count.desc()
            ).limit(5)
            
            result = await self.session.execute(top_referrals_query)
            top_referrals_data = result.all()
            
            # Формируем список для топ рефералов
            top_referrals = []
            for ref_id, spins_count, nickname_webapp, nickname, first_name in top_referrals_data:
                # Получаем отображаемое имя пользователя
                display_name = self._get_display_name(ref_id, nickname_webapp, nickname, first_name)
                
                top_referrals.append({
                    "id": ref_id,
                    "name": display_name,
                    "balance": spins_count
                })
            
            # Собираем полную статистику
            stats = {
                "total_referrals": total_referrals,
                "top_referrals": top_referrals
            }
            
            # Кэшируем статистику на некоторое время
            await cache.set(cache_key, stats, ttl=300)  # 5 минут
            
            return stats
            
        except Exception as e:
            logging.exception(f"Ошибка при получении статистики по рефералам для пользователя {user_id}: {e}")
            return {
                "total_referrals": 0,
                "top_referrals": []
            } 