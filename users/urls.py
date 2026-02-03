from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('login', views.login_view, name='login'),
    path('register', views.register_view, name='register'),
    path('logout', views.logout_view, name='logout'),
    path('profile/', views.user_profile, name='profile'),
    path('create_team/', views.create_team, name='create_team'),
    path('team/<int:team_id>/', views.team_detail, name='team_detail'),
    path('delete_user/<int:user_id>/', views.delete_user, name='delete_user'),

    path('team/<int:team_id>/invite/', views.invite_member, name='invite_member'),
    path('team/<int:team_id>/remove/<int:user_id>/', views.remove_member, name='remove_member'),
    path('team/<int:team_id>/promote/<int:user_id>/', views.promote_member, name='promote_member'),

    path('team/<int:team_id>/add_table/', views.add_table, name='add_table'),
    path('team/<int:team_id>/remove_table/<int:table_id>/', views.remove_table, name='remove_table'),
    path('team/<int:team_id>/download_table/<int:table_id>/', views.download_table, name='download_table'),
    path('team/<int:team_id>/validate_table/<int:table_id>/', views.validate_table, name='validate_table'),

    path('team/<int:team_id>/add_seqcol/', views.add_seqcol, name='add_seqcol'),
    path('team/<int:team_id>/remove_seqcol/<int:seqcol_id>/', views.remove_seqcol, name='remove_seqcol'),
    path('team/<int:team_id>/download_seqcol/<int:seqcol_id>/', views.download_seqcol, name='download_seqcol'),
    path('team/<int:team_id>/validate_seqcol/<int:seqcol_id>/', views.validate_seqcol, name='validate_seqcol'),

    path("administration", views.administration_view, name="administration"),
    path('team/<int:team_id>/delete/', views.delete_team, name='delete_team'),
    path('delete_collection/<int:collection_id>/', views.delete_plasmid_collection, name='delete_collection'),
    path('delete_mapping/<int:template_id>/', views.delete_mapping_template, name='delete_mapping')
]