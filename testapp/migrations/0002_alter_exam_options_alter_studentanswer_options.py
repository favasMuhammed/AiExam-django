# Generated by Django 5.1.6 on 2025-02-22 20:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('testapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='exam',
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterModelOptions(
            name='studentanswer',
            options={'ordering': ['submitted_at']},
        ),
    ]
