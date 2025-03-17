from django import forms
from .models import *
from users.models import User

class TeacherProfileForm(forms.Form):
    email = forms.EmailField()
    classes = forms.ModelMultipleChoiceField(queryset=Class.objects.none(), required=False)
    subjects = forms.ModelMultipleChoiceField(queryset=Subject.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop('institution')
        super().__init__(*args, **kwargs)
        self.fields['classes'].queryset = Class.objects.filter(institution=institution)
        self.fields['subjects'].queryset = Subject.objects.filter(institution=institution)
