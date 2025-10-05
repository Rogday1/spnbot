from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from pathlib import Path
import logging
import time
import random
import re

from src.database.db import get_session
from src.database.repositories import UserRepository, GameRepository, DailyStatsRepository, PrizeRepository
from src.config import settings
from src.utils.probability_manager import calculate_probabilities, select_winning_sector

# Получаем абсолютный путь до директории со статическими файлами
STATIC_DIR = Path(__file__).parent.parent / "static"

# Добавляем текущее время для предотвращения кеширования статических файлов
def get_cache_buster():
    """Возвращает текущее время в миллисекундах для предотвращения кеширования."""
    return str(int(time.time() * 1000))

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

# Новая модель для запроса на получение результата прокрутки перед анимацией
class SpinPredictionRequest(BaseModel):
    """Модель для запроса на получение результата прокрутки перед анимацией."""
    pass

class SpinResult(BaseModel):
    """Модель для ответа на запрос прокрутки."""
    success: bool = Field(..., description="Успешность операции")
    tickets: int = Field(..., description="Оставшееся количество билетов")
    result: Optional[str] = Field(None, description="Результат прокрутки")
    time_until_next_spin: Optional[str] = Field(None, description="Время до следующего бесплатного прокрута")
    message: Optional[str] = Field(None, description="Сообщение об ошибке или уведомление")
    prize: Optional[Dict[str, Any]] = Field(None, description="Информация о выигранном призе")
    is_win: bool = Field(False, description="Выигрыш или нет")
    win_amount: int = Field(0, description="Сумма выигрыша")

