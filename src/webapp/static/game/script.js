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
    isFreeTicketTimerActive: false,
    prizes: [], // Список призов
    currentPrize: null, // Текущий выигранный приз
    giveaways: [], // Список активных розыгрышей
    userGiveaways: [], // Розыгрыши, в которых участвует пользователь
    sponsorChannels: [] // Список каналов-спонсоров
};

// Простая валидация initData для Telegram WebApp
function validateTelegramWebAppData(initData) {
    // Проверяем, что строка не пуста
    if (typeof initData === 'string' && initData.length > 0) {
        // Можно добавить дополнительные проверки структуры, если нужно
        return { valid: true };
    }
    return { valid: false, error: 'initData отсутствует или некорректен' };
}

// Патчим глобальный fetch, чтобы всегда добавлять X-Telegram-Init-Data
(function() {
    const originalFetch = window.fetch;
    window.fetch = function(input, init = {}) {
        // Если это запрос к нашему API
        let url = typeof input === 'string' ? input : (input.url || '');
        if (url.startsWith('/api/') || url.startsWith('api/')) {
            if (!init.headers) init.headers = {};
            // Добавляем X-Telegram-Init-Data, если есть
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
                // Передаем initData без дополнительного кодирования,
                // сервер ожидает исходный формат query-string
                init.headers['X-Telegram-Init-Data'] = window.Telegram.WebApp.initData;
            }
        }
        return originalFetch(input, init);
    };
})();

// Функция для загрузки призов
async function loadPrizes() {
    try {
        const response = await fetch('/api/prizes');
        const data = await response.json();
        
        if (data.success) {
            state.prizes = data.prizes;
            console.log('Призы загружены:', state.prizes);
            updatePrizesDisplay();
        }
    } catch (error) {
        console.error('Ошибка при загрузке призов:', error);
    }
}

// Функция для загрузки активных розыгрышей
async function loadGiveaways() {
    try {
        const response = await fetch('/api/giveaways/active');
        const giveaways = await response.json();
        
        state.giveaways = giveaways;
        console.log('Розыгрыши загружены:', state.giveaways);
        updateGiveawaysDisplay();
    } catch (error) {
        console.error('Ошибка при загрузке розыгрышей:', error);
    }
}

// Функция для участия в розыгрыше
async function joinGiveaway(giveawayId) {
    try {
        const response = await fetch(`/api/giveaways/${giveawayId}/join`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            showSuccess('🎉 Вы успешно участвуете в розыгрыше!');
            // Обновляем отображение
            loadGiveaways();
        } else {
            showError(data.message || 'Ошибка при участии в розыгрыше');
        }
    } catch (error) {
        console.error('Ошибка при участии в розыгрыше:', error);
        showError('Ошибка при участии в розыгрыше');
    }
}

// Функция для обновления отображения призов
function updatePrizesDisplay() {
    const prizesContainer = document.getElementById('prizes-container');
    if (!prizesContainer) return;
    
    prizesContainer.innerHTML = '';
    
    state.prizes.forEach(prize => {
        const prizeElement = document.createElement('div');
        prizeElement.className = 'prize-item';
        prizeElement.innerHTML = `
            <div class="prize-image">
                ${prize.image_url ? `<img src="${prize.image_url}" alt="${prize.name}">` : '<div class="prize-placeholder">🎁</div>'}
            </div>
            <div class="prize-info">
                <h4>${prize.name}</h4>
                <p>${prize.description || ''}</p>
                <div class="prize-value">${prize.value} руб</div>
            </div>
        `;
        prizesContainer.appendChild(prizeElement);
    });
}

