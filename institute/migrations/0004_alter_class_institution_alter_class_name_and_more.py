# Generated by Django 5.1.6 on 2025-03-10 21:41

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('institute', '0003_class_teachers_studentprofile'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='class',
            name='institution',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='institute.institution'),
        ),
        migrations.AlterField(
            model_name='class',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='class',
            name='teachers',
            field=models.ManyToManyField(blank=True, related_name='class_set', to=settings.AUTH_USER_MODEL),
        ),
    ]
