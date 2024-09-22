import threading
import requests
from bs4 import BeautifulSoup
import telebot
import time
import pytz
from datetime import datetime
import re

# Telegram bot token
TOKEN = '7398509052:AAHi8DawTGRNKbv2ZM6gHuaG26WeM9UnRWg'

# Base URLs
url_rent = "https://bina.az/baki/kiraye/menziller"
url_buy = "https://bina.az/baki/alqi-satqi/menziller"

# Headers for requests
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Create Telegram bot
bot = telebot.TeleBot(TOKEN)

# Set the timezone to UTC+4 (Azerbaijan time)
tz = pytz.timezone('Asia/Baku')

# Global variables
users_data = {}  # Dictionary to store user data

# State constants
STATE_LISTING_TYPE = 'listing_type'
STATE_OPERATION_TYPE = 'operation_type'
STATE_PRICE_RANGE = 'price_range'
STATE_CONTROL = 'control'


# Handle start command
@bot.message_handler(commands=['start'])
def start_message(message):
    chat_id = message.chat.id
    users_data[chat_id] = {
        'notification_enabled': False,
        'listing_type': None,
        'operation_type': None,
        'price_from': None,
        'price_to': None,
        'notification_time': None,
        'url': None,
        'state': None,
        'notification_thread': None,
        'sent_listings': set()
    }
    ask_listing_type(chat_id)


# Ask user what type of listings they want to see
def ask_listing_type(chat_id):
    users_data[chat_id]['state'] = STATE_LISTING_TYPE
    keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    keyboard.add(telebot.types.KeyboardButton('Agentlik'))
    keyboard.add(telebot.types.KeyboardButton('Mülkiyyətçi'))
    keyboard.add(telebot.types.KeyboardButton('Hər ikisi'))
    bot.send_message(chat_id, 'Hansı tip elanları görmək istərdiz?', reply_markup=keyboard)


# Handle user response to listing type question
@bot.message_handler(func=lambda message: message.chat.id in users_data and users_data[message.chat.id][
    'state'] == STATE_LISTING_TYPE and message.text in ['Agentlik', 'Mülkiyyətçi', 'Hər ikisi'])
def handle_listing_type_response(message):
    chat_id = message.chat.id
    users_data[chat_id]['listing_type'] = message.text
    bot.send_message(chat_id, f'Siz "{message.text}" tip elanları seçdiniz.')
    ask_operation_type(chat_id)


# Ask user for the operation type (Alış yoxsa kirayə)
def ask_operation_type(chat_id):
    users_data[chat_id]['state'] = STATE_OPERATION_TYPE
    keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    keyboard.add(telebot.types.KeyboardButton('Alış'))
    keyboard.add(telebot.types.KeyboardButton('Kirayə'))
    bot.send_message(chat_id, 'Alış yoxsa kirayə?', reply_markup=keyboard)


# Handle user response to operation type question
@bot.message_handler(func=lambda message: message.chat.id in users_data and users_data[message.chat.id][
    'state'] == STATE_OPERATION_TYPE and message.text in ['Alış', 'Kirayə'])
def handle_operation_type_response(message):
    chat_id = message.chat.id
    users_data[chat_id]['operation_type'] = message.text
    bot.send_message(chat_id, f'Siz "{message.text}" seçdiniz.')
    ask_price_range(chat_id)


# Ask user for the price range
def ask_price_range(chat_id):
    users_data[chat_id]['state'] = STATE_PRICE_RANGE
    bot.send_message(chat_id, 'Zəhmət olmasa, qiymət aralığını daxil edin (məsələn, 100-400):')


# Handle user response to price range
@bot.message_handler(func=lambda message: message.chat.id in users_data and users_data[message.chat.id][
    'state'] == STATE_PRICE_RANGE and bool(re.match(r'^\d+-\d+$', message.text)))
def handle_price_range_response(message):
    chat_id = message.chat.id
    price_range = message.text
    price_from, price_to = map(int, price_range.split('-'))
    users_data[chat_id]['price_from'] = price_from
    users_data[chat_id]['price_to'] = price_to
    users_data[chat_id]['notification_enabled'] = True
    users_data[chat_id]['notification_time'] = datetime.now(tz).strftime("%H:%M")

    # Determine the URL based on operation type
    operation_type = users_data[chat_id]['operation_type']
    url = f"{url_buy}?price_from={price_from}&price_to={price_to}" if operation_type == 'Alış' else f"{url_rent}?price_from={price_from}&price_to={price_to}"
    users_data[chat_id]['url'] = url

    bot.send_message(chat_id, f'Siz "{price_from}"-dan "{price_to}"-a qədər qiymət aralığını seçdiniz.')
    bot.send_message(chat_id, 'Uğurla seçildi! Siz yeni elanlarla bağlı bildiriş alacaqsız.')
    show_control_buttons(chat_id)
    start_notifications(chat_id)


# Handle invalid price range format
@bot.message_handler(func=lambda message: message.chat.id in users_data and users_data[message.chat.id][
    'state'] == STATE_PRICE_RANGE and not re.match(r'^\d+-\d+$', message.text))
