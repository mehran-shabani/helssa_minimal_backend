# فهرست API ها

## مسیرهای اصلی
- `GET /admin/`
- `GET /swagger/`
- `GET /redoc/`
- سایر مسیرها به اپلیکیشن های زیر ارجاع می شوند:
  - `/api/` تله مدیسن
  - `/api/chat/` چت بات
  - `/certificate/` گواهی پزشکی
  - `/down/` وضعیت به‌روزرسانی اپ
  - `/doc/` پزشک آن‌کال
  - `/api/sub/` مدیریت اشتراک‌ها

## تله‌مدیسن (`/api/`)
- `POST /api/register/` – پارامتر: `phone_number`
- `POST /api/verify/` – پارامترها: `phone_number`, `code`
- `POST /api/transaction/` – پارامتر: `amount`
- `POST /api/verify-payment/` – پارامترها: `trans_id`, `id_get`
- `GET /api/visit/`
- `POST /api/visit/` یا `POST /api/create-visit/` – بدنه: `name`, `urgency`, `general_symptoms`, `neurological_symptoms`, `cardiovascular_symptoms`, `gastrointestinal_symptoms`, `respiratory_symptoms`, `description`, `drug_images`
- `POST /api/profile/`
- `POST /api/profile/update/` – پارامترها: `username`, `email`
- `GET /api/blogs/`
- `POST /api/blogs/<blog_id>/comments/` – بدنه: `comment`
- `POST /api/comments/<comment_id>/<actions>/` – پارامتر مسیر `actions`= `like` یا `dislike`
- `POST /api/box/`
- `GET /api/download-apk/`
- `POST /api/super-visit/<cost>/` – بدنه همانند ساخت ویزیت
- `GET /api/username/`
- `POST /api/username/update/` – پارامتر: `username`
- `GET /api/order/verify/<national_code>/` – پارامتر مسیر `national_code`
- `GET /api/order/download/<national_code>/` – پارامتر مسیر `national_code`

## چت‌بات (`/api/chat/`)
- `POST /api/chat/msg/` – بدنه: `message` یا تصویر/URL، `new_session` (اختیاری)، `images`/`image_url`/`image_urls`, `specialty`, `force_model`
- `GET /api/chat/summary/` – کوئری: `session_id`

## مدیریت اشتراک‌ها (`/api/sub/`)
- `GET /api/sub/plans/`
- `GET /api/sub/me/`
- `POST /api/sub/buy/` – پارامترها: `plan_code`, `months`
- `POST /api/sub/topup/` – پارامتر: `chars`
- `POST /api/sub/specialty/` – پارامترها: `specialty_code`, `months`
- `GET /api/sub/usage/`

## گواهی پزشکی (`/certificate/`)
- `GET /certificate/download/<certificate_national_code>/`
- `GET /certificate/verify/<certificate_national_code>/`
- `GET /certificate/hamester/`

## وضعیت به‌روزرسانی اپ (`/down/`)
- `GET /down/status/`

## پزشک آن‌کال (`/doc/`)
- `GET /doc/oncall/`

