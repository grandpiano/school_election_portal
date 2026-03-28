from django.urls import path
from core import views
from .views import (
    officer_dashboard, kiosk_entry, ballot_view, 
    election_results, voter_registry, system_logs, manage_candidates,
    GenerateTokenView, ValidateTokenView, SubmitVoteView, ElectionStatsView,
    view_voter_registry, view_candidate_dossier,
)
from django.urls import path
from django.contrib.auth import views as auth_views # Import Django's built-in auth views
from . import views

urlpatterns = [
    path('', views.smart_home_redirect, name='root_redirect'),

    # Main Dashboards
    path('dashboard/', views.officer_dashboard, name='officer_dashboard'),
    path('voter-registry/', views.voter_registry, name='voter_registry'),
    path('results/', views.election_results, name='election_results'),
    path('logs/', system_logs, name='system_logs'),
    path('manage-candidates/', manage_candidates, name='manage_candidates'),
    
    # Kiosk URLs
    path('kiosk/', views.kiosk_entry, name='kiosk_entry'),
    path('kiosk/ballot/', views.ballot_view, name='ballot_view'),
    path('kiosk/success/', views.vote_success, name='vote_success'),

    # API Endpoints
    path('api/generate-token/', GenerateTokenView.as_view(), name='generate_token'),
    path('api/validate-token/', views.ValidateTokenView.as_view(), name='validate_token'),
    path('api/submit-vote/', views.SubmitVoteView.as_view(), name='submit_vote'),
    path('api/election-stats/', ElectionStatsView.as_view(), name='election_stats'),

    # Report Center & Analytics
    path('reports/', views.report_center, name='report_center'),
    path('reports/turnout/', views.turnout_analytics, name='turnout_analytics'),
    
    # Voter Reports
    path('reports/voters/view/', view_voter_registry, name='view_voter_registry'),
    path('reports/voters-by-dept/', views.export_voters_by_dept, name='export_voters_by_dept'),
    
    # Candidate Reports
    path('reports/candidates-view/', view_candidate_dossier, name='export_candidate_dossier'),
    path('control-panel/', views.election_control_panel, name='election_control_panel'),

    # Results & Certification
    path('results/certify/', views.certify_results, name='certify_results'),
    path('results/report/', views.download_certified_report, name='download_certified_report'),

    # Auth System - MUST HAVE THE NAME 'login'
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]