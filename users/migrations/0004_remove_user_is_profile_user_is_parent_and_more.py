# Generated by Django 5.0.7 on 2025-01-10 03:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_user_is_profile'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='is_profile',
        ),
        migrations.AddField(
            model_name='user',
            name='is_parent',
            field=models.BooleanField(default=False, verbose_name='Is parent'),
        ),
        migrations.AddField(
            model_name='user',
            name='is_student',
            field=models.BooleanField(default=False, verbose_name='Is student'),
        ),
        migrations.AddField(
            model_name='user',
            name='is_teacher',
            field=models.BooleanField(default=False, verbose_name='Is teacher'),
        ),
        migrations.AddField(
            model_name='user',
            name='phone',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
    ]
