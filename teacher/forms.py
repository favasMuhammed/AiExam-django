from django import forms
from .models import *
from users.models import *
from institute.models import *
from teacher.models import *

from django import forms
from .models import Exam, StudentAnswer, ExamTemplate
from institute.models import Subject, Class, TeacherProfile

class ExamForm(forms.ModelForm):
    use_template = forms.BooleanField(required=False, label="Use Template")
    template = forms.ModelChoiceField(queryset=ExamTemplate.objects.none(), required=False)

    class Meta:
        model = Exam
        fields = ['title', 'subject', 'classes', 'date', 'start_time', 'duration', 'topics', 'num_questions', 'total_marks', 'instructions', 'difficulty_level', 'is_active', 'is_published', 'template']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}),
            'topics': forms.Textarea(attrs={'rows': 3, 'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}),
            'instructions': forms.Textarea(attrs={'rows': 3, 'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.is_teacher:
            teacher_profiles = user.teacher_profiles.all()
            if teacher_profiles.exists():
                # Use the first TeacherProfile (adjust if multiple profiles are intended)
                teacher_profile = teacher_profiles.first()
                institution = teacher_profile.institution
                # Adjust Subject filter based on actual relationship (assuming ManyToMany in TeacherProfile)
                self.fields['subject'].queryset = Subject.objects.filter(institution=institution)
                self.fields['classes'].queryset = Class.objects.filter(institution=institution)
            else:
                # Create a TeacherProfile if none exists
                from institute.models import Institution
                institution = Institution.objects.filter(manager__is_manager=True).first()
                if institution:
                    teacher_profile = TeacherProfile.objects.create(user=user, institution=institution)
                    self.fields['subject'].queryset = Subject.objects.filter(institution=institution)
                    self.fields['classes'].queryset = Class.objects.filter(institution=institution)
                else:
                    self.fields['subject'].queryset = Subject.objects.none()
                    self.fields['classes'].queryset = Class.objects.none()
        else:
            self.fields['subject'].queryset = Subject.objects.none()
            self.fields['classes'].queryset = Class.objects.none()

        self.fields['template'].queryset = ExamTemplate.objects.filter(created_by=user)

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
            self.fields['class_obj'].queryset = Class.objects.filter(institution=institution)
            self.fields['students'].queryset = User.objects.filter(is_student=True)