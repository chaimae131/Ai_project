from django.contrib import admin
from .models import CustomUser, Candidat, Company, EmailVerification ,Benefit, CandidateSkill ,Job ,JobApplication , Activity

# Register your models here
admin.site.register(CustomUser)
admin.site.register(Candidat)
admin.site.register(Company)
admin.site.register(EmailVerification)
admin.site.register(Benefit)
admin.site.register(CandidateSkill)
admin.site.register(Job)
admin.site.register(JobApplication)
admin.site.register(Activity)
