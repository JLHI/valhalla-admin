from django.conf import settings

def global_settings(request):
    return {
        "SITEWEBNAME": getattr(settings, "SITEWEBNAME", "Valhalla"),
        "SYSTEM_TIMEZONE": getattr(settings, "TIME_ZONE", "Europe/Paris"),
    }