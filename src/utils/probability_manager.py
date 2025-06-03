import logging
import random
from typing import Dict, List, Tuple, Any, Optional

# Базовые вероятности для каждого сектора (ключ - значение сектора, значение - базовая вероятность в %)
DEFAULT_PROBABILITIES = {
    0: 80,     # 70% вероятность выпадения 0
    300: 7,   # 7% вероятность выпадения 300
    500: 5,   # 5% вероятность выпадения 500
    1000: 4,   # 4% вероятность выпадения 1000
    2000: 4    # 4% вероятность выпадения 2000
}

# Максимальные вероятности для каждого сектора при достижении лимита
MAX_PROBABILITIES = {
    0: 90,     # 90% вероятность выпадения 0
    300: 5,    # 5% вероятность выпадения 300
    500: 3,    # 3% вероятность выпадения 500
    1000: 1,   # 1% вероятность выпадения 1000
    2000: 1    # 1% вероятность выпадения 2000
}


def calculate_probabilities(win_percentage: float) -> Dict[int, float]:
    """
    Рассчитывает текущие вероятности для каждого сектора на основе процента использованного лимита
    
    Args:
        win_percentage (float): Процент использованного дневного лимита (от 0.0 до 1.0)
        
    Returns:
        Dict[int, float]: Словарь с вероятностями для каждого сектора (ключ - значение сектора, значение - вероятность от 0.0 до 1.0)
    """
    try:
        # Ограничиваем процент от 0.0 до 1.0
        win_percentage = min(max(win_percentage, 0.0), 1.0)
        
        # Рассчитываем вероятности для каждого сектора
        probabilities = {}
        for sector, base_prob in DEFAULT_PROBABILITIES.items():
            # Получаем максимальную вероятность для сектора
            max_prob = MAX_PROBABILITIES.get(sector, base_prob)
            
            # Линейная интерполяция между базовой и максимальной вероятностью
            current_prob = base_prob + (max_prob - base_prob) * win_percentage
            
            # Сохраняем вероятность в формате от 0.0 до 1.0
            probabilities[sector] = current_prob / 100.0
            
        # Нормализуем вероятности, чтобы их сумма была равна 1.0
        total_prob = sum(probabilities.values())
        if total_prob > 0:
            for sector in probabilities:
                probabilities[sector] /= total_prob
                
        logging.debug(f"Рассчитаны вероятности при проценте {win_percentage*100:.1f}%: {probabilities}")
        return probabilities
    except Exception as e:
        logging.error(f"Ошибка при расчете вероятностей: {e}")
        # В случае ошибки возвращаем базовые вероятности
        default_probs = {k: v/100.0 for k, v in DEFAULT_PROBABILITIES.items()}
        total = sum(default_probs.values())
        return {k: v/total for k, v in default_probs.items()}


def select_winning_sector(probabilities: Dict[int, float]) -> int:
    """
    Выбирает выигрышный сектор на основе текущих вероятностей
    
    Args:
        probabilities (Dict[int, float]): Словарь с вероятностями для каждого сектора
        
    Returns:
        int: Значение выигрышного сектора
    """
    try:
        # Преобразуем словарь вероятностей в список кортежей (значение, вероятность)
        sectors = list(probabilities.items())
        
        # Разделяем значения и вероятности
        values = [sector[0] for sector in sectors]
        probs = [sector[1] for sector in sectors]
        
        # Выбираем случайный сектор с учетом вероятностей
        return random.choices(values, weights=probs, k=1)[0]
    except Exception as e:
        logging.error(f"Ошибка при выборе выигрышного сектора: {e}")
        # В случае ошибки возвращаем наиболее вероятный сектор (обычно 0)
        return max(probabilities.items(), key=lambda x: x[1])[0] 