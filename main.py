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

# --- НАСТРОЙКИ --
TOKEN = "8578499281:AAFm-Y-gnDsaShsC-t0yk_ArFhF_k2jZly4"
# ВСТАВ СЮДИ Internal Database URL від Render
DATABASE_URL = "postgresql://ivan:U5d2ww0d2jtzaeVbNhR7ESHIeAXwm7Bp@dpg-d81orj6gvqtc73ddqf5g-a/clan_db_0pel" 

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Player(Base):
    __tablename__ = 'players'
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String)
    main_pawn = Column(String)
    level = Column(Integer)
    others = Column(Text)

Base.metadata.create_all(engine)

# --- КЛАВИАТУРЫ ---
def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Мой профиль"), b.button(text="📝 Изменить данные"), b.button(text="👥 Список клана")
    return b.adjust(2).as_markup(resize_keyboard=True)

class Reg(StatesGroup):
    pawn, lvl, oth = State(), State(), State()

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
@dp.message(F.text == "📝 Изменить данные")
async def start(m: types.Message, state: FSMContext):
    await m.answer("Привет! Какая твоя **основная пешка**?", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Reg.pawn)

@dp.message(Reg.pawn)
async def p_pawn(m: types.Message, state: FSMContext):
    await state.update_data(p=m.text)
    await m.answer("Какой уровень у этой пешки? (7-15):")
    await state.set_state(Reg.lvl)

@dp.message(Reg.lvl)
async def p_lvl(m: types.Message, state: FSMContext):
    if not m.text.isdigit() or not (7 <= int(m.text) <= 15):
        return await m.answer("Введи число от 7 до 15!")
    await state.update_data(l=int(m.text))
    await m.answer("Напиши список остальных пешек:")
    await state.set_state(Reg.oth)

@dp.message(Reg.oth)
async def p_oth(m: types.Message, state: FSMContext):
    d = await state.get_data()
    session = Session()
    player = Player(user_id=m.from_user.id, username=m.from_user.username or f"id{m.from_user.id}", 
                    main_pawn=d['p'], level=d['l'], others=m.text)
    session.merge(player)
    session.commit()
    session.close()
    await m.answer("✅ Данные сохранены навсегда!", reply_markup=main_kb())
    await state.clear()

@dp.message(F.text == "👤 Мой профиль")
async def profile(m: types.Message):
    session = Session()
    p = session.query(Player).filter_by(user_id=m.from_user.id).first()
    session.close()
    if p:
        await m.answer(f"👤 **Профиль:**\n⚔️ Мейн: {p.main_pawn}\n📈 Ур: {p.level}\n📜 Прочее: {p.others}", parse_mode="Markdown")
    else:
        await m.answer("Нажми 'Изменить данные'")

@dp.message(F.text == "👥 Список клана")
async def c_list(m: types.Message):
    session = Session()
    players = session.query(Player).all()
    session.close()
    if not players: return await m.answer("Клан пуст")
    kb = InlineKeyboardBuilder()
    for p in players:
        kb.button(text=f"👤 @{p.username} ({p.main_pawn})", callback_data=f"view_{p.user_id}")
    await m.answer("Выберите игрока:", reply_markup=kb.adjust(1).as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view(c: types.CallbackQuery):
    uid = int(c.data.split("_")[1])
    session = Session()
    p = session.query(Player).filter_by(user_id=uid).first()
    session.close()
    if p:
        await c.message.answer(f"👤 @{p.username}\n⚔️ Мейн: {p.main_pawn}\n📈 Ур: {p.level}\n📜 Все пешки:\n{p.others}", parse_mode="Markdown")
    await c.answer()

async def main(): await dp.start_polling(bot)
if __name__ == "__main__": asyncio.run(main())
