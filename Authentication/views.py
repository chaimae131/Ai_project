from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import (
    CandidatRegistrationForm, CompanyRegistrationForm, CustomAuthenticationForm,
    CandidatProfileForm, CompanyProfileForm, Benefit
)
from .models import CustomUser, Candidat, Company
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib import messages
from .models import EmailVerification
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone
from django.core.paginator import Paginator
from .models import Job, JobApplication
from .forms import JobApplicationForm
from .models import Job, JobApplication
from .models import (
    Company, Job, JobApplication, Interview,
    InterviewResult, Skill, CustomUser, Activity
)
from .forms import JobForm, InterviewScheduleForm, InterviewResultForm

from .ml_utils import analyze_cv_job_match
from django.db.models import F


def home(request):
    if request.user.is_authenticated:
        if request.user.role == 'candidat':
            return redirect('candidate_dashboard')
        elif request.user.role == 'company':
            return redirect('company_dashboard')
    return render(request, 'Authentication/home.html')


def register_choice(request):
    return render(request, 'Authentication/register_choice.html')


def register_candidate(request):
    if request.method == 'POST':
        form = CandidatRegistrationForm(request.POST)
        if form.is_valid():
            # Créer l'utilisateur mais ne pas l'activer immédiatement
            user = form.save(commit=False)
            user.is_active = False  # L'utilisateur ne sera activé qu'après vérification
            user.save()
            
            # Créer le profil candidat
            # Added this for the empty full name problem  
            Candidat.objects.get_or_create(user=user)
            candidat_profile, created = Candidat.objects.get_or_create(user=user)
            candidat_profile.full_name = form.cleaned_data.get('full_name')  # Sauvegardez le nom complet
            candidat_profile.save()

            # Générer et enregistrer le code de vérification
            code = EmailVerification.generate_code()
            EmailVerification.objects.create(user=user, code=code)
            
            # Envoyer l'email avec le code
            send_verification_email(user, code)
            
            # Rediriger vers la page de vérification
            request.session['verification_email'] = user.email
            return redirect('verify_email')
    else:
        form = CandidatRegistrationForm()
    return render(request, 'Authentication/register_candidate.html', {'form': form})


