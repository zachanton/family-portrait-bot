# aiogram_bot_template/data/texts/es.py
from .dto import LocaleTexts, BotCommandInfo, BotInfo

from .dto import LocaleTexts, BotCommandInfo, BotInfo

texts = LocaleTexts(
    commands=[
        BotCommandInfo(command="start", description="✨ Crear un nuevo retrato"),
        BotCommandInfo(command="cancel", description="↩️ Empezar de nuevo"),
        BotCommandInfo(command="language", description="🌐 Cambiar idioma"),
        BotCommandInfo(command="help", description="❓ Soporte"),
    ],
    bot_info=BotInfo(
        short_description="Retratos de tu futuro hijo con IA. ✨ ¡Envía dos fotos para empezar!",
        description=(
            "Imagina tu futura familia ✨\n\n"
            "Solo envía dos fotos [ 📸 + 📸 ] y mi IA creará un retrato único de tu potencial hijo.\n\n"
            "Al empezar, aceptas nuestros /terms y /privacy."
        )
    ),
    terms_of_service=[
        """<b>Términos de Servicio para el Bot Kindred AI</b>
<i>Última actualización: 30 de agosto de 2025</i>
(Traducción no oficial, prevalece la versión en inglés)

<b>1. Aceptación de los Términos</b>
Al usar el bot Kindred AI ("el Servicio"), aceptas estos Términos de Servicio.

<b>2. Descripción del Servicio</b>
Kindred AI es un bot de IA que genera y edita imágenes. Puedes cancelar con <code>/cancel</code> o cambiar el idioma con <code>/language</code>. El Servicio se proporciona "tal cual" para entretenimiento.

<b>3. Elegibilidad y Restricción de Edad</b>
Debes tener 18 años o más, o contar con el consentimiento de tus padres.

<b>4. Obligaciones del Usuario y Uso Aceptable</b>
Te comprometes a:
- <b>Proporcionar Imágenes Apropiadas:</b> Subir solo fotos que tengas derecho a usar, con una sola persona y rostro visible. No se permite contenido ilegal o explícito.
- <b>Respetar la Privacidad y los Derechos:</b> No subir imágenes de otros sin su permiso.
- <b>No Crear Contenido Prohibido:</b> No usar el Servicio para crear contenido ilegal, dañino o de odio.
- <b>Seguir las Directrices y Reglas de Telegram.</b>
Nos reservamos el derecho de denegar el servicio por infracciones.""",
        """<b>5. Pago, Prueba Gratuita y Moneda Virtual</b>
- <b>Telegram Stars:</b> El Servicio utiliza Telegram Stars (⭐) para los pagos.
- <b>Compras:</b> Todos los gastos de Stars son finales y no reembolsables.
- <b>Prueba Gratuita:</b> Cada usuario nuevo tiene derecho a una prueba gratuita.
- <b>Sin Reembolsos:</b> Los Telegram Stars no son reembolsables.

<b>6. Licencia y Derechos de Propiedad Intelectual</b>
- <b>Contenido del Usuario:</b> Conservas los derechos sobre tu contenido y las imágenes generadas.
- <b>Licencia para Operar:</b> Nos otorgas una licencia para usar tu contenido para prestar el Servicio.
- <b>Consentimiento de Marketing (Prueba Gratuita):</b> Si usas la prueba gratuita, nos permites usar las imágenes de forma anónima para marketing. Esto no se aplica a los servicios de pago.
- <b>Privacidad para Servicios de Pago:</b> Tus imágenes de servicios de pago son privadas.
- <b>Uso del Resultado:</b> Recibes una licencia personal para usar las imágenes generadas para fines lícitos.

<b>7. Privacidad y Manejo de Datos</b>
Al usar el Servicio, aceptas nuestra Política de Privacidad.

<b>8. Servicios de Terceros</b>
El Servicio utiliza proveedores externos (IA, pagos). Tu contenido puede ser procesado por ellos.""",
        """<b>9. Moderación de Contenido</b>
El Servicio utiliza moderación automática. Podemos bloquear a usuarios por infringir las reglas.

<b>10. Descargo de Garantías</b>
El Servicio se proporciona "tal cual", sin garantías.

<b>11. Limitación de Responsabilidad</b>
Nuestra responsabilidad se limita al importe que pagaste por el Servicio en los últimos 6 meses.

<b>12. Indemnización</b>
Aceptas indemnizarnos por cualquier reclamación derivada de tu uso del Servicio.

<b>13. Terminación</b>
Podemos suspender tu acceso si violas los Términos.

<b>14. Ley Aplicable y Disputas</b>
Estos Términos se rigen por las leyes de Polonia.

<b>15. Miscelánea</b>
Estos Términos y la Política de Privacidad constituyen el acuerdo completo entre nosotros.

<b>16. Contacto y Soporte</b>
Para preguntas, contáctanos en: {support_email}"""
    ],
    privacy_policy=[
        """<b>Política de Privacidad para el Bot Kindred AI</b>
<i>Última actualización: 30 de agosto de 2025</i>
(Traducción no oficial, prevalece la versión en inglés)

Esta Política explica cómo el bot Kindred AI recopila, usa y comparte tu información.

<b>1. Información que Recopilamos</b>
- <b>Información de la Cuenta de Telegram:</b> Tu ID de usuario, nombre de usuario y idioma.
- <b>Fotos e Imágenes:</b> Las imágenes que envías se procesan y se guardan en caché temporalmente (hasta 24 horas).
- <b>Imágenes Generadas y Datos de Solicitud:</b> Guardamos los parámetros de las solicitudes y las referencias a los resultados.
- <b>Indicaciones de Texto:</b> Los textos son procesados por la IA y pueden ser revisados por seguridad.
- <b>Datos de Pago:</b> Recibimos confirmaciones de transacciones de Telegram, no tu información financiera.
- <b>Análisis de Uso:</b> Recopilamos datos técnicos para mejorar el servicio.

<b>2. Cómo Usamos tu Información</b>
- Para prestar y personalizar el servicio.
- Para procesar transacciones a través de Telegram.
- Para mantener la calidad y la seguridad.
- Para mejorar y desarrollar el servicio.
- <b>Para Marketing (Solo Prueba Gratuita):</b> Con tu consentimiento, las imágenes de la prueba gratuita pueden usarse anónimamente en materiales promocionales.
- Para cumplir con la ley.""",
        """<b>3. Cómo Compartimos o Divulgamos Información</b>
No vendemos tus datos. Los compartimos solo con:
- <b>Proveedores de Servicios de Terceros:</b> Servicios de IA externos (ej. Fal.ai, Google Gemini) y OpenAI para moderación.
- <b>Telegram y Procesadores de Pago.</b>
- <b>Por Razones Legales.</b>
- <b>Con tu Consentimiento.</b>

<b>4. Almacenamiento y Seguridad de Datos</b>
Tus datos se almacenan en servidores seguros. Las imágenes subidas se eliminan de nuestra caché activa después de 24 horas.

<b>5. Cookies y Seguimiento</b>
El bot no usa cookies.

<b>6. Tus Derechos y Opciones</b>
Tienes derecho a acceder, corregir o eliminar tus datos personales. También puedes oponerte al uso de marketing de las imágenes de tu prueba gratuita. Contacta a nuestro soporte para ejercer estos derechos.

<b>7. Privacidad de los Niños</b>
El Servicio no está destinado a menores de 18 años.

<b>8. Cambios a esta Política de Privacidad</b>
Podemos actualizar esta Política y te notificaremos de cambios importantes.

<b>9. Contáctanos</b>
Si tienes preguntas, contáctanos en: {support_email}"""
    ]
)