# Generated by Django 5.2.1 on 2025-05-30 10:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interviewapp', '0002_interview_result'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='expected_answer',
            field=models.TextField(blank=True, null=True, verbose_name='Réponse attendue'),
        ),
    ]
