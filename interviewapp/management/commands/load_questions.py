from django.core.management.base import BaseCommand
from interviewapp.models import QuestionCategory, Question

SAMPLE_QUESTIONS = {
    "Présentation": [
        {
            "question": "Pouvez-vous vous présenter brièvement ?",
            "expected_answer": "Je m'appelle [Nom], j'ai [X] ans d'expérience dans [domaine]. J'ai travaillé sur [projets pertinents] et mes compétences principales sont [compétences]. Je suis passionné(e) par [centre d'intérêt professionnel].",
            "difficulty": "F"
        },
        
    ],
    "Compétences": [
        
        {
            "question": "Comment gérez-vous les situations stressantes ?",
            "expected_answer": "Je gère le stress en [stratégie 1 comme prioriser les tâches], [stratégie 2 comme faire des pauses]. Un exemple concret est [situation stressante] où j'ai réussi à [résultat positif] en appliquant cette méthode. J'utilise aussi [outil/méthode] pour maintenir mon calme.",
            "difficulty": "M"
        },
        
    ],
    "Motivation": [
        {
            "question": "Pourquoi avez-vous postulé à ce poste ?",
            "expected_answer": "J'ai postulé car ce poste correspond parfaitement à [aspect 1 de votre expérience], [aspect 2 de vos compétences] et [aspect 3 de vos aspirations]. L'entreprise m'attire particulièrement pour [raisons spécifiques]. Je suis convaincu(e) que je peux apporter [valeur ajoutée] tout en développant [compétences futures].",
            "difficulty": "F"
        },
        
       
    ],
    "Comportement": [
         {
            "question": "Où vous voyez-vous dans 5 ans ?",
            "expected_answer": "Dans 5 ans, j'aspire à [position/role] où je pourrai [responsabilités]. Je souhaite avoir maîtrisé [compétences avancées] et contribué à [types de projets]. Mon objectif est d'évoluer vers [direction] tout en continuant à [valeurs professionnelles]. Cette trajectoire s'aligne avec [vision de l'entreprise] car [lien explicite].",
            "difficulty": "D"
        },
    ]
}

class Command(BaseCommand):
    help = 'Load sample questions with expected answers into the database'

    def handle(self, *args, **options):
        # Create categories and questions
        for category_name, questions_data in SAMPLE_QUESTIONS.items():
            category, created = QuestionCategory.objects.get_or_create(name=category_name)
            
            for question_info in questions_data:
                Question.objects.get_or_create(
                    text=question_info["question"],
                    category=category,
                    difficulty=question_info["difficulty"],
                    defaults={
                        'is_active': True,
                        'expected_answer': question_info["expected_answer"]
                    }
                )
        
        self.stdout.write(self.style.SUCCESS('Successfully loaded sample questions with expected answers'))