// Функция для обновления отображения розыгрышей
function updateGiveawaysDisplay() {
    const giveawaysList = document.getElementById('giveaways-list');
    const giveawaysEmpty = document.getElementById('giveaways-empty');
    
    if (!giveawaysList || !giveawaysEmpty) return;

    if (state.giveaways.length === 0) {
        giveawaysList.style.display = 'none';
        giveawaysEmpty.style.display = 'block';
        return;
    }

    giveawaysList.style.display = 'block';
    giveawaysEmpty.style.display = 'none';

    giveawaysList.innerHTML = state.giveaways.map(giveaway => `
        <div class="giveaway-item">
            <div class="giveaway-header">
                <h3>🎉 ${giveaway.title}</h3>
                <span class="giveaway-status status-${giveaway.status}">${getStatusText(giveaway.status)}</span>
            </div>
            <div class="giveaway-content">
                <p class="giveaway-description">${giveaway.description || ''}</p>
                <div class="giveaway-prize">
                    <span class="prize-icon">🎁</span>
                    <span class="prize-text">${giveaway.prize}</span>
                </div>
                <div class="giveaway-actions">
                    <button class="btn-join-giveaway" onclick="joinGiveaway(${giveaway.id})">
                        Участвовать
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

// Функция для получения текста статуса
function getStatusText(status) {
    const statusMap = {
        'draft': 'Черновик',
        'active': 'Активен',
        'finished': 'Завершен'
    };
    return statusMap[status] || status;
}

// Функция для загрузки каналов-спонсоров
async function loadSponsorChannels() {
    try {
        console.log('Загружаем каналы-спонсоры...');
        const response = await fetch('/api/subscription/channels');
        const channels = await response.json();
        
        state.sponsorChannels = channels;
        console.log('Каналы-спонсоры загружены:', state.sponsorChannels);
        updateSponsorChannelsDisplay();
    } catch (error) {
        console.error('Ошибка при загрузке каналов-спонсоров:', error);
        // Устанавливаем пустой массив, чтобы не блокировать страницу
        state.sponsorChannels = [];
        updateSponsorChannelsDisplay();
    }
}

// Функция для обновления отображения каналов-спонсоров
function updateSponsorChannelsDisplay() {
    const sponsorChannelsLink = document.getElementById('sponsor-channels-link');
    if (!sponsorChannelsLink) return;

    if (state.sponsorChannels.length === 0) {
        sponsorChannelsLink.textContent = 'Нет каналов';
        sponsorChannelsLink.style.pointerEvents = 'none';
        sponsorChannelsLink.style.opacity = '0.5';
        return;
    }

    // Создаем список каналов
    const channelsList = state.sponsorChannels.map(channel => 
        `• ${channel.title} (${channel.id})`
    ).join('\n');

    // Добавляем обработчик клика
    sponsorChannelsLink.addEventListener('click', (e) => {
        e.preventDefault();
        showSponsorChannelsModal();
    });
}

// Функция для показа модального окна с каналами-спонсорами
function showSponsorChannelsModal() {
    const modal = document.createElement('div');
    modal.className = 'prize-modal';
    modal.innerHTML = `
        <div class="prize-modal-content">
            <div class="prize-modal-header">
                <h2>📢 Каналы-спонсоры</h2>
                <button class="prize-modal-close">&times;</button>
            </div>
            <div class="prize-modal-body">
                <p>Подпишитесь на наши каналы-спонсоры для участия в розыгрышах:</p>
                <div class="sponsor-channels-list">
                    ${state.sponsorChannels.map(channel => `
                        <div class="sponsor-channel-item">
                            <h4>${channel.title}</h4>
                            <a href="${channel.url}" target="_blank" class="channel-link">
                                ${channel.id}
                            </a>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="prize-modal-footer">
                <button class="prize-modal-ok">Понятно</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Обработчики для закрытия модального окна
    modal.querySelector('.prize-modal-close').addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    modal.querySelector('.prize-modal-ok').addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    // Закрытие по клику вне модального окна
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
}

// Функция для отображения выигранного приза
function showPrizeWin(prize) {
    if (!prize) return;
    
    // Создаем модальное окно для показа приза
    const modal = document.createElement('div');
    modal.className = 'prize-modal';
    modal.innerHTML = `
        <div class="prize-modal-content">
            <div class="prize-modal-header">
                <h2>🎉 Поздравляем! 🎉</h2>
                <button class="prize-modal-close">&times;</button>
            </div>
            <div class="prize-modal-body">
                <div class="prize-image-large">
                    ${prize.image_url ? `<img src="${prize.image_url}" alt="${prize.name}">` : '<div class="prize-placeholder-large">🎁</div>'}
                </div>
                <h3>${prize.name}</h3>
                <p>${prize.description || ''}</p>
                <div class="prize-value-large">${prize.value} руб</div>
            </div>
            <div class="prize-modal-footer">
                <button class="prize-modal-ok">Отлично!</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Обработчики для закрытия модального окна
    modal.querySelector('.prize-modal-close').addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    modal.querySelector('.prize-modal-ok').addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    // Закрытие по клику вне модального окна
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, starting initialization...');
    
    // Кэшируем все DOM-элементы при загрузке страницы
    cacheDOM();
    
    // Скрываем прелоадер
    const preloader = document.querySelector('.app-preloader');
    if (preloader) {
        preloader.classList.add('hidden');
        setTimeout(() => {
            preloader.style.display = 'none';
        }, 300);
    }
    
    console.log('Preloader hidden, page should be visible now');
    
    // Проверяем, есть ли Telegram WebApp данные
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
        console.log('Telegram WebApp detected with initData');
        // Загружаем призы, розыгрыши и каналы
        loadPrizes();
        loadGiveaways();
        loadSponsorChannels();
    } else {
        console.log('No Telegram WebApp detected or no initData, loading without API calls');
        // Загружаем только каналы (они не требуют авторизации)
        loadSponsorChannels();
        
        // Устанавливаем заглушки для тестирования
        state.prizes = [];
        state.giveaways = [];
        updatePrizesDisplay();
        updateGiveawaysDisplay();
    }
    
    // Значения для сегментов колеса (розовая тема)
    const sectors = [
        { value: 300, color: '#F8BBD9' },  // Светло-розовый
        { value: 0, color: '#C2185B' },    // Тёмно-розовый
        { value: 1000, color: '#F8BBD9' }, // Светло-розовый
        { value: 0, color: '#C2185B' },    // Тёмно-розовый
        { value: 2000, color: '#F8BBD9' }, // Светло-розовый
        { value: 0, color: '#C2185B' },    // Тёмно-розовый
        { value: 300, color: '#F8BBD9' },  // Светло-розовый
        { value: 0, color: '#C2185B' },    // Тёмно-розовый
        { value: 500, color: '#F8BBD9' },  // Светло-розовый
        { value: 0, color: '#C2185B' },    // Тёмно-розовый
        { value: 300, color: '#F8BBD9' },  // Светло-розовый
        { value: 0, color: '#C2185B' },    // Тёмно-розовый
    ];
    
    // Инициализация приложения
    initApp();
    
    // Принудительно создаем колесо через небольшую задержку
    setTimeout(() => {
        console.log('Принудительно создаем колесо...');
        createWheel();
    }, 1000);
    
    // Принудительно настраиваем обработчики через задержку
    setTimeout(() => {
        console.log('Принудительно настраиваем обработчики...');
        setupEventListeners();
        
        // Альтернативный способ - привязываем обработчики напрямую
        const navItems = document.querySelectorAll('.nav-item');
        console.log('Альтернативно найдено элементов навигации:', navItems.length);
        
        navItems.forEach((item, index) => {
            console.log(`Альтернативно настраиваем обработчик для элемента ${index}:`, item);
            item.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('Клик по элементу навигации:', item);
                
                const tabId = item.getAttribute('data-tab');
                console.log('Переключаем на вкладку:', tabId);
                
                // Обновляем активный элемент меню
                navItems.forEach(navItem => navItem.classList.remove('active'));
                item.classList.add('active');
                
                // Показываем соответствующую вкладку
                const tabContents = document.querySelectorAll('.tab-content');
                tabContents.forEach(tab => {
                    const isVisible = tab.id === tabId;
                    tab.classList.toggle('active', isVisible);
                    console.log(`Вкладка ${tab.id} видима:`, isVisible);
                });
            });
        });
    }, 1500);
    
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
        
        // Явно получаем кнопку закрытия модального окна
        DOM.closenicknamebtn = document.getElementById('close-nickname-modal');
        
        // Получаем элементы прелоадера
        DOM.appPreloader = document.querySelector('.app-preloader');
        DOM.appContainer = document.querySelector('.app-container');
        
        // Отладочная информация
        console.log('DOM элементы закэшированы:', {
            navItems: DOM.navItems.length,
            tabContents: DOM.tabContents.length,
            wheel: !!DOM.wheel,
            spinbutton: !!DOM.spinbutton
        });
    }
    
    // Функция инициализации приложения
    function initApp() {
        // Проверяем, что приложение запущено в Telegram WebApp
        if (!(window.Telegram && window.Telegram.WebApp)) {
            showError("Пожалуйста, запускайте приложение только через Telegram WebApp. Прямая загрузка не поддерживается по соображениям безопасности.");
            if (DOM.appPreloader) DOM.appPreloader.classList.remove('hidden');
            if (DOM.appContainer) DOM.appContainer.classList.remove('loaded');
            return;
        }

        // Ждем, пока Telegram WebApp полностью инициализируется и initData будет доступен
        // Используем комбинацию ready() и интервальной проверки initData для надежности
        const waitForWebAppReady = setInterval(() => {
            if (window.Telegram.WebApp.initData) {
                clearInterval(waitForWebAppReady);
                // Вызываем ready() после получения initData, чтобы WebApp был полностью инициализирован
                window.Telegram.WebApp.ready();
                proceedWithAppInitialization();
            } else {
                // Если initData еще нет, но WebApp уже почти готов, можно добавить лог для отладки
                console.log("Telegram WebApp initData is not yet available, waiting...");
            }
        }, 100); // Проверяем каждые 100 мс
    }

    // Новая функция, которая будет выполнять остальную инициализацию после получения initData
    async function proceedWithAppInitialization() {
        state.userId = getUserId();
        
        if (!state.userId) {
            showError("Не удалось получить идентификатор пользователя");
            return;
        }
        
        // Инициализируем приложение параллельно, вызывая API после получения initData
        try {
            await Promise.all([
                fetchUserData(),
                fetchLeaders(),
                checkUserSubscription(),
                // Если есть другие API-запросы, которые выполняются при старте, добавьте их сюда:
                // fetchBotInfo() // Пример: если fetchBotInfo нужен для начальной загрузки
            ]);
            // После загрузки всех данных скрываем прелоадер и показываем контент
            hidePreloader();
        } catch (error) {
            console.error("Ошибка при инициализации приложения:", error);
            // Даже в случае ошибки скрываем прелоадер
            hidePreloader();
            showError(`Произошла ошибка при загрузке данных: ${error.message || error}. Пожалуйста, попробуйте позже.`);
        }
        
        // Очищаем колесо перед созданием нового
        if (DOM.wheel) DOM.wheel.innerHTML = '';
        
        // Создаем колесо
        createWheel();
        
        // Настройка обработчиков событий
        setupEventListeners();
        
        // Запускаем таймер обновления времени до следующего бесплатного прокрута
        startTimer();
    }
    
    // Функция для скрытия прелоадера и отображения контента
    function hidePreloader() {
        // Небольшая задержка для плавности анимации
        setTimeout(() => {
            if (DOM.appPreloader) {
                DOM.appPreloader.classList.add('hidden');
            }
            
            if (DOM.appContainer) {
                DOM.appContainer.classList.add('loaded');
            }
            
            // Полностью удаляем прелоадер после завершения анимации
            setTimeout(() => {
                if (DOM.appPreloader) {
                    DOM.appPreloader.remove();
                }
            }, 300);
        }, 500);
    }
    
    // Настройка всех обработчиков событий
    function setupEventListeners() {
        console.log('Настраиваем обработчики событий...');
        console.log('Найдено элементов навигации:', DOM.navItems.length);
        console.log('Найдено вкладок:', DOM.tabContents.length);
        
        // Навигация по вкладкам
        if (DOM.navItems && DOM.navItems.length > 0) {
            DOM.navItems.forEach((item, index) => {
                console.log(`Настраиваем обработчик для элемента ${index}:`, item);
            item.addEventListener('click', () => {
                const tabId = item.getAttribute('data-tab');
                
                // Обновляем активный элемент меню
                DOM.navItems.forEach(navItem => navItem.classList.remove('active'));
                item.classList.add('active');
                
                // Показываем соответствующую вкладку
                DOM.tabContents.forEach(tab => {
                    const isVisible = tab.id === tabId;
                    tab.classList.toggle('active', isVisible);
                    
                    // Если открыта вкладка лидеров, обновляем данные
                    if (isVisible && tabId === 'tab-leaders') {
                        fetchLeaders();
                    }
                    // Если открыта вкладка розыгрышей, подгружаем список
                    if (isVisible && tabId === 'tab-giveaways') {
                        fetchGiveaways();
                    }
                });
            });
        });
        } else {
            console.error('Элементы навигации не найдены!');
        }
        
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
        
        // Обработчик кнопки "Поделиться в Telegram"
        const shareButton = document.getElementById('share-telegram');
        if (shareButton) {
            shareButton.addEventListener('click', async () => {
                const referralLink = DOM.referrallink ? DOM.referrallink.value : '';
                if (referralLink) {
                    // Проверяем, что ссылка содержит префикс ref
                    if (!referralLink.includes('?start=ref')) {
                        console.error('Ошибка: реферальная ссылка не содержит префикс ref');
                        // Пытаемся исправить ссылку
                        const userId = state.userId || getUserId();
                        
                        // Получаем имя бота динамически
                        const botUsername = await getBotUsername();
                        
                        const correctedLink = `https://t.me/${botUsername}?start=ref${userId}`;
                        console.log(`Исправлена реферальная ссылка: ${correctedLink}`);
                        
                        if (DOM.referrallink) {
                            DOM.referrallink.value = correctedLink;
                        }
                    }
                    
                    const shareLink = DOM.referrallink ? DOM.referrallink.value : referralLink;
                    const shareText = 'Присоединяйся к Spin Bot и получай бонусы!';
                    
                    // Если приложение запущено внутри Telegram, используем встроенный метод
                    if (window.Telegram && window.Telegram.WebApp) {
                        window.Telegram.WebApp.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(shareLink)}&text=${encodeURIComponent(shareText)}`);
                    } else {
                        // Запасной вариант - открываем ссылку в новой вкладке
                        window.open(`https://t.me/share/url?url=${encodeURIComponent(shareLink)}&text=${encodeURIComponent(shareText)}`, '_blank');
                    }
                }
            });
        }
        
        // Настройка формы никнейма
        if (DOM.changenicknamebtn) {
            DOM.changenicknamebtn.addEventListener('click', showNicknameModal);
        }
        
        // Исправленная обработка кнопки закрытия модального окна
        DOM.closenicknamebtn = document.getElementById('close-nickname-modal');
        if (DOM.closenicknamebtn) {
            DOM.closenicknamebtn.addEventListener('click', hideNicknameModal);
        } else {
            console.error('Не найдена кнопка закрытия модального окна никнейма');
            // Пробуем добавить обработчик по классу
            const closeModalBtn = document.querySelector('.close-modal');
            if (closeModalBtn) {
                closeModalBtn.addEventListener('click', hideNicknameModal);
                console.log('Обработчик добавлен к элементу по классу .close-modal');
            }
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

    async function fetchGiveaways() {
        try {
            const items = await makeApiRequest('/api/giveaways/active');
            const list = document.getElementById('giveaways-list');
            const empty = document.getElementById('giveaways-empty');
            if (!list) return;
            list.innerHTML = '';
            if (!items || items.length === 0) {
                if (empty) empty.style.display = 'block';
                return;
            }
            if (empty) empty.style.display = 'none';
            items.forEach(g => {
                const row = document.createElement('div');
                row.className = 'leader-row';
                row.innerHTML = `
                    <div class="col-name">${g.title}</div>
                    <div class="col-score">${g.prize || ''}</div>
                `;
                const btn = document.createElement('button');
                btn.className = 'submit-button';
                btn.textContent = 'Участвовать';
                btn.addEventListener('click', async () => {
                    try {
                        const res = await makeApiRequest(`/api/giveaways/${g.id}/join`, 'POST', {});
                        if (res && res.success) {
                            alert('Вы участвуете! Участников: ' + res.total);
                        } else {
                            alert('Не удалось участвовать');
                        }
                    } catch (e) {
                        alert('Ошибка участия');
                    }
                });
                row.appendChild(btn);
                list.appendChild(row);
            });
        } catch (e) {
            console.error('Ошибка загрузки розыгрышей', e);
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
    async function handleSpin() {
        if (state.isSpinning || state.tickets <= 0) return;
        
        // Устанавливаем флаг вращения и блокируем кнопку
        state.isSpinning = true;
        DOM.spinbutton.disabled = true;
        
        try {
            // Получаем ID пользователя
            const userId = state.userId || getUserId();
            if (!userId) {
                showError("Не удалось аутентифицировать пользователя");
                state.isSpinning = false;
                DOM.spinbutton.disabled = false;
                return;
            }
            
            // Сначала запрашиваем результат с сервера
            const prediction = await makeApiRequest(
                `/api/spin/predict/${userId}`,
                'POST',
                {}
            );
            
            if (!prediction.success) {
                // Если не удалось получить предсказание, показываем ошибку
                showError(prediction.message || "Не удалось получить результат прокрутки");
                state.isSpinning = false;
                DOM.spinbutton.disabled = false;
                return;
            }
            
            // Получаем результат и seed для анимации
            const winningValue = parseInt(prediction.result);
            const seed = prediction.seed;
            
            // Используем seed для детерминированной генерации случайных чисел
            const rng = new Math.seedrandom(seed.toString());
            
            // Находим индекс сектора с нужным значением
            const winningSegmentIndex = sectors.findIndex(sector => sector.value === winningValue);
            if (winningSegmentIndex === -1) {
                showError("Ошибка при определении сектора");
                state.isSpinning = false;
                DOM.spinbutton.disabled = false;
                return;
            }
            
            // Вычисляем угол для остановки колеса
            const segmentCount = sectors.length;
            const segmentAngle = 360 / segmentCount;
            const stopAngle = segmentAngle * winningSegmentIndex + segmentAngle / 2;
            
            // Добавляем полные обороты для эффектности (5-7 оборотов)
            const rotations = 5 + Math.floor(rng() * 3);
            const fullRotationsAngle = rotations * 360;
            
            // Конечный угол: полные обороты + угол до целевого сегмента
            const spinAngle = -(fullRotationsAngle + stopAngle);
            
            // Уменьшаем количество билетов в интерфейсе (визуально)
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
            
            // Ожидаем завершения анимации и отправляем результат на сервер
            setTimeout(async () => {
                // Отправляем результат на сервер для подтверждения
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
                    
                    // Добавляем анимацию появления
                    setTimeout(() => {
                        DOM.winmessage.classList.add('active');
                        
                        // Добавляем звуковой эффект победы (если поддерживается)
                        try {
                            const winSound = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAAABMYXZjNTguMTQuMTAwAAA=');
                            winSound.play().catch(() => {});
                        } catch(e) {}
                    }, 500);
                    
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
                
                // Добавляем проверку билетов и обновление таймера после прокрутки
                checkTicketsAndUpdateTimer();
            }, 6000);
        } catch (error) {
            console.error("Ошибка при прокрутке колеса:", error);
            showError("Произошла ошибка при прокрутке колеса");
            state.isSpinning = false;
            DOM.spinbutton.disabled = false;
        }
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
                // Кодируем данные для корректной обработки на сервере
                const encodedData = encodeURIComponent(window.Telegram.WebApp.initData);
                headers['X-Telegram-Init-Data'] = encodedData;
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
        
        // Получаем ID текущего пользователя
        const currentUserId = getUserId();
        
        // Добавляем лидеров
        leaders.forEach(leader => {
            const leaderRow = document.createElement('div');
            leaderRow.className = 'leader-row';
            
            // Определяем медаль для первых трех мест
            let rankPrefix = '';
            if (leader.rank === 1) rankPrefix = '🥇 ';
            else if (leader.rank === 2) rankPrefix = '🥈 ';
            else if (leader.rank === 3) rankPrefix = '🥉 ';
            
            // Форматируем числа для более удобного чтения
            const formattedScore = new Intl.NumberFormat('ru-RU').format(leader.score);
            
            // Проверяем, является ли этот лидер текущим пользователем
            // Предполагаем, что в данных лидера есть поле id, которое можно сравнить с текущим пользователем
            if (leader.id === currentUserId) {
                leaderRow.classList.add('current-user');
            }
            
            leaderRow.innerHTML = `
                <div class="col-rank">${rankPrefix}${leader.rank}</div>
                <div class="col-name">${leader.name}</div>
                <div class="col-score">${formattedScore}</div>
            `;
            
            leadersList.appendChild(leaderRow);
        });
        
        // Если список пуст, показываем сообщение
        const emptyMessage = document.querySelector('.leaders-empty');
        if (emptyMessage) {
            emptyMessage.classList.toggle('active', leaders.length === 0);
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
    
    // Функция для отображения успешного сообщения
    function showSuccess(message) {
        alert(message);
    }
    
    // Функция для создания колеса с правильно расположенными цифрами
    function createWheel() {
        const segmentCount = sectors.length;
        const segmentAngle = 360 / segmentCount;
        const wheelRadius = 150; // Радиус колеса
        const labelRadius = 90; // Радиус для размещения текста (уменьшен для лучшего размещения)
        
        // Находим контейнер колеса
        const wheel = document.querySelector('.wheel-container');
        if (!wheel) {
            console.error('Контейнер колеса не найден!');
            return;
        }
        
        console.log('Создаем колесо в контейнере:', wheel);
        
        // Очищаем контейнер и создаем новый SVG
        wheel.innerHTML = '';
        
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("width", "300");
        svg.setAttribute("height", "300");
        svg.setAttribute("viewBox", "0 0 300 300");
        svg.style.display = "block";
        svg.style.margin = "0 auto";
        wheel.appendChild(svg);
        
        console.log('SVG создан:', svg);
        
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
            
            // Координаты для построения пути сектора (центр SVG = 150, 150)
            const centerX = 150;
            const centerY = 150;
            const x1 = centerX + wheelRadius * Math.cos(startRad);
            const y1 = centerY + wheelRadius * Math.sin(startRad);
            const x2 = centerX + wheelRadius * Math.cos(endRad);
            const y2 = centerY + wheelRadius * Math.sin(endRad);
            
            // Создаем путь SVG для сектора
            const largeArcFlag = segmentAngle > 180 ? 1 : 0;
            const pathData = `M ${centerX},${centerY} L ${x1},${y1} A ${wheelRadius},${wheelRadius} 0 ${largeArcFlag} 1 ${x2},${y2} Z`;
            
            segment.setAttribute("d", pathData);
            segment.setAttribute("fill", sectors[i].color);
            segment.setAttribute("stroke", "#8B5CF6"); // Фиолетовый цвет для границ секторов
            segment.setAttribute("stroke-width", "2");
            segment.setAttribute("data-value", sectors[i].value);
            segment.setAttribute("data-index", i);
            
            // Добавляем линии от центра к краям
            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", centerX);
            line.setAttribute("y1", centerY);
            line.setAttribute("x2", x1);
            line.setAttribute("y2", y1);
            line.setAttribute("stroke", "#8B5CF6"); // Фиолетовый цвет для линий
            line.setAttribute("stroke-width", "2");
            
            // Добавляем текст с числом в центр сегмента
            const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
            
            // Вычисляем позицию для текста - в центре сегмента
            const textX = centerX + labelRadius * Math.cos(midRad);
            const textY = centerY + labelRadius * Math.sin(midRad);
            
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
        
        // Создаем градиент для центрального круга
        const gradient = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
        gradient.setAttribute("id", "centerGradient");
        gradient.setAttribute("x1", "0%");
        gradient.setAttribute("y1", "0%");
        gradient.setAttribute("x2", "100%");
        gradient.setAttribute("y2", "100%");
        
        const stop1 = document.createElementNS("http://www.w3.org/2000/svg", "stop");
        stop1.setAttribute("offset", "0%");
        stop1.setAttribute("stop-color", "#9C27B0");
        
        const stop2 = document.createElementNS("http://www.w3.org/2000/svg", "stop");
        stop2.setAttribute("offset", "100%");
        stop2.setAttribute("stop-color", "#673AB7");
        
        gradient.appendChild(stop1);
        gradient.appendChild(stop2);
        
        // Добавляем градиент в defs
        const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        defs.appendChild(gradient);
        svg.appendChild(defs);
        
        centerCircle.setAttribute("fill", "url(#centerGradient)");
        centerCircle.setAttribute("stroke", "#FFFFFF");
        centerCircle.setAttribute("stroke-width", "2");
        centerCircle.setAttribute("filter", "drop-shadow(0 0 10px rgba(156, 39, 176, 0.4))");
        
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
            
            // Обрабатываем выигранный приз
            if (data.is_win && data.prize) {
                state.currentPrize = data.prize;
                showPrizeWin(data.prize);
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
            
            // Дополнительно проверяем работу кнопки закрытия
            const closeBtn = document.querySelector('#nickname-modal .close-modal');
            if (closeBtn) {
                closeBtn.addEventListener('click', hideNicknameModal);
            }
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
            DOM.nicknameerror.classList.add('active');
        }
    }
    
    // Функция для очистки ошибки никнейма
    function clearNicknameError() {
        if (DOM.nicknameerror) {
            DOM.nicknameerror.textContent = '';
            DOM.nicknameerror.classList.remove('active');
        }
    }

    // Функция для получения имени пользователя бота
    async function getBotUsername() {
        try {
            const botInfo = await makeApiRequest('/api/user/bot-info');
            return botInfo.username;
        } catch (error) {
            console.error('Ошибка при получении информации о боте:', error);
            // Используем имя по умолчанию в случае ошибки
            return 'spin_bot';
        }
    }

    // Добавим функцию обновления реферальной информации
    async function updateReferralInfo(userId, referralCount) {
        // Получаем информацию о боте
        let botUsername = '';
        try {
            const botInfo = await makeApiRequest('/api/user/bot-info');
            botUsername = botInfo.username;
            console.log(`Получено имя бота с сервера: ${botUsername}`);
        } catch (error) {
            console.error('Ошибка при получении информации о боте:', error);
            // Используем имя по умолчанию, если не удалось получить с сервера
            botUsername = 'spin_bot'; // Значение по умолчанию
            console.warn(`Используем имя бота по умолчанию: ${botUsername}`);
        }
        
        // Обновляем реферальную ссылку
        if (DOM.referrallink) {
            // Обновляем ссылку с актуальным ID пользователя и именем бота
            DOM.referrallink.value = `https://t.me/${botUsername}?start=ref${userId}`;
            
            // Проверяем, что ссылка сформирована правильно
            console.log(`Реферальная ссылка обновлена: ${DOM.referrallink.value}`);
            
            // Убедимся, что префикс ref присутствует
            if (!DOM.referrallink.value.includes('?start=ref')) {
                console.error('Ошибка в формировании реферальной ссылки: отсутствует префикс ref');
                DOM.referrallink.value = `https://t.me/${botUsername}?start=ref${userId}`;
            }
        }
        
        // Обновляем счетчик приглашенных друзей
        const invitedCountElement = document.getElementById('invited-count');
        if (invitedCountElement) {
            invitedCountElement.textContent = referralCount;
        }
        
        // Получаем и отображаем список рефералов, если мы на вкладке рефералов
        const referralTab = document.getElementById('tab-referral');
        if (referralTab && referralTab.classList.contains('active')) {
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

    // Функция для проверки подписки пользователя
    async function checkUserSubscription() {
        try {
            const userData = window.Telegram.WebApp.initDataUnsafe;
            
            if (!userData || !userData.user) {
                console.warn('Не удалось получить данные пользователя');
                return;
            }
            
            const userId = userData.user.id;
            
            const response = await makeApiRequest('/api/user/check_subscription', 'POST', {
                user_id: userId,
                initData: window.Telegram.WebApp.initData
            });
            
            if (response.success) {
                console.log('Подписка пользователя успешно проверена.');
                // Здесь можно добавить логику обработки результата проверки подписки,
                // например, если нужно обновить UI или показать сообщение.
            } else {
                console.warn('Проверка подписки не удалась:', response.message);
                // Здесь можно показать ошибку или предупреждение пользователю
            }
        } catch (error) {
            console.error('Ошибка при проверке подписки:', error);
            showError('Не удалось проверить подписку. Пожалуйста, попробуйте позже.');
        }
    }
});
