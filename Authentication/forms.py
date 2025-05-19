from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import Candidat, Company, JobApplication, CandidateSkill, Job, Interview, InterviewResult, Benefit
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class CandidatRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=255, required=True, label='Nom complet')
    
    class Meta:
        model = User
        fields = ('email', 'phone_number', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'candidat'
        user.phone_number = self.cleaned_data.get('phone_number')
        if commit:
            user.save()
            candidat_profile, created = Candidat.objects.get_or_create(user=user)
            candidat_profile.full_name = self.cleaned_data.get('full_name')
            candidat_profile.save()
            
        return user


class CompanyRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')
    phone_number = forms.CharField(max_length=15, required=True, label='Téléphone')
    company_name = forms.CharField(max_length=100, required=True, label='Nom de l\'entreprise')
    domain_of_work = forms.CharField(max_length=100, required=True, label='Domaine d\'activité')
    
    class Meta:
        model = User
        fields = ('email', 'phone_number', 'company_name', 'domain_of_work', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'company'
        user.phone_number = self.cleaned_data.get('phone_number')
        
        if commit:
            user.save()
            company_profile = Company.objects.get_or_create(user=user)[0]
            company_profile.company_name = self.cleaned_data.get('company_name')
            company_profile.domain_of_work = self.cleaned_data.get('domain_of_work')
            company_profile.save()
            
        return user


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'autofocus': True}))

class CandidatProfileForm(forms.ModelForm):
    bio = forms.CharField(widget=forms.Textarea, required=False)
    addresse = forms.CharField(max_length=255, required=False)
    photo = forms.ImageField(required=False)
    links = forms.URLField(required=False)
    
    class Meta:
        model = Candidat
        fields = ('full_name', 'cv', 'type_de_contrat', 'experience')
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['bio'].initial = user.bio
            self.fields['addresse'].initial = user.addresse
            self.fields['links'].initial = user.links
    
    def save(self, user=None, commit=True):
        profile = super().save(commit=False)
        
        if user:
            user.bio = self.cleaned_data.get('bio', '')
            user.addresse = self.cleaned_data.get('addresse', '')
            user.links = self.cleaned_data.get('links', '')
            
            if self.cleaned_data.get('photo'):
                user.photo = self.cleaned_data.get('photo')
            
            user.save()
        
        if commit:
            profile.save()
        
        return profile


class CompanyProfileForm(forms.ModelForm):
    photo = forms.ImageField(required=False)
    
    class Meta:
        model = Company
        fields = [
            'company_name', 
            'domain_of_work',
            'bio',
            'address',
            'links',
            'founded_year',
            'company_size'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
          
    def save(self, commit=True):
        profile = super().save(commit=False)
      
        # Sauvegarder le numéro de téléphone dans l'utilisateur
        if hasattr(profile, 'user'):
            profile.user.phone_number = self.cleaned_data.get('phone_number', '')
            profile.user.save()
        
        if commit:
            profile.save()

            # Gérer les avantages (benefits)
            benefits_data = self.cleaned_data.get('benefits', '')
            if benefits_data:
                try:
                    # Supprimer les avantages existants
                    Benefit.objects.filter(company=profile).delete()
                    
                    # Ajouter les nouveaux avantages
                    benefits_list = json.loads(benefits_data)
                    for benefit_item in benefits_list:
                        Benefit.objects.create(
                            company=profile,
                            name=benefit_item.get('name', '')
                        )
                except json.JSONDecodeError:
                    pass  # Ignorer si le format JSON est invalide
        
        return profile

class JobApplicationForm(forms.ModelForm):
    cover_letter = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        required=True,
        label='Lettre de motivation'
    ),
    resume = forms.FileField(
        required=True,
        label='CV'
    )
    
    class Meta:
        model = JobApplication
        fields = ['cover_letter', 'resume']


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'description', 'requirements', 'location', 'status', 'job_type']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'requirements': forms.Textarea(attrs={'rows': 5}),
        }


class InterviewScheduleForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ['scheduled_at', 'duration', 'meeting_link', 'notes']
        widgets = {
            'scheduled_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date to tomorrow
        tomorrow = timezone.now() + timedelta(days=1)
        tomorrow = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        self.fields['scheduled_at'].initial = tomorrow
        # Set default duration to 30 minutes
        self.fields['duration'].initial = timedelta(minutes=30)

class InterviewResultForm(forms.ModelForm):
    class Meta:
        model = InterviewResult
        fields = ['technical_score', 'communication_score', 'cultural_fit_score', 'feedback']
        widgets = {
            'feedback': forms.Textarea(attrs={'rows': 4}),
        }


class SkillForm(forms.Form):
    skill_name = forms.CharField(max_length=100, required=True, label='Compétence')
    skill_level = forms.ChoiceField(
        choices=CandidateSkill.LEVEL_CHOICES,
        required=True,
        label='Niveau'
    )