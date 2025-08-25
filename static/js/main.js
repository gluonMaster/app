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

    // Функция для обновления счетчика уведомлений
    function updateNotificationBadge() {
        fetch('/notifications/api/unread-count/')
            .then(response => response.json())
            .then(data => {
                const badge = document.querySelector('#notificationsDropdown .badge');
                const notificationLink = document.querySelector('#notificationsDropdown');

                if (data.unread_count > 0) {
                    if (badge) {
                        badge.textContent = data.unread_count;
                        badge.style.display = 'inline';
                    } else {
                        // Создаем badge если его нет
                        const newBadge = document.createElement('span');
                        newBadge.className = 'position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger';
                        newBadge.textContent = data.unread_count;
                        notificationLink.appendChild(newBadge);
                    }
                } else {
                    if (badge) {
                        badge.style.display = 'none';
                    }
                }
            })
            .catch(error => console.error('Error updating notification badge:', error));
    }

    // AJAX для загрузки последних уведомлений
    function loadNotifications() {
        fetch('/notifications/api/latest/')
            .then(response => response.json())
            .then(data => {
                const dropdownMenu = document.querySelector('#notificationsDropdown + .dropdown-menu');
                if (dropdownMenu && data.notifications) {
                    // Очищаем старое содержимое (кроме заголовка и ссылки "Все показать")
                    const header = dropdownMenu.querySelector('.dropdown-header');
                    const divider = dropdownMenu.querySelector('.dropdown-divider');
                    const viewAllLink = dropdownMenu.querySelector('.dropdown-item.text-center');

                    dropdownMenu.innerHTML = '';

                    // Восстанавливаем заголовок
                    if (header) dropdownMenu.appendChild(header);
                    if (divider) dropdownMenu.appendChild(divider);

                    // Добавляем уведомления
                    if (data.notifications.length === 0) {
                        const emptyItem = document.createElement('li');
                        emptyItem.innerHTML = '<span class="dropdown-item-text text-muted">Keine neuen Benachrichtigungen</span>';
                        dropdownMenu.appendChild(emptyItem);
                    } else {
                        data.notifications.slice(0, 5).forEach(notification => {
                            const item = document.createElement('li');
                            const priorityClass = notification.priority === 'critical' ? 'text-danger' :
                                                notification.priority === 'high' ? 'text-warning' : '';

                            item.innerHTML = `
                                <a class="dropdown-item ${notification.is_read ? '' : 'fw-bold'}"
                                   href="/notifications/${notification.id}/">
                                    <div class="d-flex justify-content-between align-items-start">
                                        <div style="max-width: 250px;">
                                            <div class="fw-bold ${priorityClass}">${notification.title}</div>
                                            <small class="text-muted">${notification.message}</small>
                                            <br><small class="text-muted">${notification.created_at}</small>
                                        </div>
                                        ${!notification.is_read ? '<span class="badge bg-primary ms-2">Neu</span>' : ''}
                                    </div>
                                </a>
                            `;
                            dropdownMenu.appendChild(item);
                        });

                        // Добавляем разделитель
                        const dividerItem = document.createElement('li');
                        dividerItem.innerHTML = '<hr class="dropdown-divider">';
                        dropdownMenu.appendChild(dividerItem);
                    }

                    // Восстанавливаем ссылку "Все показать"
                    if (viewAllLink) dropdownMenu.appendChild(viewAllLink);
                }
            })
            .catch(error => console.error('Error loading notifications:', error));
    }

    // Загружаем уведомления при клике на dropdown
    const notificationDropdown = document.querySelector('#notificationsDropdown');
    if (notificationDropdown) {
        notificationDropdown.addEventListener('click', function() {
            loadNotifications();
        });
    }

    // Обновляем счетчик каждые 30 секунд
    updateNotificationBadge();
    setInterval(updateNotificationBadge, 30000);

    // Функция для отметки всех уведомлений как прочитанных
    window.markAllNotificationsRead = function() {
        fetch('/notifications/api/mark-all-read/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateNotificationBadge();
                loadNotifications();
            }
        })
        .catch(error => console.error('Error marking notifications as read:', error));
    };
});
