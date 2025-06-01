from django.core.management.base import BaseCommand
from interviewapp.models import QuestionCategory, Question

SAMPLE_QUESTIONS = {
    "Présentation": [
        {
            "question": "Pouvez-vous vous présenter brièvement ?",
            "expected_answer": "Je m'appelle [Nom], j'ai [X] ans d'expérience dans [domaine]. J'ai travaillé sur [projets pertinents] et mes compétences principales sont [compétences]. Je suis passionné(e) par [centre d'intérêt professionnel].",
            "difficulty": "F"
        },
        {
            "question": "Parlez-moi de votre parcours professionnel.",
            "expected_answer": "J'ai commencé ma carrière en tant que [premier poste] où j'ai acquis [compétences]. Par la suite, j'ai évolué vers [postes suivants] avec des responsabilités croissantes. Mon expérience la plus significative était [détail important] qui m'a permis de développer [compétences clés].",
            "difficulty": "M"
        },
        {
            "question": "Qu'est-ce qui vous motive dans votre travail ?",
            "expected_answer": "Je suis motivé(e) par [facteurs de motivation comme les défis, l'apprentissage, l'impact]. J'apprécie particulièrement [aspect spécifique du travail]. Un exemple concret est [situation où vous étiez motivé(e)] car cela m'a permis de [résultat obtenu].",
            "difficulty": "D"
        },
    ],
    "Compétences": [
        {
            "question": "Quelles sont vos principales compétences ?",
            "expected_answer": "Mes compétences principales incluent [compétence 1] que j'ai développée grâce à [expérience], [compétence 2] démontrée lors de [projet], et [compétence 3] qui m'a permis de [réalisation]. Je maîtrise également [outils/technologies pertinents].",
            "difficulty": "F"
        },
        {
            "question": "Comment gérez-vous les situations stressantes ?",
            "expected_answer": "Je gère le stress en [stratégie 1 comme prioriser les tâches], [stratégie 2 comme faire des pauses]. Un exemple concret est [situation stressante] où j'ai réussi à [résultat positif] en appliquant cette méthode. J'utilise aussi [outil/méthode] pour maintenir mon calme.",
            "difficulty": "M"
        },
        {
            "question": "Pouvez-vous donner un exemple de problème complexe que vous avez résolu ?",
            "expected_answer": "Lors de [projet/contexte], j'ai fait face à [problème complexe]. Après analyse, j'ai identifié [causes]. J'ai alors [actions entreprises] en utilisant [méthodes/outils]. Le résultat fut [résultat quantifiable] avec [impact positif]. J'ai appris [leçon importante].",
            "difficulty": "D"
        },
    ],
    "Motivation": [
        {
            "question": "Pourquoi avez-vous postulé à ce poste ?",
            "expected_answer": "J'ai postulé car ce poste correspond parfaitement à [aspect 1 de votre expérience], [aspect 2 de vos compétences] et [aspect 3 de vos aspirations]. L'entreprise m'attire particulièrement pour [raisons spécifiques]. Je suis convaincu(e) que je peux apporter [valeur ajoutée] tout en développant [compétences futures].",
            "difficulty": "F"
        },
        {
            "question": "Qu'attendez-vous de cette opportunité ?",
            "expected_answer": "J'espère approfondir mes connaissances en [domaine], contribuer à [objectifs de l'entreprise] et évoluer vers [aspiration professionnelle]. Je souhaite particulièrement [attente spécifique comme travailler sur des projets innovants] tout en développant [compétences cibles]. Cette opportunité correspond à mon plan de carrière car [lien avec vos objectifs].",
            "difficulty": "M"
        },
        {
            "question": "Où vous voyez-vous dans 5 ans ?",
            "expected_answer": "Dans 5 ans, j'aspire à [position/role] où je pourrai [responsabilités]. Je souhaite avoir maîtrisé [compétences avancées] et contribué à [types de projets]. Mon objectif est d'évoluer vers [direction] tout en continuant à [valeurs professionnelles]. Cette trajectoire s'aligne avec [vision de l'entreprise] car [lien explicite].",
            "difficulty": "D"
        },
    ],
    "Comportement": [
        {
            "question": "Décrivez une situation où vous avez dû travailler en équipe.",
            "expected_answer": "Lors de [projet], notre équipe devait [objectif]. J'ai joué le rôle de [votre rôle] en collaborant avec [collègues]. Nous avons rencontré [défi] que nous avons surmonté en [solution]. Le résultat fut [résultat] et j'ai appris [leçon] sur l'importance de [aspect de travail d'équipe].",
            "difficulty": "F"
        },
        {
            "question": "Comment gérez-vous les désaccords avec un collègue ?",
            "expected_answer": "Face à un désaccord, j'écoute activement le point de vue de l'autre, puis j'expose le mien avec des faits concrets comme [exemple]. Je cherche un compromis basé sur [critères objectifs]. Par exemple, lorsque [situation], nous avons trouvé une solution en [méthode]. Je privilégie toujours [approche constructive] pour préserver [relation professionnelle].",
            "difficulty": "M"
        },
        {
            "question": "Donnez un exemple où vous avez dû prendre une décision difficile.",
            "expected_answer": "Dans [contexte], j'ai dû prendre la décision de [décision difficile] après avoir analysé [facteurs]. J'ai consulté [personnes/ressources] et évalué les options comme [alternatives]. Le choix de [solution] a conduit à [résultat à court terme] mais s'est avéré bénéfique car [impact positif à long terme]. J'ai appris [leçon] sur [aspect de prise de décision].",
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