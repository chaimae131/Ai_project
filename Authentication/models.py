from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
import random
import string
from datetime import timedelta
from django.utils import timezone

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('candidat', 'Candidat'),
        ('company', 'Entreprise'),
        # ('admin', 'Administrateur'),
    )
    
    username = models.CharField(max_length=150, blank=True, null=True)
    email = models.EmailField(_('email address'), unique=True)
    bio = models.TextField(blank=True, null=True)
    addresse = models.CharField(max_length=255, blank=True, null=True)
    photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    links = models.URLField(max_length=200, blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = CustomUserManager()
    
    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        created = not self.pk  # Vérifie si c'est une création ou une mise à jour
        super().save(*args, **kwargs)
        
        # Crée automatiquement le profil correspondant lors de la création de l'utilisateur
        if created:
            if self.role == 'candidat':
                Candidat.objects.create(user=self)
            elif self.role == 'company':
                Company.objects.create(user=self)

class Candidat(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='candidat_profile')
    cv = models.FileField(upload_to='cv/', blank=True, null=True)
    type_de_contrat = models.CharField(max_length=100, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    experience = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Candidat: {self.user.email}"

class Company(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='company_profile')
    company_name = models.CharField(max_length=100, blank=True, null=True)
    domain_of_work = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    links = models.URLField(blank=True, null=True)
    founded_year = models.IntegerField(blank=True, null=True)
    company_size = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return f"Entreprise: {self.company_name or self.user.email}"


class Benefit(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='benefits')
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.name} - {self.company}"

class EmailVerification(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    
    @classmethod
    def generate_code(cls):
        """Génère un code de vérification à 6 chiffres"""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_valid(self):
        """Vérifie si le code est encore valide (moins de 24 heures)"""
        return timezone.now() < self.created_at + timedelta(hours=24)
    
    def __str__(self):
        return f"Vérification pour {self.user.email}"


# je l'ai ajouté 

class Skill(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class CandidateSkill(models.Model):
    LEVEL_CHOICES = (
        (1, 'Débutant'),
        (2, 'Intermédiaire'),
        (3, 'Avancé'),
        (4, 'Expert'),
    )
    
    candidate = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name='skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    level = models.IntegerField(choices=LEVEL_CHOICES, default=1)
    
    class Meta:
        unique_together = ('candidate', 'skill')
    
    def __str__(self):
        return f"{self.candidate.user.email} - {self.skill.name} ({self.get_level_display()})"

class Job(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('draft', 'Draft'),
    )

    JOB_TYPE_CHOICES = (
        ('CDI', 'CDI'),
        ('CDD', 'CDD'),
        ('stage', 'Stage'),
        ('freelance', 'Freelance'),
        ('alternance', 'Alternance'),
        ('volontariat', 'Volontariat'),
    )

    title = models.CharField(max_length=200)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='jobs')
    description = models.TextField()
    requirements = models.TextField()
    location = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    job_type = models.CharField(max_length=15, choices=JOB_TYPE_CHOICES, default='cdi')
    tags = models.ManyToManyField(Skill, related_name='jobs')

    def __str__(self):
        return f"{self.title} - {self.company.company_name}"

    

class JobApplication(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('reviewing', 'En cours d\'examen'),
        ('interview', 'Entretien'),
        ('accepted', 'Acceptée'),
        ('rejected', 'Rejetée'),
    )
    
    candidate = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name='applications')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)
    cover_letter = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    similarity_score = models.FloatField(null=True, blank=True)

    
    class Meta:
        unique_together = ('candidate', 'job')
    
    def __str__(self):
        return f"{self.candidate.user.email} - {self.job.title}"

class Interview(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Programmé'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé'),
    )
    
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='interviews')
    scheduled_at = models.DateTimeField()
    duration = models.DurationField(default=timedelta(minutes=30))
    meeting_link = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='scheduled')
    
    def __str__(self):
        return f"Entretien: {self.application.candidate.user.email} - {self.application.job.title}"

class InterviewResult(models.Model):
    interview = models.OneToOneField(Interview, on_delete=models.CASCADE, related_name='result')
    technical_score = models.IntegerField(default=0)
    communication_score = models.IntegerField(default=0)
    cultural_fit_score = models.IntegerField(default=0)
    feedback = models.TextField()
    
    @property
    def average_score(self):
        return (self.technical_score + self.communication_score + self.cultural_fit_score) / 3
    
    def __str__(self):
        return f"Résultat: {self.interview}"

class Activity(models.Model):
    TYPE_CHOICES = (
        ('application', 'Candidature'),
        ('interview', 'Entretien'),
        ('profile_update', 'Mise à jour du profil'),
        ('job_view', 'Consultation d\'offre'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.get_activity_type_display()}"