# Create your views here.
# views.py
from django.shortcuts import render, redirect, get_object_or_404
from .models import TechnicalTest, TestSession, TestQuestion, TestResponse, TestReport
from Authentication.models import JobApplication
from interviewapp.models import Interview
from .utils import generate_questions_for_skill, evaluate_qcm_response, evaluate_open_response
import uuid
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db import models
from .pdf_utils import generate_test_report_pdf
from django.http import HttpResponse

def technical_test_start(request, application_id):
    application = get_object_or_404(JobApplication, id=application_id, candidate=request.user.candidat_profile)
    
    # Vérifier si l'entretien vidéo est terminé
    interview = Interview.objects.filter(
        job_application=application,
        status='C'
    ).first()
    
    #if not interview:
     #   messages.warning(request, "Veuillez d'abord compléter l'entretien vidéo")
      #  return redirect('interviewapp:interview_detail', application_id=application.id)
    
    # Vérifier si un test existe déjà
    technical_test = TechnicalTest.objects.filter(job_application=application).first()
    
    # Créer le test technique s'il n'existe pas
    if not technical_test:
        technical_test = TechnicalTest.objects.create(
            job_application=application,
            title=f"Test Technique - {application.job.title}",
            description=f"Évaluation technique pour le poste {application.job.title}"
        )
        
        # Générer les questions dynamiquement
        required_skills = application.job.tags.all()  # Récupérer les compétences requises pour le poste
        order_counter = 1  # compteur global
        for skill in required_skills:
            questions = generate_questions_for_skill(skill.name, num_qcm=3, num_open=1)
            for q in questions:
                q.test = technical_test
                q.order = order_counter
                q.save()
                order_counter += 1  

            
    
    # Créer la session de test
    session = TestSession.objects.create(
        candidate=request.user.candidat_profile,
        test=technical_test,
        interview=interview,
        status='O'
    )
    
    return redirect('quiz:question', session_uuid=session.unique_id, question_order=1)

def technical_test_question(request, session_uuid, question_order):
    session = get_object_or_404(TestSession, unique_id=session_uuid, candidate=request.user.candidat_profile)
    
    # Empêcher l'accès si le test est terminé
    if session.status in ['C', 'E']:
        return redirect('quiz:review', session_uuid=session_uuid)
    
    # Récupérer la question spécifique
    try:
        question = session.test.questions.get(order=question_order)
    except TestQuestion.DoesNotExist:
        return redirect('quiz:complete', session_uuid=session_uuid)
    
    # Vérifier si une réponse existe déjà
    if TestResponse.objects.filter(session=session, question=question).exists():
        return redirect('quiz:question', 
                        session_uuid=session_uuid, 
                        question_order=question_order + 1)
    
    return render(request, 'quiz/question.html', {
        'session': session,
        'question': question,
        'question_order': question_order
    })

@transaction.atomic
def technical_test_submit_answer(request, session_uuid, question_id):
    session = get_object_or_404(TestSession, unique_id=session_uuid, candidate=request.user.candidat_profile)
    question = get_object_or_404(TestQuestion, id=question_id)

    # Si test déjà complété, rediriger
    if session.status in ['C', 'E']:
        return redirect('quiz:review', session_uuid=session_uuid)

    if request.method == 'POST':
        response, _ = TestResponse.objects.get_or_create(session=session, question=question)

        # QCM
        if question.question_type == 'QCM':
            user_choice = request.POST.get('answer_choice')
            if not user_choice:
                messages.warning(request, "Veuillez sélectionner une réponse.")
                return redirect('quiz:question', session_uuid=session_uuid, question_order=question.order)

            evaluation = evaluate_qcm_response(user_choice, question.correct_answer)
            response.answer_choice = user_choice
            response.points_earned = evaluation['score']
            response.feedback = "Correct" if evaluation['is_correct'] else "Incorrect"

        # Question ouverte
        else:
            user_answer = request.POST.get('answer_text', '').strip()
            if not user_answer:
                messages.warning(request, "Votre réponse ne peut pas être vide.")
                return redirect('quiz:question', session_uuid=session_uuid, question_order=question.order)

            evaluation = evaluate_open_response(user_answer, question.model_answer)
            response.answer_text = user_answer
            response.points_earned = evaluation['score']
            response.similarity_score = evaluation['similarity']
            response.feedback = f"Similarité: {evaluation['similarity']:.2f}"

        response.save()

        # Calcul du score total uniquement si réponse valide
        total_score = session.responses.aggregate(
            total=models.Sum('points_earned')
        )['total'] or 0

        session.score = total_score
        session.max_score = session.test.questions.count() * 4  # 4 pts/question
        session.save()

    # Passer à la question suivante
    next_order = question.order + 1
    if session.test.questions.filter(order=next_order).exists():
        return redirect('quiz:question', session_uuid=session_uuid, question_order=next_order)

    return redirect('quiz:complete', session_uuid=session_uuid)