def handle_invalid_price_range(message):
    bot.send_message(message.chat.id, 'Zəhmət olmasa, qiymət aralığını düzgün formatda daxil edin (məsələn, 100-400):')


# Show control buttons
def show_control_buttons(chat_id):
    users_data[chat_id]['state'] = STATE_CONTROL
    keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    keyboard.add(telebot.types.KeyboardButton('Bildirişləri söndür'))
    keyboard.add(telebot.types.KeyboardButton('Filterləri dəyiş'))
    bot.send_message(chat_id, 'Seçimlərinizi dəyişmək üçün düymələr:', reply_markup=keyboard)


# Handle control buttons
@bot.message_handler(func=lambda message: message.chat.id in users_data and users_data[message.chat.id][
    'state'] == STATE_CONTROL and message.text in ['Bildirişləri söndür', 'Filterləri dəyiş', 'Bildirişləri yandır'])
def handle_control_buttons(message):
    chat_id = message.chat.id
    if message.text == 'Bildirişləri söndür':
        users_data[chat_id]['notification_enabled'] = False
        keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        keyboard.add(telebot.types.KeyboardButton('Bildirişləri yandır'))
        keyboard.add(telebot.types.KeyboardButton('Filterləri dəyiş'))
        bot.send_message(chat_id, 'Bildirişlər söndürüldü.', reply_markup=keyboard)
        stop_notifications(chat_id)  # Stop notifications thread
    elif message.text == 'Filterləri dəyiş':
        users_data[chat_id]['notification_enabled'] = False
        stop_notifications(chat_id)  # Stop notifications thread
        ask_listing_type(chat_id)
    elif message.text == 'Bildirişləri yandır':
        users_data[chat_id]['notification_enabled'] = True
        users_data[chat_id]['notification_time'] = datetime.now(tz).strftime("%H:%M")  # Update notification time
        bot.send_message(chat_id, f'Bildirişlər yandırıldı. Yeni vaxt: {users_data[chat_id]["notification_time"]}. Siz yeni elanlarla bağlı bildiriş alacaqsız.')
        show_control_buttons(chat_id)
        start_notifications(chat_id)


# Start notifications in a separate thread
def start_notifications(chat_id):
    if users_data[chat_id]['notification_thread'] and users_data[chat_id]['notification_thread'].is_alive():
        return

    def notification_worker(chat_id):
        while users_data[chat_id]['notification_enabled']:
            print(f"Notification is {users_data[chat_id]['notification_enabled']}")
            # Check for new listings every 20 seconds
            time.sleep(20)
            # Fetch new data from website
            response = requests.get(users_data[chat_id]['url'], headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            new_items = soup.find_all('div', class_='items-i') + soup.find_all('div',
                                                                               class_='items-i featured vipped') + soup.find_all(
                'div', class_='items-i vipped')

            for item in new_items:
                city_when = item.find('div', class_='city_when').text.strip()
                if users_data[chat_id]['listing_type'] == 'Agentlik':
                    label = item.find('div', class_='products-label')
                    if label and 'Agentlik' in label.text:
                        process_item(item, city_when, users_data[chat_id]['notification_time'], chat_id)
                elif users_data[chat_id]['listing_type'] == 'Mülkiyyətçi':
                    item_link = 'https://bina.az' + item.find('a', class_='item_link')['href']
                    # Fetch the details page to check the owner type
                    item_response = requests.get(item_link, headers=headers)
                    item_soup = BeautifulSoup(item_response.content, 'html.parser')
                    owner_info = item_soup.find('div', class_='product-owner__info-region')
                    if owner_info and 'mülkiyyətçi' in owner_info.text:
                        process_item(item, city_when, users_data[chat_id]['notification_time'], chat_id)
                elif users_data[chat_id]['listing_type'] == 'Hər ikisi':
                    process_item(item, city_when, users_data[chat_id]['notification_time'], chat_id)

    users_data[chat_id]['notification_thread'] = threading.Thread(target=notification_worker, args=(chat_id,))
    users_data[chat_id]['notification_thread'].start()


# Stop notifications
def stop_notifications(chat_id):
    users_data[chat_id]['notification_enabled'] = False
    if users_data[chat_id]['notification_thread']:
        users_data[chat_id]['notification_thread'].join()


def process_item(item, city_when, notification_time, chat_id):
    if city_when.find('bugün') != -1:
        match = re.search(r'(\d{2}:\d{2})', city_when)
        city_when_time = match.group(1)
        item_link = 'https://bina.az' + item.find('a', class_='item_link')['href']
        identifier = item_link.split('/')[-1]
        if identifier not in users_data[chat_id]['sent_listings'] and datetime.strptime(city_when_time,
                                                                                        "%H:%M").time() >= datetime.strptime(
                notification_time, "%H:%M").time():
            name = item.find('ul', class_='name').text.strip()
            price = item.find('div', class_='price').text.strip()
            location = item.find('div', class_='location').text.strip()

            message_text = f"{name}\nQiymət: {price}\nYer: {location}\nŞəhər və vaxt: {city_when}\nLink: {item_link}"
            bot.send_message(chat_id, message_text)
            bot.send_message(chat_id, "------------------------")
            users_data[chat_id]['sent_listings'].add(identifier)


# Start bot polling
bot.polling()
