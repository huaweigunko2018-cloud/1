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

TOKEN = "8578499281:AAFm-Y-gnDsaShsC-t0yk_ArFhF_k2jZly4"
DATABASE_URL = "postgresql://ivan:2iPAjL60A8Wg8XZEcnh4aoVccF7oHDEb@dpg-d81pf5favr4c73bdbrug-a/clan_db_jhgl" 

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Player(Base):
    __tablename__ = 'players'
    user_id = Column(BigInteger, primary_key=True)
    real_name = Column(String)
    game_nick = Column(String)
    crit_value = Column(Integer)
    is_legendary = Column(String)
    main_info = Column(String) # Мейн пешка + рівень
    others = Column(Text)

Base.metadata.create_all(engine)

class Reg(StatesGroup):
    real_name = State()
    game_nick = State()
    crit = State()
    legendary = State()
    main_pawn = State()
    others = State()

class Edit(StatesGroup):
    target = State()

# --- КЛАВІАТУРИ ---
def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Мой профиль"), b.button(text="👥 Список клана")
    b.button(text="⚙️ Настройки профиля")
    return b.adjust(2, 1).as_markup(resize_keyboard=True)

def leg_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Да ✅", callback_data="reg_leg_Да")
    kb.button(text="Нет ❌", callback_data="reg_leg_Нет")
    return kb.as_markup()

# --- ЛОГІКА РЕЄСТРАЦІЇ ПРИ /START ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message, state: FSMContext):
    session = Session()
    p = session.query(Player).get(m.from_user.id)
    session.close()

    if p:
        await m.answer(f"С возвращением, {p.real_name}! Твой профиль готов.", reply_markup=main_kb())
    else:
        await m.answer("Привет! Ты новый участник. Давай заполним анкету клана.\n\nКак тебя зовут (реальное имя)?")
        await state.set_state(Reg.real_name)

@dp.message(Reg.real_name)
async def reg_name(m: types.Message, state: FSMContext):
    await state.update_data(rn=m.text)
    await m.answer("Твой игровой ник в Rush Royale:")
    await state.set_state(Reg.game_nick)

@dp.message(Reg.game_nick)
async def reg_nick(m: types.Message, state: FSMContext):
    await state.update_data(gn=m.text)
    await m.answer("Твой процент критического урона (только число):")
    await state.set_state(Reg.crit)

@dp.message(Reg.crit)
async def reg_crit(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Введи число!")
    await state.update_data(cr=int(m.text))
    await m.answer("Твоя основная пешка и её уровень (напр. Танцор 13):")
    await state.set_state(Reg.main_pawn)

@dp.message(Reg.main_pawn)
async def reg_main(m: types.Message, state: FSMContext):
    await state.update_data(mp=m.text)
    await m.answer("У тебя есть легендарный статус?", reply_markup=leg_kb())
    await state.set_state(Reg.legendary)

@dp.callback_query(Reg.legendary, F.data.startswith("reg_leg_"))
async def reg_leg(c: types.CallbackQuery, state: FSMContext):
    val = c.data.replace("reg_leg_", "")
    await state.update_data(leg=val)
    await c.message.answer("Напиши список остальных пешек и их уровни (одним сообщением):")
    await state.set_state(Reg.others)
    await c.answer()

@dp.message(Reg.others)
async def reg_final(m: types.Message, state: FSMContext):
    d = await state.get_data()
    session = Session()
    new_p = Player(
        user_id=m.from_user.id,
        real_name=d['rn'],
        game_nick=d['gn'],
        crit_value=d['cr'],
        main_info=d['mp'],
        is_legendary=d['leg'],
        others=m.text
    )
    session.merge(new_p)
    session.commit()
    session.close()
    await m.answer("🎉 Регистрация завершена! Теперь ты в базе клана.", reply_markup=main_kb())
    await state.clear()

# --- ІНШІ ФУНКЦІЇ (ПРОФІЛЬ ТА СПИСОК) ---

@dp.message(F.text == "👤 Мой профиль")
async def profile(m: types.Message):
    session = Session()
    p = session.query(Player).get(m.from_user.id)
    session.close()
    if p:
        txt = (f"👤 **{p.real_name}** (`{p.game_nick}`)\n"
               f"🔥 Крит: {p.crit_value}% | ⭐ Лега: {p.is_legendary}\n"
               f"⚔️ Мейн: {p.main_info}\n\n"
               f"📜 **Другие пешки:**\n{p.others}")
        await m.answer(txt, parse_mode="Markdown")
    else:
        await m.answer("Напиши /start для регистрации.")

@dp.message(F.text == "👥 Список клана")
async def clan_list(m: types.Message):
    session = Session()
    players = session.query(Player).all()
    session.close()
    if not players: return await m.answer("Клан пуст.")
    kb = InlineKeyboardBuilder()
    for p in players:
        kb.button(text=f"{p.game_nick} ({p.crit_value}%)", callback_data=f"view_{p.user_id}")
    await m.answer("Участники клана:", reply_markup=kb.adjust(1).as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_p(c: types.CallbackQuery):
    uid = int(c.data.split("_")[1])
    session = Session()
    p = session.query(Player).get(uid)
    session.close()
    if p:
        txt = (f"👤 **{p.real_name}** (@{p.game_nick})\n🔥 Крит: {p.crit_value}% | ⭐ Лега: {p.is_legendary}\n"
               f"⚔️ Мейн: {p.main_info}\n\n📜 **Все пешки:**\n{p.others}")
        await c.message.answer(txt)
    await c.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
