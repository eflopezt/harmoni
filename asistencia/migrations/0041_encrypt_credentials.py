"""
Cifra at-rest los secretos existentes de ConfiguracionSistema (singleton).

Al releer la fila, EncryptedCharField devuelve el valor en claro
(legacy sin prefijo enc$) y al guardarla lo escribe cifrado.
No se reversa: bajar implicaría reescribir secretos en claro.
"""
from django.db import migrations

CAMPOS = [
    'ia_api_key', 'ia_gemini_api_key', 'zapsign_api_key',
    'telegram_bot_token', 'whatsapp_access_token', 'openclaw_gateway_token',
]


def encrypt_existing(apps, schema_editor):
    ConfiguracionSistema = apps.get_model('tareo', 'ConfiguracionSistema')
    for obj in ConfiguracionSistema.objects.all():
        con_valor = [f for f in CAMPOS if getattr(obj, f)]
        if con_valor:
            obj.save(update_fields=con_valor)


class Migration(migrations.Migration):

    dependencies = [
        ('tareo', '0040_alter_configuracionsistema_ia_api_key_and_more'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing, migrations.RunPython.noop),
    ]
