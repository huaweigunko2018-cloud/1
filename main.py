import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sqlalchemy import create_engine, Column, BigInteger, String, Integer
from sqlalchemy.orm import sessionmaker, declarative_base

# --- НАЛАШТУВАННЯ ---
TOKEN = "8578499281:AAFm-Y-gnDsaShsC-t0yk_ArFhF_k2jZly4"
# Сюди встав посилання від Supabase
DATABASE_URL = "postgresql://postgres.awnhftewsauhbwaaymku:TWbDpVjt9XF0QdnT@aws-0-eu-central-1.pooler.supabase.com:6543/postgres?sslmode=require"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# --- МОДЕЛЬ ДАНИХ ---
class Player(Base):
    __tablename__ = "players"
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    main_pawn = Column(String)
    level = Column(Integer)
    other_pawns = Column(String)

Base.metadata.create_all(engine)

# --- КНОПКИ ---
def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="👤 Мій профіль")
    builder.button(text="📝 Змінити дані")
    builder.button(text="👥 Список клану")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

class Registration(StatesGroup):
    waiting_for_main_pawn = State()
    waiting_for_level = State()
    waiting_for_others = State()

# --- ЛОГІКА ---

@dp.message(Command("start"))
@dp.message(F.text == "📝 Змінити дані")
async def start_reg(message: types.Message, state: FSMContext):
    await message.answer("Яка твоя **основна пешка**?", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Registration.waiting_for_main_pawn)

@dp.message(Registration.waiting_for_main_pawn)
async def proc_pawn(message: types.Message, state: FSMContext):
    await state.update_data(pawn=message.text)
    await message.answer("Рівень (від 7 до 15):")
    await state.set_state(Registration.waiting_for_level)

@dp.message(Registration.waiting_for_level)
async def proc_level(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not (7 <= int(message.text) <= 15):
        return await message.answer("Введи число від 7 до 15!")
    await state.update_data(level=int(message.text))
    await message.answer("Напиши інші свої пешки одним повідомленням:")
    await state.set_state(Registration.waiting_for_others)

@dp.message(Registration.waiting_for_others)
async def proc_final(message: types.Message, state: FSMContext):
    data = await state.get_data()
    db = SessionLocal()
    player = db.query(Player).filter(Player.user_id == message.from_user.id).first()
    
    if not player:
        player = Player(user_id=message.from_user.id)
    
    player.username = message.from_user.username or f"id{message.from_user.id}"
    player.main_pawn = data['pawn']
    player.level = data['level']
    player.other_pawns = message.text
    
    db.add(player)
    db.commit()
    db.close()
    
    await message.answer("✅ Дані збережено!", reply_markup=main_menu())
    await state.clear()

@dp.message(F.text == "👤 Мій профіль")
async def my_profile(message: types.Message):
    db = SessionLocal()
    p = db.query(Player).filter(Player.user_id == message.from_user.id).first()
    db.close()
    if p:
        await message.answer(f"👤 Твій мейн: {p.main_pawn}\n📈 Рівень: {p.level}\n📜 Інше: {p.other_pawns}", parse_mode="Markdown")
    else:
        await message.answer("Заповни дані через кнопку 'Змінити дані'.")

@dp.message(F.text == "👥 Список клану")
async def clan_list(message: types.Message):
    db = SessionLocal()
    all_p = db.query(Player).all()
    db.close()
    if not all_p: return await message.answer("Клан порожній.")
    
    res = "📊 **Клан:**\n"
    for p in all_p:
        res += f"• @{p.username}: {p.main_pawn} ({p.level} ур.)\n"
    await message.answer(res, parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
