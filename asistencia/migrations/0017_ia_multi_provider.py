"""
Fase 4.4 — Migración IA Multi-Provider.

Cambios:
  - IA_PROVIDER_CHOICES expandido: GEMINI | DEEPSEEK | OPENAI | OLLAMA | NINGUNO
  - Nuevo campo ia_api_key (API key cloud providers)
  - Nuevo campo ia_ocr_provider (GEMINI | NINGUNO)
  - ia_modelo default cambia a 'gemini-2.0-flash' (mantiene valor existente si ya tiene uno)
  - ia_endpoint: ampliado max_length a 300 (URL DeepSeek/OpenAI más largas)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tareo', '0016_add_mod_roster_config'),
    ]

    operations = [
        # Ampliar ia_provider choices (max_length ya es 20, suficiente para DEEPSEEK)
        migrations.AlterField(
            model_name='configuracionsistema',
            name='ia_provider',
            field=models.CharField(
                choices=[
                    ('GEMINI',   'Gemini (Google — recomendado)'),
                    ('DEEPSEEK', 'DeepSeek (más económico)'),
                    ('OPENAI',   'OpenAI (GPT-4o-mini)'),
                    ('OLLAMA',   'Ollama (Local — sin costo)'),
                    ('NINGUNO',  'Sin IA'),
                ],
                default='NINGUNO',
                max_length=20,
                verbose_name='Proveedor de IA (Chat/RAG)',
                help_text='Proveedor para chat, análisis y mapeo de columnas',
            ),
        ),

        # Ampliar ia_endpoint para URLs cloud
        migrations.AlterField(
            model_name='configuracionsistema',
            name='ia_endpoint',
            field=models.CharField(
                blank=True,
                default='http://localhost:11434',
                max_length=300,
                verbose_name='Endpoint (Ollama / DeepSeek custom)',
                help_text='URL del servidor. Ollama: http://localhost:11434 | DeepSeek: https://api.deepseek.com/v1',
            ),
        ),

        # Actualizar ia_modelo default
        migrations.AlterField(
            model_name='configuracionsistema',
            name='ia_modelo',
            field=models.CharField(
                blank=True,
                default='gemini-2.0-flash',
                max_length=100,
                verbose_name='Modelo',
                help_text='Gemini: gemini-2.0-flash | DeepSeek: deepseek-chat | OpenAI: gpt-4o-mini | Ollama: llama3.2',
            ),
        ),

        # Nuevo campo: ia_api_key
        migrations.AddField(
            model_name='configuracionsistema',
            name='ia_api_key',
            field=models.CharField(
                blank=True,
                default='',
                max_length=500,
                verbose_name='API Key del proveedor',
                help_text='Clave API de Gemini, DeepSeek u OpenAI. No aplica para Ollama.',
            ),
        ),

        # Nuevo campo: ia_ocr_provider
        migrations.AddField(
            model_name='configuracionsistema',
            name='ia_ocr_provider',
            field=models.CharField(
                choices=[
                    ('GEMINI',  'Gemini 2.5 Flash (PDF nativos)'),
                    ('NINGUNO', 'Sin OCR IA'),
                ],
                default='NINGUNO',
                max_length=20,
                verbose_name='Proveedor OCR (PDFs escaneados)',
                help_text='Gemini Files API para OCR de PDFs escaneados. Requiere ia_api_key de Gemini.',
            ),
        ),
    ]
