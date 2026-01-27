from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

app_name = 'templates'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create/', views.create_template, name='create_template'),
    path('edit/<int:template_id>/', views.edit_template, name='edit_template'),
    path('download/<int:template_id>/', views.download_template, name='download_template'),
    path('submit/', views.submit, name="submit"),
    path('delete/<int:template_id>/',views.delete_template, name="delete_template"),
    path('delete_campaign/<int:campaign_id>/',views.delete_campaign, name="delete_campaign"),
    path('simulate/', views.simulate, name="simulate"),
    path('view/', views.view_plasmid, name="view_plasmid"),
    path('simulate/view_plasmid/<int:campaign_id>/', views.user_view_plasmid, name='user_view_plasmid'),
    path('search/', views.plasmid_search, name='search_templates'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

