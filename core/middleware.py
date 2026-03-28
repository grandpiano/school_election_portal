from django.shortcuts import redirect
from django.urls import resolve

class KioskSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.groups.filter(name='Kiosk_Stations').exists():
            # These are the ONLY names a Kiosk user is allowed to resolve
            allowed_url_names = [
                'kiosk_entry', 
                'ballot_view', 
                'vote_success',
                'validate_token', 
                'submit_vote', 
                'logout', 
                'login', 
                'root_redirect' # This is the crucial one!
            ]
            
            try:
                current_url_name = resolve(request.path_info).url_name
                if current_url_name not in allowed_url_names:
                    return redirect('kiosk_entry')
            except:
                return redirect('kiosk_entry')

        return self.get_response(request)