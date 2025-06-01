from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Interview, VideoResponse



class InterviewStartForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = []

class VideoResponseForm(forms.ModelForm):
    class Meta:
        model = VideoResponse
        fields = ['video_file']
        widgets = {
            'video_file': forms.FileInput(attrs={
                'accept': 'video/*',
                'capture': 'user',
                'class': 'form-control',
            })
        }