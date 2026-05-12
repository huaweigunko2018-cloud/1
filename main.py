import asyncio
import http.server
import threading
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from sqlalchemy import create_engine, Column, BigInteger, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- [ НАЛАШТУВАННЯ ] ---
TOKEN = "8578499281:AAFm-Y-gnDsaShsC-t0yk_ArFhF_k2jZly4"
DATABASE_URL = "postgresql://ivan:P9QgCYmcpNfsMik1CqmaMIRepXcFnaJb@dpg-d81ra8bbc2fs73fvpuk0-a/clan_db_xlqx" # Internal URL з Render
ADMIN_IDS = [1364079697]

# --- [ ВЕБ-СЕРВЕР ДЛЯ RENDER ] ---
def run_dummy_server():
    class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write("Bot is alive!".encode('utf-8'))
    
    server_address = ('', 8080)
    httpd = http.server.HTTPServer(server_address, HealthCheckHandler)
    httpd.serve_forever()

# --- [ БАЗА ДАНИХ ] ---
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Player(Base):
    __tablename__ = 'players'
    user_id = Column(BigInteger, primary_key=True)
    real_name = Column(String)
    game_nick = Column(String)
    crit_value = Column(Integer)
    legendary_val = Column(Integer)
    main_info = Column(String)
    others = Column(Text)

Base.metadata.create_all(engine)

# --- [ СТАНИ (FSM) ] ---
class Reg(StatesGroup):
    real_name = State()
    game_nick = State()
    crit = State()
    legendary = State()
    main_pawn = State()
    others = State()

class Edit(StatesGroup):
    target = State()

# --- [ КЛАВІАТУРИ ] ---
def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Мой профиль"), b.button(text="👥 Список клана")
    b.button(text="⚙️ Настройки профиля")
    return b.adjust(2, 1).as_markup(resize_keyboard=True)

def edit_inline_kb():
    kb = InlineKeyboardBuilder()
    fields = [
        ("Имя", "real_name"), ("Ник", "game_nick"), 
        ("Крит", "crit_value"), ("Легендарность", "legendary_val"), 
        ("Мейн", "main_info"), ("Другие пешки", "others")
    ]
    for name, call in fields:
        kb.button(text=name, callback_data=f"edit_{call}")
    return kb.adjust(2).as_markup()

# --- [ ОБРОБНИКИ ] ---
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    session = Session()
    try:
        p = session.query(Player).get(message.from_user.id)
        if p:
            await message.answer(f"Привет, {p.real_name}! Твой профиль активен.", reply_markup=main_kb())
        else:
            await message.answer("Добро пожаловать! Давай создадим профиль.\n\nКак тебя зовут (реальное имя)?")
            await state.set_state(Reg.real_name)
    finally:
        session.close()

# --- РЕЄСТРАЦІЯ (ВИПРАВЛЕНО) ---
@dp.message(Reg.real_name)
async def r1(message: types.Message, state: FSMContext):
    await state.update_data(rn=message.text)
    await message.answer("Твой игровой ник:")
    await state.set_state(Reg.game_nick)

@dp.message(Reg.game_nick)
async def r2(message: types.Message, state: FSMContext):
    await state.update_data(gn=message.text)
    await message.answer("Твой процент крита (число):")
    await state.set_state(Reg.crit)

