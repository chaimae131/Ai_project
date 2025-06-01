from django.urls import path
from . import views
app_name = 'interviewapp'

urlpatterns = [
    #path('admin/', admin.site.urls),
    #path('', views.home, name='home'),
    #path('signup/', views.candidate_signup, name='candidate_signup'),
    path('start/', views.interview_start, name='interview_start'),
    path('<uuid:unique_id>/question/<int:question_order>/', 
         views.interview_question, name='interview_question'),
    path('<uuid:unique_id>/question/<int:question_order>/review/', 
         views.interview_question_review, name='interview_question_review'),
    path('<uuid:unique_id>/complete/', 
         views.interview_complete, name='interview_complete'),
    path('<uuid:unique_id>/', 
         views.interview_detail, name='interview_detail'),

    #path('interview/<uuid:unique_id>/report.pdf', 
         #views.interview_report_pdf, name='interview_report_pdf'),
]