def register_company(request):
    if request.method == 'POST':
        form = CompanyRegistrationForm(request.POST)
        if form.is_valid():
            # Créer l'utilisateur mais ne pas l'activer immédiatement
            user = form.save(commit=False)
            user.is_active = False  # L'utilisateur ne sera activé qu'après vérification
            user.save()
            
            # Créer le profil entreprise
            # added this too ;)
            Company.objects.get_or_create(user=user)
            company_profile = Company.objects.get_or_create(user=user)[0]
            company_profile.company_name = form.cleaned_data.get('company_name')
            company_profile.domain_of_work = form.cleaned_data.get('domain_of_work')
            company_profile.save()
            # Générer et enregistrer le code de vérification
            code = EmailVerification.generate_code()
            EmailVerification.objects.create(user=user, code=code)
            
            # Envoyer l'email avec le code
            send_verification_email(user, code)
            
            # Rediriger vers la page de vérification
            request.session['verification_email'] = user.email
            return redirect('verify_email')
    else:
        form = CompanyRegistrationForm()
    return render(request, 'Authentication/register_company.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                if user.role == 'candidat':
                    return redirect('candidate_dashboard')
                elif user.role == 'company':
                    return redirect('company_dashboard')
                else:
                    return redirect('home')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'Authentication/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def company_dashboard(request):
    if request.user.role != 'company':
        return redirect('home')
    
    try:
        company = request.user.company_profile
    except Company.DoesNotExist:
        company = Company.objects.create(user=request.user)
    
    # Get company statistics
    total_jobs = Job.objects.filter(company=company).count()
    active_jobs = Job.objects.filter(company=company, status='active').count()
    total_applications = JobApplication.objects.filter(job__company=company).count()
    pending_applications = JobApplication.objects.filter(job__company=company, status='pending').count()
    scheduled_interviews = Interview.objects.filter(
        application__job__company=company,
        status='scheduled',
        scheduled_at__gt=timezone.now()
    ).count()
    
    # Recent applications
    recent_applications = JobApplication.objects.filter(
        job__company=company
    ).order_by('-created_at')[:5]
    
    # Upcoming interviews
    upcoming_interviews = Interview.objects.filter(
        application__job__company=company,
        status='scheduled',
        scheduled_at__gt=timezone.now()
    ).order_by('scheduled_at')[:5]
    
    # Statistics cards
    stats = [
        {'title': 'Offres actives', 'value': active_jobs, 'color': 'blue', 'icon': 'fas fa-briefcase'},
        {'title': 'Candidatures', 'value': total_applications, 'color': 'green', 'icon': 'fas fa-file-alt'},
        {'title': 'En attente', 'value': pending_applications, 'color': 'yellow', 'icon': 'fas fa-clock'},
        {'title': 'Entretiens prévus', 'value': scheduled_interviews, 'color': 'purple', 'icon': 'fas fa-calendar-check'},
    ]
    
    context = {
        'company': company,
        'stats': stats,
        'recent_applications': recent_applications,
        'upcoming_interviews': upcoming_interviews,
        'total_jobs': total_jobs,
    }
    
    return render(request, 'Authentication/company_dashboard.html', context)


@login_required
def edit_company_profile(request):
    if request.user.role != 'company':
        return redirect('home')
    
    # Récupérer ou créer le profil d'entreprise
    try:
        company = request.user.company_profile
    except Company.DoesNotExist:
        company = Company.objects.create(user=request.user)
    
    # Récupérer les avantages existants
    benefits = Benefit.objects.filter(company=company)
    
    if request.method == 'POST':
        form = CompanyProfileForm(request.POST, request.FILES, instance=company)
        
        if form.is_valid():
            # Sauvegarder le formulaire
            company_profile = form.save()
            
            # Mettre à jour la photo de l'utilisateur si fournie
            if 'photo' in request.FILES:
                request.user.photo = request.FILES['photo']
                request.user.save()
            
            # Gérer les avantages
            if 'benefits' in request.POST:
                # Supprimer les avantages existants
                Benefit.objects.filter(company=company_profile).delete()
                
                # Ajouter les nouveaux avantages
                benefits = request.POST.getlist('benefits')
                for benefit_name in benefits:
                    if benefit_name.strip():
                        Benefit.objects.create(company=company_profile, name=benefit_name.strip())
            
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect('company_dashboard')
        else:
            # Si le formulaire n'est pas valide, afficher les erreurs
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        # Initialiser le formulaire avec les données existantes
        form = CompanyProfileForm(instance=company)
    
    context = {
        'form': form,
        'benefits': benefits,
    }
    
    return render(request, 'Authentication/edit_company_profile.html', context)


def send_verification_email(user, code):
    """Envoie un email avec le code de vérification"""
    subject = 'Vérification de votre compte RemoteInterview'
    html_message = render_to_string('Authentication/email/verification_email.html', {
        'user': user,
        'code': code
    })
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject,
        plain_message,
        None,  # From email (utilisera DEFAULT_FROM_EMAIL)
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )


