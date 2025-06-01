from django.contrib import admin
from .models import QuestionCategory, Question, Interview ,VideoResponse ,InterviewAnalysis , InterviewQuestion
# Register your models here.
admin.site.register(Question)
admin.site.register(QuestionCategory)
admin.site.register(Interview)
admin.site.register(VideoResponse)
admin.site.register(InterviewAnalysis)
admin.site.register(InterviewQuestion)