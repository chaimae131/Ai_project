from django.contrib import admin
from .models import (
    TechnicalTest,
    TestSession,
    TestQuestion,
    TestResponse,
    TestReport
)
# Register your models here.
admin.site.register(TechnicalTest)
admin.site.register(TestSession) 
admin.site.register(TestQuestion)
admin.site.register(TestResponse)
admin.site.register(TestReport)