# Новая модель для ответа на запрос предсказания результата прокрутки
class SpinPredictionResult(BaseModel):
    """Модель для ответа на запрос предсказания результата прокрутки."""
    success: bool = Field(..., description="Успешность операции")
    result: str = Field(..., description="Предсказанный результат прокрутки")
    seed: int = Field(..., description="Seed для генератора случайных чисел")
    can_spin: bool = Field(..., description="Может ли пользователь крутить колесо")
    tickets: int = Field(..., description="Количество доступных билетов")
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
    
    # Читаем HTML файл
    html_path = STATIC_DIR / "game" / "spin_wheel.html"
    with open(html_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    
    # Заменяем версионные параметры на текущее время
    cache_buster = get_cache_buster()
    
    # Используем регулярное выражение для замены всех версионных параметров
    html_content = re.sub(r'\?v=\d+', f'?nocache={cache_buster}', html_content)
    
    # Добавляем параметр кеширования для всех ссылок на CSS и JS файлы, даже если у них нет параметра v
    html_content = re.sub(r'(href|src)="([^"]+\.(css|js))"', f'\\1="\\2?nocache={cache_buster}"', html_content)
    html_content = re.sub(r'(href|src)="([^"]+\.(css|js))\?v=\d+"', f'\\1="\\2?nocache={cache_buster}"', html_content)
    html_content = re.sub(r'(href|src)="([^"]+\.(css|js))\?nocache=\d+"', f'\\1="\\2?nocache={cache_buster}"', html_content)
    
    # Создаем ответ с HTML контентом
    response = HTMLResponse(content=html_content)
    
    # Добавляем заголовки для предотвращения кэширования
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return response

# Маршрут для статических файлов с предотвращением кеширования
@game_page_router.get("/static/game/{file_path:path}")
async def serve_static_file(file_path: str):
    """
    Обслуживает статические файлы с добавлением заголовков для предотвращения кеширования.
    
    Args:
        file_path (str): Путь к файлу относительно директории static/game
        
    Returns:
        FileResponse: Файл со специальными заголовками
    """
    full_path = STATIC_DIR / "game" / file_path
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    response = FileResponse(full_path)
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
    Подтверждает результат прокрутки колеса и обновляет данные пользователя.
    
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
        prize_repo = PrizeRepository(session)
        
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
        
        # Получаем результат из запроса
        client_result_value = int(spin_data.result)
        
        # Используем результат из запроса (предполагается, что он был получен из /spin/predict)
        result_value = client_result_value
        
        # В режиме отладки логируем информацию
        if settings.DEBUG:
            logging.debug(f"Подтверждение результата прокрутки для пользователя {user_id}: {result_value}")
        
        # Определяем, является ли это выигрышем
        is_win = result_value > 0
        win_amount = result_value if is_win else 0
        
        # Получаем информацию о призе, если это выигрыш
        prize_info = None
        if is_win:
            # Ищем приз с соответствующей стоимостью
            prizes = await prize_repo.get_active_prizes()
            matching_prize = None
            for prize in prizes:
                if prize.value == result_value:
                    matching_prize = prize
                    break
            
            if matching_prize:
                prize_info = {
                    "id": matching_prize.id,
                    "name": matching_prize.name,
                    "description": matching_prize.description,
                    "value": matching_prize.value,
                    "image_url": matching_prize.image_url
                }
        
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
        
        # Создаем запись об игре с информацией о призе
        prize_id = prize_info["id"] if prize_info else None
        await game_repo.create_game_with_prize(user_id, str(result_value), prize_id, is_win, win_amount)
        
        # Получаем обновленные данные пользователя
        updated_user = await user_repo.get_user_by_id(user_id)
        
        # Логируем успешную прокрутку
        if is_win:
            logging.info(f"Пользователь {user_id} успешно выполнил прокрутку и выиграл {result_value} (приз: {prize_info['name'] if prize_info else 'Неизвестный приз'})")
        else:
            logging.info(f"Пользователь {user_id} выполнил прокрутку, но не выиграл")
        
        elapsed_time = time.time() - start_time
        logging.debug(f"Время обработки запроса прокрутки: {elapsed_time:.2f} сек.")
        
        return SpinResult(
            success=True,
            tickets=updated_user.tickets,
            result=str(result_value),
            time_until_next_spin=updated_user.get_time_until_free_spin(),
            prize=prize_info,
            is_win=is_win,
            win_amount=win_amount
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

# Новый API-эндпоинт для получения результата прокрутки перед анимацией
@spin_router.post("/spin/predict/{user_id}", response_model=SpinPredictionResult)
async def predict_spin_result(
    user_id: int,
    request: SpinPredictionRequest = Body(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Определяет результат прокрутки колеса до начала анимации.
    
    Args:
        user_id (int): ID пользователя
        request (SpinPredictionRequest): Пустой запрос для совместимости с API
        session (AsyncSession): Сессия базы данных
    
    Returns:
        SpinPredictionResult: Предсказанный результат прокрутки и seed для анимации
    
    Raises:
        HTTPException: Ошибка при обработке запроса
    """
    try:
        user_repo = UserRepository(session)
        stats_repo = DailyStatsRepository(session)
        
        # Получаем пользователя
        user = await user_repo.get_user_by_id(user_id)
        if not user:
            logging.warning(f"Пользователь {user_id} не найден при попытке предсказания прокрутки колеса")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Проверяем, может ли пользователь крутить колесо
        can_spin = user.can_spin()
        
        # Если пользователь может получить бесплатный прокрут, отмечаем это
        if not can_spin and user.can_get_free_spin():
            can_spin = True
            message = "Доступен бесплатный прокрут"
        else:
            message = None
        
        # Если пользователь не может крутить колесо, возвращаем информацию об этом
        if not can_spin:
            return SpinPredictionResult(
                success=False,
                result="0",  # По умолчанию возвращаем 0
                seed=random.randint(1000, 9999),  # Случайный seed для анимации
                can_spin=False,
                tickets=user.tickets,
                message="Недостаточно билетов для прокрутки"
            )
        
        # Получаем текущий процент использованного дневного лимита
        win_percentage = await stats_repo.get_win_percentage()
        
        # Рассчитываем текущие вероятности для каждого сектора
        probabilities = calculate_probabilities(win_percentage)
        
        # Определяем результат на основе вероятностей
        result_value = select_winning_sector(probabilities)
        
        # Генерируем случайный seed для анимации
        seed = random.randint(1000, 9999)
        
        # В режиме отладки логируем информацию
        if settings.DEBUG:
            logging.debug(f"Предсказан результат прокрутки для пользователя {user_id}: {result_value}, seed: {seed}")
        
        return SpinPredictionResult(
            success=True,
            result=str(result_value),
            seed=seed,
            can_spin=True,
            tickets=user.tickets,
            message=message
        )
        
    except Exception as e:
        logging.exception(f"Ошибка при предсказании результата прокрутки: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# API для получения списка активных призов
@spin_router.get("/prizes", response_model=Dict[str, Any])
async def get_prizes(session: AsyncSession = Depends(get_session)):
    """
    Возвращает список активных призов.
    
    Args:
        session (AsyncSession): Сессия базы данных
    
    Returns:
        Dict[str, Any]: Список активных призов
    
    Raises:
        HTTPException: Ошибка при обработке запроса
    """
    try:
        prize_repo = PrizeRepository(session)
        prizes = await prize_repo.get_active_prizes()
        
        prizes_data = []
        for prize in prizes:
            prizes_data.append({
                "id": prize.id,
                "name": prize.name,
                "description": prize.description,
                "value": prize.value,
                "probability": prize.probability,
                "image_url": prize.image_url
            })
        
        return {
            "success": True,
            "prizes": prizes_data,
            "total": len(prizes_data)
        }
        
    except Exception as e:
        logging.exception(f"Ошибка при получении призов: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

# Объединяем роутеры для экспорта
router = APIRouter()
router.include_router(game_page_router)
router.include_router(spin_router) 