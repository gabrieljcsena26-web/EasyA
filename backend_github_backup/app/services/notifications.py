from twilio.rest import Client

# Substitua pelos seus dados
TWILIO_SID = "SEU_TWILIO_SID"
TWILIO_TOKEN = "SEU_TWILIO_TOKEN"
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"  # Twilio Sandbox

client = Client(TWILIO_SID, TWILIO_TOKEN)

def enviar_sms(numero: str, mensagem: str):
    message = client.messages.create(
        body=mensagem,
        from_=TWILIO_WHATSAPP_NUMBER,
        to=numero
    )
    return message.sid
