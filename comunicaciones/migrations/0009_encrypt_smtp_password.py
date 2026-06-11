"""
Cifra at-rest la contraseña SMTP existente de ConfiguracionSMTP (singleton).

Al releer la fila, EncryptedCharField devuelve el valor en claro
(legacy sin prefijo enc$) y al guardarla lo escribe cifrado.
No se reversa: bajar implicaría reescribir secretos en claro.
"""
from django.db import migrations


def encrypt_existing(apps, schema_editor):
    ConfiguracionSMTP = apps.get_model('comunicaciones', 'ConfiguracionSMTP')
    for obj in ConfiguracionSMTP.objects.all():
        if obj.smtp_password:
            obj.save(update_fields=['smtp_password'])


class Migration(migrations.Migration):

    dependencies = [
        ('comunicaciones', '0008_alter_configuracionsmtp_smtp_password'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing, migrations.RunPython.noop),
    ]
