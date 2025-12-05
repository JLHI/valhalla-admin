# Registre global pour stocker les widgets
#home_widgets.py
HOME_WIDGETS = []

def register_widget(func):
    """Décorateur pour enregistrer un widget de dashboard."""
    HOME_WIDGETS.append(func)
    return func

