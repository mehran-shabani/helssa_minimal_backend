from django.core.management.base import BaseCommand
from decimal import Decimal
from sub.models import Plan, Specialty

SPECIALTIES = [
    ("dermatology","پوست","آنالیز ضایعات پوستی، اگزما، آکنه.","تمرکز بر آنالیز پوست؛ سوال درباره مدت/محیط/داروهای قبلی."),
    ("pediatrics","کودکان","تب، سرفه، تغذیه کودک.","توصیه‌های ایمن برای کودکان؛ هشدار علائم خطر."),
    ("cardiology","قلب","درد قفسه سینه، تنگی نفس، فشار خون.","ارزیابی خطر؛ توصیه مراجعه اورژانسی در صورت نیاز."),
    ("neurology","مغز و اعصاب","سردرد، تشنج، بی‌حسی.","ارزیابی علائم نورولوژیک، علائم هشدار."),
    ("orthopedics","ارتوپدی","درد مفصل، شکستگی، کشیدگی.","راهنمایی اولیه، آتل و استراحت/یخ/فشار/بالا نگه‌داشتن."),
    ("ophthalmology","چشم","قرمزی، تاری دید، جسم خارجی.","هشدار درد شدید/کاهش دید ناگهانی."),
    ("otolaryngology","گوش‌حلق‌وبینی","سینوزیت، گوش‌درد، گلودرد.","تفاوت‌های عفونی/حساسیتی."),
    ("gynecology","زنان","چرخه قاعدگی، درد لگن، بارداری.","احتیاط در بارداری/شیردهی."),
    ("urology","اورولوژی","سوزش ادرار، تکرر، درد پهلو.","هشدار تب/درد شدید/خونریزی."),
    ("gastroenterology","گوارش","دل‌درد، تهوع، اسهال/یبوست.","هیدراتاسیون و رژیم BRAT در اسهال خفیف."),
    ("endocrinology","غدد","دیابت، تیروئید.","کنترل قند/TSH و علائم عدم تعادل."),
    ("pulmonology","ریه","سرفه، تنگی نفس، آسم.","اسپیرومتری/علائم هشدار."),
    ("rheumatology","روماتولوژی","دردهای مزمن، خودایمنی.","ارزیابی الگو/سفتی صبحگاهی."),
    ("hematology","خون","کم‌خونی، کبودی، خونریزی.","CBC و علائم هشدار."),
    ("nephrology","کلیه","آزوتِمی، پروتئینوری.","هیدراتاسیون و پایش فشار."),
    ("infectious","عفونی","تب، عفونت‌های شایع.","الگوریتم تب بر اساس سن/ریسک."),
    ("psychiatry","روانپزشکی","اضطراب، افسردگی، خواب.","پایبندی به راهنمایی‌های ایمن و ارجاع."),
    ("allergy","آلرژی/ایمونولوژی","حساسیت‌ها، رینیت، کهیر.","اجتناب از آلرژن و درمان حمایتی."),
    ("nutrition","تغذیه","رژیم، اضافه/کاهش وزن.","راهنمایی اصولی و قابل اجرا."),
    ("dentistry","دندانپزشکی","درد دندان، لثه.","مراقبت حمایتی و ارجاع در آبسه/تب."),
]

class Command(BaseCommand):
    help = "Seed default plans and 20 specialties."

    def handle(self, *args, **opts):
        s_objs = {}
        for code, name, desc, prompt in SPECIALTIES:
            s, _ = Specialty.objects.get_or_create(code=code, defaults={
                "name": name, "description": desc, "system_prompt_ext": prompt
            })
            s_objs[code] = s

        starter, _ = Plan.objects.get_or_create(
            code="starter",
            defaults=dict(
                name="Starter", monthly_price=Decimal("0"),
                daily_char_limit=10_000, daily_requests_limit=25, max_tokens_per_request=500,
                allow_vision=False, max_images=0, allow_agent_tools=True, priority="normal",
            ),
        )
        pro, _ = Plan.objects.get_or_create(
            code="pro",
            defaults=dict(
                name="Pro", monthly_price=Decimal("9.90"),
                daily_char_limit=60_000, daily_requests_limit=150, max_tokens_per_request=1500,
                allow_vision=True, max_images=4, allow_agent_tools=True, priority="high",
            ),
        )
        business, _ = Plan.objects.get_or_create(
            code="business",
            defaults=dict(
                name="Business", monthly_price=Decimal("39.00"),
                daily_char_limit=240_000, daily_requests_limit=1000, max_tokens_per_request=2000,
                allow_vision=True, max_images=6, allow_agent_tools=True, priority="high",
            ),
        )

        starter.specialties.set([s_objs["dermatology"], s_objs["otolaryngology"], s_objs["allergy"]])
        pro.specialties.set([s_objs[c] for c in ["dermatology","pediatrics","cardiology","gastroenterology","ophthalmology","infectious","nutrition"]])
        business.specialties.set([s for s in s_objs.values()])

        self.stdout.write(self.style.SUCCESS("Plans & 20 specialties seeded."))
