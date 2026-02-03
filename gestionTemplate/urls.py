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
    path('simulate/<int:campaign_id>/digestion/', views.campaign_digestion, name='campaign_digestion'),
    path('simulate/<int:campaign_id>/digestion/image/', views.campaign_digestion_image, name='campaign_digestion_image'),
    path('search/', views.plasmid_search, name='search_templates'),
    path('search-public/', views.search_public_templates, name='search_public_templates'),
    path('import-public-templates/<int:template_id>/', views.import_public_templates, name='import_public_templates'),
    path('publier/<int:template_id>/', views.publier_template, name="publier"),
    path("user/plasmid_archive/<int:campaign_id>/", views.user_view_plasmid_archive, name="user_view_plasmid_archive"),
    path('make_public/', views.make_public, name='make_public'),
    path('make_public_bulk/', views.make_public_bulk, name='make_public_bulk'),
    path('plasmid/download/', views.download_plasmid, name='download_plasmid'),
    path('plasmid/<int:plasmid_id>/', views.plasmid_detail, name='plasmid_detail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

