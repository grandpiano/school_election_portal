from rest_framework import serializers
from .models import Voter, Candidate, Position

class CandidateSerializer(serializers.ModelSerializer):
    # This maps 'manifesto' from models to 'bio' for the JavaScript template
    bio = serializers.CharField(source='manifesto', read_only=True)
    
    class Meta:
        model = Candidate
        fields = ['id', 'name', 'photo', 'bio']

class PositionSerializer(serializers.ModelSerializer):
    candidates = CandidateSerializer(many=True, read_only=True)

    class Meta:
        model = Position
        fields = ['id', 'title', 'candidates']

class VoterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voter
        fields = ['id', 'student_id', 'name', 'department', 'has_voted']

from rest_framework import serializers
from .models import Voter, Candidate, Position, VotingToken

class TokenValidationSerializer(serializers.Serializer):
    # Ensure this matches exactly what the frontend JS sends
    token = serializers.CharField(max_length=6, min_length=6)

class VoteSubmissionSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=6)
    selections = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )