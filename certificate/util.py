import os
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors
from bidi.algorithm import get_display
import arabic_reshaper
import jdatetime
import io
from PIL import Image
import qrcode
import logging

def binary_generator():
    image_path = os.path.join(os.path.dirname(__file__), 'logo.png')
    with open(image_path, "rb") as image_file:
        binary_data = image_file.read()
    return binary_data


def create_qr_code(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="#4682B4", back_color="white")
    temp_qr_path = "temp_qr.png"
    qr_image.save(temp_qr_path)
    return temp_qr_path


def reshape_text(text):
    return get_display(arabic_reshaper.reshape(text))


def create_medical_certificate(first_name, last_name, national_code, sick_days, sick_name, verification_url):
    try:
        # ثبت فونت
        font_path = os.path.join(os.path.dirname(__file__), 'IRANSans.ttf')
        pdfmetrics.registerFont(TTFont('IRANSans', font_path))

        # مسیر پوشه media/pdf
        output_dir = os.path.join(settings.MEDIA_ROOT, 'pdf', 'certificate')

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)  # ساخت پوشه اگر وجود نداشته باشد

        # نام فایل PDF
        file_name = os.path.join(output_dir, f'certificate_{national_code}.pdf')

        # ابعاد صفحه A4
        width, height = A4
        margin = 40

        c = canvas.Canvas(file_name, pagesize=A4)

        # کادر بیرونی
        c.setStrokeColor(colors.HexColor('#4682B4'))
        c.setLineWidth(2)
        c.roundRect(margin, margin, width - 2 * margin, height / 1.8, 15)

        # کادر داخلی تزئینی
        inner_margin = margin + 10
        c.setStrokeColor(colors.HexColor('#B0C4DE'))
        c.setLineWidth(1)
        c.roundRect(inner_margin, inner_margin, width - 2 * inner_margin, height / 1.8 - 20, 10)

        # لوگو در بالای صفحه
        logo_data = binary_generator()
        with Image.open(io.BytesIO(logo_data)) as img:
            temp_logo_path = "temp_logo.png"
            img.save(temp_logo_path)

            logo_width = 100
            logo_height = 40
            logo_x = (width - logo_width) / 2
            logo_y = height / 1.8 - margin + 20  # بالای نوار تزئینی

            c.drawImage(temp_logo_path, logo_x, logo_y, width=logo_width, height=logo_height)
            os.remove(temp_logo_path)

        # نوار تزئینی بالای صفحه
        c.setFillColor(colors.HexColor('#4682B4'))
        c.rect(margin, height / 1.8 - margin, width - 2 * margin, 15, fill=1)

        # عنوان
        c.setFont('IRANSans', 22)
        c.setFillColor(colors.HexColor('#1E4F78'))
        title = reshape_text("گواهی استعلاجی")
        c.drawCentredString(width / 2, height / 1.8 - margin - 40, title)

        # خطوط تزئینی زیر عنوان
        c.setStrokeColor(colors.HexColor('#4682B4'))
        c.setLineWidth(1.5)
        title_underline_y = height / 1.8 - margin - 50
        c.line(width / 3, title_underline_y, width * 2 / 3, title_underline_y)

        # محتوای اصلی
        content_start_y = height / 1.8 - margin - 90
        line_height = 30

        # تنظیم فونت برای متن اصلی
        c.setFont('IRANSans', 12)
        c.setFillColor(colors.black)

        # اطلاعات در دو ستون - با اضافه کردن کد ملی
        right_column = [
            reshape_text(f"نام: {first_name}"),
            reshape_text(f"تاریخ: {jdatetime.date.today().strftime('%Y/%m/%d')}"),
            reshape_text(f"کد ملی: {national_code}"),  # اضافه کردن کد ملی
        ]

        left_column = [
            reshape_text(f"نام خانوادگی: {last_name}"),
            reshape_text(f"شماره گواهی: {jdatetime.datetime.now().strftime('%Y%m%d%H%M')}"),
            reshape_text(""),  # برای حفظ تراز با ستون راست
        ]

        # چاپ ستون راست
        for i, text in enumerate(right_column):
            y_pos = content_start_y - (i * line_height)
            c.drawRightString(width - inner_margin - 10, y_pos, text)

        # چاپ ستون چپ
        for i, text in enumerate(left_column):
            y_pos = content_start_y - (i * line_height)
            c.drawRightString(width / 2 + 50, y_pos, text)

        # اطلاعات بیماری - با تنظیم مجدد فاصله
        c.setFont('IRANSans', 12)
        disease_info = reshape_text(f"نام بیماری: {sick_name}")
        sick_days_info = reshape_text(f"تعداد روزهای استعلاجی: {sick_days}")

        disease_y = content_start_y - (3.5 * line_height)  # تنظیم فاصله برای جا دادن کد ملی
        c.drawCentredString(width / 2, disease_y, disease_info)
        c.drawCentredString(width / 2, disease_y - line_height, sick_days_info)

        # توضیحات - با تنظیم مجدد فاصله
        c.setFont('IRANSans', 10)
        description = reshape_text("این گواهی جهت تایید استعلاجی نام برده صادر شده و تا 24 ساعت از صدور اعتبار دارد.")
        c.drawCentredString(width / 2, disease_y - (2 * line_height), description)

        # اطلاعات پزشک - با تنظیم مجدد فاصله
        c.setFont('IRANSans', 12)
        doctor_info = reshape_text("دکتر شبانی شهرضا ن.پ:168396")
        c.drawRightString(width - inner_margin - 10, disease_y - (3 * line_height), doctor_info)

        # QR code در محل قبلی امضا
        qr_path = create_qr_code(verification_url)
        qr_size = 80
        qr_x = (width - qr_size) / 2
        qr_y = margin + 50  # موقعیت جدید - پایین‌تر
        c.drawImage(qr_path, qr_x, qr_y, width=qr_size, height=qr_size)
        os.remove(qr_path)

        # متن راهنمای QR
        c.setFont('IRANSans', 9)
        c.setFillColor(colors.HexColor('#1E4F78'))
        qr_guide = reshape_text("برای تایید اصالت گواهی، کد را اسکن کنید")
        c.drawCentredString(width / 2, qr_y - 15, qr_guide)

        # متن پایین صفحه
        c.setFont('IRANSans', 11)
        footer_text = reshape_text("ویزیت آنلاین مدوگرام")
        c.drawCentredString(width / 2, margin + 20, footer_text)

        c.save()
        print(f'OK file: {file_name} created')

        return True

    except Exception as e:
        logging.error(f"Error in creating PDF for {national_code}: {str(e)}")
        return False