def verify_email(request):
    verification_email = request.session.get('verification_email')
    
    if not verification_email:
        messages.error(request, "Session expirée. Veuillez vous inscrire à nouveau.")
        return redirect('register_choice')
    
    if request.method == 'POST':
        code = request.POST.get('verification_code')
        
        try:
            user = CustomUser.objects.get(email=verification_email)
            verification = EmailVerification.objects.get(user=user)
            
            if not verification.is_valid():
                # Le code a expiré
                verification.delete()
                messages.error(request, "Le code de vérification a expiré. Un nouveau code a été envoyé.")
                
                # Générer un nouveau code
                new_code = EmailVerification.generate_code()
                EmailVerification.objects.create(user=user, code=new_code)
                send_verification_email(user, new_code)
                
                return redirect('verify_email')
            
            if verification.code == code:
                # Code valide, activer l'utilisateur
                user.is_active = True
                user.save()
                
                verification.is_verified = True
                verification.save()
                
                # Connecter l'utilisateur
                login(request, user)
                
                # Nettoyer la session
                del request.session['verification_email']
                
                messages.success(request, "Votre compte a été vérifié avec succès!")
                
                # Rediriger vers le tableau de bord approprié
                if user.role == 'candidat':
                    return redirect('candidate_dashboard')
                else:
                    return redirect('company_dashboard')
            else:
                messages.error(request, "Code de vérification incorrect. Veuillez réessayer.")
        
        except (CustomUser.DoesNotExist, EmailVerification.DoesNotExist):
            messages.error(request, "Une erreur s'est produite. Veuillez vous inscrire à nouveau.")
            return redirect('register_choice')
    
    return render(request, 'Authentication/verify_email.html', {'email': verification_email})


@require_POST
@csrf_exempt
def resend_verification(request):
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        user = CustomUser.objects.get(email=email)
        
        # Supprimer l'ancien code s'il existe
        EmailVerification.objects.filter(user=user).delete()
        
        # Générer un nouveau code
        code = EmailVerification.generate_code()
        EmailVerification.objects.create(user=user, code=code)
        
        # Envoyer l'email
        send_verification_email(user, code)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
# ce que j'ai ajouté pour le candidat

from django.db.models import Q, Count, Avg, F
from django.core.paginator import Paginator
from .models import (
    Skill, CandidateSkill, Job, JobApplication,
    Interview, InterviewResult, Activity
)

@login_required
def candidate_dashboard(request):
    if request.user.role != 'candidat':
        return redirect('home')
    
    try:
        candidate = request.user.candidat_profile
    except Candidat.DoesNotExist:
        candidate = Candidat.objects.create(user=request.user)
    
    # Exemple de statistiques par défaut
    default_stats = [
        {'title': 'Candidatures', 'value': 0, 'color': 'blue', 'icon': 'fas fa-file-alt', 'id': 'applications'},
        {'title': 'Entretiens', 'value': 0, 'color': 'green', 'icon': 'fas fa-check-circle', 'id': 'interviews'},
        {'title': 'Offres sauvegardées', 'value': 0, 'color': 'yellow', 'icon': 'fas fa-star', 'id': 'saved_jobs'},
        {'title': 'Score moyen', 'value': 0, 'color': 'purple', 'icon': 'fas fa-trophy', 'id': 'average_score'},
    ]
    
    # Exemple de statistiques dynamiques (si disponibles)
    stats = []  # Remplissez cette liste avec des données réelles si nécessaire
    
    # Récupérer les compétences principales
    top_skills = CandidateSkill.objects.filter(candidate=candidate).order_by('-level')[:6]
    skills_with_width = [{'name': skill.skill.name, 'level': skill.level, 'width': skill.level * 25} for skill in top_skills]
    recommended_jobs = Job.objects.filter(status='active').order_by('-created_at')[:10]

    
    global_score = min(100, CandidateSkill.objects.filter(candidate=candidate).aggregate(Avg('level'))['level__avg'] * 25 if top_skills.exists() else 0)
    profile_completion = 50  # Exemple de valeur par défaut
    
    context = {
        'candidate': candidate,
        'top_skills': skills_with_width,
        'global_score': int(global_score),
        'profile_completion': profile_completion,
        'stats': stats,  # Statistiques dynamiques
        'default_stats': default_stats,  # Statistiques par défaut
        'recommended_jobs': recommended_jobs,
    }
    
    return render(request, 'Authentication/candidate_dashboard.html', context)


