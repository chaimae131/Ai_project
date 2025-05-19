from django.contrib import admin
from .models import CustomUser, Candidat, Company, EmailVerification

# Register your models here
admin.site.register(CustomUser)
admin.site.register(Candidat)
admin.site.register(Company)
admin.site.register(EmailVerification)
