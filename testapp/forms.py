from django import forms
from django.utils import timezone
from datetime import datetime
from .models import Exam, Question, StudentAnswer

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        exclude = ['created_by', 'is_approved', 'is_active']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'topics': forms.Textarea(attrs={'rows': 3}),
            'syllabus': forms.Textarea(attrs={'rows': 4}),
            'content': forms.Textarea(attrs={'rows': 4}),
            'instructions': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        start_time = cleaned_data.get('start_time')
        if date and start_time:
            exam_dt = timezone.make_aware(datetime.combine(date, start_time))
            if exam_dt < timezone.now():
                raise forms.ValidationError("Exam cannot be in the past.")
        return cleaned_data

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        exclude = ['exam']
        widgets = {
            'question_text': forms.Textarea(attrs={'rows': 3}),
            'correct_answer': forms.Textarea(attrs={'rows': 3}),
            'explanation': forms.Textarea(attrs={'rows': 2}),
        }

class StudentAnswerForm(forms.ModelForm):
    class Meta:
        model = StudentAnswer
        fields = ['answer_text']
        widgets = {'answer_text': forms.Textarea(attrs={'rows': 4})}

class GradeAnswerForm(forms.ModelForm):
    class Meta:
        model = StudentAnswer
        fields = ['score', 'feedback']
        widgets = {'feedback': forms.Textarea(attrs={'rows': 2})}

    def clean_score(self):
        score = self.cleaned_data['score']
        if score is not None and score > self.instance.question.marks:
            raise forms.ValidationError(f"Score cannot exceed {self.instance.question.marks}.")
        return score