from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_choice, name='register_choice'),
    path('register/candidate/', views.register_candidate, name='register_candidate'),
    path('register/company/', views.register_company, name='register_company'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    #path('candidate/dashboard/', views.candidate_dashboard, name='candidate_dashboard'),
    path('company/dashboard/', views.company_dashboard, name='company_dashboard'),
    path('candidate/profile/edit/', views.edit_candidate_profile, name='edit_candidate_profile'),
    path('company/profile/edit/', views.edit_company_profile, name='edit_company_profile'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),

    
    path('company/jobs/', views.company_jobs, name='company_jobs'),
    path('company/jobs/create/', views.create_job, name='create_job'),
    path('company/jobs/<int:job_id>/edit/', views.edit_job, name='edit_job'),
    path('company/jobs/<int:job_id>/applications/', views.job_applications, name='job_applications'),
    path('company/applications/<int:application_id>/', views.application_detail, name='application_detail'),
    path('company/applications/<int:application_id>/schedule/', views.schedule_interview, name='schedule_interview'),
    path('company/interviews/', views.interview_management, name='interview_management'),
    path('company/interviews/<int:interview_id>/result/', views.interview_result, name='interview_result'),

    
    #je l'ai ajouté
     path('candidate/dashboard/', views.candidate_dashboard, name='candidate_dashboard'),
    
    # Candidatures
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('candidate/job_applications/', views.job_applications, name='applications'),
    path('apply/<int:job_id>/', views.apply_to_job, name='apply_to_job'),
    path('candidate/job_applications/<int:application_id>/', views.application_detail, name='application_detail'),
    
    
    # Profil
    path('candidate/profile/edit/', views.edit_candidate_profile, name='edit_candidate_profile'),
]