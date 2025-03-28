from django import forms
from .models import *
from users.models import *
from institute.models import *
from teacher.models import *

from django import forms
from .models import Exam, StudentAnswer, ExamTemplate
from institute.models import Subject, Class, TeacherProfile, Institution

from django.utils import timezone
from datetime import datetime


from django.utils import timezone

# teacher/forms.py
from django import forms
from django.utils import timezone
from datetime import datetime


class ExamForm(forms.ModelForm):
    use_template = forms.BooleanField(
        required=False,
        label="Use Template",
        help_text="Check this to apply an existing exam template."
    )
    template = forms.ModelChoiceField(
        queryset=ExamTemplate.objects.none(),
        required=False,
        empty_label="Select a template (optional)",
        help_text="Choose a template to pre-fill exam details."
    )

    DIFFICULTY_LEVELS = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    class Meta:
        model = Exam
        fields = [
            'title', 'subject', 'classes', 'date', 'start_time', 'duration',
            'topics', 'num_questions', 'total_marks', 'instructions',
            'difficulty_level', 'is_active', 'is_published', 'template'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
                'placeholder': 'Enter exam title (e.g., Midterm Exam 2025)',
            }),
            'subject': forms.Select(attrs={
                'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm appearance-none bg-white',
            }),
            'classes': forms.SelectMultiple(attrs={
                'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm appearance-none bg-white',
            }),
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'mt-1 block w-full pl-10 pr-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            }),
            'start_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'mt-1 block w-full pl-10 pr-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            }),
            'duration': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full pl-10 pr-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
                'min': 1,
                'placeholder': 'Enter duration in minutes',
            }),
            'topics': forms.Textarea(attrs={
                'rows': 3,
                'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm resize-y',
                'placeholder': 'Enter topics covered (e.g., Algebra, Geometry)',
            }),
            'instructions': forms.Textarea(attrs={
                'rows': 3,
                'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm resize-y',
                'placeholder': 'Enter instructions for students (e.g., Bring a calculator)',
            }),
            'num_questions': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
                'min': 1,
            }),
            'total_marks': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
                'min': 1,
            }),
            'difficulty_level': forms.Select(attrs={
                'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm appearance-none bg-white',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
            }),
            'is_published': forms.CheckboxInput(attrs={
                'class': 'mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
            }),
            'template': forms.Select(attrs={
                'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm appearance-none bg-white',
            }),
        }
        labels = {
            'title': 'Exam Title',
            'subject': 'Subject',
            'classes': 'Classes',
            'date': 'Exam Date',
            'start_time': 'Start Time',
            'duration': 'Duration (minutes)',
            'topics': 'Topics Covered',
            'num_questions': 'Number of Questions',
            'total_marks': 'Total Marks',
            'instructions': 'Instructions',
            'difficulty_level': 'Difficulty Level',
            'is_active': 'Is Active',
            'is_published': 'Is Published',
        }
        help_texts = {
            'title': 'Enter a descriptive title for the exam.',
            'subject': 'Select the subject for this exam.',
            'classes': 'Select the classes that will take this exam.',
            'date': 'Choose the date of the exam (must be today or in the future).',
            'start_time': 'Set the start time for the exam.',
            'duration': 'Enter the duration of the exam in minutes (e.g., 60 for 1 hour).',
            'topics': 'List the topics covered in the exam.',
            'num_questions': 'Enter the total number of questions.',
            'total_marks': 'Enter the total marks for the exam. Must be greater than or equal to the sum of question marks.',
            'instructions': 'Provide any special instructions for students.',
            'difficulty_level': 'Select the difficulty level of the exam.',
            'is_active': 'Check to make the exam active.',
            'is_published': 'Check to publish the exam to students.',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['difficulty_level'].choices = self.DIFFICULTY_LEVELS

        if user and user.is_teacher:
            teacher_profiles = user.teacher_profiles.all()
            if teacher_profiles.exists():
                teacher_profile = teacher_profiles.first()
                institution = teacher_profile.institution
                self.fields['subject'].queryset = teacher_profile.subjects.all()
                self.fields['classes'].queryset = teacher_profile.classes.all()
            else:
                institution = Institution.objects.filter(manager__is_manager=True).first()
                if institution:
                    teacher_profile = TeacherProfile.objects.create(user=user, institution=institution)
                    self.fields['subject'].queryset = teacher_profile.subjects.all()
                    self.fields['classes'].queryset = teacher_profile.classes.all()
                else:
                    self.fields['subject'].queryset = Subject.objects.none()
                    self.fields['classes'].queryset = Class.objects.none()
        else:
            self.fields['subject'].queryset = Subject.objects.none()
            self.fields['classes'].queryset = Class.objects.none()

        self.fields['template'].queryset = ExamTemplate.objects.filter(created_by=user)

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        start_time = cleaned_data.get('start_time')

        if date and start_time:
            try:
                exam_datetime = timezone.make_aware(
                    datetime.combine(date, start_time)
                )
                if exam_datetime <= timezone.now():
                    raise forms.ValidationError(
                        "The exam date and time must be in the future."
                    )
            except ValueError as e:
                raise forms.ValidationError(f"Invalid date or time: {str(e)}")

        num_questions = cleaned_data.get('num_questions')
        total_marks = cleaned_data.get('total_marks')
        if num_questions is not None and num_questions <= 0:
            self.add_error('num_questions', "Number of questions must be greater than 0.")
        if total_marks is not None and total_marks <= 0:
            self.add_error('total_marks', "Total marks must be greater than 0.")

        return cleaned_data

    def clean_duration(self):
        duration = self.cleaned_data.get('duration')
        if duration is not None:
            try:
                duration = int(duration)
                if duration <= 0:
                    raise forms.ValidationError("Duration must be a positive number of minutes.")
            except (ValueError, TypeError):
                raise forms.ValidationError("Duration must be a valid number of minutes.")
        return duration
        

class GradeAnswerForm(forms.ModelForm):
    class Meta:
        model = StudentAnswer
        fields = ['score', 'feedback']
        widgets = {
            'score': forms.NumberInput(attrs={'class': 'w-20 p-2 border border-gray-300 rounded-md'}),
            'feedback': forms.Textarea(attrs={'rows': 2, 'class': 'w-full p-2 border border-gray-300 rounded-md'}),
        }


class ClassStudentForm(forms.Form):
    class_obj = forms.ModelChoiceField(queryset=Class.objects.none(), label="Class")
    students = forms.ModelMultipleChoiceField(queryset=User.objects.filter(is_student=True), label="Students")

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            teacher_profile = getattr(user, 'teacher_profile', None)
            if not teacher_profile:
                # Fallback if no profile exists
                institution = Institution.objects.filter(manager__is_manager=True).first()
                if institution:
                    teacher_profile, created = TeacherProfile.objects.get_or_create(
                        user=user,
                        defaults={'institution': institution}
                    )
                else:
                    # Handle no institution case (optional)
                    self.fields['class_obj'].queryset = Class.objects.none()
                    self.fields['students'].queryset = User.objects.none()
                    return
                
            institution = teacher_profile.institution
            self.fields['class_obj'].queryset = teacher_profile.classes.all()
            self.fields['students'].queryset = User.objects.filter(is_student=True)