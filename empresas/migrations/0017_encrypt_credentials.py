"""
Cifra at-rest las credenciales existentes de Empresa.

Al releer cada fila, EncryptedCharField devuelve el valor en claro
(legacy sin prefijo enc$) y al guardarla lo escribe cifrado.
No se reversa: bajar implicaría reescribir secretos en claro.
"""
from django.db import migrations

CAMPOS = ['email_host_password', 'whatsapp_access_token', 'openclaw_gateway_token']


def encrypt_existing(apps, schema_editor):
    Empresa = apps.get_model('empresas', 'Empresa')
    for obj in Empresa.objects.all():
        con_valor = [f for f in CAMPOS if getattr(obj, f)]
        if con_valor:
            obj.save(update_fields=con_valor)


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0016_alter_empresa_email_host_password_and_more'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing, migrations.RunPython.noop),
    ]
