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

class GenerateTokenView(views.APIView):
    permission_classes = [IsAuthenticated, IsAdminRegistrar, IsNotKiosk]
    def post(self, request):
        config = ElectionConfig.load()
        if not config.is_open():
            return Response({"error": "Election is closed."}, status=403)
        voter_id = request.data.get('voter_id')
        try:
            voter = Voter.objects.get(id=voter_id)
            if voter.has_voted:
                return Response({"error": "Already voted."}, status=400)
            VotingToken.objects.filter(voter=voter).delete()
            token_code = ''.join(random.choices(string.digits, k=6))
            expiry = timezone.now() + timedelta(minutes=5)
            VotingToken.objects.create(token=token_code, voter=voter, expires_at=expiry)
            return Response({"token": token_code, "student_name": voter.name}, status=201)
        except Voter.DoesNotExist:
            return Response({"error": "Not found."}, status=404)

class ValidateTokenView(views.APIView):
    def post(self, request):
        token_str = request.data.get('token')
        try:
            vt = VotingToken.objects.get(token=token_str)
            if not vt.is_valid(): return Response({"error": "Invalid"}, status=403)
            positions = Position.objects.all().order_by('order')
            ballot_data = []
            for pos in positions:
                ballot_data.append({
                    'id': pos.id,
                    'title': pos.title,
                    'candidates': [{'id': c.id, 'name': c.name} for c in pos.candidates.all()]
                })
            return Response({"valid": True, "student_name": vt.voter.name, "ballot": ballot_data}, status=200)
        except VotingToken.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

class SubmitVoteView(views.APIView):
    @method_decorator(election_open_required)
    def post(self, request):
        token_str = request.data.get('token')
        selections = request.data.get('selections')
        try:
            with transaction.atomic():
                vt = VotingToken.objects.select_for_update().get(token=token_str)
                if not vt.is_valid(): return Response({"error": "Invalid"}, status=403)
                for cand_id in selections:
                    c = Candidate.objects.get(id=cand_id)
                    Vote.objects.create(candidate=c, position=c.position)
                vt.voter.has_voted = True
                vt.voter.save()
                vt.used = True
                vt.save()
                return Response({"message": "Success"}, status=200)
        except Exception as e: return Response({"error": str(e)}, status=500)

@login_required
def officer_dashboard(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    voters = Voter.objects.all()
    return render(request, 'dashboard.html', {'voters': voters})

@login_required
def manage_candidates(request):
    if is_kiosk(request.user): return redirect('kiosk_entry')
    if request.method == "POST":
        action = request.POST.get('action')
        if action == "add_position":
            Position.objects.create(title=request.POST.get('title'))
        elif action == "add_candidate":
            pos = Position.objects.get(id=request.POST.get('position_id'))
            Candidate.objects.create(name=request.POST.get('name'), position=pos)
        return redirect('manage_candidates')
    return render(request, 'manage_candidates.html', {
        'positions': Position.objects.all().order_by('order'),
        'candidates': Candidate.objects.all()
    })

def election_results(request):
    config = ElectionConfig.load()
    positions = Position.objects.prefetch_related('candidates').all().order_by('order')
    results_data = []
    for pos in positions:
        total = Vote.objects.filter(position=pos).count()
        cand_list = []
        for cand in pos.candidates.all():
            count = Vote.objects.filter(candidate=cand).count()
            cand_list.append({'name': cand.name, 'votes': count})
        results_data.append({'title': pos.title, 'candidates': cand_list, 'total_votes': total})
    return render(request, 'results.html', {'results': results_data, 'config': config})

@login_required
@user_passes_test(is_kiosk)
def kiosk_entry(request): return render(request, 'kiosk_entry.html')

def ballot_view(request): return render(request, 'ballot.html')

def smart_home_redirect(request):
    if 'Kiosk_Stations' in request.user.groups.values_list('name', flat=True):
        return redirect('kiosk_entry')
    return redirect('officer_dashboard')