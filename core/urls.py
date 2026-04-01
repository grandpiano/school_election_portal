from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    officer_dashboard, kiosk_entry, ballot_view, 
    election_results, voter_registry, system_logs, manage_candidates,
    GenerateTokenView, ValidateTokenView, SubmitVoteView, ElectionStatsView,
    certify_results, smart_home_redirect
)

urlpatterns = [
    # Main Dashboards & Redirects
    path('', smart_home_redirect, name='root_redirect'),
    path('dashboard/', officer_dashboard, name='officer_dashboard'),
    path('voter-registry/', voter_registry, name='voter_registry'),
    path('results/', election_results, name='election_results'),
    path('logs/', system_logs, name='system_logs'),
    path('manage-candidates/', manage_candidates, name='manage_candidates'),
    
    # Kiosk URLs
    path('kiosk/', kiosk_entry, name='kiosk_entry'),
    path('kiosk/ballot/', ballot_view, name='ballot_view'),
    # If you need a separate success page, keep this but ensure 
    # it points to a template or a view in your views.py
    path('kiosk/success/', ballot_view, name='vote_success'), 

    # API Endpoints
    path('api/generate-token/', GenerateTokenView.as_view(), name='generate_token'),
    path('api/validate-token/', ValidateTokenView.as_view(), name='validate_token'),
    path('api/submit-vote/', SubmitVoteView.as_view(), name='submit_vote'),
    path('api/election-stats/', ElectionStatsView.as_view(), name='election_stats'),

    # Results & Certification
    path('results/certify/', certify_results, name='certify_results'),

    # Auth System
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]