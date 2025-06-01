import json
import random
from Authentication.models import JobApplication
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from .models import (
    Question, Interview, InterviewQuestion, 
    VideoResponse, InterviewAnalysis, QuestionCategory
)
from .forms import (
    InterviewStartForm, 
    VideoResponseForm
)
from .tasks import analyze_video_response, generate_interview_report ,check_interview_completion
import uuid
import os

'''
@login_required
def interview_start(request):
    if request.method == 'POST':
        form = InterviewStartForm(request.POST)
        if form.is_valid():
            # Create new interview
            interview = Interview.objects.create(
                candidate=request.user.candidat_profile,
                status='P'
            )
            
            # Select random questions (x easy, x medium, x hard)
            present_questions = list(Question.objects.filter(category__name='Présentation', is_active=True))
            com_questions = list(Question.objects.filter(category__name='Compétences', is_active=True))
            mot_questions = list(Question.objects.filter(category__name='Motivation', is_active=True))
            comp_questions = list(Question.objects.filter(category__name='Comportement', is_active=True))

            selected_questions = (
                random.sample(present_questions, min(1, len(present_questions))) +
                random.sample(com_questions, min(1, len(com_questions))) +
                random.sample(mot_questions, min(1, len(mot_questions))) +
                random.sample(comp_questions, min(1, len(comp_questions))))
            
            
            # Add questions to interview
            for i, question in enumerate(selected_questions, start=1):
                InterviewQuestion.objects.create(
                    interview=interview,
                    question=question,
                    order=i
                )
            
            interview.status = 'O'
            interview.save()
            
            return redirect('interviewapp:interview_question', unique_id=interview.unique_id, question_order=1)
    else:
        form = InterviewStartForm()
    
    return render(request, 'interviewapp/interview_start.html', {
        'form': form,
    })
'''
@login_required
def interview_start(request):
    application_id = request.GET.get('application_id')
    application = None
    
    if application_id:
        application = get_object_or_404(
            JobApplication, 
            id=application_id, 
            candidate=request.user.candidat_profile,
            status='interview'  # S'assurer que le statut est bien "interview"
        )
    
    if request.method == 'POST':
        form = InterviewStartForm(request.POST)
        if form.is_valid():
            # Create new interview
            interview = Interview.objects.create(
                candidate=request.user.candidat_profile,
                status='P',
                job_application=application
            )
            
            # Select random questions (x easy, x medium, x hard)
            present_questions = list(Question.objects.filter(category__name='Présentation', is_active=True))
            com_questions = list(Question.objects.filter(category__name='Compétences', is_active=True))
            mot_questions = list(Question.objects.filter(category__name='Motivation', is_active=True))
            comp_questions = list(Question.objects.filter(category__name='Comportement', is_active=True))

            selected_questions = (
                random.sample(present_questions, min(1, len(present_questions))) +
                random.sample(com_questions, min(1, len(com_questions))) +
                random.sample(mot_questions, min(1, len(mot_questions))) +
                random.sample(comp_questions, min(1, len(comp_questions))))
            
            # Add questions to interview
            for i, question in enumerate(selected_questions, start=1):
                InterviewQuestion.objects.create(
                    interview=interview,
                    question=question,
                    order=i
                )
            
            interview.status = 'O'
            interview.save()
            
            return redirect('interviewapp:interview_question', unique_id=interview.unique_id, question_order=1)
    else:
        form = InterviewStartForm()
    
    return render(request, 'interviewapp/interview_start.html', {
        'form': form,
        'application': application,
    })

@login_required
def interview_question(request, unique_id, question_order):
    interview = get_object_or_404(Interview, unique_id=unique_id, candidate=request.user.candidat_profile)
    interview_question = get_object_or_404(
        InterviewQuestion, 
        interview=interview, 
        order=question_order
    )
    
    # Check if there's already a video response
    try:
        video_response = VideoResponse.objects.get(interview_question=interview_question)
        return redirect('interviewapp:interview_question_review', unique_id=unique_id, question_order=question_order)
    except VideoResponse.DoesNotExist:
        video_response = None
    
    if request.method == 'POST':
        form = VideoResponseForm(request.POST, request.FILES)
        if form.is_valid():
            video_response = form.save(commit=False)
            video_response.interview_question = interview_question
            video_response.save()
            
            # Launch async analysis
            analyze_video_response.delay(video_response.id)

            
            return redirect('interviewapp:interview_question_review', unique_id=unique_id, question_order=question_order)
    else:
        form = VideoResponseForm()
    
    next_question = InterviewQuestion.objects.filter(
        interview=interview,
        order=question_order + 1
    ).first()
    
    return render(request, 'interviewapp/interview_question.html', {
        'interview': interview,
        'interview_question': interview_question,
        'form': form,
        'next_question': next_question,
    })

@login_required
def interview_question_review(request, unique_id, question_order):
    interview = get_object_or_404(Interview, unique_id=unique_id, candidate=request.user.candidat_profile)
    interview_question = get_object_or_404(
        InterviewQuestion, 
        interview=interview, 
        order=question_order
    )
    video_response = get_object_or_404(VideoResponse, interview_question=interview_question)
    
    next_question = InterviewQuestion.objects.filter(
        interview=interview,
        order=question_order + 1
    ).first()
    
    return render(request, 'interviewapp/interview_question_review.html', {
        'interview': interview,
        'interview_question': interview_question,
        'video_response': video_response,
        'next_question': next_question,
    })

@login_required
def interview_complete(request, unique_id):
    interview = get_object_or_404(Interview, unique_id=unique_id, candidate=request.user.candidat_profile)
    # Check all questions have responses
    questions_without_responses = InterviewQuestion.objects.filter(
        interview=interview
    ).exclude(
        video_response__isnull=False
    ).exists()
    
    if questions_without_responses:
        return redirect('interviewapp:interview_question', unique_id=unique_id, question_order=1)
    
    # Mark interview as completed
    interview.status = 'C'
    interview.completed_at = timezone.now()
    interview.save()
    
    # Create analysis record
    analysis, created = InterviewAnalysis.objects.get_or_create(interview=interview)
    check_interview_completion.delay(interview.id)
    
    return render(request, 'interviewapp/interview_complete.html', {
        'interview': interview,
    })

@login_required
def interview_detail(request, unique_id):
    interview = get_object_or_404(Interview, unique_id=unique_id)
    
    # Only allow candidate or staff to view
    if not (request.user.candidat_profile == interview.candidate or request.user.is_staff):
        return HttpResponse("Unauthorized", status=401)
    
    return render(request, 'interviewapp/interview_detail.html', {
        'interview': interview,
    })

'''
@login_required
def interview_report_pdf(request, unique_id):
    interview = get_object_or_404(Interview, unique_id=unique_id)
    analysis = get_object_or_404(InterviewAnalysis, interview=interview)
    
    if not analysis.overall_report:
        return HttpResponse("Report not ready yet", status=404)
    
    with open(analysis.overall_report.path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename=interview_report_{interview.id}.pdf'
        return response
'''