from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    path('start/<int:application_id>/', 
         views.technical_test_start, 
         name='start'),
    
    path('session/<uuid:session_uuid>/question/<int:question_order>/', 
         views.technical_test_question, 
         name='question'),
    
    path('session/<uuid:session_uuid>/submit/<int:question_id>/', 
         views.technical_test_submit_answer, 
         name='submit_answer'),
    
    path('session/<uuid:session_uuid>/complete/', 
         views.technical_test_complete, 
         name='complete'),
    path('test-report/<int:report_id>/', views.view_test_report, name='view_test_report'),
    
    path('session/<uuid:session_uuid>/review/', 
         views.technical_test_review, 
         name='review'), ]