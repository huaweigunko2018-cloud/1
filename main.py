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
            # ВИПРАВЛЕНО: Прибрали префікс 'b', щоб не було помилки ASCII
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

# --- [ ЛОГІКА ] ---
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class Reg(StatesGroup):
    real_name, game_nick, crit, legendary, main_pawn, others = State(), State(), State(), State(), State(), State()

class Edit(StatesGroup):
    target = State()

def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Мой профиль"), b.button(text="👥 Список клана")
    b.button(text="⚙️ Настройки профиля")
    return b.adjust(2, 1).as_markup(resize_keyboard=True)

def edit_inline_kb():
    kb = InlineKeyboardBuilder()
    fields = [("Имя", "real_name"), ("Ник", "game_nick"), ("Крит", "crit_value"), 
              ("Легендарность", "legendary_val"), ("Мейн", "main_info"), ("Другие", "others")]
    for name, call in fields:
        kb.button(text=name, callback_data=f"edit_{call}")
    return kb.adjust(2).as_markup()

# --- ОБРОБНИКИ ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message, state: FSMContext):
    session = Session()
    try:
        p = session.query(Player).get(m.from_user.id)
        if p: await m.answer(f"Привет, {p.real_name}!", reply_markup=main_kb())
        else:
            await m.answer("Добро пожаловать! Как тебя зовут?")
            await state.set_state(Reg.real_name)
    finally: session.close()

# Реєстрація (спрощено)
@dp.message(Reg.real_name)
async def r1(m, s): await s.update_data(rn=m.text); await m.answer("Ник?"); await s.set_state(Reg.game_nick)
@dp.message(Reg.game_nick)
async def r2(m, s): await s.update_data(gn=m.text); await m.answer("Крит (число)?"); await s.set_state(Reg.crit)
@dp.message(Reg.crit)
async def r3(m, s): 
    if not m.text.isdigit(): return await m.answer("Цифрами!")
    await s.update_data(cr=int(m.text)); await m.answer("Легендарность (число)?"); await s.set_state(Reg.legendary)
@dp.message(Reg.legendary)
async def r4(m, s):
    if not m.text.isdigit(): return await m.answer("Цифрами!")
    await s.update_data(leg=int(m.text)); await m.answer("Мейн пешка?"); await s.set_state(Reg.main_pawn)
@dp.message(Reg.main_pawn)
async def r5(m, s): await s.update_data(mp=m.text); await m.answer("Остальные пешки?"); await s.set_state(Reg.others)
@dp.message(Reg.others)
async def r6(m, s):
    d = await s.get_data()
    session = Session()
    try:
        new_p = Player(user_id=m.from_user.id, real_name=d['rn'], game_nick=d['gn'], 
                        crit_value=d['cr'], legendary_val=d['leg'], main_info=d['mp'], others=m.text)
        session.merge(new_p)
        session.commit()
        await m.answer("✅ Готово!", reply_markup=main_kb())
    finally: session.close(); await s.clear()

@dp.message(F.text == "👤 Мой профиль")
async def profile(m: types.Message):
    session = Session()
    try:
        p = session.query(Player).get(m.from_user.id)
        if p:
            txt = (f"👤 **{p.real_name}** (`{p.game_nick}`)\n"
                   f"🔥 Крит: {p.crit_value}% | 💎 Легендарность: {p.legendary_val}\n"
                   f"⚔️ Мейн: {p.main_info}\n\n📜 **Другие:**\n{p.others}")
            await m.answer(txt, parse_mode="Markdown")
    finally: session.close()

@dp.message(F.text == "⚙️ Настройки профиля")
async def show_edit(m: types.Message):
    await m.answer("Что изменить?", reply_markup=edit_inline_kb())

@dp.callback_query(F.data.startswith("edit_"))
async def start_edit(c: types.CallbackQuery, state: FSMContext):
    field = c.data.replace("edit_", "")
    await state.update_data(f=field)
    await c.message.answer("Введите новое значение:")
    await state.set_state(Edit.target)
    await c.answer()

@dp.message(Edit.target)
async def save_edit(m: types.Message, state: FSMContext):
    d = await state.get_data()
    session = Session()
    try:
        p = session.query(Player).get(m.from_user.id)
        val = int(m.text) if d['f'] in ['crit_value', 'legendary_val'] else m.text
        setattr(p, d['f'], val)
        session.commit()
        await m.answer("✅ Обновлено!", reply_markup=main_kb())
    except: await m.answer("Ошибка! Проверьте формат.")
    finally: session.close(); await state.clear()

@dp.message(F.text == "👥 Список клана")
async def clan_list(m: types.Message):
    session = Session()
    try:
        players = session.query(Player).all()
        if not players: return await m.answer("Клан пуст.")
        kb = InlineKeyboardBuilder()
        for p in players: kb.button(text=f"{p.game_nick} ({p.crit_value}%)", callback_data=f"view_{p.user_id}")
        await m.answer("Участники:", reply_markup=kb.adjust(1).as_markup())
    finally: session.close()

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
                kb.button(text="❌ Удалить", callback_data=f"confirm_del_{uid}")
            await c.message.answer(txt, parse_mode="Markdown", reply_markup=kb.as_markup())
    finally: session.close(); await c.answer()

@dp.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete(c: types.CallbackQuery):
    uid = int(c.data.split("_")[2])
    kb = InlineKeyboardBuilder()
    kb.button(text="ДА, УДАЛИТЬ", callback_data=f"final_delete_{uid}")
    kb.button(text="Отмена", callback_data="cancel_del")
    await c.message.answer("⚠️ Удалить?", reply_markup=kb.adjust(1).as_markup()); await c.answer()

@dp.callback_query(F.data.startswith("final_delete_"))
async def final_delete(c: types.CallbackQuery):
    uid = int(c.data.split("_")[2])
    session = Session()
    try:
        p = session.query(Player).get(uid)
        if p: session.delete(p); session.commit(); await c.message.edit_text("✅ Удален.")
    finally: session.close(); await c.answer()

@dp.callback_query(F.data == "cancel_del")
async def cancel_del(c: types.CallbackQuery): await c.message.delete(); await c.answer()

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
