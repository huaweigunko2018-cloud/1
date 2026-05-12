import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- НАЛАШТУВАННЯ ---
TOKEN = "8578499281:AAFm-Y-gnDsaShsC-t0yk_ArFhF_k2jZly4"
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- БАЗА ДАНИХ (SQLite) ---
def init_db():
    conn = sqlite3.connect("clan.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS players 
                      (user_id INTEGER PRIMARY KEY, username TEXT, main_pawn TEXT, level INTEGER, others TEXT)''')
    conn.commit()
    conn.close()

# --- КНОПКИ ---
def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Мій профіль"), b.button(text="📝 Змінити дані"), b.button(text="👥 Список клану")
    return b.adjust(2).as_markup(resize_keyboard=True)

class Reg(StatesGroup):
    pawn = State()
    lvl = State()
    oth = State()

# --- ОБРОБНИКИ ---
@dp.message(Command("start"))
@dp.message(F.text == "📝 Змінити дані")
async def start(m: types.Message, state: FSMContext):
    await m.answer("Яка твоя основна пешка?", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Reg.pawn)

@dp.message(Reg.pawn)
async def p_pawn(m: types.Message, state: FSMContext):
    await state.update_data(p=m.text)
    await m.answer("Рівень (7-15):")
    await state.set_state(Reg.lvl)

@dp.message(Reg.lvl)
async def p_lvl(m: types.Message, state: FSMContext):
    if not m.text.isdigit() or not (7 <= int(m.text) <= 15):
        return await m.answer("Введи число від 7 до 15!")
    await state.update_data(l=int(m.text))
    await m.answer("Напиши інші пешки:")
    await state.set_state(Reg.oth)

@dp.message(Reg.oth)
async def p_oth(m: types.Message, state: FSMContext):
    d = await state.get_data()
    conn = sqlite3.connect("clan.db")
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO players VALUES (?, ?, ?, ?, ?)", 
                (m.from_user.id, m.from_user.username, d['p'], d['l'], m.text))
    conn.commit()
    conn.close()
    await m.answer("✅ Збережено!", reply_markup=main_kb())
    await state.clear()

@dp.message(F.text == "👤 Мій профіль")
async def profile(m: types.Message):
    conn = sqlite3.connect("clan.db")
    res = conn.execute("SELECT * FROM players WHERE user_id=?", (m.from_user.id,)).fetchone()
    conn.close()
    if res:
        await m.answer(f"👤 Мейн: {res[2]}\n📈 Рівень: {res[3]}\n📜 Інше: {res[4]}")
    else:
        await m.answer("Натисни 'Змінити дані'")

@dp.message(F.text == "👥 Список клану")
async def c_list(m: types.Message):
    conn = sqlite3.connect("clan.db")
    players = conn.execute("SELECT username, main_pawn, level FROM players").fetchall()
    conn.close()
    if not players: return await m.answer("Клан порожній")
    txt = "📊 Склад:\n" + "\n".join([f"• @{p[0]}: {p[1]} ({p[2]} ур.)" for p in players])
    await m.answer(txt)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
