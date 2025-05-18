// Объект для кэширования DOM-элементов
const DOM = {};

// Объект для хранения состояния приложения
const state = {
    points: 0,
    isSpinning: false,
    tickets: 0,
    userId: null,
    timerInterval: null,
    freeTicketTimerId: null,
    freeTicketTimeLeft: 0,
    isFreeTicketTimerActive: false
};

document.addEventListener('DOMContentLoaded', () => {
    // Кэшируем все DOM-элементы при загрузке страницы
    cacheDOM();
    
    // Значения для сегментов колеса (все сегменты одного основного цвета)
    const sectors = [
        { value: 300, color: '#C4B5FD' },  // Светло-фиолетовый
        { value: 0, color: '#4C1D95' },    // Тёмно-фиолетовый
        { value: 1000, color: '#C4B5FD' }, // Светло-фиолетовый
        { value: 0, color: '#4C1D95' },    // Тёмно-фиолетовый
        { value: 2000, color: '#C4B5FD' }, // Светло-фиолетовый
        { value: 0, color: '#4C1D95' },    // Тёмно-фиолетовый
        { value: 300, color: '#C4B5FD' },  // Светло-фиолетовый
        { value: 0, color: '#4C1D95' },    // Тёмно-фиолетовый
        { value: 500, color: '#C4B5FD' },  // Светло-фиолетовый
        { value: 0, color: '#4C1D95' },    // Тёмно-фиолетовый
        { value: 300, color: '#C4B5FD' },  // Светло-фиолетовый
        { value: 0, color: '#4C1D95' },    // Тёмно-фиолетовый
    ];
    
    // Инициализация приложения
    initApp();
    
    // Функция для кэширования всех DOM-элементов
    function cacheDOM() {
        // Получаем элементы с помощью селекторов и сохраняем их в объекте DOM
        ['wheel', 'spin-button', 'points', 'win-message', 'win-amount', 'ok-button', 
         'referral-link', 'copy-link', 'tickets-count', 'timer', 'current-nickname', 
         'change-nickname-btn', 'nickname-modal', 'close-nickname-modal', 'nickname-form', 
         'nickname-input', 'nickname-error'].forEach(id => {
            DOM[id.replace(/-/g, '')] = document.getElementById(id);
        });

        // Получаем группы элементов
        DOM.navItems = document.querySelectorAll('.nav-item');
        DOM.tabContents = document.querySelectorAll('.tab-content');
    }
    
    // Функция инициализации приложения
    function initApp() {
        // Получаем ID пользователя из URL или хранилища
        state.userId = getUserId();
        
        if (!state.userId) {
            showError("Не удалось получить идентификатор пользователя");
            return;
        }
        
        // Инициализируем приложение параллельно
        Promise.all([
            fetchUserData(),
            fetchLeaders()
        ]).catch(error => {
            console.error("Ошибка при инициализации приложения:", error);
        });
        
        // Очищаем колесо перед созданием нового
        if (DOM.wheel) DOM.wheel.innerHTML = '';
        
        // Создаем колесо
        createWheel();
        
        // Настройка обработчиков событий
        setupEventListeners();
        
        // Запускаем таймер обновления времени до следующего бесплатного прокрута
        startTimer();
    }
    
    // Настройка всех обработчиков событий
    function setupEventListeners() {
        // Навигация по вкладкам
        DOM.navItems.forEach(item => {
            item.addEventListener('click', () => {
                const tabId = item.getAttribute('data-tab');
                
                // Обновляем активный элемент меню
                DOM.navItems.forEach(navItem => navItem.classList.remove('active'));
                item.classList.add('active');
                
                // Показываем соответствующую вкладку
                DOM.tabContents.forEach(tab => {
                    const isVisible = tab.id === tabId;
                    tab.style.display = isVisible ? 'block' : 'none';
                    
                    // Если открыта вкладка лидеров, обновляем данные
                    if (isVisible && tabId === 'tab-leaders') {
                        fetchLeaders();
                    }
                });
            });
        });
        
        // Копирование реферальной ссылки
        if (DOM.copylink) {
            DOM.copylink.addEventListener('click', () => {
                DOM.referrallink.select();
                DOM.referrallink.setSelectionRange(0, 99999); // Для мобильных устройств
                
                navigator.clipboard.writeText(DOM.referrallink.value)
                    .then(() => {
                        const originalIcon = DOM.copylink.innerHTML;
                        DOM.copylink.innerHTML = '<span class="material-icons-round">check</span>';
                        
                        setTimeout(() => {
                            DOM.copylink.innerHTML = originalIcon;
                        }, 2000);
                    })
                    .catch(err => {
                        console.error('Ошибка при копировании текста: ', err);
                    });
            });
        }
        
        // Настройка формы никнейма
        if (DOM.changenicknamebtn) {
            DOM.changenicknamebtn.addEventListener('click', showNicknameModal);
        }
        
        if (DOM.closenicknamebtn) {
            DOM.closenicknamebtn.addEventListener('click', hideNicknameModal);
        }
        
        window.addEventListener('click', (event) => {
            if (event.target === DOM.nicknamemodal) {
                hideNicknameModal();
            }
        });
        
        if (DOM.nicknameform) {
            DOM.nicknameform.addEventListener('submit', handleNicknameSubmit);
        }
        
        // Настройка кнопки вращения
        if (DOM.spinbutton) {
            DOM.spinbutton.addEventListener('click', handleSpin);
        }
        
        // Закрытие сообщения о выигрыше
        if (DOM.okbutton) {
            DOM.okbutton.addEventListener('click', () => {
                DOM.winmessage.classList.remove('active');
                fetchUserData();
                DOM.spinbutton.disabled = state.tickets <= 0;
            });
        }
    }
    
    // Обработчик отправки формы никнейма
    async function handleNicknameSubmit(event) {
        event.preventDefault();
        
        const nickname = DOM.nicknameinput.value.trim();
        const currentUserId = getUserId();
        
        // Валидация никнейма на клиенте
        if (nickname.length < 3) {
            showNicknameError("Никнейм должен содержать минимум 3 символа");
            return;
        }
        
        if (nickname.length > 20) {
            showNicknameError("Никнейм должен содержать максимум 20 символов");
            return;
        }
        
        try {
            const response = await fetch(`/api/user/${currentUserId}/update-nickname`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ nickname }),
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                showNicknameError(errorData.detail || "Ошибка при обновлении никнейма");
                return;
            }
            
            const data = await response.json();
            DOM.currentnickname.textContent = data.nickname_webapp || data.nickname;
            hideNicknameModal();
            fetchLeaders();
        } catch (error) {
            console.error("Ошибка при отправке никнейма:", error);
            showNicknameError("Не удалось сохранить никнейм. Попробуйте позже.");
        }
    }
    
    // Обработчик нажатия на кнопку "Крутить"
    function handleSpin() {
        if (state.isSpinning || state.tickets <= 0) return;
        
        state.isSpinning = true;
        DOM.spinbutton.disabled = true;
        
        // Выбираем случайный сегмент для выигрыша
        const segmentCount = sectors.length;
        const segmentAngle = 360 / segmentCount;
        const winningSegmentIndex = Math.floor(Math.random() * segmentCount);
        const winningValue = sectors[winningSegmentIndex].value;
        
        // Вычисляем угол для остановки колеса
        const stopAngle = segmentAngle * winningSegmentIndex + segmentAngle / 2;
        
        // Добавляем полные обороты для эффектности (5-7 оборотов)
        const rotations = 5 + Math.floor(Math.random() * 3);
        const fullRotationsAngle = rotations * 360;
        
        // Конечный угол: полные обороты + угол до целевого сегмента
        const spinAngle = -(fullRotationsAngle + stopAngle);
        
        // Уменьшаем количество билетов в интерфейсе
        state.tickets--;
        if (DOM.ticketscount) {
            DOM.ticketscount.textContent = state.tickets;
        }
        
        // Получаем маркер (стрелку)
        const marker = document.querySelector('.wheel-marker');
        if (marker) {
            // Добавляем класс для состояния вращения
            marker.classList.add('spinning');
        }
        
        // Анимируем вращение колеса
        const svg = DOM.wheel.querySelector('svg');
        svg.style.transition = 'transform 6s cubic-bezier(0.32, 0.64, 0.23, 1)';
        svg.style.transform = `rotate(${spinAngle}deg)`;
        
        // Короткий звуковой сигнал при начале вращения (если поддерживается)
        try {
            const startSound = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAAABMYXZjNTguMTQuMTAwAAA=');
            startSound.play().catch(() => {});
        } catch(e) {}
        
        // Получаем выигрыш с небольшой задержкой
        setTimeout(() => {
            setTimeout(async () => {
                // Отправляем результат на сервер
                console.log(`Отправляем результат: ${winningValue}, тип: ${typeof winningValue}`);
                const result = await sendSpinResult(winningValue);
                
                // Останавливаем анимацию стрелки
                if (marker) {
                    marker.classList.remove('spinning');
                }
                
                if (result.success) {
                    // Обновляем данные пользователя
                    await fetchUserData();
                    
                    // Показываем сообщение о выигрыше
                    DOM.winamount.textContent = winningValue;
                    DOM.winmessage.classList.add('active');
                    
                    // Обновляем отображение баланса
                    if (DOM.points) {
                        DOM.points.textContent = state.points;
                    }
                    
                    // Обновляем интерфейс с новыми данными
                    state.tickets = result.tickets;
                    if (DOM.ticketscount) {
                        DOM.ticketscount.textContent = state.tickets;
                    }
                    
                    // Обновляем таймер
                    if (DOM.timer && result.time_until_next_spin) {
                        DOM.timer.textContent = result.time_until_next_spin;
                    }
                    
                    console.log(`Выигрыш: ${winningValue}, Новый баланс: ${state.points}`);
                } else {
                    // Показываем сообщение об ошибке
                    showError(result.message || "Произошла ошибка при сохранении результата");
                }
                
                state.isSpinning = false;
                
                // Разблокируем кнопку, если еще есть билеты
                if (DOM.spinbutton) {
                    DOM.spinbutton.disabled = state.tickets <= 0;
                }
                
                // Звуковой сигнал победы (если поддерживается)
                try {
                    const winSound = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAAABMYXZjNTguMTQuMTAwAAA=');
                    winSound.play().catch(() => {});
                } catch(e) {}
                
                // Добавляем проверку билетов и обновление таймера после прокрутки
                checkTicketsAndUpdateTimer();
            }, 500);
        }, 6000);
    }
    
    // Функция для получения ID пользователя
    function getUserId() {
        // Сначала пытаемся получить ID из Telegram WebApp, так как это наиболее достоверный источник
        let id = null;
        
        try {
            if (window.Telegram && window.Telegram.WebApp) {
                // Проверяем, что initData не пустой, что означает, что WebApp запущен из Telegram
                if (window.Telegram.WebApp.initData) {
                    // Проверяем подлинность данных
                    const validationResult = validateTelegramWebAppData(window.Telegram.WebApp.initData);
                    
                    if (!validationResult.valid) {
                        console.error("Ошибка валидации данных Telegram WebApp:", validationResult.error);
                        showError("Ошибка аутентификации. Пожалуйста, перезапустите приложение.");
                        return null;
                    }
                    
                    const webAppUser = window.Telegram.WebApp.initDataUnsafe.user;
                    if (webAppUser && webAppUser.id) {
                        id = webAppUser.id;
                        console.log("Получен ID из Telegram WebApp:", id);
                        
                        // Устанавливаем цвета в соответствии с темой Telegram
                        if (window.Telegram.WebApp.colorScheme) {
                            document.documentElement.setAttribute('data-theme', window.Telegram.WebApp.colorScheme);
                        }
                        
                        // Сообщаем Telegram, что приложение готово
                        window.Telegram.WebApp.ready();
                        
                        // Растягиваем WebApp на весь экран
                        window.Telegram.WebApp.expand();
                        
                        // Если получили ID из Telegram, сохраняем его и возвращаем сразу
                        if (id) {
                            localStorage.setItem('user_id', id);
                            return id;
                        }
                    }
                }
            }
        } catch (e) {
            console.error("Ошибка при получении ID пользователя из Telegram WebApp:", e);
        }
        
        // Если не удалось получить из Telegram, проверяем сохраненный ID
        let savedId = localStorage.getItem('user_id');
        if (savedId) {
            console.log("Использован сохраненный ID:", savedId);
            return savedId;
        }
        
        // Если нет сохраненного ID, пробуем из URL параметров
        const urlParams = new URLSearchParams(window.location.search);
        id = urlParams.get('user_id');
        if (id) {
            console.log("Получен ID из URL параметров:", id);
            localStorage.setItem('user_id', id);
            return id;
        }
        
        // Если все методы не сработали, возвращаем null - пользователь должен авторизоваться
        console.warn("Не удалось получить ID пользователя, авторизация необходима");
        return null;
    }
    
    // Функция для валидации данных Telegram WebApp
    function validateTelegramWebAppData(initData) {
        try {
            // Базовая проверка формата данных
            if (!initData || typeof initData !== 'string') {
                return { valid: false, error: "Данные инициализации отсутствуют или имеют неверный формат" };
            }
            
            // Разбираем параметры из initData
            const params = new URLSearchParams(initData);
            
            // В режиме разработки или тестирования пропускаем строгую проверку
            if (window.location.hostname === 'localhost' || 
                window.location.hostname === '127.0.0.1' || 
                !params.get('hash')) {
                console.log("Режим разработки: пропускаем проверку данных Telegram WebApp");
                return { valid: true };
            }
            
            // Проверяем наличие hash для предотвращения подделки
            if (!params.get('hash')) {
                return { valid: false, error: "Отсутствует hash в данных инициализации" };
            }
            
            // Проверка auth_date (не должна быть слишком устаревшей)
            const authDate = parseInt(params.get('auth_date') || '0');
            const currentTime = Math.floor(Date.now() / 1000);
            
            // В продакшене увеличиваем допустимую разницу до 24 часов
            const maxTimeDiff = 86400; // 24 часа
            
            if (currentTime - authDate > maxTimeDiff) {
                return { valid: false, error: "Данные авторизации устарели" };
            }
            
            // Если данные прошли все проверки на клиенте, 
            // остальную проверку выполнит сервер, где есть BOT_TOKEN
            return { valid: true };
            
        } catch (error) {
            console.error("Ошибка при валидации данных Telegram WebApp:", error);
            return { valid: false, error: "Внутренняя ошибка валидации" };
        }
    }
    
    // Оптимизированная функция для HTTP-запросов с кэшированием и повторными попытками
    async function makeApiRequest(endpoint, method = 'GET', body = null, retries = 2) {
        try {
            // Получаем актуальный ID пользователя
            const currentUserId = state.userId || getUserId();
            
            if (!currentUserId && endpoint.includes('${currentUserId}')) {
                throw new Error("Не удалось аутентифицировать пользователя");
            }
            
            // Формируем полный URL
            const url = endpoint.startsWith('/') 
                ? endpoint.replace(/\${currentUserId}/g, currentUserId)
                : `/${endpoint}`.replace(/\${currentUserId}/g, currentUserId);
            
            // Добавляем инициализационные данные в запрос для проверки на сервере
            const headers = {
                'Content-Type': 'application/json',
                'Cache-Control': method === 'GET' ? 'max-age=60' : 'no-cache'
            };
            
            // Если есть данные initData из Telegram, добавляем их для валидации на сервере
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
                headers['X-Telegram-Init-Data'] = window.Telegram.WebApp.initData;
            }
            
            const options = {
                method,
                headers
            };
            
            if (body) {
                options.body = JSON.stringify(body);
            }
            
            const response = await fetch(url, options);
            
            if (!response.ok) {
                if (response.status === 401) {
                    showError("Ошибка аутентификации. Пожалуйста, перезапустите приложение.");
                    throw new Error("Ошибка аутентификации");
                }
                
                // Для ошибок сети и 5xx ошибок пробуем повторить запрос
                if ((response.status >= 500 || !response.status) && retries > 0) {
                    console.log(`Повторная попытка запроса к ${url}, осталось попыток: ${retries}`);
                    // Экспоненциальная задержка перед повторной попыткой
                    await new Promise(resolve => setTimeout(resolve, 1000 * (3 - retries)));
                    return makeApiRequest(endpoint, method, body, retries - 1);
                }
                
                throw new Error(`Ошибка HTTP: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`Ошибка при выполнении запроса к ${endpoint}:`, error);
            throw error;
        }
    }
    
    // Функция для получения данных пользователя
    async function fetchUserData() {
        try {
            const userData = await makeApiRequest(`/api/user/${state.userId || getUserId()}`);
            
            // Сохраняем предыдущее значение билетов для проверки изменений
            const previousTickets = state.tickets;
            
            // Обновляем состояние приложения
            state.tickets = userData.tickets || 0;
            state.points = userData.spins_count || 0;
            
            console.log("Получены данные пользователя. Билетов:", state.tickets, "Было:", previousTickets);
            
            // Проверяем, изменилось ли количество билетов
            const ticketsChanged = previousTickets !== state.tickets;
            
            // Проверяем, нужно ли запустить или остановить таймер до бесплатного билета
            if (userData.time_until_free_ticket_seconds !== undefined) {
                state.freeTicketTimeLeft = userData.time_until_free_ticket_seconds;
                
                console.log("Время до бесплатного билета:", state.freeTicketTimeLeft);
                
                // Если у пользователя есть билеты, останавливаем таймер 
                // вне зависимости от предыдущего состояния
                if (state.tickets > 0) {
                    if (state.isFreeTicketTimerActive) {
                        console.log("В fetchUserData: у пользователя есть билеты, останавливаем таймер");
                        
                        clearInterval(state.freeTicketTimerId);
                        state.freeTicketTimerId = null;
                        state.isFreeTicketTimerActive = false;
                        state.freeTicketTimeLeft = 0;
                    }
                    
                    // Устанавливаем текст таймера на нулевое значение и плавно скрываем таймер
                    if (DOM.timer) {
                        DOM.timer.textContent = "00:00";
                        DOM.timer.classList.remove('pulsing');
                        
                        // Плавно скрываем таймер
                        if (DOM.timer.parentElement) {
                            DOM.timer.parentElement.classList.add('hidden-timer');
                            DOM.timer.parentElement.classList.remove('active-timer');
                            DOM.timer.parentElement.classList.remove('timer-appearing');
                        }
                    }
                } 
                // Если у пользователя 0 билетов, запускаем или обновляем таймер
                else if (state.tickets === 0) {
                    checkFreeTicketTimer();
                }
            }
            
            // Если количество билетов изменилось, проверяем и обновляем состояние таймера
            if (ticketsChanged) {
                console.log("Количество билетов изменилось, проверяем таймер");
                checkTicketsAndUpdateTimer();
            }
            
            // Отображаем никнейм пользователя - сначала из веб-приложения, затем из Telegram, если есть
            if (DOM.currentnickname) {
            if (userData.nickname_webapp) {
                    DOM.currentnickname.textContent = userData.nickname_webapp;
            } else if (userData.nickname) {
                    DOM.currentnickname.textContent = userData.nickname;
            } else {
                // Если никнейм вообще не установлен, показываем модальное окно для ввода
                setTimeout(() => {
                    showNicknameModal();
                }, 1000);
                }
            }
            
            updateUI(userData);
            
            // Обновляем реферальную ссылку и статистику
            updateReferralInfo(state.userId, userData.referral_count || 0);
            
            return userData;
        } catch (error) {
            console.error("Ошибка при получении данных пользователя:", error);
            showError("Не удалось загрузить данные пользователя");
            return null;
        }
    }
    
    // Функция для получения списка лидеров
    async function fetchLeaders() {
        try {
            const userId = state.userId || getUserId();
            
            // Формируем URL с ID пользователя
            const endpoint = userId 
                ? `/api/leaders?limit=10&user_id=${userId}`
                : '/api/leaders?limit=10';
            
            const data = await makeApiRequest(endpoint);
            updateLeaderboard(data.leaders);
            
        } catch (error) {
            console.error("Ошибка при получении списка лидеров:", error);
        }
    }
    
    // Функция обновления списка лидеров в интерфейсе
    function updateLeaderboard(leaders) {
        const leadersList = document.querySelector('.leaders-list');
        if (!leadersList) return;
        
        // Очищаем текущий список
        leadersList.innerHTML = '';
        
        // Добавляем лидеров
        leaders.forEach(leader => {
            const leaderItem = document.createElement('div');
            leaderItem.className = 'leader-item';
            
            leaderItem.innerHTML = `
                <div class="leader-rank">${leader.rank}</div>
                <div class="leader-info">
                    <div class="leader-name" style="color: #4a148c; font-weight: 800; text-shadow: 0px 1px 1px rgba(0, 0, 0, 0.4); letter-spacing: 0.3px;">${leader.name}</div>
                    <div class="leader-score">Баланс: ${leader.score}</div>
                </div>
            `;
            
            leadersList.appendChild(leaderItem);
        });
        
        // Если список пуст, показываем сообщение
        if (leaders.length === 0) {
            const emptyMessage = document.createElement('div');
            emptyMessage.className = 'empty-message';
            emptyMessage.textContent = 'Пока нет данных о лидерах';
            leadersList.appendChild(emptyMessage);
        }
    }
    
    // Функция обновления интерфейса
    function updateUI(userData) {
        // Обновляем отображение количества билетов
        if (DOM.ticketscount) {
            DOM.ticketscount.textContent = userData.tickets || 0;
        }
        
        // Обновляем локальную переменную points перед обновлением UI
        state.points = userData.spins_count || 0;
        
        // Обновляем счетчик прокрутов в интерфейсе
        if (DOM.points) {
            DOM.points.textContent = state.points;
        }
        
        // Обновляем таймер до следующего бесплатного прокрута или билета
        if (DOM.timer) {
            if (state.tickets === 0 && state.freeTicketTimeLeft > 0) {
                // Если запущен таймер до бесплатного билета, обновляем отображение через updateTimerDisplay()
                updateTimerDisplay();
                
                // Плавно показываем таймер, если он не активен
                if (!DOM.timer.parentElement.classList.contains('active-timer')) {
                    DOM.timer.parentElement.classList.remove('hidden-timer');
                    DOM.timer.parentElement.classList.add('active-timer');
                    DOM.timer.parentElement.classList.add('timer-appearing');
                    
                    // Удаляем класс анимации появления через секунду
                    setTimeout(() => {
                        DOM.timer.parentElement.classList.remove('timer-appearing');
                    }, 1000);
                }
            } else {
                // Если у пользователя есть билеты, плавно скрываем таймер
                if (userData.tickets > 0) {
                    DOM.timer.textContent = "00:00";
                    DOM.timer.classList.remove('pulsing');
                    
                    // Плавно скрываем таймер
                    DOM.timer.parentElement.classList.add('hidden-timer');
                    DOM.timer.parentElement.classList.remove('active-timer');
            } else {
                    // Иначе просто показываем время до следующего бесплатного прокрута
                    DOM.timer.textContent = userData.time_until_free_spin || "00:00";
                    DOM.timer.classList.remove('pulsing');
                    
                    // Убираем визуальные эффекты активного таймера
                    DOM.timer.parentElement.classList.remove('active-timer');
                    DOM.timer.parentElement.classList.remove('hidden-timer');
                }
            }
        }
        
        // Активируем/деактивируем кнопку в зависимости от наличия билетов
        if (DOM.spinbutton) {
            const hasTickets = userData.tickets > 0;
            DOM.spinbutton.disabled = !hasTickets;
            DOM.spinbutton.classList.toggle("disabled", !hasTickets);
            DOM.spinbutton.title = hasTickets ? "Крутить колесо" : "Недостаточно билетов";
        }
    }
    
    // Функция для запуска таймера обновления времени
    function startTimer() {
        // Стандартное обновление данных каждую минуту
        setInterval(() => {
            fetchUserData();
        }, 60000); // 60 секунд
        
        // Дополнительная проверка состояния билетов (уменьшена частота до 30 секунд)
        setInterval(() => {
            // Запрашиваем актуальное состояние билетов с сервера
            makeApiRequest(`/api/user/${state.userId || getUserId()}`)
                .then(userData => {
                    // Если количество билетов изменилось
                    if (userData.tickets !== state.tickets) {
                        console.log("Изменение билетов обнаружено:", userData.tickets);
                        
                        // Обновляем состояние
                        state.tickets = userData.tickets || 0;
                        
                        // Проверяем и обновляем состояние таймера
                        checkTicketsAndUpdateTimer();
                        
                        // Обновляем отображение билетов
                        if (DOM.ticketscount) {
                            DOM.ticketscount.textContent = state.tickets;
                        }
                        
                        // Активируем/деактивируем кнопку в зависимости от наличия билетов
                        if (DOM.spinbutton) {
                            const hasTickets = state.tickets > 0;
                            DOM.spinbutton.disabled = !hasTickets;
                            DOM.spinbutton.classList.toggle("disabled", !hasTickets);
                        }
                    }
                })
                .catch(error => {
                    console.error("Ошибка при проверке билетов:", error);
                });
        }, 30000); // Проверка каждые 30 секунд (было 5 секунд)
        
        // Запускаем таймер обратного отсчета до бесплатного билета, если нужно
        checkFreeTicketTimer();
    }
    
    // Функция для проверки и запуска таймера до бесплатного билета
    function checkFreeTicketTimer() {
        // Очищаем предыдущий таймер, если он был
        if (state.freeTicketTimerId) {
            clearInterval(state.freeTicketTimerId);
            state.freeTicketTimerId = null;
        }
        
        // Если у пользователя 0 билетов и есть время до бесплатного билета
        if (state.tickets === 0 && state.freeTicketTimeLeft > 0) {
            // Запускаем таймер обратного отсчета
            startFreeTicketCountdown();
        }
    }
    
    // Функция для запуска обратного отсчета до бесплатного билета
    function startFreeTicketCountdown() {
        console.log("Запускаем обратный отсчет до бесплатного билета", state.freeTicketTimeLeft);
        
        state.isFreeTicketTimerActive = true;
        
        // Плавно показываем таймер
        if (DOM.timer && DOM.timer.parentElement) {
            DOM.timer.parentElement.classList.remove('hidden-timer');
            DOM.timer.parentElement.classList.add('active-timer');
            DOM.timer.parentElement.classList.add('timer-appearing');
            
            // Удаляем класс анимации появления через секунду
            setTimeout(() => {
                DOM.timer.parentElement.classList.remove('timer-appearing');
            }, 1000);
        }
        
        // Обновляем отображение таймера каждую секунду
        state.freeTicketTimerId = setInterval(() => {
            // Дополнительная проверка: если у пользователя появились билеты, останавливаем таймер
            if (state.tickets > 0) {
                console.log("Внутри таймера: у пользователя появились билеты, останавливаем таймер");
                
                clearInterval(state.freeTicketTimerId);
                state.freeTicketTimerId = null;
                state.isFreeTicketTimerActive = false;
                state.freeTicketTimeLeft = 0;
                
                // Обновляем отображение - сбрасываем таймер полностью с плавной анимацией
                if (DOM.timer) {
                    DOM.timer.textContent = "00:00";
                    DOM.timer.classList.remove('pulsing');
                    
                    // Плавно скрываем таймер
                    if (DOM.timer.parentElement) {
                        DOM.timer.parentElement.classList.add('hidden-timer');
                        DOM.timer.parentElement.classList.remove('active-timer');
                    }
                }
                
                // Запрашиваем обновление данных с сервера после небольшой паузы
                setTimeout(fetchUserData, 500);
                    return;
                }
                
            if (state.freeTicketTimeLeft <= 0) {
                // Время вышло, даем бесплатный билет
                console.log("Время таймера истекло");
                
                clearInterval(state.freeTicketTimerId);
                state.freeTicketTimerId = null;
                state.isFreeTicketTimerActive = false;
                
                // Запрашиваем обновление данных с сервера
                fetchUserData();
                    } else {
                // Уменьшаем оставшееся время на 1 секунду
                state.freeTicketTimeLeft--;
                
                // Обновляем отображение таймера
                updateTimerDisplay();
            }
        }, 1000);
    }
    
    // Функция для обновления отображения таймера
    function updateTimerDisplay() {
        if (DOM.timer) {
            const minutes = Math.floor(state.freeTicketTimeLeft / 60);
            const seconds = state.freeTicketTimeLeft % 60;
            
            // Форматируем время как "MM:SS"
            const formattedTime = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            DOM.timer.textContent = formattedTime;
            
            // Добавляем пульсирующую анимацию, если осталось мало времени (менее 10 секунд)
            if (state.freeTicketTimeLeft < 10) {
                DOM.timer.classList.add('pulsing');
            } else {
                DOM.timer.classList.remove('pulsing');
            }
        }
    }
    
    // Функция для отображения ошибки
    function showError(message) {
        alert(message);
    }
    
    // Функция для создания колеса с правильно расположенными цифрами
    function createWheel() {
        const segmentCount = sectors.length;
        const segmentAngle = 360 / segmentCount;
        const wheelRadius = 150; // Радиус колеса
        const labelRadius = 90; // Радиус для размещения текста (уменьшен для лучшего размещения)
        
        // Создаем SVG для колеса, если его еще нет
        let svg = wheel.querySelector('svg');
        if (!svg) {
            svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.setAttribute("width", "300");
            svg.setAttribute("height", "300");
            svg.setAttribute("viewBox", "0 0 300 300");
            wheel.appendChild(svg);
        }
        
        // Создаем фильтр для текстовой тени
        const filterId = "textShadow";
        const filter = document.createElementNS("http://www.w3.org/2000/svg", "filter");
        filter.setAttribute("id", filterId);
        
        const feDropShadow = document.createElementNS("http://www.w3.org/2000/svg", "feDropShadow");
        feDropShadow.setAttribute("dx", "0");
        feDropShadow.setAttribute("dy", "0");
        feDropShadow.setAttribute("stdDeviation", "1");
        feDropShadow.setAttribute("flood-color", "black");
        feDropShadow.setAttribute("flood-opacity", "0.5");
        
        filter.appendChild(feDropShadow);
        svg.appendChild(filter);
        
        // Создаем сегменты
        for (let i = 0; i < segmentCount; i++) {
            // Вычисляем углы для текущего сегмента
            const startAngle = i * segmentAngle;
            const endAngle = (i + 1) * segmentAngle;
            const midAngle = startAngle + (segmentAngle / 2);
            
            // Создаем сектор SVG для сегмента
            const segment = document.createElementNS("http://www.w3.org/2000/svg", "path");
            
            // Конвертируем углы в радианы для расчетов
            const startRad = (startAngle - 90) * Math.PI / 180;
            const endRad = (endAngle - 90) * Math.PI / 180;
            const midRad = (midAngle - 90) * Math.PI / 180;
            
            // Координаты для построения пути сектора
            const x1 = wheelRadius + wheelRadius * Math.cos(startRad);
            const y1 = wheelRadius + wheelRadius * Math.sin(startRad);
            const x2 = wheelRadius + wheelRadius * Math.cos(endRad);
            const y2 = wheelRadius + wheelRadius * Math.sin(endRad);
            
            // Создаем путь SVG для сектора
            const largeArcFlag = segmentAngle > 180 ? 1 : 0;
            const pathData = `
                M ${wheelRadius},${wheelRadius}
                L ${x1},${y1}
                A ${wheelRadius},${wheelRadius} 0 ${largeArcFlag} 1 ${x2},${y2}
                Z
            `;
            
            segment.setAttribute("d", pathData);
            segment.setAttribute("fill", sectors[i].color);
            segment.setAttribute("stroke", "#8B5CF6"); // Фиолетовый цвет для границ секторов
            segment.setAttribute("stroke-width", "2");
            segment.setAttribute("data-value", sectors[i].value);
            segment.setAttribute("data-index", i);
            
            // Добавляем линии от центра к краям
            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", wheelRadius);
            line.setAttribute("y1", wheelRadius);
            line.setAttribute("x2", x1);
            line.setAttribute("y2", y1);
            line.setAttribute("stroke", "#8B5CF6"); // Фиолетовый цвет для линий
            line.setAttribute("stroke-width", "2");
            
            // Добавляем текст с числом в центр сегмента
            const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
            
            // Вычисляем позицию для текста - в центре сегмента
            const textX = wheelRadius + labelRadius * Math.cos(midRad);
            const textY = wheelRadius + labelRadius * Math.sin(midRad);
            
            text.setAttribute("x", textX);
            text.setAttribute("y", textY);
            text.setAttribute("fill", "#FFFFFF");
            text.setAttribute("font-family", "Montserrat, sans-serif");
            text.setAttribute("font-size", "22");
            text.setAttribute("font-weight", "bold");
            text.setAttribute("text-anchor", "middle");
            text.setAttribute("dominant-baseline", "central");
            text.setAttribute("filter", `url(#${filterId})`);
            
            // Поворачиваем текст только для выравнивания горизонтально
            text.setAttribute("transform", `rotate(${midAngle - 90}, ${textX}, ${textY})`);
            
            text.textContent = sectors[i].value;
            
            // Добавляем элементы в SVG
            svg.appendChild(segment);
            svg.appendChild(line);
            svg.appendChild(text);
        }
        
        // Добавляем центр колеса
        const centerCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        centerCircle.setAttribute("cx", wheelRadius);
        centerCircle.setAttribute("cy", wheelRadius);
        centerCircle.setAttribute("r", "25");
        centerCircle.setAttribute("fill", "#8B5CF6"); // Фиолетовый цвет для центра колеса
        centerCircle.setAttribute("stroke", "#FFFFFF");
        centerCircle.setAttribute("stroke-width", "2");
        
        svg.appendChild(centerCircle);
        
        // Добавляем маркер (стрелку) над колесом
        const wheelContainer = document.querySelector('.wheel-container');
        const existingMarker = document.getElementById('wheel-marker');
        
        if (!existingMarker) {
            const marker = document.createElement('div');
            marker.className = 'wheel-marker';
            marker.id = 'wheel-marker';
            wheelContainer.appendChild(marker);
        }
    }
    
    // Функция для отправки результата на сервер
    async function sendSpinResult(result) {
        try {
            const userId = state.userId || getUserId();
            
            if (!userId) {
                showError("Не удалось аутентифицировать пользователя");
                return {success: false, message: "Не удалось аутентифицировать пользователя"};
            }
            
            // Отправляем результат на сервер
            const data = await makeApiRequest(
                `/api/spin/${userId}`, 
                'POST', 
                { result: String(result) }
            );
            
            if (!data.success) {
                throw new Error(data.message || "Не удалось выполнить прокрут");
            }
            
            // Добавляем эффект подсветки для стрелки при выигрыше
            if (result > 0) {
                const marker = document.querySelector('.wheel-marker');
                if (marker) {
                    // Добавляем класс для подсветки стрелки
                    marker.classList.add('win-highlight');
                    
                    // Удаляем класс через 2 секунды
                    setTimeout(() => {
                        marker.classList.remove('win-highlight');
                    }, 2000);
                }
            }
            
            // Обновляем данные в приложении
            state.tickets = data.tickets;
            if (DOM.ticketscount) {
                DOM.ticketscount.textContent = state.tickets;
            }
            
            // Обновляем таймер
            if (data.time_until_next_spin && DOM.timer) {
                DOM.timer.textContent = data.time_until_next_spin;
            }
            
            return data;
        } catch (error) {
            console.error("Ошибка при отправке результата прокрута:", error);
            showError(error.message || "Ошибка при выполнении прокрута");
            return {success: false, message: error.message || "Ошибка при выполнении прокрута"};
        }
    }
    
    // Функция для показа модального окна никнейма
    function showNicknameModal() {
        if (DOM.nicknamemodal) {
            DOM.nicknamemodal.classList.add('active');
            // Устанавливаем текущий никнейм в поле ввода
            if (DOM.nicknameinput) {
                // Используем текущее значение в поле nicknameDisplay
                DOM.nicknameinput.value = DOM.currentnickname.textContent === 'Гость' ? '' : DOM.currentnickname.textContent;
                DOM.nicknameinput.focus();
            }
            // Сбрасываем ошибки
            clearNicknameError();
        }
    }
    
    // Функция для скрытия модального окна никнейма
    function hideNicknameModal() {
        if (DOM.nicknamemodal) {
            DOM.nicknamemodal.classList.remove('active');
        }
    }
    
    // Функция для отображения ошибки никнейма
    function showNicknameError(message) {
        if (DOM.nicknameerror) {
            DOM.nicknameerror.textContent = message;
            DOM.nicknameerror.style.display = 'block';
        }
    }
    
    // Функция для очистки ошибки никнейма
    function clearNicknameError() {
        if (DOM.nicknameerror) {
            DOM.nicknameerror.textContent = '';
            DOM.nicknameerror.style.display = 'none';
        }
    }

    // Добавим функцию обновления реферальной информации
    async function updateReferralInfo(userId, referralCount) {
        // Обновляем реферальную ссылку
        if (referralLink) {
            // Обновляем ссылку с актуальным ID пользователя
            const botUsername = 'smarty_gector_ai_bot'; // Можно получать динамически, если нужно
            referralLink.value = `https://t.me/${botUsername}?start=ref${userId}`;
        }
        
        // Обновляем счетчик приглашенных друзей
        const referralCountElement = document.querySelector('.referral-stats .stat-value');
        if (referralCountElement) {
            referralCountElement.textContent = referralCount;
        }
        
        // Получаем и отображаем список рефералов, если мы на вкладке рефералов
        if (document.getElementById('tab-referral').style.display !== 'none') {
            try {
                // Загружаем первые 5 рефералов
                const referralsData = await makeApiRequest(`/api/user/${userId}/referrals?limit=5`);
                
                // Находим контейнер для списка рефералов или создаем его
                let referralsList = document.querySelector('.referrals-list');
                if (!referralsList) {
                    // Если контейнера нет, создаем его
                    const referralInfo = document.querySelector('.referral-info');
                    if (referralInfo) {
                        referralsList = document.createElement('div');
                        referralsList.className = 'referrals-list';
                        referralInfo.appendChild(referralsList);
                    }
                }
                
                // Если контейнер найден, обновляем его содержимое
                if (referralsList) {
                    // Очищаем текущее содержимое
                    referralsList.innerHTML = '';
                    
                    // Если есть рефералы, отображаем их
                    if (referralsData.referrals && referralsData.referrals.length > 0) {
                        // Добавляем заголовок
                        const header = document.createElement('h3');
                        header.textContent = 'Ваши рефералы';
                        header.className = 'referrals-header';
                        referralsList.appendChild(header);
                        
                        // Создаем список рефералов
                        referralsData.referrals.forEach((referral, index) => {
                            const referralItem = document.createElement('div');
                            referralItem.className = 'referral-item';
                            
                            // Создаем элементы для номера, имени и баланса
                            const referralRank = document.createElement('div');
                            referralRank.className = 'referral-rank';
                            referralRank.textContent = index + 1;
                            
                            const referralInfo = document.createElement('div');
                            referralInfo.className = 'referral-info-item';
                            
                            const referralName = document.createElement('div');
                            referralName.className = 'referral-name';
                            referralName.textContent = referral.name;
                            
                            const referralBalance = document.createElement('div');
                            referralBalance.className = 'referral-balance';
                            referralBalance.textContent = `Баланс: ${referral.balance}`;
                            
                            // Собираем все вместе
                            referralInfo.appendChild(referralName);
                            referralInfo.appendChild(referralBalance);
                            
                            referralItem.appendChild(referralRank);
                            referralItem.appendChild(referralInfo);
                            
                            referralsList.appendChild(referralItem);
                        });
                        
                        // Если есть больше рефералов, добавляем ссылку "Показать все"
                        if (referralsData.total_count > referralsData.referrals.length) {
                            const showMoreLink = document.createElement('div');
                            showMoreLink.className = 'show-more-link';
                            showMoreLink.textContent = 'Показать всех';
                            referralsList.appendChild(showMoreLink);
                        }
                    } else {
                        // Если рефералов нет, показываем сообщение
                        const emptyMessage = document.createElement('div');
                        emptyMessage.className = 'empty-referrals-message';
                        emptyMessage.textContent = 'У вас пока нет рефералов. Поделитесь своей ссылкой с друзьями!';
                        referralsList.appendChild(emptyMessage);
                    }
                }
                
            } catch (error) {
                console.error("Ошибка при загрузке рефералов:", error);
                // Не показываем ошибку пользователю, просто логируем
            }
        }
    }

    // Дополнительно добавим функцию для проверки состояния билетов, которую будем вызывать после каждого действия
    function checkTicketsAndUpdateTimer() {
        console.log("Проверка билетов и таймера. Билетов:", state.tickets, "Таймер активен:", state.isFreeTicketTimerActive);
        
        // Если у пользователя есть билеты, но таймер активен - останавливаем таймер
        if (state.tickets > 0 && state.isFreeTicketTimerActive) {
            console.log("У пользователя есть билеты, останавливаем таймер");
            
            clearInterval(state.freeTicketTimerId);
            state.freeTicketTimerId = null;
            state.isFreeTicketTimerActive = false;
            state.freeTicketTimeLeft = 0;
            
            // Обновляем отображение - сбрасываем таймер и убираем визуальные эффекты с плавной анимацией
            if (DOM.timer) {
                DOM.timer.textContent = "00:00";
                DOM.timer.classList.remove('pulsing');
                
                // Плавно скрываем таймер
                if (DOM.timer.parentElement) {
                    DOM.timer.parentElement.classList.add('hidden-timer');
                    DOM.timer.parentElement.classList.remove('active-timer');
                    DOM.timer.parentElement.classList.remove('timer-appearing');
                }
            }
            
            // Принудительно обновляем данные с сервера для синхронизации
            setTimeout(fetchUserData, 500);
        }
        // Если билетов нет и таймер не активен, но есть время - запускаем таймер
        else if (state.tickets === 0 && !state.isFreeTicketTimerActive && state.freeTicketTimeLeft > 0) {
            console.log("У пользователя нет билетов, запускаем таймер", state.freeTicketTimeLeft);
            
            // Плавно показываем таймер
            if (DOM.timer && DOM.timer.parentElement) {
                DOM.timer.parentElement.classList.remove('hidden-timer');
                DOM.timer.parentElement.classList.add('active-timer');
                DOM.timer.parentElement.classList.add('timer-appearing');
                
                // Удаляем класс анимации появления через секунду
                setTimeout(() => {
                    DOM.timer.parentElement.classList.remove('timer-appearing');
                }, 1000);
            }
            
            checkFreeTicketTimer();
        }
    }
});
