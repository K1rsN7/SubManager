import requests
from bs4 import BeautifulSoup
from pathlib import Path
import logging
import time
import os 
import sys
import json

# URL for GitHub API
BASE_URL = 'https://api.github.com'

# Upload the ban list
GLOBAL_PATH = str(Path(__file__).resolve().parent)
BAN_LIST_FILE_PATH_FOLLOWERS = f'{GLOBAL_PATH}/ban_list_followers.txt'  
BAN_LIST_FILE_PATH_FOLLOWING = f'{GLOBAL_PATH}/ban_list_following.txt' 

# Characters for process display
LOADING_CHAR = ['|', '/', '-', '\\']

# Configuring logging
logging.basicConfig(filename=f'{GLOBAL_PATH}/subscription_manager.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Global variables
USERNAME = None
TOKEN = None
PROMOTION_ON = None
DAYS_PERIOD = None
COUNT_PROMOTION_USERS = None
RETRY_ON = None  

def check_internet_connection() -> None:
    """Check if the internet connection is available."""
    try:
        requests.get("https://github.com", timeout=10)
    except requests.RequestException as e:
        raise ConnectionError(f"No internet connection: {e}") from e


def load_config_file(path_config_file: str) -> None:
    global USERNAME, TOKEN, PROMOTION_ON, DAYS_PERIOD, COUNT_PROMOTION_USERS, RETRY_ON
    """Loads the configuration file."""
    with open(path_config_file, 'r', encoding='utf-8') as file:
        data = json.load(file)
    USERNAME = data["USERNAME"]
    TOKEN = data["TOKEN"]
    PROMOTION_ON = data["PROMOTION"]
    DAYS_PERIOD = data["DAYS_PERIOD"]
    COUNT_PROMOTION_USERS = data["COUNT_PROMOTION_USERS"]
    RETRY_ON = data.get("RETRY_ON", True)  # Default to True if not specified

def load_ban_list(file_path:str) -> set:
    """Loads a ban list from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return set(line.strip() for line in file if line.strip())
    except FileNotFoundError:
        return set()

def retry_request(url, method='get', max_retries=10, delay=1, **kwargs):
    """Retry a request with exponential backoff."""
    retries = 0
    while retries < max_retries:
        try:
            if method == 'get':
                response = requests.get(url, **kwargs)
            elif method == 'put':
                response = requests.put(url, **kwargs)
            elif method == 'delete':
                response = requests.delete(url, **kwargs)
            else:
                raise ValueError("Unsupported HTTP method")
            
            response.raise_for_status()
            return response
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [503, 504, 429] and RETRY_ON:
                retries += 1
                time.sleep(delay * (2 ** retries))
            else:
                raise e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if RETRY_ON and retries < max_retries:
                retries += 1
                logging.warning(f"Connection error: {e}. Retry {retries}/{max_retries}")
                time.sleep(delay * (2 ** retries))
            else:
                raise e
    raise requests.exceptions.RetryError(f"Max retries ({max_retries}) exceeded.")

def get_users_list(ban_list: set, message:str, user_type:str='followers', current_username:str=None, isPromoted:bool=False, isPrint=True):
    """
    Gets a list of users (subscribers or subscriptions) with support for paginated navigation,
    excluding users from the ban list.

    Args:
        ban_list (set): List of users to be excluded
        message (str): Message to be output in the process
        user_type (str): Type of users to receive (‘followers’ or ‘following’)
        username (str): GitHub username 
        isPromoted (bool): Include promoted users in the list (default: False)
    Returns:
        list: User list
    """
    if current_username is None:
        current_username = USERNAME
    if user_type not in ['followers', 'following']:
        raise ValueError("user_type must be ‘followers’ or ‘following’")

    logging.info(f"Parsing {'followers' if user_type == 'followers' else 'following'}...") 
    users = []
    page = 1
    while True:
        if isPrint:
            sys.stdout.write(f'\r{message} {LOADING_CHAR[page % 4]}')
            sys.stdout.flush() 
        url = f'https://github.com/{current_username}?tab={user_type}&page={page}'
        try:
            response = retry_request(url, method='get')
            response.raise_for_status() # Checking for errors
            
            # Parsing the HTML code of a page
            soup = BeautifulSoup(response.text, 'html.parser')
            current_users = soup.find_all('img', class_='avatar')
            
            if not current_users: # If the current page is empty, exit the loop
                break
            
            # Filter users to exclude those on the ban list
            for user in current_users[1:]:
                username = user.get('alt')[1:]
                if username not in ban_list:
                    users.append(username)

            # If the number of current users is less than 2, exit the loop
            if len(current_users) < 2 or isPromoted:
                break
            
            page += 1  # Go to the next page
            time.sleep(0.75) # Delay between requests to bypass error 429

        except requests.exceptions.HTTPError as e:
            logging.error(f'HTTP Error: {e}')
            break

    return users

def print_logo() -> None:
    """Printing of the programme logo"""
    logo = r"""
  _____       _    ___  ___                                  
 /  ___|     | |   |  \/  |                                  
 \ `--. _   _| |__ | .  . | __ _ _ __   __ _  __ _  ___ _ __ 
  `--. \ | | | '_ \| |\/| |/ _` | '_ \ / _` |/ _` |/ _ \ '__|
 /\__/ / |_| | |_) | |  | | (_| | | | | (_| | (_| |  __/ |   
 \____/ \__,_|_.__/\_|  |_|\__,_|_| |_|\__,_|\__, |\___|_|   
                                              __/ |          
                                             |___/           
_____________________________________________________________          
    """
    print(logo)

def update_subscription(username:str, isFollowing=False) -> None:
    """
    Manages the subscription for the user.
    Args:
        username (str): GitHub username
        isFollowing (bool): True if the user should be followed, False otherwise"""
    url = f'{BASE_URL}/user/following/{username}'
    try:
        if isFollowing:
            response = retry_request(url, method='put', max_retries=3, delay=1, auth=(USERNAME, TOKEN))
        else:
            response = retry_request(url, method='delete', max_retries=3, delay=1, auth=(USERNAME, TOKEN))
        response.raise_for_status()
        message = f'{"Subscribed to" if isFollowing else "Unsubscribed from"} {username}'
        print(message)
        logging.info(message)
    except requests.exceptions.HTTPError as e:
        message = f'Failed {"subscribe" if isFollowing else "unsubscribe"} from {username}: {e}'
        print(message)
        logging.error(message)
    except requests.exceptions.RequestException as e:
        message = f'Query error on {"subscriptions" if isFollowing else "unsubscribes"} for {username}: {e}'
        print(message)
        logging.error(message)

def promotion(follower_list:list, ban_list_followers:list, count:int) -> list:
    """
    Promotion logic subscribers.

    Args:
        follower_list (list): List of followers.
        ban_list_followers (list): The list of users to be excluded from the subscription list.
        count (int): The number of followers required to be promoted.
    Returns:
        list: List of users who should be promoted.
    """
    # Placeholder for promotion logic
    promotion_users = []  # Placeholder for promoted users
    counter = 0
    for follower_current in follower_list:
        followers_user = get_users_list(ban_list_followers, message=f"Getting {follower_current}'s latest subscribers.", current_username=follower_current, isPromoted=True, isPrint=False)
        for new_followers in followers_user :
            if new_followers not in follower_list and new_followers not in promotion_users:
                sys.stdout.write(f'\rGet a list of users for promotion {LOADING_CHAR[counter % 4]}')
                sys.stdout.flush()
                counter += 1
                if len(promotion_users) < count and new_followers != USERNAME:
                    promotion_users.append(new_followers)
                else:
                    break
        if len(promotion_users) >= count:
            break  # If the required number of followers has been promoted, exit the loop
    
    # Saving promoted users to a text file
    current_date = time.strftime("%Y-%m-%d", time.localtime())
    try:
        with open(f"{GLOBAL_PATH}/promoted_users.txt", "a") as file:
            for user in promotion_users:
                file.write(f"{user} {current_date}\n")
    except FileNotFoundError:
        with open(f"{GLOBAL_PATH}/promoted_users.txt", "w") as file:
            for user in promotion_users:
                file.write(f"{user} {current_date}\n")
    
    return promotion_users
    
def check_promotion(days_period:int=5) -> tuple[list[str], list[str]]:
    """Checks users who have been promoted and updates the list
    depending on the specified time period.

    :param days_period: Period in days to check, default is 5.
    :return: A tuple of two lists:
             - Updated users that are still active.
             - Users that have been removed from the promotion list.
    """
    with open(f"{GLOBAL_PATH}/promoted_users.txt", "r") as file:  
        all_promoted_users = file.readlines()[:-1]  
        
    updated_promoted_users = [] # Clear all promoted users
    check_promoted_users = [] # Promoted users to check
    cutoff_time = days_period * 24 * 60 * 60
    current_time = time.time()
    counter = 0
    for entry in all_promoted_users:
        sys.stdout.write(f'\rChecking the old user list for promotion {LOADING_CHAR[counter % 4]}')
        sys.stdout.flush() 
        username, date_str = entry.rsplit(' ', 1)  # Split the string into username and date
        entry_time = time.mktime(time.strptime(date_str.strip(), "%Y-%m-%d"))  
        if current_time - entry_time <= cutoff_time: 
            updated_promoted_users.append(f"{username} {date_str}")
        else:
            check_promoted_users.append(username)
        counter += 1
        
    with open(f"{GLOBAL_PATH}/promoted_users.txt", "w") as file:  
        for line in updated_promoted_users:
            file.write(line)  # Write the actual records back to the file
    updated_promoted_users = [item.split()[0] for item in updated_promoted_users]
    return updated_promoted_users, check_promoted_users
 
def manage_subscriptions(ban_list_followers: set, ban_list_following: set) -> None:
    """
    Manages the user's subscriptions based on bins lists.

    Args:
        ban_list_followers (set): The set of users to be unsubscribed from the subscription list.
        ban_list_following (set): The set of users who should be excluded from the subscription list.
    """
    followers = get_users_list(ban_list_followers, message="Get a list of subscribers", user_type='followers')
    print("\nSubscription list received!")
    following = get_users_list(ban_list_following, message="Getting a list of subscriptions", user_type='following')
    print("\nSubscription list received!")

    if PROMOTION_ON:
        # Promote users clear
        not_check_promotion_user, check_promotion_user = check_promotion(days_period=DAYS_PERIOD)
        followers.extend(not_check_promotion_user)
        following.extend(check_promotion_user)
        print()
        
        # Promote users add
        promotion_user = promotion(followers, ban_list_followers, count=COUNT_PROMOTION_USERS)
        followers.extend(promotion_user)
        print()
        
    # Subscribe to everyone who subscribes to you
    for follower in followers:
        if follower not in following:
            update_subscription(follower, isFollowing=True)
            time.sleep(0.3)

    # Unsubscribe from those who are not subscribed to you
    for followed in following:
        if followed not in followers:
            update_subscription(followed)
            time.sleep(0.3)

if __name__ == '__main__':
    print_logo()
    print("Script Started")
    logging.info("Script started") 
    
    print("Load config...")
    load_config_file(f"{GLOBAL_PATH}/config.json")

    try:
        check_internet_connection()
       
        ban_list_followers = load_ban_list(BAN_LIST_FILE_PATH_FOLLOWERS)  
        ban_list_following = load_ban_list(BAN_LIST_FILE_PATH_FOLLOWING)  
        
        manage_subscriptions(ban_list_followers, ban_list_following) 
    except ConnectionError as e:
        print(e)

    print("Script Finished")
