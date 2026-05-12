import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from sqlalchemy import create_engine, Column, BigInteger, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- НАСТРОЙКИ ---
TOKEN = "8578499281:AAFm-Y-gnDsaShsC-t0yk_ArFhF_k2jZly4"
DATABASE_URL = "postgresql://ivan:U5d2ww0d2jtzaeVbNhR7ESHIeAXwm7Bp@dpg-d81orj6gvqtc73ddqf5g-a/clan_db_0pel" # Твой Internal Database URL с Render

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# --- МОДЕЛЬ ДАННЫХ ---
class Player(Base):
    __tablename__ = 'players'
    user_id = Column(BigInteger, primary_key=True)
    real_name = Column(String)     # Имя человека
    game_nick = Column(String)     # Игровой ник
    crit_value = Column(Integer)   # Значение крита
    is_legendary = Column(String)  # Легендарность
    main_pawn = Column(String)
    main_lvl = Column(Integer)
    others = Column(Text)          # Другие пешки с уровнями

Base.metadata.create_all(engine)

# --- СОСТОЯНИЯ (FSM) ---
class Reg(StatesGroup):
    real_name = State()
    game_nick = State()
    crit = State()
    legendary = State()
    main_pawn = State()
    main_lvl = State()
    others = State()

class Edit(StatesGroup):
    target = State()

# --- КЛАВИАТУРЫ ---
def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Мой профиль"), b.button(text="👥 Список клана")
    b.button(text="⚙️ Настройки профиля")
    return b.adjust(2, 1).as_markup(resize_keyboard=True)

def edit_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Имя", callback_data="edit_real_name")
    kb.button(text="Ник", callback_data="edit_game_nick")
    kb.button(text="Крит", callback_data="edit_crit_value")
    kb.button(text="Мейн пешка", callback_data="edit_main_pawn")
    kb.button(text="Другие пешки", callback_data="edit_others")
    return kb.adjust(2).as_markup()

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Добро пожаловать в бот клана! Заполни свой профиль, чтобы участвовать в рейдах.", reply_markup=main_kb())

@dp.message(F.text == "⚙️ Настройки профиля")
async def settings(m: types.Message):
    await m.answer("Что ты хочешь изменить?", reply_markup=edit_kb())

# --- ПРОЦЕСС РЕДАКТИРОВАНИЯ (УНИВЕРСАЛЬНЫЙ) ---
@dp.callback_query(F.data.startswith("edit_"))
async def start_edit(c: types.CallbackQuery, state: FSMContext):
    field = c.data.replace("edit_", "")
    await state.update_data(field=field)
    
    prompts = {
        "real_name": "Введите ваше реальное имя:",
        "game_nick": "Введите ваш игровой ник:",
        "crit_value": "Введите ваш процент критического урона (число):",
        "main_pawn": "Введите вашу основную пешку и её уровень (напр. Танцор 13):",
        "others": "Введите список остальных пешек с уровнями (каждая с новой строки):"
    }
    
    await c.message.answer(prompts.get(field, "Введите новое значение:"))
    await state.set_state(Edit.target)
    await c.answer()

@dp.message(Edit.target)
async def save_edit(m: types.Message, state: FSMContext):
    data = await state.get_data()
    field = data['field']
    val = m.text
    
    session = Session()
    player = session.query(Player).get(m.from_user.id)
    
    if not player:
        player = Player(user_id=m.from_user.id)
        session.add(player)
    
    if field == "crit_value":
        if not val.isdigit(): return await m.answer("Введите число!")
        player.crit_value = int(val)
    elif field == "real_name": player.real_name = val
    elif field == "game_nick": player.game_nick = val
    elif field == "main_pawn": player.main_pawn = val
    elif field == "others": player.others = val
    
    session.commit()
    session.close()
    await m.answer(f"✅ Поле {field} успешно обновлено!", reply_markup=main_kb())
    await state.clear()

# --- ПРОСМОТР ---
@dp.message(F.text == "👤 Мой профиль")
async def my_profile(m: types.Message):
    session = Session()
    p = session.query(Player).get(m.from_user.id)
    session.close()
    
    if not p:
        return await m.answer("Профиль пуст. Нажми 'Настройки профиля', чтобы заполнить.")
    
    text = (f"👤 **Профиль: {p.real_name or 'Не указано'}**\n"
            f"🎮 Ник: `{p.game_nick or 'Не указано'}`\n"
            f"🔥 Крит: {p.crit_value or 0}%\n"
            f"⚔️ Мейн: {p.main_pawn or 'Не указано'}\n\n"
            f"📜 **Все пешки:**\n{p.others or 'Пусто'}")
    await m.answer(text, parse_mode="Markdown")

@dp.message(F.text == "👥 Список клана")
async def clan_list(m: types.Message):
    session = Session()
    players = session.query(Player).all()
    session.close()
    
    if not players: return await m.answer("Клан пуст.")
    
    kb = InlineKeyboardBuilder()
    for p in players:
        kb.button(text=f"{p.game_nick or p.user_id} ({p.crit_value or 0}%)", callback_data=f"view_{p.user_id}")
    
    await m.answer("Список участников:", reply_markup=kb.adjust(1).as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_p(c: types.CallbackQuery):
    uid = int(c.data.split("_")[1])
    session = Session()
    p = session.query(Player).get(uid)
    session.close()
    
    if p:
        text = (f"👤 **Игрок: {p.real_name}**\n🎮 Ник: `{p.game_nick}`\n🔥 Крит: {p.crit_value}%\n"
                f"⚔️ Мейн: {p.main_pawn}\n\n📜 **Все пешки:**\n{p.others}")
        await c.message.answer(text, parse_mode="Markdown")
    await c.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
