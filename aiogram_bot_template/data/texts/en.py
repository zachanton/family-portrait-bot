# aiogram_bot_template/data/texts/en.py
from .dto import LocaleTexts, BotCommandInfo, BotInfo

texts = LocaleTexts(
    commands=[
        BotCommandInfo(command="start", description="✨ Create a new portrait"),
        BotCommandInfo(command="cancel", description="↩️ Start over"),
        BotCommandInfo(command="language", description="🌐 Change language"),
        BotCommandInfo(command="help", description="❓ Get help"),
    ],
    bot_info=BotInfo(
        short_description="AI Family Portraits ✨ See your future child!",
        description=(
            "Welcome! I can create a beautiful portrait of your future child or a family photo. ✨\n\n"
            "Just send me photos of two parents [ 📸 + 📸 ], and my AI will work its magic.\n\n"
            "By starting, you agree to our /terms and /privacy policy."
        )
    ),
    terms_of_service=[
        """<b>Terms of Service (Sample)</b>
<i>Last Updated: September 05, 2025</i>

<b>1. Service Description</b>
This bot uses AI to merge two individual photos into a single group portrait for entertainment purposes.

<b>2. User Obligations</b>
You agree to only upload photos that you have the rights to use. Do not upload illegal, explicit, or harmful content.

<b>3. Payments</b>
The service uses Telegram Stars (⭐) for payments. All purchases are final and non-refundable.

<b>4. Intellectual Property</b>
You retain the rights to the images you upload and the final generated portrait.

<b>5. Contact</b>
For support, contact us at: {support_email}
(Note: This is a sample text. Consult a lawyer for a real policy.)"""
    ],
    privacy_policy=[
        """<b>Privacy Policy (Sample)</b>
<i>Last Updated: September 05, 2025</i>

<b>1. Information We Collect</b>
- Your Telegram user ID and language code to operate the bot.
- Photos you upload are processed by our AI and cached for up to 24 hours for operational purposes.

<b>2. How We Use Information</b>
We use your data solely to provide the image generation service and process payments through Telegram. We do not sell your data.

<b>3. Third-Party Services</b>
Your photos are sent to third-party AI providers to generate the portrait.

<b>4. Data Storage</b>
We store metadata about your requests but uploaded images are deleted from our active cache within 24 hours.

<b>5. Contact</b>
If you have questions, please contact us at: {support_email}
(Note: This is a sample text. Consult a lawyer for a real policy.)"""
    ]
)