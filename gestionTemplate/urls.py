from django.urls import path
from . import views

app_name = 'templates'

urlpatterns = [
    path('create/', views.create, name="create"),
    path('submit/', views.submit, name="submit"),
]