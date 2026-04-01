import csv
import io
import random
import string
from datetime import timedelta

from django.db import transaction, models
from django.db.models import Count, Q
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator

from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Voter, VotingToken, Position, Candidate, Vote, AuditLog, ElectionConfig
from .serializers import (
    VoterSerializer, 
    CandidateSerializer, 
    PositionSerializer, 
    TokenValidationSerializer,
    VoteSubmissionSerializer
)
from .permissions import IsCommissioner, IsAdminRegistrar, IsObserver, IsNotKiosk

# ==========================================
# GUARDS & HELPERS
# ==========================================

def is_kiosk(user):
    return user.groups.filter(name='Kiosk_Stations').exists()

def is_commissioner_check(user):
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
    permission_classes = [IsAuthenticated, IsAdminRegistrar, IsNotKiosk]
    
    def post(self, request):
        config = ElectionConfig.load()
        
        if not config.start_time or not config.end_time:
            return Response({"error": "Election configuration incomplete."}, status=400)

        if not config.is_open():
            return Response({"error": "Election is closed."}, status=403)

        voter_id = request.data.get('voter_id')
        
        try:
            voter = Voter.objects.get(id=voter_id)
            if voter.has_voted:
                return Response({"error": "This student has already voted."}, status=400)

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
            }, status=201)

        except Voter.DoesNotExist:
            return Response({"error": "Voter ID not found."}, status=404)

class ValidateTokenView(views.APIView):
    def post(self, request):
        serializer = TokenValidationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": "Invalid format."}, status=400)

        token_str = serializer.validated_data['token']
        config = ElectionConfig.load()
        if not config.is_open():
            return Response({"error": "Election is closed."}, status=403)

        try:
            vt = VotingToken.objects.get(token=token_str)
            if not vt.is_valid():
                return Response({"error": "Token expired or used."}, status=403)

            positions = Position.objects.all().order_by('order')
            ballot_data = []
            for pos in positions:
                cand_list = []
                for cand in pos.candidates.all():
                    cand_list.append({
                        'id': cand.id,
                        'name': cand.name,
                        'photo_url': cand.photo_url if cand.photo_url else 'https://via.placeholder.com/400x300?text=No+Photo'
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
                vt = VotingToken.objects.select_for_update().get(token=token_str)
                if not vt.is_valid():
                    return Response({"error": "Token invalid."}, status=403)

                for cand_id in selections:
                    candidate = Candidate.objects.get(id=cand_id)
                    Vote.objects.create(candidate=candidate, position=candidate.position)

                vt.voter.has_voted = True
                vt.voter.save()
                vt.used = True
                vt.save()

                return Response({"message": "Vote cast successfully!"}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class ElectionStatsView(views.APIView):
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
        }, status=200)

# ==========================================
# DASHBOARDS & MANAGEMENT
# ==========================================

@login_required
def officer_dashboard(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
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
    if is_kiosk(request.user): return redirect('kiosk_entry')
    if request.method == "POST":
        action = request.POST.get('action')
        if action == "single_entry":
            student_id = request.POST.get('student_id')
            name = request.POST.get('full_name')
            dept = request.POST.get('department')
            Voter.objects.get_or_create(student_id=student_id, defaults={'name': name, 'department': dept})
        elif action == "bulk_import" and request.FILES.get('csv_file'):
            csv_file = request.FILES['csv_file']
            data_set = csv_file.read().decode('UTF-8')
            io_string = io.StringIO(data_set)
            next(io_string)
            voters_to_create = [
                Voter(student_id=row[0].strip(), name=row[1].strip(), department=row[2].strip())
                for row in csv.reader(io_string, delimiter=',', quotechar='"') if len(row) >= 3
            ]
            Voter.objects.bulk_create(voters_to_create, ignore_conflicts=True)
        return redirect('voter_registry')

    voters = Voter.objects.all().order_by('name')
    return render(request, 'voter_registry.html', {'voters': voters})

@login_required
def manage_candidates(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    if request.method == "POST":
        action = request.POST.get('action')
        if action == "add_position":
            Position.objects.create(title=request.POST.get('title'))
        elif action == "add_candidate":
            pos = Position.objects.get(id=request.POST.get('position_id'))
            Candidate.objects.create(
                name=request.POST.get('name'), 
                position=pos, 
                photo_url=request.POST.get('photo_url') # Using URL instead of File
            )
        return redirect('manage_candidates')

    return render(request, 'manage_candidates.html', {
        'positions': Position.objects.all().order_by('order'),
        'candidates': Candidate.objects.all()
    })

# ==========================================
# RESULTS & REPORTS
# ==========================================

def election_results(request):
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
            cand_list.append({
                'name': cand.name,
                'votes': vote_count,
                'percentage': round(perc, 1),
                'photo_url': cand.photo_url # Correct field reference
            })
        results_data.append({
            'id': pos.id, 
            'title': pos.title, 
            'candidates': sorted(cand_list, key=lambda x: x['votes'], reverse=True),
            'total_votes': total_pos_votes
        })

    context = {
        'results': results_data,
        'config': config,
        'election_has_ended': election_has_ended,
        'is_commissioner': is_commissioner_check(request.user),
    }
    return render(request, 'results.html', context)

@login_required
@user_passes_test(is_commissioner_check)
def certify_results(request):
    config = ElectionConfig.load()
    if timezone.now() >= config.end_time:
        config.results_certified = True
        config.certified_at = timezone.now()
        config.save()
        messages.success(request, "Election Certified.")
    return redirect('election_results')

# ==========================================
# KIOSK & SYSTEM
# ==========================================

@login_required
@user_passes_test(is_kiosk)
def kiosk_entry(request): 
    return render(request, 'kiosk_entry.html')

def ballot_view(request): 
    return render(request, 'ballot.html')

def smart_home_redirect(request):
    if not request.user.is_authenticated: return redirect('login') 
    user_groups = request.user.groups.values_list('name', flat=True)
    if 'Kiosk_Stations' in user_groups: return redirect('kiosk_entry')
    return redirect('officer_dashboard')

@login_required
def system_logs(request):
    logs = AuditLog.objects.all().order_by('-timestamp')[:100]
    return render(request, 'system_logs.html', {'logs': logs})