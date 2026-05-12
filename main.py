import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from motor.motor_asyncio import AsyncIOMotorClient

# --- НАЛАШТУВАННЯ ---
TOKEN = "8578499281:AAFm-Y-gnDsaShsC-t0yk_ArFhF_k2jZly4"
MONGO_URL = "mongodb+srv://huaweigunko2018_db_user:<db_password>@cluster0.hwj6vqs.mongodb.net/?appName=Cluster0"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
client = AsyncIOMotorClient(MONGO_URL)
db = client['clan_database']
collection = db['players']

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
    user_data = {
        "_id": m.from_user.id,
        "username": m.from_user.username or f"id{m.from_user.id}",
        "main_pawn": d['p'],
        "level": d['l'],
        "others": m.text
    }
    # Оновлюємо або вставляємо дані
    await collection.replace_one({"_id": m.from_user.id}, user_data, upsert=True)
    await m.answer("✅ Дані збережено в хмару навсегда!", reply_markup=main_kb())
    await state.clear()

@dp.message(F.text == "👤 Мій профіль")
async def profile(m: types.Message):
    res = await collection.find_one({"_id": m.from_user.id})
    if res:
        await m.answer(f"👤 Мейн: {res['main_pawn']}\n📈 Рівень: {res['level']}\n📜 Інше: {res['others']}")
    else:
        await m.answer("Дані не знайдені. Натисни '📝 Змінити дані'")

@dp.message(F.text == "👥 Список клану")
async def c_list(m: types.Message):
    cursor = collection.find()
    players = await cursor.to_list(length=100)
    if not players: return await m.answer("Клан порожній")
    txt = "📊 Склад клану:\n" + "\n".join([f"• @{p['username']}: {p['main_pawn']} ({p['level']} ур.)" for p in players])
    await m.answer(txt)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
