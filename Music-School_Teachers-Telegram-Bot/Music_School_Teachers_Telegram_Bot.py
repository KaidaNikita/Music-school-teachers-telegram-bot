# -*- coding: utf-8 -*-
import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from dotenv import load_dotenv

# Завантажуємо змінні з файлу .env
load_dotenv()
token = os.getenv('TELEGRAM_BOT_TEACHER_TOKEN')
teacher_secret_password = os.getenv('TEACHER_SECRET_PASSWORD')

# Константи для етапів діалогу
REGISTER_TEACHER_PASS, REGISTER_TEACHER_FULLNAME, ADD_CLASS_DATE, ADD_CLASS_ROOM = range(4)

# Статичний список кабінетів
classrooms = ['101', '102', '103', '104', '105']

# Підключення до бази даних
def init_db():
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()

    # Таблиця для користувачів
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        fullname TEXT,
        is_teacher INTEGER DEFAULT 0
    )''')

    # Таблиця для викладачів
    cursor.execute('''CREATE TABLE IF NOT EXISTS teachers (
        teacher_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')

    # Таблиця для розкладу
    cursor.execute('''CREATE TABLE IF NOT EXISTS schedule (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        room TEXT,
        teacher_id INTEGER,
        FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
    )''')

    # Таблиця для учнів
    cursor.execute('''CREATE TABLE IF NOT EXISTS students (
        student_id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT,
        teacher_id INTEGER,
        FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
    )''')

    conn.close()

# Основне меню
def main_menu_keyboard():
    return ReplyKeyboardMarkup([['Переглянути профіль', 'Додати урок'], ['Скасувати']], resize_keyboard=True)

# Обробник для головного меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_teacher FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if user and user[0] == 1:
        await update.message.reply_text('Вітаю! Ви зареєстровані як викладач. Виберіть опцію:', reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    else:
        await update.message.reply_text('Вітаю! Введіть спеціальний пароль для реєстрації викладача:', reply_markup=ReplyKeyboardMarkup([['Скасувати']], resize_keyboard=True))
        return REGISTER_TEACHER_PASS
    conn.close()

# Реєстрація викладача
async def register_teacher_pass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text
    if password == teacher_secret_password:
        await update.message.reply_text("Пароль вірний. Введіть своє ПІБ:", reply_markup=ReplyKeyboardMarkup([['Скасувати']], resize_keyboard=True))
        context.user_data['is_teacher'] = True
        return REGISTER_TEACHER_FULLNAME
    else:
        await update.message.reply_text("Невірний пароль. Спробуйте знову або скасуйте операцію.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

async def register_teacher_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    fullname = update.message.text
    user_id = update.message.from_user.id
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    
    # Перевіряємо, чи користувач вже існує
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user_exists = cursor.fetchone()
    
    if user_exists:
        await update.message.reply_text("Ви вже зареєстровані як викладач.", reply_markup=main_menu_keyboard())
    else:
        # Додаємо користувача і викладача
        cursor.execute("INSERT INTO users (user_id, fullname, is_teacher) VALUES (?, ?, 1)", (user_id, fullname))
        cursor.execute("INSERT INTO teachers (user_id) VALUES (?)", (user_id,))
        
        conn.commit()
        await update.message.reply_text("Реєстрація завершена!", reply_markup=main_menu_keyboard())
    
    conn.close()
    return ConversationHandler.END


# Переглянути профіль викладача
async def view_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    
    # Отримуємо інформацію про викладача
    cursor.execute('''SELECT u.fullname, s.fullname
                      FROM teachers t
                      JOIN users u ON t.user_id = u.user_id
                      LEFT JOIN students s ON t.teacher_id = s.teacher_id
                      WHERE t.user_id = ?''', (user_id,))
    result = cursor.fetchall()
    
    if result:
        teacher_name = result[0][0]
        student_names = [row[1] for row in result if row[1] is not None]
        
        profile_info = f"Ім'я викладача: {teacher_name}\nУчні:\n" + ("\n".join(student_names) if student_names else "Немає учнів.")
    else:
        profile_info = "Інформація про профіль недоступна."
    
    await update.message.reply_text(profile_info, reply_markup=main_menu_keyboard())
    conn.close()

# Додати урок (тільки для викладача)
async def add_class(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введіть дату для нового уроку (у форматі РРРР-ММ-ДД):", reply_markup=ReplyKeyboardMarkup([['Скасувати']], resize_keyboard=True))
    return ADD_CLASS_DATE

async def add_class_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    date = update.message.text
    context.user_data['class_date'] = date
    await update.message.reply_text("Виберіть кабінет:", reply_markup=ReplyKeyboardMarkup([[room] for room in classrooms] + [['Скасувати']], resize_keyboard=True))
    return ADD_CLASS_ROOM

async def add_class_room(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    room = update.message.text
    user_id = update.message.from_user.id
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("SELECT teacher_id FROM teachers WHERE user_id=?", (user_id,))
    teacher = cursor.fetchone()

    if teacher:
        teacher_id = teacher[0]
        cursor.execute("INSERT INTO schedule (date, room, teacher_id) VALUES (?, ?, ?)", (context.user_data['class_date'], room, teacher_id))
        conn.commit()
        await update.message.reply_text(f"Урок на дату {context.user_data['class_date']} у кабінеті {room} успішно додано.", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("Ви не зареєстровані як викладач.", reply_markup=main_menu_keyboard())
    
    conn.close()
    return ConversationHandler.END

# Скасування операції
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Операція скасована.', reply_markup=main_menu_keyboard())
    return ConversationHandler.END

def main() -> None:
    init_db()

    application = ApplicationBuilder().token(token).build()

    # Додано обробник реєстрації викладача
    register_teacher_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            REGISTER_TEACHER_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_teacher_pass)],
            REGISTER_TEACHER_FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_teacher_fullname)]
        },
        fallbacks=[MessageHandler(filters.Regex('^Скасувати$'), cancel)]
    )

    # Додано обробник додавання уроку
    add_class_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Додати урок$'), add_class)],
        states={
            ADD_CLASS_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_class_date)],
            ADD_CLASS_ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_class_room)],
        },
        fallbacks=[MessageHandler(filters.Regex('^Скасувати$'), cancel)]
    )

    application.add_handler(MessageHandler(filters.Regex('^Переглянути профіль$'), view_profile))
    application.add_handler(register_teacher_conv_handler)
    application.add_handler(add_class_conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
