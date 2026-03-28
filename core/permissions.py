from rest_framework import permissions

class IsCommissioner(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.groups.filter(name='Commissioner Head').exists() or request.user.is_superuser
        )

class IsAdminRegistrar(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.groups.filter(name='Admin Registrar').exists() or request.user.is_superuser
        )

class IsObserver(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.groups.filter(name='Observer').exists() or request.user.is_superuser
        )
    
class IsNotKiosk(permissions.BasePermission):
    """
    Task 5: Prevents Kiosk users from accessing specific API endpoints 
    even if they are authenticated.
    """
    def has_permission(self, request, view):
        return not request.user.groups.filter(name='Kiosk_Stations').exists()