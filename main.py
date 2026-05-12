import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from motor.motor_asyncio import AsyncIOMotorClient

# --- НАСТРОЙКИ ---
TOKEN = "8578499281:AAFm-Y-gnDsaShsC-t0yk_ArFhF_k2jZly4"

MONGO_URL = "mongodb+srv://huaweigunko2018_db_user:vWU5mlA39t9uOtgS@cluster0.hwj6vqs.mongodb.net/?appName=Cluster0"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
client = AsyncIOMotorClient(MONGO_URL)
db = client['clan_database']
collection = db['players']

# --- КЛАВИАТУРЫ ---
def main_kb():
    b = ReplyKeyboardBuilder()
    b.button(text="👤 Мой профиль")
    b.button(text="📝 Изменить данные")
    b.button(text="👥 Список клана")
    return b.adjust(2).as_markup(resize_keyboard=True)

class Reg(StatesGroup):
    pawn = State()
    lvl = State()
    oth = State()

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
@dp.message(F.text == "📝 Изменить данные")
async def start(m: types.Message, state: FSMContext):
    await m.answer("Привет! Давай заполним твой профиль для клана.\nКакая твоя **основная пешка**?", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Reg.pawn)

@dp.message(Reg.pawn)
async def p_pawn(m: types.Message, state: FSMContext):
    await state.update_data(p=m.text)
    await m.answer("Какой уровень у этой пешки? (число от 7 до 15):")
    await state.set_state(Reg.lvl)

@dp.message(Reg.lvl)
async def p_lvl(m: types.Message, state: FSMContext):
    if not m.text.isdigit() or not (7 <= int(m.text) <= 15):
        return await m.answer("Нужно ввести число от 7 до 15! Попробуй еще раз:")
    await state.update_data(l=int(m.text))
    await m.answer("Напиши список своих остальных пешек и их уровни (одним сообщением):")
    await state.set_state(Reg.oth)

@dp.message(Reg.oth)
async def p_oth(m: types.Message, state: FSMContext):
    d = await state.get_data()
    user_id = m.from_user.id
    username = m.from_user.username or f"id{user_id}"
    
    user_data = {
        "_id": user_id,
        "username": username,
        "main_pawn": d['p'],
        "level": d['l'],
        "others": m.text
    }
    
    # Сохраняем в MongoDB (обновляем если есть, или создаем новый)
    await collection.replace_one({"_id": user_id}, user_data, upsert=True)
    
    await m.answer("✅ Данные успешно сохранены в базу клана!", reply_markup=main_kb())
    await state.clear()

@dp.message(F.text == "👤 Мой профиль")
async def profile(m: types.Message):
    res = await collection.find_one({"_id": m.from_user.id})
    if res:
        text = (f"👤 **Твой профиль:**\n\n"
                f"⚔️ Мейн: {res['main_pawn']}\n"
                f"📈 Уровень: {res['level']}\n"
                f"📜 Остальные пешки:\n{res['others']}")
        await m.answer(text, parse_mode="Markdown")
    else:
        await m.answer("Профиль не найден. Нажми '📝 Изменить данные'")

@dp.message(F.text == "👥 Список клана")
async def c_list(m: types.Message):
    cursor = collection.find()
    players = await cursor.to_list(length=100)
    
    if not players:
        return await m.answer("В базе клана пока никого нет.")
    
    kb = InlineKeyboardBuilder()
    for p in players:
        # Кнопка: Имя (Мейн пешка)
        kb.button(text=f"👤 @{p['username']} ({p['main_pawn']})", callback_data=f"view_{p['_id']}")
    
    kb.adjust(1)
    await m.answer("Выберите участника для просмотра деталей:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_player(call: types.CallbackQuery):
    target_id = int(call.data.split("_")[1])
    res = await collection.find_one({"_id": target_id})
    
    if res:
        text = (f"👤 **Игрок:** @{res['username']}\n"
                f"⚔️ **Мейн пешка:** {res['main_pawn']}\n"
                f"📈 **Уровень:** {res['level']}\n\n"
                f"📜 **Все пешки:**\n{res['others']}")
        await call.message.answer(text, parse_mode="Markdown")
        await call.answer()
    else:
        await call.answer("Данные игрока не найдены", show_alert=True)

async def main():
    # В MongoDB таблицы (коллекции) создаются автоматически при первой вставке
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
