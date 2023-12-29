const currentURL = window.location.pathname;

    // Функция для применения стилей активной кнопке
    function setActiveButton(button, buttonImage, buttonText) {
        button.style.backgroundColor = '#585e6c';
        buttonImage.src = buttonImage.src.replace('-black.png', '.png');
        buttonText.style.color = 'white';
    }

    // Получаем кнопки навигации по их идентификаторам
    const homeButton = document.getElementById('homeButton');
    const catalogButton = document.getElementById('catalogButton');
    const cartButton = document.getElementById('cartButton');
    const faqButton = document.getElementById('faqButton');
    const profileButton = document.getElementById('profileButton');
    const loginButton = document.getElementById('loginButton');

    // Проверяем текущий URL и применяем стили активной кнопке

    if (currentURL === '/') {
        setActiveButton(homeButton, document.getElementById('homeButtonImage'), document.getElementById('homeButtonText'));
    } else if (currentURL === '/catalog/') {
        setActiveButton(catalogButton, document.getElementById('catalogButtonImage'), document.getElementById('catalogButtonText'));
    } else if (currentURL === '/cart/') {
        setActiveButton(cartButton, document.getElementById('cartButtonImage'), document.getElementById('cartButtonText'));
    } else if (currentURL === '/faq/') {
        setActiveButton(faqButton, document.getElementById('faqButtonImage'), document.getElementById('faqButtonText'));
    } else if (currentURL === '/profile/') {
        setActiveButton(profileButton, document.getElementById('profileButtonImage'), document.getElementById('profileButtonText'));
    } else if (currentURL === '/login/') {
        setActiveButton(loginButton, document.getElementById('loginButtonImage'), document.getElementById('loginButtonText'));
    }