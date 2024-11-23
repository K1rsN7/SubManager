import requests
import logging

# Замените эти значения на свои
USERNAME = 'YOUR_USERNAME'
TOKEN = 'YOUR_ACCESS_TOKEN'
GLOBAL_PATH = "YOUR_GLOBAL_PATH"

# URL для API GitHub
BASE_URL = 'https://api.github.com'
BAN_LIST_FILE_PATH_FOLLOWERS = f'{GLOBAL_PATH}/ban_list_followers.txt'  
BAN_LIST_FILE_PATH_FOLLOWING = f'{GLOBAL_PATH}/ban_list_following.txt' 

# Настройка логирования
logging.basicConfig(filename=f'{GLOBAL_PATH}/subscription_manager.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def load_ban_list(file_path):
    """Загружает бан-лист из файла."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return {line.strip() for line in file if line.strip()}
    except FileNotFoundError:
        return set()

def get_followers(ban_list):
    """Получает список подписчиков с поддержкой постраничной навигации, исключая пользователей из бан-листа."""
    followers = []
    page = 1
    while True:
        url = f'{BASE_URL}/users/{USERNAME}/followers?per_page=100page={page}'
        try:
            response = requests.get(url)
            response.raise_for_status()  # Проверка на ошибки
            current_followers = response.json()
            
            if not current_followers:  # Если текущая страница пустая, выходим из цикла
                break
            
            # Фильтруем подписчиков, исключая тех, кто в бан-листе
            followers.extend(follower['login'] for follower in current_followers if follower['login'] not in ban_list)
            page += 1  # Переход к следующей странице

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:  # Проверка на ошибку 403 (лимит запросов)
                logging.error('API недоступен временно: превышен лимит запросов.')
                break  # Выход из цикла при превышении лимита

    return followers

def get_following(ban_list):
    """Получает список пользователей, на которых вы подписаны с поддержкой постраничной навигации, исключая пользователей из бан-листа."""
    following = []
    page = 1
    while True:
        url = f'{BASE_URL}/users/{USERNAME}/following?per_page=100&page={page}'
        try:
            response = requests.get(url)
            response.raise_for_status()  # Проверка на ошибки
            current_following = response.json()
            
            if not current_following:  # Если текущая страница пустая, выходим из цикла
                break
            
            # Фильтруем подписок, исключая тех, кто в бан-листе
            following.extend(followed['login'] for followed in current_following if followed['login'] not in ban_list)
            page += 1  # Переход к следующей странице

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:  # Проверка на ошибку 403 (лимит запросов)
                logging.error('API недоступен временно: превышен лимит запросов.')
                break  # Выход из цикла при превышении лимита

    return following

def follow_user(username):
    """Подписывается на пользователя."""
    url = f'{BASE_URL}/user/following/{username}'
    try:
        response = requests.put(url, auth=(USERNAME, TOKEN))
        response.raise_for_status()
        logging.info(f'Подписались на {username}')
    except requests.exceptions.HTTPError as e:
        logging.error(f'Не удалось подписаться на {username}: {e}')
    except requests.exceptions.RequestException as e:
        logging.error(f'Ошибка запроса при подписке на {username}: {e}')

def unfollow_user(username):
    """Отписывается от пользователя."""
    url = f'{BASE_URL}/user/following/{username}'
    try:
        response = requests.delete(url, auth=(USERNAME, TOKEN))
        response.raise_for_status()
        logging.info(f'Отписались от {username}')
    except requests.exceptions.HTTPError as e:
        logging.error(f'Не удалось отписаться от {username}: {e}')
    except requests.exceptions.RequestException as e:
        logging.error(f'Ошибка запроса при отписке от {username}: {e}')

def manage_subscriptions(ban_list_followers, ban_list_following):
    """Управляет подписками с учетом бан-листов."""
    followers = get_followers(ban_list_followers)
    following = get_following(ban_list_following)

    # Подписываемся на всех, кто на вас подписан
    for follower in followers:
        if follower not in following:
            follow_user(follower)

    # Отписываемся от тех, кто не подписан на вас
    for followed in following:
        if followed not in followers:
            unfollow_user(followed)

if __name__ == '__main__':
    logging.info("Скрипт запущен") 
    ban_list_followers = load_ban_list(BAN_LIST_FILE_PATH_FOLLOWERS)  
    ban_list_following = load_ban_list(BAN_LIST_FILE_PATH_FOLLOWING)  
    
    manage_subscriptions(ban_list_followers, ban_list_following)  
