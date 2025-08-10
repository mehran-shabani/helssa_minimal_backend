import re

def clean_bot_message(message):
    """
    تمیزکاری پیام بدون حذف ایموجی‌ها و بدون چسبیدن کلمات فارسی.
    """
    # 1. حذف فاصله‌های اضافی از ابتدا و انتها
    cleaned_message = message.strip()
    # 2. حذف فاصله‌های بیش از یک عدد
    cleaned_message = re.sub(r'\s+', ' ', cleaned_message)
    # 3. تبدیل خط جدید به <br>
    cleaned_message = cleaned_message.replace('\n', '<br>')
    # 4. تبدیل ویرگول انگلیسی به فارسی و چند نقطه به …
    cleaned_message = cleaned_message.replace(',', '،')
    cleaned_message = re.sub(r'\.{2,}', '…', cleaned_message)
    # 5. حذف فاصله‌های اضافی دور علائم (فقط قبل)
    cleaned_message = re.sub(r'\s+([،.؟!…])', r'\1', cleaned_message)
    # 6. اطمینان از وجود یک فاصله بعد از علائم (به جز انتهای جمله)
    cleaned_message = re.sub(r'([،.؟!…])([^\s<])', r'\1 \2', cleaned_message)
    # 7. جایگزینی خط‌تیره با نیم‌فاصله فقط بین دو حرف فارسی (نه اعداد و نه لاتین)
    cleaned_message = re.sub(r'([اآبپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی])\s*-\s*([اآبپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی])', r'\1‌\2', cleaned_message)
    # 8. حذف کاراکترهای غیرمجاز (بدون حذف ایموجی)
    cleaned_message = re.sub(r'[^\w\s\.\،\؟\!\-\«\»\"\(\)\[\]\{\}\u0600-\u06FF\u200c\uFE0F\u061F]', '', cleaned_message)
    # 9. نقل‌قول و پرانتزها
    cleaned_message = cleaned_message.replace('"', '«').replace("'", "»")
    cleaned_message = cleaned_message.replace('(', '«').replace(')', '»')
    # 10. حذف تکرار علائم
    cleaned_message = re.sub(r'([،.؟!…])\1+', r'\1', cleaned_message)
    # 11. حذف فاصله اضافی مجدد
    cleaned_message = re.sub(r'\s+', ' ', cleaned_message).strip()
    return cleaned_message
