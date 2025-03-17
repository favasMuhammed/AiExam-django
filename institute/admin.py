from django.contrib import admin
from .models import *

class ClassInline(admin.TabularInline):
    model = Class
    readonly_fields = ['created_at', 'updated_at']
    extra = 1

class SubjectInline(admin.TabularInline):
    model = Subject
    extra = 1
    fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')

class TeacherProfileInline(admin.TabularInline):
    model = TeacherProfile
    extra = 0
    fields = ('user', 'classes', 'subjects')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('classes', 'subjects')

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    inlines = [ClassInline, SubjectInline, TeacherProfileInline]
    list_display = ('name', 'manager', 'created_at')
    list_filter = ('manager', 'created_at')
    search_fields = ('name', 'manager__email')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'manager')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'institution', 'created_at')
    list_filter = ('institution', 'created_at')
    search_fields = ('name', 'institution__name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'institution')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'institution', 'created_at')
    list_filter = ('institution', 'created_at')
    search_fields = ('name', 'institution__name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'institution', 'classes_count', 'subjects_count', 'created_at')
    list_filter = ('institution', 'created_at')
    search_fields = ('user__email', 'institution__name')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('classes', 'subjects')

    def classes_count(self, obj):
        return obj.classes.count()
    classes_count.short_description = 'Classes'

    def subjects_count(self, obj):
        return obj.subjects.count()
    subjects_count.short_description = 'Subjects'
