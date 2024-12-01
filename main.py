import requests
from bs4 import BeautifulSoup
import logging
import time

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
    logging.info("Парсим подписчиков...") 
    """Получает список подписчиков с поддержкой постраничной навигации, исключая пользователей из бан-листа."""
    followers = list() 
    page = 1
    
    while True:
        url = f'https://github.com/{USERNAME}?tab=followers&page={page}'
        try:
            response = requests.get(url)
            response.raise_for_status()  # Проверка на ошибки
            # Парсинг HTML-кода страницы
            soup = BeautifulSoup(response.text, 'html.parser')
            current_followers = soup.find_all('img', class_='avatar')
            
            if not current_followers:  # Если текущая страница пустая, выходим из цикла
                break

            # Фильтруем подписчиков, исключая тех, кто в бан-листе
            for follower in current_followers[1:]:
                follower_username = follower.get('alt')[1:]
                if follower_username not in ban_list:
                    followers.append(follower_username)
                
            # Если количество текущих подписчиков меньше 2, выходим из цикла
            if len(current_followers) < 2:
                break
            
            page += 1  # Переход к следующей странице
            time.sleep(1)  # Задержка между запросами

        except requests.exceptions.HTTPError as e:
            logging.error(f'Ошибка HTTP: {e}')
            break  # Выход из цикла при ошибке

    return followers

def get_following(ban_list):
    logging.info("Парсим подписки...") 
    """Получает список пользователей, на которых вы подписаны с поддержкой постраничной навигации, исключая пользователей из бан-листа."""
    following = list() 
    page = 1
    
    while True:
        url = f'https://github.com/{USERNAME}?tab=following&page={page}'
        try:
            response = requests.get(url)
            response.raise_for_status()  # Проверка на ошибки
            
            # Парсинг HTML-кода страницы
            soup = BeautifulSoup(response.text, 'html.parser')
            current_following = soup.find_all('img', class_='avatar')
            
            if not current_following:  # Если текущая страница пустая, выходим из цикла
                break
            
            # Фильтруем подписок, исключая тех, кто в бан-листе
            for followed in current_following[1:]:
                followed_username = followed.get('alt')[1:]
                if followed_username not in ban_list:
                    following.append(followed_username)

            # Если количество текущих подписок меньше 2, выходим из цикла
            if len(current_following) < 2:
                break
            
            page += 1  # Переход к следующей странице
            time.sleep(1)  # Задержка между запросами

        except requests.exceptions.HTTPError as e:
            logging.error(f'Ошибка HTTP: {e}')
            break  # Выход из цикла при ошибке

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
