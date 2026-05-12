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

# --- [НАЛАШТУВАННЯ] ---
TOKEN = "8578499281:AAFm-Y-gnDsaShsC-t0yk_ArFhF_k2jZly4"
DATABASE_URL = "postgresql://ivan:rloI9ngcFx82CEcV2daiOcCBmXsH6AB7@dpg-d81pm0rtqb8s738miehg-a/clan_db_i80p" # Internal URL з Render
ADMIN_IDS = [1364079697] # Твій ID та ID помічника

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# --- МОДЕЛЬ БАЗИ ДАНИХ ---
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

# --- СТАНИ (FSM) ---
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

def edit_inline_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Имя", callback_data="edit_real_name")
    kb.button(text="Ник", callback_data="edit_game_nick")
    kb.button(text="Крит", callback_data="edit_crit_value")
    kb.button(text="Легендарность", callback_data="edit_legendary_val")
    kb.button(text="Мейн", callback_data="edit_main_info")
    kb.button(text="Другие пешки", callback_data="edit_others")
    return kb.adjust(2).as_markup()

# --- РЕЄСТРАЦІЯ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message, state: FSMContext):
    session = Session()
    p = session.query(Player).get(m.from_user.id)
    session.close()
    if p:
        await m.answer(f"Привет, {p.real_name}! Твой профиль активен.", reply_markup=main_kb())
    else:
        await m.answer("Добро пожаловать! Давай создадим твой профиль.\n\nКак тебя зовут (реальное имя)?")
        await state.set_state(Reg.real_name)

@dp.message(Reg.real_name)
async def reg_name(m: types.Message, state: FSMContext):
    await state.update_data(rn=m.text)
    await m.answer("Твой игровой ник:")
    await state.set_state(Reg.game_nick)

@dp.message(Reg.game_nick)
async def reg_nick(m: types.Message, state: FSMContext):
    await state.update_data(gn=m.text)
    await m.answer("Твой процент крита (число):")
    await state.set_state(Reg.crit)

@dp.message(Reg.crit)
async def reg_crit(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Введи число!")
    await state.update_data(cr=int(m.text))
    await m.answer("Твое значение легендарности (число):")
    await state.set_state(Reg.legendary)

@dp.message(Reg.legendary)
async def reg_leg(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Введи число!")
    await state.update_data(leg=int(m.text))
    await m.answer("Твоя основная пешка и уровень:")
    await state.set_state(Reg.main_pawn)

@dp.message(Reg.main_pawn)
async def reg_main(m: types.Message, state: FSMContext):
    await state.update_data(mp=m.text)
    await m.answer("Список остальных пешек и их уровни:")
    await state.set_state(Reg.others)

@dp.message(Reg.others)
async def reg_final(m: types.Message, state: FSMContext):
    d = await state.get_data()
    session = Session()
    new_p = Player(user_id=m.from_user.id, real_name=d['rn'], game_nick=d['gn'], 
                    crit_value=d['cr'], legendary_val=d['leg'], main_info=d['mp'], others=m.text)
    session.merge(new_p)
    session.commit()
    session.close()
    await m.answer("✅ Регистрация завершена!", reply_markup=main_kb())
    await state.clear()

# --- НАЛАШТУВАННЯ ТА РЕДАГУВАННЯ ---
@dp.message(F.text == "⚙️ Настройки профиля")
async def show_edit_menu(m: types.Message):
    await m.answer("Что именно ты хочешь изменить?", reply_markup=edit_inline_kb())

@dp.callback_query(F.data.startswith("edit_"))
async def start_edit(c: types.CallbackQuery, state: FSMContext):
    field = c.data.replace("edit_", "")
    await state.update_data(f=field)
    await c.message.answer(f"Введите новое значение для этого поля:")
    await state.set_state(Edit.target)
    await c.answer()

@dp.message(Edit.target)
async def save_edit(m: types.Message, state: FSMContext):
    d = await state.get_data()
    field = d['f']
    session = Session()
    p = session.query(Player).get(m.from_user.id)
    try:
        if field in ['crit_value', 'legendary_val']:
            setattr(p, field, int(m.text))
        else:
            setattr(p, field, m.text)
        session.commit()
        await m.answer("✅ Данные обновлены!", reply_markup=main_kb())
    except:
        await m.answer("Ошибка! Возможно, вы ввели текст там, где нужно число.")
    finally:
        session.close()
        await state.clear()

# --- ПЕРЕГЛЯД ПРОФІЛІВ ТА ВИДАЛЕННЯ ---
@dp.message(F.text == "👤 Мой профиль")
async def profile(m: types.Message):
    session = Session()
    p = session.query(Player).get(m.from_user.id)
    session.close()
    if p:
        txt = (f"👤 **{p.real_name}** (`{p.game_nick}`)\n"
               f"🔥 Крит: {p.crit_value}% | 💎 Легендарность: {p.legendary_val}\n"
               f"⚔️ Мейн: {p.main_info}\n\n"
               f"📜 **Другие пешки:**\n{p.others}")
        await m.answer(txt, parse_mode="Markdown")

@dp.message(F.text == "👥 Список клана")
async def clan_list(m: types.Message):
    session = Session()
    players = session.query(Player).all()
    session.close()
    if not players: return await m.answer("Клан пуст.")
    kb = InlineKeyboardBuilder()
    for p in players:
        kb.button(text=f"{p.game_nick} ({p.crit_value}%)", callback_data=f"view_{p.user_id}")
    await m.answer("Участники:", reply_markup=kb.adjust(1).as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_p(c: types.CallbackQuery):
    uid = int(c.data.split("_")[1])
    session = Session()
    p = session.query(Player).get(uid)
    session.close()
    if p:
        txt = (f"👤 **{p.real_name}**\n🎮 Ник: `{p.game_nick}`\n🔥 Крит: {p.crit_value}%\n"
               f"💎 Легендарность: {p.legendary_val}\n⚔️ Мейн: {p.main_info}\n\n📜 **Пешки:**\n{p.others}")
        kb = InlineKeyboardBuilder()
        if c.from_user.id in ADMIN_IDS:
            kb.button(text="❌ Удалить из клана", callback_data=f"confirm_del_{uid}")
        await c.message.answer(txt, parse_mode="Markdown", reply_markup=kb.as_markup())
    await c.answer()

@dp.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete(c: types.CallbackQuery):
    uid = int(c.data.split("_")[2])
    kb = InlineKeyboardBuilder()
    kb.button(text="ДА, УДАЛИТЬ 💣", callback_data=f"final_delete_{uid}")
    kb.button(text="Отмена ↩️", callback_data="cancel_del")
    await c.message.answer("⚠️ Вы уверены, что хотите удалить игрока?", reply_markup=kb.adjust(1).as_markup())
    await c.answer()

@dp.callback_query(F.data.startswith("final_delete_"))
async def final_delete(c: types.CallbackQuery):
    uid = int(c.data.split("_")[2])
    session = Session()
    p = session.query(Player).get(uid)
    if p:
        n = p.game_nick
        session.delete(p)
        session.commit()
        await c.message.edit_text(f"✅ Игрок **{n}** удален.")
    session.close()
    await c.answer()

@dp.callback_query(F.data == "cancel_del")
async def cancel_del(c: types.CallbackQuery):
    await c.message.delete()
    await c.answer("Отменено")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
