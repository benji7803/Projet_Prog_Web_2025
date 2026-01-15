from django.urls import path
from . import views

app_name = 'templates'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create/', views.create_template, name='create_template'),
    path('edit/<int:template_id>/', views.edit_template, name='edit_template'),
    path('download/<int:template_id>/', views.download_template, name='download_template'),
    path('submit/', views.submit, name="submit"),
    path('delete/<int:template_id>/',views.delete_template, name="delete_template"),
    path('simulate/', views.simulate, name="simulate"),
    path('view/', views.view_plasmid, name="view_plasmid"),
]

