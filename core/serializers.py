from rest_framework import serializers
from .models import Voter, Candidate, Position, VotingToken

class CandidateSerializer(serializers.ModelSerializer):
    # Maps 'manifesto' to 'bio' for the JS template
    bio = serializers.CharField(source='manifesto', read_only=True)
    
    class Meta:
        model = Candidate
        # CRITICAL: 'photo_url' must be in this list
        fields = ['id', 'name', 'photo_url', 'bio']

class PositionSerializer(serializers.ModelSerializer):
    candidates = CandidateSerializer(many=True, read_only=True)

    class Meta:
        model = Position
        fields = ['id', 'title', 'candidates']

class VoterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voter
        fields = ['id', 'student_id', 'name', 'department', 'has_voted']

class TokenValidationSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=6, min_length=6)

class VoteSubmissionSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=6)
    selections = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )