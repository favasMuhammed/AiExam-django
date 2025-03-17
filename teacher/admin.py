from django.contrib import admin
from .models import ExamTemplate, Exam, Question, StudentAnswer, ExamAttempt

# Inline for Questions in Exam
class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1  # Number of empty forms to display
    fields = ('question_text', 'correct_answer', 'marks', 'explanation')
    readonly_fields = ('created_at', 'updated_at')

# Inline for Student Answers in Question
class StudentAnswerInline(admin.TabularInline):
    model = StudentAnswer
    extra = 0
    fields = ('student', 'answer_text', 'score', 'feedback', 'graded_by', 'graded_at')
    readonly_fields = ('created_at', 'updated_at', 'graded_at')

@admin.register(ExamTemplate)
class ExamTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'num_questions', 'total_marks', 'difficulty_level', 'created_by', 'created_at')
    list_filter = ('difficulty_level', 'created_by', 'subject')
    search_fields = ('name', 'topics')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'subject', 'created_by')
        }),
        ('Exam Details', {
            'fields': ('topics', 'num_questions', 'total_marks', 'difficulty_level')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    inlines = [QuestionInline]
    list_display = ('title', 'subject', 'date', 'start_time', 'duration', 'difficulty_level', 'is_approved', 'created_by', 'created_at')
    list_filter = ('difficulty_level', 'is_approved', 'is_active', 'is_published', 'created_by', 'subject', 'date')
    search_fields = ('title', 'topics', 'instructions')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('title', 'subject', 'created_by', 'template')
        }),
        ('Scheduling', {
            'fields': ('date', 'start_time', 'duration')
        }),
        ('Details', {
            'fields': ('classes', 'topics', 'num_questions', 'total_marks', 'instructions', 'difficulty_level')
        }),
        ('Status', {
            'fields': ('is_approved', 'is_active', 'is_published')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    filter_horizontal = ('classes',)  # Better UI for ManyToManyField

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    inlines = [StudentAnswerInline]
    list_display = ('exam', 'question_text_short', 'marks', 'created_at')
    list_filter = ('exam', 'marks')
    search_fields = ('question_text', 'correct_answer', 'explanation')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('exam',)
        }),
        ('Question Details', {
            'fields': ('question_text', 'correct_answer', 'marks', 'explanation')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def question_text_short(self, obj):
        """Shorten question text for list display"""
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = 'Question'

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('student', 'question_short', 'score', 'graded_by', 'graded_at', 'created_at')
    list_filter = ('score', 'graded_by', 'question__exam', 'created_at')
    search_fields = ('student__email', 'answer_text', 'feedback')
    readonly_fields = ('created_at', 'updated_at', 'graded_at')
    fieldsets = (
        (None, {
            'fields': ('student', 'question')
        }),
        ('Answer Details', {
            'fields': ('answer_text', 'score', 'feedback', 'graded_by', 'graded_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def question_short(self, obj):
        """Shorten question text for list display"""
        return obj.question.question_text[:50] + '...' if len(obj.question.question_text) > 50 else obj.question.question_text
    question_short.short_description = 'Question'

@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'start_time', 'completed', 'created_at')
    list_filter = ('completed', 'exam', 'start_time')
    search_fields = ('student__email', 'exam__title')
    readonly_fields = ('created_at', 'updated_at', 'start_time')
    fieldsets = (
        (None, {
            'fields': ('student', 'exam')
        }),
        ('Attempt Details', {
            'fields': ('start_time', 'completed')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )