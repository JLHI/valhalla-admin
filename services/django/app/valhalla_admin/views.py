from django.shortcuts import render
from valhalla_admin.home_widgets import HOME_WIDGETS
import valhalla_admin.widgets
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView

@login_required
def home(request):
    modules = [widget(request) for widget in HOME_WIDGETS]
    return render(request, "home.html", {"modules": modules})

class AdminLogin(LoginView):
    template_name = "admin/login.html"  # utiliser le thème admin
    redirect_authenticated_user = True

    def get_success_url(self):
        # Toujours rediriger vers /
        return "/"
