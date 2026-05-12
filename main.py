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
DATABASE_URL = "postgresql://ivan:Go8qQ9tHmkKXOJldunU1ES9oSoAPwdgm@dpg-d81r8frbc2fs73fvoo70-a/clan_db_dxh4" # Internal URL з Render
ADMIN_IDS = [1364079697]# Впиши ID обох адмінів

# --- [ ВЕБ-СЕРВЕР ДЛЯ RENDER (ЩОБ НЕ СПАВ) ] ---
def run_dummy_server():
    class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Bot is running!")
    
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

# --- [ КЛАВІАТУРИ ] ---
def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Мой профиль"), b.button(text="👥 Список клана")
    b.button(text="⚙️ Настройки профиля")
    return b.adjust(2, 1).as_markup(resize_keyboard=True)

# --- [ ЛОГІКА БОТА ] ---
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class Reg(StatesGroup):
    real_name = State()
    game_nick = State()
    crit = State()
    legendary = State()
    main_pawn = State()
    others = State()

@dp.message(Command("start"))
async def cmd_start(m: types.Message, state: FSMContext):
    session = Session()
    try:
        p = session.query(Player).get(m.from_user.id)
        if p:
            await m.answer(f"Привет, {p.real_name}!", reply_markup=main_kb())
        else:
            await m.answer("Добро пожаловать! Как тебя зовут (реальное имя)?")
            await state.set_state(Reg.real_name)
    finally:
        session.close()

# Етап реєстрації: Ім'я -> Нік
@dp.message(Reg.real_name)
async def reg_name(m: types.Message, state: FSMContext):
    await state.update_data(rn=m.text)
    await m.answer("Твой игровой ник:")
    await state.set_state(Reg.game_nick)

# Нік -> Крит
@dp.message(Reg.game_nick)
async def reg_nick(m: types.Message, state: FSMContext):
    await state.update_data(gn=m.text)
    await m.answer("Твой процент крита (число):")
    await state.set_state(Reg.crit)

# Крит -> Легендарність
@dp.message(Reg.crit)
async def reg_crit(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Введи число!")
    await state.update_data(cr=int(m.text))
    await m.answer("Твое значение легендарности (число):")
    await state.set_state(Reg.legendary)

# Легендарність -> Мейн
@dp.message(Reg.legendary)
async def reg_leg(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Введи число!")
    await state.update_data(leg=int(m.text))
    await m.answer("Твоя основная пешка и уровень:")
    await state.set_state(Reg.main_pawn)

# Мейн -> Інші пешки
@dp.message(Reg.main_pawn)
async def reg_main(m: types.Message, state: FSMContext):
    await state.update_data(mp=m.text)
    await m.answer("Список остальных пешек и уровни:")
    await state.set_state(Reg.others)

# Фінал реєстрації
@dp.message(Reg.others)
async def reg_final(m: types.Message, state: FSMContext):
    d = await state.get_data()
    session = Session()
    try:
        new_p = Player(user_id=m.from_user.id, real_name=d['rn'], game_nick=d['gn'], 
                        crit_value=d['cr'], legendary_val=d['leg'], main_info=d['mp'], others=m.text)
        session.merge(new_p)
        session.commit()
        await m.answer("✅ Регистрация завершена!", reply_markup=main_kb())
    finally:
        session.close()
        await state.clear()

# Перегляд списку клану
@dp.message(F.text == "👥 Список клана")
async def clan_list(m: types.Message):
    session = Session()
    try:
        players = session.query(Player).all()
        if not players: return await m.answer("Клан пуст.")
        kb = InlineKeyboardBuilder()
        for p in players:
            kb.button(text=f"{p.game_nick} ({p.crit_value}%)", callback_data=f"view_{p.user_id}")
        await m.answer("Участники:", reply_markup=kb.adjust(1).as_markup())
    finally:
        session.close()

# Детальний перегляд та видалення
@dp.callback_query(F.data.startswith("view_"))
async def view_p(c: types.CallbackQuery):
    uid = int(c.data.split("_")[1])
    session = Session()
    try:
        p = session.query(Player).get(uid)
        if p:
            txt = (f"👤 **{p.real_name}**\n🎮 Ник: `{p.game_nick}`\n🔥 Крит: {p.crit_value}%\n"
                   f"💎 Легендарность: {p.legendary_val}\n⚔️ Мейн: {p.main_info}\n\n📜 **Пешки:**\n{p.others}")
            kb = InlineKeyboardBuilder()
            if c.from_user.id in ADMIN_IDS:
                kb.button(text="❌ Удалить из клана", callback_data=f"confirm_del_{uid}")
            await c.message.answer(txt, parse_mode="Markdown", reply_markup=kb.as_markup())
    finally:
        session.close()
        await c.answer()

@dp.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete(c: types.CallbackQuery):
    uid = int(c.data.split("_")[2])
    kb = InlineKeyboardBuilder()
    kb.button(text="ДА, УДАЛИТЬ 💣", callback_data=f"final_delete_{uid}")
    kb.button(text="Отмена ↩️", callback_data="cancel_del")
    await c.message.answer("⚠️ Удалить игрока?", reply_markup=kb.adjust(1).as_markup())
    await c.answer()

@dp.callback_query(F.data.startswith("final_delete_"))
async def final_delete(c: types.CallbackQuery):
    uid = int(c.data.split("_")[2])
    session = Session()
    try:
        p = session.query(Player).get(uid)
        if p:
            n = p.game_nick
            session.delete(p)
            session.commit()
            await c.message.edit_text(f"✅ Игрок **{n}** удален.")
    finally:
        session.close()
        await c.answer()

@dp.callback_query(F.data == "cancel_del")
async def cancel_del(c: types.CallbackQuery):
    await c.message.delete()
    await c.answer()

# --- [ ЗАПУСК ] ---
async def main():
    # Запускаємо сервер-обманку в окремому потоці
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
