// Основной JavaScript для системы
document.addEventListener('DOMContentLoaded', function() {
    // Автоматическое скрытие сообщений через 5 секунд
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // AJAX для загрузки уведомлений
    function loadNotifications() {
        fetch('/notifications/api/latest/')
            .then(response => response.json())
            .then(data => {
                const dropdown = document.querySelector('#notificationsDropdown + .dropdown-menu');
                if (dropdown && data.notifications) {
                    // Обновляем содержимое dropdown
                    // TODO: Реализовать обновление уведомлений
                }
            })
            .catch(error => console.error('Error loading notifications:', error));
    }

    // Загружаем уведомления каждые 30 секунд
    setInterval(loadNotifications, 30000);
});
