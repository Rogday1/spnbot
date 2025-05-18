from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from pathlib import Path
import logging
import time
import random

from src.database.db import get_session
from src.database.repositories import UserRepository, GameRepository, DailyStatsRepository
from src.config import settings
from src.utils.probability_manager import calculate_probabilities, select_winning_sector

# Получаем абсолютный путь до директории со статическими файлами
STATIC_DIR = Path(__file__).parent.parent / "static"

# Модели Pydantic для API
class SpinRequest(BaseModel):
    """Модель для запроса на прокрутку колеса."""
    result: str = Field(..., description="Результат прокрутки")
    
    @validator("result")
    def validate_result(cls, v):
        """Проверяет, что результат является допустимым числом."""
        try:
            # Преобразуем в строку, если пришло число
            if isinstance(v, (int, float)):
                v = str(int(v))
                
            # Преобразуем строку в число для проверки
            value = int(v)
            
            # Проверяем, что значение находится в допустимом диапазоне
            allowed_values = [0, 300, 500, 1000, 2000]
            if value not in allowed_values:
                raise ValueError(f"Недопустимое значение: {value}. Разрешены только {allowed_values}")
            
            # Возвращаем строковое представление
            return str(value)
        except ValueError as e:
            # Перехватываем ошибку преобразования и выдаем понятное сообщение
            if "invalid literal for int" in str(e):
                raise ValueError("Результат должен быть числом")
            # Пробрасываем остальные ошибки
            raise

class SpinResult(BaseModel):
    """Модель для ответа на запрос прокрутки."""
    success: bool = Field(..., description="Успешность операции")
    tickets: int = Field(..., description="Оставшееся количество билетов")
    result: Optional[str] = Field(None, description="Результат прокрутки")
    time_until_next_spin: Optional[str] = Field(None, description="Время до следующего бесплатного прокрута")
    message: Optional[str] = Field(None, description="Сообщение об ошибке или уведомление")

# Создаем роутер для game с пустым префиксом, чтобы корректно обрабатывать маршрут /game
game_page_router = APIRouter(tags=["game_page"])

# Создаем роутер для spin API с префиксом /api
spin_router = APIRouter(prefix="/api", tags=["game"])

# Маршрут для мини-приложения
@game_page_router.get("/game")
async def game_app(request: Request, t: Optional[int] = Query(None)):
    """
    Возвращает HTML-страницу мини-приложения.
    Параметр t используется для обхода кэширования.
    
    Args:
        request (Request): Объект запроса
        t (Optional[int]): Временная метка для обхода кэширования
    
    Returns:
        FileResponse: HTML-страница мини-приложения
    """
    # Логируем информацию о запросе в режиме отладки
    if settings.DEBUG:
        user_agent = request.headers.get("User-Agent", "Неизвестный")
        remote_addr = request.client.host if request.client else "Неизвестный"
        logging.debug(f"Запрос игры от {remote_addr}, User-Agent: {user_agent}")
    
    response = FileResponse(STATIC_DIR / "game" / "spin_wheel.html")
    
    # Добавляем заголовки для предотвращения кэширования
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return response

