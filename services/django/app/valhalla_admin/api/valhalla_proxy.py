from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from valhalla_admin.graph.models import BuildTask
import requests

@method_decorator(csrf_exempt, name='dispatch')
class ValhallaProxyView(View):
    """
    Proxy toutes les requêtes Valhalla (route, isochrone, etc.) vers le bon conteneur selon l'alias de graph.
    """
    def dispatch(self, request, *args, **kwargs):
        graph_alias = kwargs.get('graph_alias')
        # Chercher le port du conteneur Valhalla pour ce graph
        try:
            task = BuildTask.objects.get(name=graph_alias, is_serving=True)
            port = task.serve_port
            if not port:
                return JsonResponse({'error': 'Aucun port Valhalla pour ce graph'}, status=502)
        except BuildTask.DoesNotExist:
            return JsonResponse({'error': 'Graph non trouvé ou non servi'}, status=404)

        # Reconstituer l'URL cible
        path = kwargs.get('path', '')
        url = f"http://host.docker.internal:{port}/{path}"
        if request.META.get('QUERY_STRING'):
            url += '?' + request.META['QUERY_STRING']

        # Proxy la requête (GET, POST, etc.)
        try:
            resp = requests.request(
                method=request.method,
                url=url,
                headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                data=request.body if request.body else None,
                stream=True,
                timeout=60
            )
        except requests.RequestException as e:
            return JsonResponse({'error': f'Erreur proxy Valhalla: {str(e)}'}, status=502)

        # Réponse streaming (pour gros résultats)
        proxy_response = StreamingHttpResponse(
            resp.raw.stream(decode_content=False),
            status=resp.status_code
        )
        for k, v in resp.headers.items():
            if k.lower() != 'transfer-encoding':
                proxy_response[k] = v
        return proxy_response