def technical_test_complete(request, session_uuid):
    session = get_object_or_404(TestSession, unique_id=session_uuid, candidate=request.user.candidat_profile)
    
    # Marquer la session comme terminée
    if session.status == 'O':
        session.status = 'C'
        session.completed_at = timezone.now()
        session.save()
    
    # Générer le rapport automatiquement
    if not hasattr(session, 'report'):
        generate_test_report(session)
    
    return render(request, 'quiz/complete.html', {
        'session': session
    })

def technical_test_review(request, session_uuid):
    session = get_object_or_404(TestSession, unique_id=session_uuid, candidate=request.user.candidat_profile)
    responses = session.responses.select_related('question')
    
    return render(request, 'quiz/review.html', {
        'session': session,
        'responses': responses,
        'report': getattr(session, 'report', None)
    })

# ---------- Fonctions utilitaires ---------- 
def generate_test_report(session):
    """Génère un rapport d'évaluation automatisé"""
    skills_evaluation = {}
    #strengths = []
    #weaknesses = []
    
    # Analyser les résultats par compétence
    for response in session.responses.select_related('question__skill'):
        skill_name = response.question.skill.name
        
        if skill_name not in skills_evaluation:
            skills_evaluation[skill_name] = {
                'total': 0,
                'max': 0,
                'questions': 0
            }
        
        skills_evaluation[skill_name]['total'] += response.points_earned
        skills_evaluation[skill_name]['max'] += 4  # Points max par question
        skills_evaluation[skill_name]['questions'] += 1
        
        '''# Identifier les forces/faiblesses
        if response.points_earned >= 3:
            strengths.append(skill_name)
        elif response.points_earned <= 1:
            weaknesses.append(skill_name)'''
    
    # Calculer les scores par compétence
    for skill in skills_evaluation:
        data = skills_evaluation[skill]
        data['score'] = data['total'] / data['max'] * 100 if data['max'] > 0 else 0
    
    # Créer le rapport
    report = TestReport.objects.create(
        session=session,
        overall_score = (
            session.score / session.max_score * 100
            if session.score is not None and session.max_score is not None and session.max_score > 0
            else 0
        ),  
        skills_evaluation=skills_evaluation,
        #strengths=", ".join(set(strengths)),
        #weaknesses=", ".join(set(weaknesses)),
        #recommendations="Consulter les résultats détaillés pour une analyse complète" 
    )
    
    # Mettre à jour le statut de la session
    session.status = 'E'
    session.save()
    
    return report

def view_test_report(request, report_id):
    report = get_object_or_404(TestReport, id=report_id)
    
    # Si on veut télécharger le PDF
    if 'download' in request.GET:
        buffer = generate_test_report_pdf(report)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="rapport_test_{report.session.id}.pdf"'
        return response
    
    # Sinon afficher la page de consultation
    context = {'report': report}
    return render(request, 'quiz/report_view.html', context)