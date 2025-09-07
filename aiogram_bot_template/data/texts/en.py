# aiogram_bot_template/data/texts/en.py
from .dto import LocaleTexts, BotCommandInfo, BotInfo

texts = LocaleTexts(
    commands=[
        BotCommandInfo(command="start", description="✨ Create a new portrait"),
        BotCommandInfo(command="cancel", description="↩️ Start over"),
        BotCommandInfo(command="language", description="🌐 Change language"),
        BotCommandInfo(command="help", description="❓ Support"),
    ],
    bot_info=BotInfo(
        description=(
            "Imagine your future family ✨\n\n"
            "Just send two photos [ 📸 + 📸 ] and my AI will create a unique portrait of your potential child.\n\n"
            "By starting, you agree to our /terms and /privacy policy."
        ),
        short_description="See your future child with AI. ✨ Send two photos to begin!",
    ),
    terms_of_service=[
        """<b>Terms of Service for Kindred AI Bot</b>
<i>Last Updated: August 30, 2025</i>

<b>1. Acceptance of Terms</b>
By accessing or using the Kindred AI bot ("the Service") on Telegram, you agree to these Terms of Service ("Terms"). If you do not agree, you must stop using the Service immediately.

<b>2. Description of the Service</b>
Kindred AI is a Telegram bot that uses artificial intelligence to generate and edit images based on user inputs, including Child Image Generation and Image Editing. You can cancel an ongoing operation with <code>/cancel</code> and change the language with <code>/language</code>. The Service is provided "as is" for personal, entertainment purposes.

<b>3. Eligibility and Age Restriction</b>
You must be 18 years or older to use this Service, or have the consent of a parent or legal guardian.

<b>4. User Obligations and Acceptable Use</b>
When using Kindred AI, you agree to:
- <b>Provide Appropriate Images:</b> Only upload photos you have the right to use, featuring a single person with a clear face. Do not upload illegal or explicit content.
- <b>Respect Privacy and Rights:</b> Do not upload images of others without their permission.
- <b>No Prohibited Content:</b> Do not use the Service to create illegal, harmful, hateful, or otherwise objectionable content.
- <b>Follow Usage Guidelines & Telegram Rules:</b> Adhere to bot instructions and Telegram’s terms of service.
We reserve the right to refuse service for violations.""",
        """<b>5. Payment, Free Trial, and Virtual Currency</b>
- <b>Telegram Stars:</b> The Service uses Telegram Stars (⭐) for payments. Prices are shown in the bot.
- <b>Purchases:</b> All spending of Stars is final and non-refundable.
- <b>Free Trial:</b> Each new user is entitled to one free trial generation.
- <b>No Refunds:</b> Telegram Stars are non-refundable.

<b>6. License and Intellectual Property Rights</b>
- <b>User Content:</b> You retain ownership of the content you provide and the generated images ("Output").
- <b>License to Operate:</b> You grant us a license to use your content as necessary to provide the Service.
- <b>Free Trial Marketing Consent:</b> If you use the free trial, you grant us the right to use the provided photos and the generated image for our marketing purposes, anonymously. This does not apply to paid services.
- <b>Privacy for Paid Services:</b> Your images from paid services are treated as private.
- <b>Output Usage:</b> You receive a personal license to use the generated images for any lawful purpose.

<b>7. Privacy and Data Handling</b>
Our Privacy Policy explains how we collect and process your data. By using the Service, you agree to it.

<b>8. Third-Party Services</b>
The Service uses external providers (e.g., AI models, payment processors). Your content may be processed by them to deliver features.""",
        """<b>9. Content Moderation</b>
The Service uses automated moderation. We reserve the right to ban users who violate content rules.

<b>10. Disclaimer of Warranties</b>
The Service is provided "as is" without warranties of any kind.

<b>11. Limitation of Liability</b>
To the maximum extent permitted by law, we are not liable for indirect or consequential damages. Our total liability is limited to the amount you paid for the Service in the last 6 months.

<b>12. Indemnification</b>
You agree to indemnify us from any claims arising out of your use of the Service.

<b>13. Termination</b>
We may suspend or terminate your access if you violate these Terms.

<b>14. Governing Law and Disputes</b>
These Terms are governed by the laws of Poland.

<b>15. Miscellaneous</b>
These Terms, along with the Privacy Policy, are the entire agreement between us.

<b>16. Contact and Support</b>
For questions, contact us at: {support_email}"""
    ],
    privacy_policy=[
        """<b>Privacy Policy for Kindred AI Bot</b>
<i>Last Updated: August 30, 2025</i>

This Privacy Policy explains how the Kindred AI Telegram bot collects, uses, and shares your information.

<b>1. Information We Collect</b>
- <b>Telegram Account Information:</b> User ID, username, display name, language code.
- <b>Photos and Images:</b> Images you send are processed and temporarily cached for up to 24 hours.
- <b>Generated Images and Request Data:</b> We store request parameters and references to results.
- <b>Text Prompts:</b> Prompts are processed by the AI and may be checked for content safety.
- <b>Payment Data:</b> We receive transaction confirmations from Telegram. We do not handle your financial information.
- <b>Usage Analytics:</b> We collect technical data to improve the service.

<b>2. How We Use Your Information</b>
- To provide and personalize the service.
- To process transactions via Telegram.
- To maintain quality and security.
- To improve and develop the service.
- <b>For Marketing (Free Trial Only):</b> With consent, images from the free trial may be used anonymously in promotional materials. This does not apply to paid services.
- For legal compliance.""",
        """<b>3. How We Share or Disclose Information</b>
We do not sell your data. We share it only with:
- <b>Third-Party Service Providers:</b> External AI services (e.g., Fal.ai, Google Gemini) for image processing and OpenAI for content moderation.
- <b>Telegram and Payment Processors.</b>
- <b>For Legal Reasons.</b>
- <b>With Your Consent.</b>

<b>4. Data Storage and Security</b>
Your data is stored on secure servers. We use encryption and access controls. Uploaded images are deleted from our active cache after 24 hours.

<b>5. Cookies and Tracking</b>
The bot does not use cookies.

<b>6. Your Rights and Choices</b>
You have the right to access, correct, or delete your personal data. You can also object to the marketing use of your free trial images. Contact our support to exercise these rights.

<b>7. Children's Privacy</b>
The Service is not for users under 18.

<b>8. Changes to this Privacy Policy</b>
We may update this Policy. We will notify you of significant changes.

<b>9. Contact Us</b>
If you have questions, please contact us at: {support_email}"""
    ]
)