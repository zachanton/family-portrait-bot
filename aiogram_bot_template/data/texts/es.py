# aiogram_bot_template/data/texts/es.py
from .dto import LocaleTexts, BotCommandInfo, BotInfo

texts = LocaleTexts(
    commands=[
        BotCommandInfo(command="start", description="✨ Crear un nuevo retrato"),
        BotCommandInfo(command="cancel", description="↩️ Empezar de nuevo"),
        BotCommandInfo(command="language", description="🌐 Cambiar idioma"),
        BotCommandInfo(command="help", description="❓ Soporte"),
    ],
    bot_info=BotInfo(
        short_description="¡Retratos de grupo con IA! ✨ ¡Envía dos fotos!",
        description=(
            "¡Crea un hermoso retrato de grupo a partir de dos fotos! ✨\n\n"
            "Simplemente envía dos fotos [ 📸 + 📸 ] y mi IA las combinará en una única imagen cohesiva.\n\n"
            "Al comenzar, aceptas nuestros /terms y /privacy."
        )
    ),
    terms_of_service=[
        """<b>Términos de Servicio (Ejemplo)</b>
<i>Última actualización: 5 de septiembre de 2025</i>

<b>1. Descripción del Servicio</b>
Este bot utiliza IA para fusionar dos fotos individuales en un único retrato de grupo con fines de entretenimiento.

<b>2. Obligaciones del Usuario</b>
Aceptas subir solo fotos para las que tienes los derechos de uso. No subas contenido ilegal, explícito o dañino.

<b>3. Pagos</b>
El servicio utiliza Telegram Stars (⭐) para los pagos. Todas las compras son finales y no reembolsables.

<b>4. Propiedad Intelectual</b>
Conservas los derechos sobre las imágenes que subes y el retrato final generado.

<b>5. Contacto</b>
Para soporte, contáctanos en: {support_email}
(Nota: Este es un texto de ejemplo. Consulta a un abogado para una política real.)"""
    ],
    privacy_policy=[
        """<b>Política de Privacidad (Ejemplo)</b>
<i>Última actualización: 5 de septiembre de 2025</i>

<b>1. Información que Recopilamos</b>
- Tu ID de usuario de Telegram y código de idioma para operar el bot.
- Las fotos que subes son procesadas por nuestra IA y almacenadas en caché hasta por 24 horas para fines operativos.

<b>2. Cómo Usamos la Información</b>
Usamos tus datos únicamente para proporcionar el servicio de generación de imágenes y procesar pagos a través de Telegram. No vendemos tus datos.

<b>3. Servicios de Terceros</b>
Tus fotos se envían a proveedores de IA de terceros para generar el retrato.

<b>4. Almacenamiento de Datos</b>
Almacenamos metadatos sobre tus solicitudes, pero las imágenes subidas se eliminan de nuestra caché activa en 24 horas.

<b>5. Contacto</b>
Si tienes preguntas, contáctanos en: {support_email}
(Nota: Este es un texto de ejemplo. Consulta a un abogado para una política real.)"""
    ]
)