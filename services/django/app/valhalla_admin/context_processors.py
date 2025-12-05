from django.conf import settings

def global_settings(request):
    return {
        "SITEWEBNAME": getattr(settings, "SITEWEBNAME", "Valhalla"),
    }