@login_required
def create_job(request):
    if request.user.role != 'company':
        return redirect('home')
    
    company = get_object_or_404(Company, user=request.user)
    
    if request.method == 'POST':
        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.company = company
            job.save()
            
            # Save tags/skills
            skills_data = request.POST.getlist('skill_name[]')
            for skill_name in skills_data:
                if skill_name.strip():
                    skill, created = Skill.objects.get_or_create(name=skill_name.strip())
                    job.tags.add(skill)
            
            # Record activity
            Activity.objects.create(
                user=request.user,
                activity_type='job_creation',
                description=f"Création de l'offre: {job.title}"
            )
            
            messages.success(request, "L'offre d'emploi a été créée avec succès.")
            return redirect('company_jobs')
    else:
        form = JobForm()
    
    # Get all skills for autocomplete
    all_skills = Skill.objects.all().values_list('name', flat=True)
    
    context = {
        'form': form,
        'all_skills': list(all_skills),
    }
    
    return render(request, 'Authentication/create_job.html', context)


@login_required
def company_jobs(request):
    if request.user.role != 'company':
        return redirect('home')
    
    company = get_object_or_404(Company, user=request.user)
    
    # Filter by status if specified
    status_filter = request.GET.get('status', '')
    
    jobs = Job.objects.filter(company=company)
    
    if status_filter:
        jobs = jobs.filter(status=status_filter)
    
    # Add application counts to each job
    for job in jobs:
        job.application_count = JobApplication.objects.filter(job=job).count()
        job.pending_count = JobApplication.objects.filter(job=job, status='pending').count()
        job.interview_count = JobApplication.objects.filter(job=job, status='interview').count()
    
    # Pagination
    paginator = Paginator(jobs, 10)  
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'jobs': page_obj,
        'status_filter': status_filter,
        'total_jobs': jobs.count(),
        'active_jobs': jobs.filter(status='active').count(),
        'closed_jobs': jobs.filter(status='closed').count(),
        'draft_jobs': jobs.filter(status='draft').count(),
    }
    
    return render(request, 'Authentication/company_jobs.html', context)


@login_required
def edit_job(request, job_id):
    if request.user.role != 'company':
        return redirect('home')
    
    company = get_object_or_404(Company, user=request.user)
    job = get_object_or_404(Job, id=job_id, company=company)
    
    if request.method == 'POST':
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            job = form.save()
            
            # Update tags/skills
            job.tags.clear()
            skills_data = request.POST.getlist('skill_name[]')
            for skill_name in skills_data:
                if skill_name.strip():
                    skill, created = Skill.objects.get_or_create(name=skill_name.strip())
                    job.tags.add(skill)
            
            # Record activity
            Activity.objects.create(
                user=request.user,
                activity_type='job_update',
                description=f"Mise à jour de l'offre: {job.title}"
            )
            
            messages.success(request, "L'offre d'emploi a été mise à jour avec succès.")
            return redirect('company_jobs')
    else:
        form = JobForm(instance=job)
    
    # Get current skills
    current_skills = job.tags.all().values_list('name', flat=True)
    
    # Get all skills for autocomplete
    all_skills = Skill.objects.all().values_list('name', flat=True)
    
    context = {
        'form': form,
        'job': job,
        'current_skills': list(current_skills),
        'all_skills': list(all_skills),
    }
    
    return render(request, 'Authentication/edit_job.html', context)


