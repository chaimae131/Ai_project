from django.db import models
#from django.contrib.auth.models import User
from Authentication.models import Candidat , JobApplication
from django.utils import timezone
import uuid

class QuestionCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="Catégorie")
    description = models.TextField(blank=True, verbose_name="Description")
    
    class Meta:
        verbose_name = "Catégorie de question"
        verbose_name_plural = "Catégories de questions"
    
    def __str__(self):
        return self.name

class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('F', 'Facile'),
        ('M', 'Moyen'),
        ('D', 'Difficile'),
    ]
    
    text = models.TextField(verbose_name="Texte de la question")
    expected_answer = models.TextField(verbose_name="Réponse attendue", blank=True, null=True) 
    category = models.ForeignKey(QuestionCategory, on_delete=models.CASCADE, verbose_name="Catégorie")
    difficulty = models.CharField(max_length=1, choices=DIFFICULTY_CHOICES, verbose_name="Difficulté")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        ordering = ['category', 'difficulty']
    
    def __str__(self):
        return f"{self.text[:50]}... ({self.get_difficulty_display()})"

class Interview(models.Model):
    STATUS_CHOICES = [
        ('P', 'En préparation'),
        ('O', 'En cours'),
        ('C', 'Terminé'),
        ('A', 'Analyse en cours'),
        ('D', 'Analyse terminée'),
    ]
    RESULT_CHOICES = [
        ('P', 'Réussi'),
        ('F', 'Échoué'),
        ('N', 'Non évalué'),
    ]
    job_application = models.ForeignKey(JobApplication,  
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interviews',
        verbose_name="Candidature associée"
    )
    candidate = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name='interviews', verbose_name="Candidat")
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='P', verbose_name="Statut")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Date de création")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de complétion")
    result = models.CharField(max_length=1, choices=RESULT_CHOICES, default='N', verbose_name="Résultat")

    class Meta:
        verbose_name = "Entretien"
        verbose_name_plural = "Entretiens"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Entretien #{self.id} - {self.candidate.full_name}"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('interview_detail', kwargs={'unique_id': self.unique_id})

class InterviewQuestion(models.Model):
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"Q{self.order}: {self.question.text[:50]}..."

class VideoResponse(models.Model):
    interview_question = models.OneToOneField(InterviewQuestion, on_delete=models.CASCADE, related_name='video_response')
    video_file = models.FileField(upload_to='interview_videos/', verbose_name="Fichier vidéo")
    duration = models.FloatField(null=True, blank=True, verbose_name="Durée (secondes)")
    analysis_result = models.JSONField(null=True, blank=True, verbose_name="Résultat d'analyse")
    analysis_completed = models.BooleanField(default=False, verbose_name="Analyse terminée")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Réponse vidéo"
        verbose_name_plural = "Réponses vidéos"
        ordering = ['interview_question__order']
    
    def __str__(self):
        return f"Réponse à Q{self.interview_question.order} - {self.interview_question.interview}"

class InterviewAnalysis(models.Model):
    interview = models.OneToOneField(Interview, on_delete=models.CASCADE, related_name='analysis')
    overall_report = models.FileField(upload_to='interview_reports/', null=True, blank=True)
    summary = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Analyse d'entretien"
        verbose_name_plural = "Analyses d'entretiens"
    
    def __str__(self):
        return f"Analyse pour {self.interview}"