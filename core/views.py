import csv
import io
import random
import string
import datetime
from datetime import timedelta
from functools import wraps

from django.db import transaction, models
from django.db.models import Count, Q
from django.utils import timezone  # Global import
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator

from rest_framework import status, views
from rest_framework.response import Response

from .models import Voter, VotingToken, Position, Candidate, Vote, AuditLog, ElectionConfig
from .serializers import (
    VoterSerializer, 
    CandidateSerializer, 
    PositionSerializer, 
    TokenValidationSerializer,
    VoteSubmissionSerializer
)
from rest_framework.permissions import IsAuthenticated
from .permissions import IsCommissioner, IsAdminRegistrar, IsObserver, IsNotKiosk

# Near the top of views.py
from .permissions import IsCommissioner, IsAdminRegistrar, IsObserver

# ==========================================
# GUARDS & HELPERS
# ==========================================

def is_kiosk(user):
    """Checks if the logged-in user belongs to the Kiosk group."""
    return user.groups.filter(name='Kiosk_Stations').exists()

def is_commissioner_check(user):
    """Helper function to check if the user is a Commissioner."""
    return user.is_superuser or user.groups.filter(name='Commissioner Head').exists()

def election_open_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        config = ElectionConfig.load()
        if not config.is_open():
            return Response({"error": "Election is currently closed."}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# ==========================================
# API VIEWS (Kiosk & Token Logic)
# ==========================================
class GenerateTokenView(views.APIView):
    # Task 5: Must be logged in AND must NOT be a Kiosk to generate tokens
    permission_classes = [IsAuthenticated, IsAdminRegistrar, IsNotKiosk]
    
    def post(self, request):
        config = ElectionConfig.load()
        
        if not config.start_time or not config.end_time:
            return Response({
                "error": "Election configuration is incomplete. Please set dates in the Control Panel."
            }, status=status.HTTP_400_BAD_REQUEST)

        if not config.is_open():
            return Response({
                "error": f"Election is closed. It is scheduled from {config.start_time.strftime('%H:%M')} to {config.end_time.strftime('%H:%M')}."
            }, status=status.HTTP_403_FORBIDDEN)

        voter_id = request.data.get('voter_id')
        
        try:
            voter = Voter.objects.get(id=voter_id)
            
            if voter.has_voted:
                return Response({"error": "This student has already cast their ballot."}, status=status.HTTP_400_BAD_REQUEST)

            VotingToken.objects.filter(voter=voter).delete()
            token_code = ''.join(random.choices(string.digits, k=6))
            expiry = timezone.now() + timedelta(minutes=5)

            VotingToken.objects.create(
                token=token_code, 
                voter=voter, 
                expires_at=expiry
            )

            AuditLog.objects.create(
                user=request.user.username, 
                action="TOKEN_GENERATED", 
                details={"student_id": voter.student_id, "voter_name": voter.name}
            )

            return Response({
                "token": token_code,
                "student_name": voter.name,
                "expires_at": expiry.strftime('%H:%M:%S')
            }, status=status.HTTP_201_CREATED)

        except Voter.DoesNotExist:
            return Response({"error": "Voter ID not found in registry."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Internal Server Error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Update 1: Change this inside your ValidateTokenView
class ValidateTokenView(views.APIView):
    def post(self, request):
        serializer = TokenValidationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({"error": "Invalid token format. Must be 6 digits."}, status=400)

        token_str = serializer.validated_data['token']
        config = ElectionConfig.load()
        if not config.is_open():
            return Response({"error": "The election is currently closed or not yet started."}, status=403)

        try:
            vt = VotingToken.objects.get(token=token_str)
            if not vt.is_valid():
                return Response({"error": "This token has expired or has already been used to vote."}, status=403)

            positions = Position.objects.all().order_by('order')
            
            # CUSTOM FIX: Manually build the ballot data to include the external photo URL
            ballot_data = []
            for pos in positions:
                cand_list = []
                for cand in pos.candidates.all():
                    # If 'photo' field contains a URL (like ImgBB), use it. 
                    # Otherwise, try to get the local file URL.
                    photo_url = str(cand.photo) if cand.photo else 'https://via.placeholder.com/400x300?text=No+Photo'
                    
                    cand_list.append({
                        'id': cand.id,
                        'name': cand.name,
                        'photo_url': photo_url 
                    })
                
                ballot_data.append({
                    'id': pos.id,
                    'title': pos.title,
                    'candidates': cand_list
                })
            
            return Response({
                "valid": True, 
                "student_name": vt.voter.name,
                "ballot": ballot_data
            }, status=200)

        except VotingToken.DoesNotExist:
            return Response({"error": "Token not found."}, status=404)
        except Exception as e:
            return Response({"error": f"Server Error: {str(e)}"}, status=500)
        
        
class SubmitVoteView(views.APIView):
    @method_decorator(election_open_required)
    def post(self, request):
        serializer = VoteSubmissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        token_str = serializer.validated_data['token']
        selections = serializer.validated_data['selections']

        try:
            with transaction.atomic():
                # Task 6 & 7: Strict token validation and immediate invalidation
                vt = VotingToken.objects.select_for_update().get(token=token_str)
                
                if not vt.is_valid():
                    return Response({"error": "Token expired or already used."}, status=403)

                for cand_id in selections:
                    candidate = Candidate.objects.get(id=cand_id)
                    Vote.objects.create(candidate=candidate, position=candidate.position)

                # Task 7: Invalidate immediately
                vt.voter.has_voted = True
                vt.voter.save()
                vt.used = True
                vt.save()

                return Response({"message": "Vote cast successfully!"}, status=200)
        except Exception as e:
            return Response({"error": "System Error: " + str(e)}, status=500)


class ElectionStatsView(views.APIView):
    # Task 5: Kiosk cannot view live stats
    permission_classes = [IsAuthenticated, (IsObserver | IsCommissioner), IsNotKiosk]
    
    def get(self, request):
        total_voters = Voter.objects.count()
        voted_count = Voter.objects.filter(has_voted=True).count()
        turnout_pct = (voted_count / total_voters * 100) if total_voters > 0 else 0
        active_tokens = VotingToken.objects.filter(used=False, expires_at__gt=timezone.now()).count()

        return Response({
            "total_registered": total_voters,
            "total_voted": voted_count,
            "turnout_percentage": round(turnout_pct, 2),
            "current_active_voters": active_tokens,
            "status": "In Progress"
        }, status=status.HTTP_200_OK)

# ==========================================
# DASHBOARDS & MANAGEMENT
# ==========================================

@login_required
def officer_dashboard(request):
    # REDIRECT KIOSK USERS: If a kiosk account accidentally tries to see the dashboard, send them back to vote.
    if is_kiosk(request.user):
        return redirect('kiosk_entry')

    query = request.GET.get('q')
    voters = Voter.objects.all()
    if query:
        voters = voters.filter(Q(student_id__icontains=query) | Q(name__icontains=query))
    
    total_registered = Voter.objects.count()
    voted_count = Voter.objects.filter(has_voted=True).count()
    turnout_pct = round((voted_count / total_registered * 100), 1) if total_registered > 0 else 0

    return render(request, 'dashboard.html', {
        'voters': voters, 'query': query, 'total_registered': total_registered,
        'voted_count': voted_count, 'turnout_pct': turnout_pct
    })

@login_required
def voter_registry(request):
    if is_kiosk(request.user): return redirect('kiosk_entry') # Kiosk safety
    
    if request.method == "POST":
        action = request.POST.get('action')
        if action == "single_entry":
            student_id = request.POST.get('student_id')
            name = request.POST.get('full_name')
            dept = request.POST.get('department')
            if not Voter.objects.filter(student_id=student_id).exists():
                Voter.objects.create(student_id=student_id, name=name, department=dept)
                messages.success(request, f"Voter {name} registered!")
            else:
                messages.error(request, "Student ID already exists.")

        elif action == "bulk_import" and request.FILES.get('csv_file'):
            csv_file = request.FILES['csv_file']
            try:
                data_set = csv_file.read().decode('UTF-8')
                io_string = io.StringIO(data_set)
                next(io_string) 
                voters_to_create = [
                    Voter(student_id=row[0].strip(), name=row[1].strip(), department=row[2].strip())
                    for row in csv.reader(io_string, delimiter=',', quotechar='"') if len(row) >= 3
                ]
                Voter.objects.bulk_create(voters_to_create, ignore_conflicts=True)
                messages.success(request, f'Imported {len(voters_to_create)} students!')
            except Exception as e:
                messages.error(request, f"File error: {str(e)}")

    query = request.GET.get('q', '')
    dept_filter = request.GET.get('dept', '')
    voters = Voter.objects.all().order_by('name')
    if query: voters = voters.filter(Q(student_id__icontains=query) | Q(name__icontains=query))
    if dept_filter: voters = voters.filter(department=dept_filter)

    return render(request, 'voter_registry.html', {
        'voters': voters,
        'voted_count': Voter.objects.filter(has_voted=True).count(),
        'remaining_count': Voter.objects.filter(has_voted=False).count(),
        'departments': Voter.objects.values_list('department', flat=True).distinct(),
        'current_dept': dept_filter, 'current_query': query
    })

@login_required
def manage_candidates(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    if request.method == "POST":
        action = request.POST.get('action')
        if action == "add_position":
            Position.objects.create(title=request.POST.get('title'))
        elif action == "add_candidate":
            pos = Position.objects.get(id=request.POST.get('position_id'))
            Candidate.objects.create(name=request.POST.get('name'), position=pos, photo=request.FILES.get('photo'))
        return redirect('manage_candidates')

    return render(request, 'manage_candidates.html', {
        'positions': Position.objects.all().order_by('order'),
        'candidates': Candidate.objects.all()
    })

# ==========================================
# REPORT CENTER & ANALYTICS
# ==========================================

@login_required
def report_center(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    departments = Voter.objects.values_list('department', flat=True).distinct().order_by('department')
    return render(request, 'report_center.html', {'departments': departments})

@login_required
def view_voter_registry(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    dept_name = request.GET.get('department')
    voters = Voter.objects.all().order_by('department', 'name')
    if dept_name: voters = voters.filter(department=dept_name)
    return render(request, 'reports/voter_list_view.html', {'voters': voters, 'selected_dept': dept_name})

@login_required
def view_candidate_dossier(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    candidates = Candidate.objects.all().order_by('position__title', 'name')
    return render(request, 'reports/candidate_view.html', {'candidates': candidates})

@login_required
def turnout_analytics(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    stats = Voter.objects.values('department').annotate(
        total=Count('id'),
        voted_count=Count('id', filter=Q(has_voted=True))
    )
    processed_stats = []
    for s in stats:
        pct = (s['voted_count'] / s['total'] * 100) if s['total'] > 0 else 0
        processed_stats.append({
            'department': s['department'], 'total': s['total'],
            'voted': s['voted_count'], 'percentage': round(pct, 1)
        })
    return render(request, 'reports/turnout_analytics.html', {'stats': processed_stats})

# ==========================================
# KIOSK VIEWS (Restricted)
# ==========================================

@login_required
@user_passes_test(is_kiosk)
def kiosk_entry(request): 
    """The landing page for the voting terminal after Commissioner login."""
    return render(request, 'kiosk_entry.html')

def ballot_view(request): return render(request, 'ballot.html')
def vote_success(request): return render(request, 'vote_success.html')

@login_required
def system_logs(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    logs = AuditLog.objects.all().order_by('-timestamp')[:100]
    return render(request, 'system_logs.html', {'logs': logs})

def election_results(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    config = ElectionConfig.load()
    current_server_time = timezone.now()
    election_has_ended = current_server_time > config.end_time
    
    positions = Position.objects.prefetch_related('candidates').all().order_by('order')
    results_data = []

    for pos in positions:
        total_pos_votes = Vote.objects.filter(candidate__position=pos).count()
        cand_list = []
        for cand in pos.candidates.all():
            vote_count = Vote.objects.filter(candidate=cand).count()
            perc = (vote_count / total_pos_votes * 100) if total_pos_votes > 0 else 0
            
            # CUSTOM FIX: Get the external URL string directly from the field
            photo_url = str(cand.photo) if cand.photo else None
            
            cand_list.append({
                'name': cand.name,
                'votes': vote_count,
                'percentage': round(perc, 1),
                'photo': photo_url
            })
        cand_list = sorted(cand_list, key=lambda x: x['votes'], reverse=True)
        results_data.append({
            'id': pos.id, 'title': pos.title, 'candidates': cand_list, 'total_votes': total_pos_votes
        })

    is_commissioner = (request.user.is_superuser or request.user.groups.filter(name='Commissioner Head').exists())

    context = {
        'results': results_data,
        'config': config,
        'election_has_ended': election_has_ended,
        'is_commissioner': is_commissioner,
        'server_time': current_server_time,
    }
    return render(request, 'results.html', context)

@login_required
@user_passes_test(is_commissioner_check)
def certify_results(request):
    if request.method == 'POST':
        config = ElectionConfig.load()
        if timezone.now() < config.end_time:
            messages.error(request, "Cannot certify: The election period is still active.")
            return redirect('election_results')

        config.results_certified = True
        config.certified_at = timezone.now()
        config.save()
        
        AuditLog.objects.create(
            user=request.user.username,
            action="ELECTION_CERTIFIED",
            details={"timestamp": str(config.certified_at), "title": config.title}
        )
        messages.success(request, f"Success! {config.title} has been officially certified.")
    return redirect('election_results')

@login_required
def download_certified_report(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    config = ElectionConfig.load()
    if not config.results_certified:
        messages.error(request, "Official certificates are only available after certification.")
        return redirect('election_results')

    positions = Position.objects.prefetch_related('candidates').all().order_by('order')
    results_data = []
    for pos in positions:
        winner = None
        max_votes = 0
        for cand in pos.candidates.all():
            count = Vote.objects.filter(candidate=cand).count()
            if count > max_votes:
                max_votes = count
                winner = cand.name
            elif count == max_votes and count > 0:
                winner = f"TIE: {winner} & {cand.name}"
        results_data.append({'title': pos.title, 'winner': winner, 'max_votes': max_votes})

    return render(request, 'reports/certified_results.html', {'config': config, 'results': results_data})


@login_required
def election_control_panel(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    is_commissioner = request.user.groups.filter(name='Commissioner Head').exists()
    if not (request.user.is_superuser or is_commissioner):
        messages.error(request, "Access denied.")
        return redirect('officer_dashboard')

    config = ElectionConfig.load()
    if request.method == 'POST':
        config.title = request.POST.get('title')
        config.start_time = request.POST.get('start_time')
        config.end_time = request.POST.get('end_time')
        config.save()
        
        AuditLog.objects.create(
            user=request.user.username, action="ELECTION_CONFIG_OVERRIDE",
            details={"new_title": config.title}
        )
        messages.success(request, "System synchronized.")
        return redirect('election_control_panel')

    context = {'config': config, 'is_active': config.is_open(), 'server_time': timezone.now()}
    return render(request, 'election_control.html', context)


@login_required
def export_voters_by_dept(request):
    """Direct CSV download of the voter registry."""
    if is_kiosk(request.user): 
        return redirect('kiosk_entry')
        
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="voters_2026.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Voter Name', 'Department', 'Has Voted'])
    
    for v in Voter.objects.all():
        writer.writerow([v.student_id, v.name, v.department, "Yes" if v.has_voted else "No"])
        
    return response

# views.py (Update your existing function)
from django.shortcuts import redirect

def smart_home_redirect(request):
    # 1. Force Login First
    if not request.user.is_authenticated:
        return redirect('login') 

    # 2. Get Group Names for easy checking
    user_groups = request.user.groups.values_list('name', flat=True)

    # 3. Kiosk Logic (High Priority)
    if 'Kiosk_Stations' in user_groups:
        return redirect('kiosk_entry')

    # 4. Commissioner / Staff / Superuser Logic
    # Send them to the main officer dashboard or a specific admin view
    if request.user.is_superuser or 'Commissioner Head' in user_groups or 'Admin Registrar' in user_groups:
        return redirect('officer_dashboard')

    # 5. Observer Logic
    if 'Observer' in user_groups:
        return redirect('election_results')

    # 6. Final Fallback
    return redirect('officer_dashboard')