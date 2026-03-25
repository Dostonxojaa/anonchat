from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.utils.keyboard import (
    ReplyKeyboardBuilder
)

class online:
    def builder(text):
        builder = ReplyKeyboardBuilder()
        text = [text]
        [
            builder.button(text=item)
            for item in text
        ]

        return builder.as_markup(resize_keyboard = True)
    
class inline:
    ...

