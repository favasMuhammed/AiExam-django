# Generated by Django 5.1.6 on 2025-03-25 09:05

import django.core.validators
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('institute', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('start_time', models.DateTimeField(default=django.utils.timezone.now)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('session_data', models.JSONField(default=dict, help_text='Stores randomized question order or other session-specific data')),
                ('attempt_uuid', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique identifier for this attempt', unique=True)),
                ('time_taken', models.DurationField(blank=True, help_text='Time taken to complete the exam', null=True)),
            ],
            options={
                'verbose_name': 'Exam Attempt',
                'verbose_name_plural': 'Exam Attempts',
            },
        ),
        migrations.CreateModel(
            name='ExamTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200, unique=True)),
                ('topics', models.TextField(help_text='Comma-separated list of topics covered')),
                ('num_questions', models.IntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('total_marks', models.IntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('difficulty_level', models.CharField(choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], default='medium', max_length=10)),
                ('is_shared', models.BooleanField(default=False, help_text='Allow other teachers to use this template')),
            ],
            options={
                'verbose_name': 'Exam Template',
                'verbose_name_plural': 'Exam Templates',
            },
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('question_text', models.TextField(help_text='The content of the question.')),
                ('correct_answer', models.TextField(help_text='The expected correct answer for the question.')),
                ('marks', models.IntegerField(help_text='The number of marks allocated to this question.', validators=[django.core.validators.MinValueValidator(1)])),
                ('explanation', models.TextField(blank=True, help_text='Optional explanation or hint for the question.')),
                ('order', models.PositiveIntegerField(db_index=True, default=1, help_text='The sequence number of the question in the exam.')),
                ('question_type', models.CharField(choices=[('essay', 'Essay'), ('mcq', 'Multiple Choice'), ('short_answer', 'Short Answer')], default='essay', help_text='The type of question (e.g., Essay, Multiple Choice, Short Answer).', max_length=20)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this question is currently active in the exam.')),
            ],
            options={
                'verbose_name': 'Question',
                'verbose_name_plural': 'Questions',
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='StudentAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('answer_text', models.TextField(default='No answer provided', help_text="The student's response to the question.")),
                ('score', models.FloatField(blank=True, help_text='Teacher-assigned score', null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('graded_at', models.DateTimeField(blank=True, null=True)),
                ('feedback', models.TextField(blank=True, help_text='Teacher feedback on the answer')),
                ('ai_score', models.FloatField(blank=True, help_text='AI-assigned score', null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('ai_feedback', models.TextField(blank=True, help_text='AI-generated feedback')),
                ('ai_graded_at', models.DateTimeField(blank=True, null=True)),
                ('submitted_at', models.DateTimeField(default=django.utils.timezone.now, help_text='Time the answer was submitted')),
            ],
            options={
                'verbose_name': 'Student Answer',
                'verbose_name_plural': 'Student Answers',
            },
        ),
        migrations.CreateModel(
            name='Exam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=200, unique=True)),
                ('date', models.DateField()),
                ('start_time', models.TimeField()),
                ('duration', models.IntegerField(help_text='Duration in minutes', validators=[django.core.validators.MinValueValidator(1)])),
                ('topics', models.TextField(help_text='Comma-separated list of topics')),
                ('num_questions', models.IntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('total_marks', models.IntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('instructions', models.TextField(blank=True)),
                ('difficulty_level', models.CharField(choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], default='medium', max_length=10)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending Approval'), ('approved', 'Approved'), ('completed', 'Completed')], default='draft', help_text='Current status of the exam', max_length=10)),
                ('is_approved', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('is_published', models.BooleanField(default=False)),
                ('randomize_questions', models.BooleanField(default=False, help_text='Randomize question order for each student')),
                ('classes', models.ManyToManyField(related_name='exams', to='institute.class')),
            ],
            options={
                'verbose_name': 'Exam',
                'verbose_name_plural': 'Exams',
            },
        ),
    ]
