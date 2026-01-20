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
    path('team/<int:team_id>/invite/', views.invite_member, name='invite_member'),
    path('team/<int:team_id>/delete/', views.delete_team, name='delete_team'),
    path("administration", views.administration_view, name="administration"),
]