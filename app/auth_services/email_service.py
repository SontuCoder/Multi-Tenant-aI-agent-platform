import resend
from core.config import settings


resend.api_key = settings.RESEND_API_KEY

async def send_verification_email(
    email: str,
    raw_token: str
) -> None:

    verification_url = (
        f"{settings.FRONTEND_URL}/verify-email"
        f"?token={raw_token}"
    )
    if not bool(settings.IS_Prod):
        email = "subhadipmaity792@gmail.com"

    params: resend.Emails.SendParams = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [email],
        "subject": "Verify your email address",
        "html": f"""
            <html>
                <body>
                    <h2>Welcome to Multi-Tenant AI Agent Platform!</h2>

                    <p>Thank you for registering.</p>

                    <p>
                        Please click the button below to verify
                        your email address.
                    </p>

                    <a href="{verification_url}"
                       style="
                           background-color: #2563eb;
                           color: white;
                           padding: 12px 20px;
                           text-decoration: none;
                           border-radius: 5px;
                       ">
                        Verify Email
                    </a>

                    <p>This link expires in {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes.</p>

                    <p>If you did not register, ignore this email.</p>
                </body>
            </html>
        """
    }

    await resend.Emails.send_async(params)