@login_required
def job_detail(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    try:
        candidate = Candidat.objects.get(user=request.user)
    except Candidat.DoesNotExist:
        candidate = None

    has_applied = False
    if candidate:
        has_applied = JobApplication.objects.filter(job=job, candidate=candidate).exists()

    user_skills = request.user.profile.skills.all() if hasattr(request.user, 'profile') else []
    skills_match = []
    for skill in job.tags.all():  # correction ici
        skills_match.append({
            'name': skill.name,
            'match': skill in user_skills
        })

    context = {
        'job': job,
        'has_applied': has_applied,
        'skills_match': skills_match,
    }
    return render(request, 'Authentication/job_detail.html', context)


from django.http import JsonResponse

@login_required
@require_POST
def apply_to_job(request, job_id):
    job = get_object_or_404(Job, id=job_id)
    
    if request.user.role != 'candidat':
        return JsonResponse({'error': "Seuls les candidats peuvent postuler."}, status=403)
    
    candidat = request.user.candidat_profile

    if JobApplication.objects.filter(job=job, candidate=candidat).exists():
        return JsonResponse({'error': "Vous avez déjà postulé à cette offre."}, status=409)
    
    if not candidat.cv:
        return JsonResponse({'error': "Veuillez d'abord télécharger votre CV dans votre profil."}, status=400)

    # Créer la candidature (sans score au début)
    application = JobApplication.objects.create(
        job=job,
        candidate=candidat,
        status='pending',
        resume=candidat.cv
    )

    # Analyse automatique du CV avec ml_utils.py
    try:
        # Vérification du CV
        import os
        print(f"\n{'='*50}\nDEBUG: CV Information\n{'='*50}")
        print(f"CV path: {candidat.cv.path}")
        print(f"CV exists: {os.path.exists(candidat.cv.path)}")
        print(f"CV size: {os.path.getsize(candidat.cv.path) if os.path.exists(candidat.cv.path) else 'N/A'}")
        print(f"CV URL: {candidat.cv.url}")
        
        # Vérification de l'offre d'emploi
        print(f"\n{'='*50}\nDEBUG: Job Information\n{'='*50}")
        print(f"Job title: {job.title}")
        print(f"Job description length: {len(job.description)}")
        print(f"Job requirements length: {len(job.requirements)}")
        
        # Récupérer les tags/compétences de l'offre
        job_tags = list(job.tags.all().values_list('name', flat=True))
        print(f"Job tags: {job_tags}")
        
        # Utiliser la fonction d'analyse complète de ml_utils.py
        from .ml_utils import analyze_cv_job_match
        print(f"\n{'='*50}\nDEBUG: Calling analyze_cv_job_match\n{'='*50}")
        similarity_score = analyze_cv_job_match(
            cv_path=candidat.cv.path,
            job_title=job.title,
            job_description=job.description,
            job_requirements=job.requirements,
            job_tags=job_tags
        )
        
        print(f"\n{'='*50}\nDEBUG: Similarity Score Result\n{'='*50}")
        print(f"Similarity score: {similarity_score}")
        
        # Sauvegarder le score dans la candidature
        application.similarity_score = similarity_score
        application.save()
        print(f"Score saved to application: {application.similarity_score}")
        
    except Exception as e:
        import traceback
        print(f"\n{'='*50}\nDEBUG: Error in CV Analysis\n{'='*50}")
        print(f"Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        # L'application continue même si l'analyse échoue

    # Enregistrer l'activité
    Activity.objects.create(
        user=request.user,
        activity_type='application',
        description=f"Candidature soumise pour: {job.title} - {job.company.company_name}"
    )

    return JsonResponse({'message': "Votre candidature a été soumise avec succès !"}, status=201)


@login_required
def job_applications(request, job_id):
    if request.user.role != 'company':
        return redirect('home')
    
    company = get_object_or_404(Company, user=request.user)
    job = get_object_or_404(Job, id=job_id, company=company)

    
    # Filter by status if specified
    status_filter = request.GET.get('status', '')
    
    # Get sort parameter
    sort_by = request.GET.get('sort', 'date')
    
    applications = JobApplication.objects.filter(job=job)
    
    # Apply status filter if specified
    if status_filter:
        applications = applications.filter(status=status_filter)
    
    # Apply sorting
    if sort_by == 'score_desc':
        # Sort by similarity score (high to low)
        # Use "-" for descending order and handle None values with nulls_last=True
        applications = applications.order_by(F('similarity_score').desc(nulls_last=True))
    elif sort_by == 'score_asc':
        # Sort by similarity score (low to high)
        applications = applications.order_by(F('similarity_score').asc(nulls_first=True))
    else:
        # Default: sort by date (newest first)
        applications = applications.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(applications, 10)  # 10 applications per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'job': job,
        'applications': page_obj,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'total_applications': applications.count(),
        'pending_applications': applications.filter(status='pending').count(),
        'reviewing_applications': applications.filter(status='reviewing').count(),
        'interview_applications': applications.filter(status='interview').count(),
        'accepted_applications': applications.filter(status='accepted').count(),
        'rejected_applications': applications.filter(status='rejected').count(),
    }
    
    return render(request, 'Authentication/job_applications.html', context)


@login_required
def application_detail(request, application_id):
    if request.user.role != 'company':
        return redirect('home')
    
    company = get_object_or_404(Company, user=request.user)
    application = get_object_or_404(JobApplication, id=application_id, job__company=company)
    
    # Get candidate skills
    candidate_skills = application.candidate.skills.all()
    
    # Get job required skills
    job_skills = application.job.tags.all()
    
    # Calculate matching skills
    matching_skills = []
    missing_skills = []
    
    for job_skill in job_skills:
        if candidate_skills.filter(skill=job_skill).exists():
            candidate_skill = candidate_skills.get(skill=job_skill)
            matching_skills.append({
                'name': job_skill.name,
                'level': candidate_skill.level,
                'level_display': candidate_skill.get_level_display()
            })
        else:
            missing_skills.append({'name': job_skill.name})
    
    # Calculate match percentage
    match_percentage = min(100, int((len(matching_skills) / max(1, len(job_skills))) * 100))
    
    # Get interviews
    interviews = Interview.objects.filter(application=application)
    
    # Update application status if needed
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status and new_status in dict(JobApplication.STATUS_CHOICES).keys():
            application.status = new_status
            application.save()
            
            # Record activity
            Activity.objects.create(
                user=request.user,
                activity_type='application_update',
                description=f"Mise à jour du statut de candidature: {application.candidate.user.email} - {application.job.title}"
            )
            
            messages.success(request, "Le statut de la candidature a été mis à jour avec succès.")
            return redirect('application_detail', application_id=application.id)
    
    context = {
        'application': application,
        'matching_skills': matching_skills,
        'missing_skills': missing_skills,
        'match_percentage': match_percentage,
        'interviews': interviews,
    }
    
    return render(request, 'Authentication/application_detail.html', context)


@login_required
def schedule_interview(request, application_id):
    if request.user.role != 'company':
        return redirect('home')
    
    company = get_object_or_404(Company, user=request.user)
    application = get_object_or_404(JobApplication, id=application_id, job__company=company)
    
    if request.method == 'POST':
        form = InterviewScheduleForm(request.POST)
        if form.is_valid():
            interview = form.save(commit=False)
            interview.application = application
            interview.save()
            
            # Update application status
            application.status = 'interview'
            application.save()
            
            # Record activity
            Activity.objects.create(
                user=request.user,
                activity_type='interview_scheduled',
                description=f"Entretien programmé avec: {application.candidate.user.email} - {application.job.title}"
            )
            
            messages.success(request, "L'entretien a été programmé avec succès.")
            return redirect('application_detail', application_id=application.id)
    else:
        form = InterviewScheduleForm()
    
    context = {
        'form': form,
        'application': application,
    }
    
    return render(request, 'Authentication/schedule_interview.html', context)


@login_required
def interview_management(request):
    if request.user.role != 'company':
        return redirect('home')
    
    company = get_object_or_404(Company, user=request.user)
    
    # Filter by status if specified
    status_filter = request.GET.get('status', '')
    
    interviews = Interview.objects.filter(application__job__company=company)
    
    if status_filter:
        interviews = interviews.filter(status=status_filter)
    
    # Upcoming interviews
    upcoming_interviews = interviews.filter(
        status='scheduled',
        scheduled_at__gt=timezone.now()
    ).order_by('scheduled_at')
    
    # Past interviews
    past_interviews = interviews.filter(
        status='completed'
    ).order_by('-scheduled_at')
    
    # Cancelled interviews
    cancelled_interviews = interviews.filter(
        status='cancelled'
    ).order_by('-scheduled_at')
    
    context = {
        'upcoming_interviews': upcoming_interviews,
        'past_interviews': past_interviews,
        'cancelled_interviews': cancelled_interviews,
        'status_filter': status_filter,
    }
    
    return render(request, 'Authentication/interview_management.html', context)


@login_required
def interview_result(request, interview_id):
    if request.user.role != 'company':
        return redirect('home')
    
    company = get_object_or_404(Company, user=request.user)
    interview = get_object_or_404(Interview, id=interview_id, application__job__company=company)
    
    # Check if result already exists
    try:
        result = interview.result
        form = InterviewResultForm(request.POST or None, instance=result)
    except InterviewResult.DoesNotExist:
        result = None
        form = InterviewResultForm(request.POST or None)
    
    if request.method == 'POST' and form.is_valid():
        result = form.save(commit=False)
        result.interview = interview
        result.save()
        
        # Update interview status
        interview.status = 'completed'
        interview.save()
        
        # Record activity
        Activity.objects.create(
            user=request.user,
            activity_type='interview_completed',
            description=f"Résultat d'entretien enregistré: {interview.application.candidate.user.email} - {interview.application.job.title}"
        )
        
        messages.success(request, "Le résultat de l'entretien a été enregistré avec succès.")
        return redirect('interview_management')
    
    context = {
        'form': form,
        'interview': interview,
        'result': result,
    }
    
    return render(request, 'Authentication/interview_result.html', context)


@login_required
def edit_candidate_profile(request):
    if request.user.role != 'candidat':
        return redirect('home')
    
    candidate = get_object_or_404(Candidat, user=request.user)
    
    if request.method == 'POST':
        # Traitement du formulaire principal
        form = CandidatProfileForm(request.POST, request.FILES, instance=candidate, user=request.user)
        
        if form.is_valid():
            form.save(user=request.user)
            
            # Traitement des compétences
            # Supprimer toutes les compétences existantes
            CandidateSkill.objects.filter(candidate=candidate).delete()
            
            # Ajouter les nouvelles compétences
            skills_data = request.POST.getlist('skill_name[]')
            levels_data = request.POST.getlist('skill_level[]')
            
            for i in range(len(skills_data)):
                if skills_data[i].strip():
                    skill_name = skills_data[i].strip()
                    skill_level = int(levels_data[i]) if i < len(levels_data) else 1
                    
                    # Obtenir ou créer la compétence
                    skill, created = Skill.objects.get_or_create(name=skill_name)
                    
                    # Créer la relation candidat-compétence
                    CandidateSkill.objects.create(
                        candidate=candidate,
                        skill=skill,
                        level=skill_level
                    )
            
            # Enregistrer l'activité
            Activity.objects.create(
                user=request.user,
                activity_type='profile_update',
                description="Mise à jour du profil"
            )
            
            messages.success(request, 'Votre profil a été mis à jour avec succès.')
            return redirect('candidate_dashboard')
    else:
        form = CandidatProfileForm(instance=candidate, user=request.user)
    
    # Récupérer les compétences existantes
    skills = CandidateSkill.objects.filter(candidate=candidate)
    
    context = {
        'form': form,
        'skills': skills
    }
    
    return render(request, 'Authentication/edit_candidate_profile.html', context)

# Ajouter cette fonction à la fin du fichier views.py
@login_required
def debug_company_profile(request):
    """Vue de débogage pour vérifier les données de l'entreprise"""
    if request.user.role != 'company':
        return redirect('home')
    
    try:
        company = request.user.company_profile
        benefits = Benefit.objects.filter(company=company)
        
        context = {
            'company': company,
            'benefits': benefits,
            'user': request.user
        }
        
        return render(request, 'Authentication/debug_company_profile.html', context)
    except Company.DoesNotExist:
        messages.error(request, "Profil d'entreprise non trouvé.")
        return redirect('company_dashboard')