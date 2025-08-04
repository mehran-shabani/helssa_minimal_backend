import os
import django

# پیام اشکال‌زدایی (برای بررسی مسیر پروژه)
print("Setting up Django...")

# تنظیم متغیر
# محیطی برای استفاده از تنظیمات پروژه (نام پروژه خود را بررسی کنید)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medogram.settings')

# راه‌اندازی Django
django.setup()

# پیام اشکال‌زدایی
print("Django has been set up.")

from rest_framework_simplejwt.tokens import RefreshToken
from telemedicine.models import CustomUser  # جایگزین با نام اپلیکیشن و مدل کاربر خودتان


def generate_jwt_for_user(user_id):
    try:
        # دریافت کاربر با استفاده از user_id
        user = CustomUser.objects.get(id=user_id)

        # ایجاد توکن‌ها
        refresh = RefreshToken.for_user(user)

        # چاپ و ذخیره توکن‌ها
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        print(f"Access Token: {access_token}")
        print(f"Refresh Token: {refresh_token}")

        # ذخیره توکن‌ها در فایل
        with open("tokens.txt", "w") as file:
            file.write(f"{access_token}\n")
            file.write(f"{refresh_token}\n")

        print("Tokens have been saved to tokens.txt")

    except CustomUser.DoesNotExist:
        print(f"User with ID {user_id} does not exist.")


if __name__ == "__main__":
    # ID کاربر را که می‌خواهید توکن برایش ایجاد شود وارد کنید
    user_id = 2  # ID کاربر مورد نظر
    generate_jwt_for_user(user_id)