# API для прокрутки колеса
@spin_router.post("/spin/{user_id}", response_model=SpinResult)
async def spin_wheel(
    user_id: int, 
    spin_data: SpinRequest = Body(...),
    request: Request = None,
    session: AsyncSession = Depends(get_session)
):
    """
    Выполняет прокрутку колеса и возвращает результат.
    
    Args:
        user_id (int): ID пользователя
        spin_data (SpinRequest): Данные о прокрутке колеса
        request (Request): Объект запроса
        session (AsyncSession): Сессия базы данных
    
    Returns:
        SpinResult: Результат прокрутки
    
    Raises:
        HTTPException: Ошибка при обработке запроса
    """
    start_time = time.time()
    
    try:
        user_repo = UserRepository(session)
        game_repo = GameRepository(session)
        stats_repo = DailyStatsRepository(session)
        
        # Получаем пользователя
        user = await user_repo.get_user_by_id(user_id)
        if not user:
            logging.warning(f"Пользователь {user_id} не найден при попытке прокрутки колеса")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Проверяем, может ли пользователь крутить колесо
        if not user.can_spin():
            # Если пользователь может получить бесплатный прокрут, даем его
            if user.can_get_free_spin():
                user.add_ticket()
                await session.commit()
                logging.info(f"Пользователю {user_id} выдан бесплатный прокрут")
            else:
                # Иначе возвращаем сообщение о невозможности прокрутки
                logging.info(f"Пользователь {user_id} не может крутить колесо (нет билетов)")
                return SpinResult(
                    success=False,
                    tickets=user.tickets,
                    time_until_next_spin=user.get_time_until_free_spin(),
                    message="Недостаточно билетов для прокрутки"
                )
        
        # Получаем текущий процент использованного дневного лимита
        win_percentage = await stats_repo.get_win_percentage()
        
        # Рассчитываем текущие вероятности для каждого сектора
        probabilities = calculate_probabilities(win_percentage)
        
        # В режиме отладки логируем информацию о вероятностях
        if settings.DEBUG:
            logging.debug(f"Текущий процент использованного лимита: {win_percentage*100:.1f}%")
            logging.debug(f"Текущие вероятности: {probabilities}")
        
        # Проверяем, что результат не подделан
        client_result_value = int(spin_data.result)
        
        # Определяем результат на основе вероятностей
        server_result_value = select_winning_sector(probabilities)
        
        # В режиме отладки позволяем любой результат, иначе используем серверный
        if not settings.DEBUG:
            # Используем результат, определенный сервером
            result_value = server_result_value
            
            # Если клиентский результат не совпадает с серверным, логируем это
            if client_result_value != result_value:
                logging.warning(
                    f"Пользователь {user_id} отправил результат {client_result_value}, "
                    f"но сервер определил {result_value}"
                )
        else:
            # В режиме отладки используем клиентский результат
            result_value = client_result_value
        
        # Используем прокрут с проверенным результатом
        success = await user_repo.use_spin(user_id, result_value)
        if not success:
            logging.error(f"Не удалось выполнить прокрутку для пользователя {user_id}")
            return SpinResult(
                success=False,
                tickets=user.tickets,
                time_until_next_spin=user.get_time_until_free_spin(),
                message="Не удалось выполнить прокрутку"
            )
        
        # Обновляем статистику за день
        await stats_repo.update_daily_stats(result_value)
        
        # Создаем запись об игре
        await game_repo.create_game(user_id, str(result_value))
        
        # Получаем обновленные данные пользователя
        updated_user = await user_repo.get_user_by_id(user_id)
        
        # Логируем успешную прокрутку
        logging.info(f"Пользователь {user_id} успешно выполнил прокрутку и выиграл {result_value}")
        
        elapsed_time = time.time() - start_time
        logging.debug(f"Время обработки запроса прокрутки: {elapsed_time:.2f} сек.")
        
        return SpinResult(
            success=True,
            tickets=updated_user.tickets,
            result=str(result_value),
            time_until_next_spin=updated_user.get_time_until_free_spin()
        )
        
    except Exception as e:
        logging.exception(f"Ошибка при выполнении прокрутки колеса: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# Добавляем маршрут для получения информации о времени бесплатной прокрутки
@spin_router.get("/spin/timer/{user_id}", response_model=Dict[str, Any])
async def get_spin_timer(user_id: int, session: AsyncSession = Depends(get_session)):
    """
    Возвращает информацию о времени до следующего бесплатного прокрута.
    
    Args:
        user_id (int): ID пользователя
        session (AsyncSession): Сессия базы данных
    
    Returns:
        Dict[str, Any]: Информация о времени до следующего прокрута
    
    Raises:
        HTTPException: Ошибка при обработке запроса
    """
    try:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Проверяем, может ли пользователь получить бесплатный прокрут
        can_get_free = user.can_get_free_spin()
        
        return {
            "tickets": user.tickets,
            "can_get_free_spin": can_get_free,
            "time_until_next_spin": "00:00" if can_get_free else user.get_time_until_free_spin()
        }
        
    except Exception as e:
        logging.exception(f"Ошибка при получении таймера прокрутки: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# API для получения текущих вероятностей выигрыша
@spin_router.get("/spin/probabilities", response_model=Dict[str, Any])
async def get_probabilities(session: AsyncSession = Depends(get_session)):
    """
    Возвращает текущие вероятности выигрыша для каждого сектора.
    
    Args:
        session (AsyncSession): Сессия базы данных
    
    Returns:
        Dict[str, Any]: Информация о текущих вероятностях
    
    Raises:
        HTTPException: Ошибка при обработке запроса
    """
    try:
        stats_repo = DailyStatsRepository(session)
        
        # Получаем текущий процент использованного дневного лимита
        win_percentage = await stats_repo.get_win_percentage()
        
        # Получаем статистику за сегодня
        stats = await stats_repo.get_today_stats()
        
        # Рассчитываем текущие вероятности
        probabilities = calculate_probabilities(win_percentage)
        
        # Преобразуем вероятности в проценты для удобства чтения
        prob_percent = {str(k): f"{v*100:.1f}%" for k, v in probabilities.items()}
        
        # Получаем максимальный выигрыш за день
        max_win = settings.MAX_WIN_PER_DAY if hasattr(settings, 'MAX_WIN_PER_DAY') else 5000
        
        return {
            "daily_stats": {
                "total_win": stats.total_win,
                "spin_count": stats.spin_count,
                "max_win_per_day": max_win,
                "percentage_used": f"{win_percentage*100:.1f}%"
            },
            "probabilities": prob_percent
        }
        
    except Exception as e:
        logging.exception(f"Ошибка при получении вероятностей: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# Объединяем роутеры для экспорта
router = APIRouter()
router.include_router(game_page_router)
router.include_router(spin_router) 