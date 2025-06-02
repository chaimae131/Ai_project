from django.db import models
from django.utils import timezone
from Authentication.models import Candidat, JobApplication, Skill
from interviewapp.models import Interview
import uuid

class TechnicalTest(models.Model):
    """Un test technique associé à une offre d'emploi"""
    job_application = models.ForeignKey(
        JobApplication,
        on_delete=models.CASCADE,
        related_name='technical_tests',
        verbose_name="Candidature associée"
    )
    title = models.CharField(max_length=200, verbose_name="Titre du test")
    description = models.TextField(verbose_name="Description")
    duration_minutes = models.PositiveIntegerField(
        default=1,
        verbose_name="Durée (minutes)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Test technique"
        verbose_name_plural = "Tests techniques"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Test technique pour {self.job_application}"

class TestSession(models.Model):
    """Session de test pour un candidat"""
    STATUS_CHOICES = [
        ('P', 'En préparation'),
        ('O', 'En cours'),
        ('C', 'Terminé'),
        ('E', 'Évalué'),
    ]

    candidate = models.ForeignKey(
        Candidat,
        on_delete=models.CASCADE,
        related_name='test_sessions',
        verbose_name="Candidat"
    )
    test = models.ForeignKey(
        TechnicalTest,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name="Test technique"
    )
    interview = models.ForeignKey(
        Interview,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='technical_tests',
        verbose_name="Entretien associé"
    )
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='P',
        verbose_name="Statut"
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Débuté le")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Terminé le")
    score = models.FloatField(null=True, blank=True, verbose_name="Score")
    max_score = models.FloatField(null=True, blank=True, verbose_name="Score maximum")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Session de test"
        verbose_name_plural = "Sessions de test"
        ordering = ['-created_at']
        unique_together = ('candidate', 'test')

    @property
    def passed(self):
        if self.max_score:
            return (self.score or 0) / self.max_score >= 0.5
        return False
    def __str__(self):
        return f"Session #{self.id} - {self.candidate.user.email}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('technical_test:session_detail', kwargs={'unique_id': self.unique_id})

class TestQuestion(models.Model):
    """Questions pour un test technique"""
    TYPE_CHOICES = [
        ('QCM', 'Question à choix multiple'),
        ('OPEN', 'Question ouverte'),
    ]

    test = models.ForeignKey(
        TechnicalTest,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name="Test technique"
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        verbose_name="Compétence évaluée"
    )
    question_type = models.CharField(
        max_length=4,
        choices=TYPE_CHOICES,
        verbose_name="Type de question"
    )
    text = models.TextField(verbose_name="Texte de la question")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    # Pour les questions QCM
    option_a = models.TextField(blank=True, null=True, verbose_name="Option A")
    option_b = models.TextField(blank=True, null=True, verbose_name="Option B")
    option_c = models.TextField(blank=True, null=True, verbose_name="Option C")
    option_d = models.TextField(blank=True, null=True, verbose_name="Option D")
    correct_answer = models.CharField(

        max_length=1,
        blank=True,
        null=True,
        choices=[('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D')],
        verbose_name="Réponse correcte"
    )

    # Pour les questions ouvertes
    model_answer = models.TextField(
        blank=True,
        null=True,
        verbose_name="Réponse modèle"
    )
    keywords = models.TextField(
        blank=True,
        null=True,
        help_text="Mots-clés importants séparés par des virgules",
        verbose_name="Mots-clés"
    )

    class Meta:
        verbose_name = "Question de test"
        verbose_name_plural = "Questions de test"
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.text[:50]}..."

class TestResponse(models.Model):
    """Réponses d'un candidat à un test"""
    session = models.ForeignKey(
        TestSession,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name="Session"
    )
    question = models.ForeignKey(
        TestQuestion,
        on_delete=models.CASCADE,
        verbose_name="Question"
    )
    answer_text = models.TextField(
        blank=True,
        null=True,
        verbose_name="Réponse texte"
    )
    answer_choice = models.CharField(
        max_length=1,
        blank=True,
        null=True,
        choices=[('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D')],
        verbose_name="Réponse choix"
    )
    similarity_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Score de similarité"
    )
    points_earned = models.FloatField(
        default=0,
        verbose_name="Points obtenus"
    )
    feedback = models.TextField(
        blank=True,
        null=True,
        verbose_name="Feedback"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réponse au test"
        verbose_name_plural = "Réponses aux tests"
        unique_together = ('session', 'question')

    def __str__(self):
        return f"Réponse à Q{self.question.order} - {self.session}"

class TestReport(models.Model):
    """Rapport d'évaluation d'un test technique"""
    session = models.OneToOneField(
        TestSession,
        on_delete=models.CASCADE,
        related_name='report',
        verbose_name="Session"
    )
    overall_score = models.FloatField(verbose_name="Score global")
    skills_evaluation = models.JSONField(
        verbose_name="Évaluation par compétence"
    )
    #strengths = models.TextField(verbose_name="Points forts")
    #weaknesses = models.TextField(verbose_name="Points faibles")
    #recommendations = models.TextField(verbose_name="Recommandations")
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rapport de test"
        verbose_name_plural = "Rapports de test"
        ordering = ['-generated_at']

    def __str__(self):
        return f"Rapport pour {self.session}"