@dp.message(Reg.crit)
async def r3(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введи число!")
    await state.update_data(cr=int(message.text))
    await message.answer("Твое значение легендарности (число):")
    await state.set_state(Reg.legendary)

@dp.message(Reg.legendary)
async def r4(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введи число!")
    await state.update_data(leg=int(message.text))
    await message.answer("Твоя основная пешка и уровень:")
    await state.set_state(Reg.main_pawn)

@dp.message(Reg.main_pawn)
async def r5(message: types.Message, state: FSMContext):
    await state.update_data(mp=message.text)
    await message.answer("Список остальных пешек и их уровни:")
    await state.set_state(Reg.others)

@dp.message(Reg.others)
async def r6(message: types.Message, state: FSMContext):
    data = await state.get_data()
    session = Session()
    try:
        new_p = Player(
            user_id=message.from_user.id, real_name=data['rn'], game_nick=data['gn'], 
            crit_value=data['cr'], legendary_val=data['leg'], main_info=data['mp'], others=message.text
        )
        session.merge(new_p)
        session.commit()
        await message.answer("✅ Регистрация завершена!", reply_markup=main_kb())
    finally:
        session.close()
        await state.clear()

# --- ПРОФІЛЬ ТА РЕДАГУВАННЯ (ВИПРАВЛЕНО) ---
@dp.message(F.text == "👤 Мой профиль")
async def profile(message: types.Message):
    session = Session()
    try:
        p = session.query(Player).get(message.from_user.id)
        if p:
            txt = (f"👤 **{p.real_name}** (`{p.game_nick}`)\n"
                   f"🔥 Крит: {p.crit_value}% | 💎 Легендарность: {p.legendary_val}\n"
                   f"⚔️ Мейн: {p.main_info}\n\n"
                   f"📜 **Другие пешки:**\n{p.others}")
            await message.answer(txt, parse_mode="Markdown")
    finally:
        session.close()

@dp.message(F.text == "⚙️ Настройки профиля")
async def show_edit_menu(message: types.Message):
    await message.answer("Что именно ты хочешь изменить?", reply_markup=edit_inline_kb())

@dp.callback_query(F.data.startswith("edit_"))
async def start_edit(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_", "")
    await state.update_data(f=field)
    await callback.message.answer(f"Введите новое значение:")
    await state.set_state(Edit.target)
    await callback.answer()

@dp.message(Edit.target)
async def save_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    field = data['f']
    session = Session()
    try:
        p = session.query(Player).get(message.from_user.id)
        if field in ['crit_value', 'legendary_val']:
            setattr(p, field, int(message.text))
        else:
            setattr(p, field, message.text)
        session.commit()
        await message.answer("✅ Данные обновлены!", reply_markup=main_kb())
    except:
        await message.answer("Ошибка! Проверьте формат ввода (число или текст).")
    finally:
        session.close()
        await state.clear()

# --- СПИСОК КЛАНУ ТА ВИДАЛЕННЯ ---
@dp.message(F.text == "👥 Список клана")
async def clan_list(message: types.Message):
    session = Session()
    try:
        players = session.query(Player).all()
        if not players: return await message.answer("Клан пуст.")
        kb = InlineKeyboardBuilder()
        for p in players:
            kb.button(text=f"{p.game_nick} ({p.crit_value}%)", callback_data=f"view_{p.user_id}")
        await message.answer("Участники клана:", reply_markup=kb.adjust(1).as_markup())
    finally:
        session.close()

@dp.callback_query(F.data.startswith("view_"))
async def view_p(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    session = Session()
    try:
        p = session.query(Player).get(uid)
        if p:
            txt = (f"👤 **{p.real_name}**\n🎮 Ник: `{p.game_nick}`\n🔥 Крит: {p.crit_value}%\n"
                   f"💎 Легендарность: {p.legendary_val}\n⚔️ Мейн: {p.main_info}\n\n📜 **Пешки:**\n{p.others}")
            kb = InlineKeyboardBuilder()
            if callback.from_user.id in ADMIN_IDS:
                kb.button(text="❌ Удалить из клана", callback_data=f"confirm_del_{uid}")
            await callback.message.answer(txt, parse_mode="Markdown", reply_markup=kb.as_markup())
    finally:
        session.close()
        await callback.answer()

@dp.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[2])
    kb = InlineKeyboardBuilder()
    kb.button(text="ДА, ВИДАЛИТИ 💣", callback_data=f"final_delete_{uid}")
    kb.button(text="Отмена ↩️", callback_data="cancel_del")
    await callback.message.answer("⚠️ Вы уверены, что хотите удалить игрока?", reply_markup=kb.adjust(1).as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("final_delete_"))
async def final_delete(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[2])
    session = Session()
    try:
        p = session.query(Player).get(uid)
        if p:
            n = p.game_nick
            session.delete(p)
            session.commit()
            await callback.message.edit_text(f"✅ Игрок **{n}** удален.")
    finally:
        session.close()
        await callback.answer()

@dp.callback_query(F.data == "cancel_del")
async def cancel_del(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

# --- [ ЗАПУСК ] ---
async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
