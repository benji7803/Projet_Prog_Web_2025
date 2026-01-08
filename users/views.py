from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm
from django.contrib.auth import login, logout
from django.views.decorators.http import require_POST

# Create your views here.

def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            login(request, form.save())
            return redirect("templates:dashboard")
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {"form": form})

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data = request.POST)
        if form.is_valid():
            login(request, form.get_user())
            if "next" in request.POST:
                return redirect(request.POST.get("next"))
            else:
                return redirect("templates:dashboard")
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {"form": form})

@require_POST
def logout_view(request):
    logout(request)
    return redirect("templates:dashboard")
