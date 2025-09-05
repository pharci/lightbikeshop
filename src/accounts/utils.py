from django.conf import settings
from django.core.mail import EmailMultiAlternatives
import secrets

def generate_verification_code():
    return str(secrets.randbelow(900000) + 100000)

def send_verification_code(email, code: str):
    subject = "LIGHTBIKESHOP — подтверждение входа"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]

    text_message = f"Ваш код для входа в LIGHTBIKESHOP: {code}"

    html_message = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
      
      <!-- header -->
      <div style="background:#111827;padding:18px;text-align:center;">
        <h1 style="margin:0;font-size:22px;font-weight:800;color:#fff;letter-spacing:1px;">
          LIGHTBIKESHOP
        </h1>
      </div>
      
      <!-- body -->
      <div style="padding:24px;color:#111827;">
        <h2 style="margin-top:0;font-size:20px;">Подтверждение входа</h2>
        <p style="font-size:15px;margin-bottom:14px;">Здравствуйте!</p>
        <p style="font-size:15px;margin-bottom:18px;">Используйте этот код, чтобы войти в аккаунт на сайте <strong><a style="text-decoration: none; color:#111827;" href="lightbikeshop.ru">LIGHTBIKESHOP</a></strong>:</p>
        
        <div style="font-size:32px;font-weight:bold;letter-spacing:6px;padding:20px;background:#fff;border:2px dashed #111827;border-radius:10px;text-align:center;margin:20px 0;color:#111827;">
          {code}
        </div>
        
        <p style="font-size:13px;color:#6b7280;margin-top:16px;">
          Код действителен несколько минут.<br>
          Если вы не запрашивали вход — просто проигнорируйте это письмо.
        </p>
      </div>
      
      <!-- footer -->
      <div style="background:#f3f4f6;padding:14px;text-align:center;font-size:12px;color:#6b7280;">
        © {settings.SITE_NAME if hasattr(settings, "SITE_NAME") else "LIGHTBIKESHOP"} — ride the light 🚴
      </div>
    </div>
    """

    email_obj = EmailMultiAlternatives(subject, text_message, from_email, recipient_list)
    email_obj.attach_alternative(html_message, "text/html")
    email_obj.send()