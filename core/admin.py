from django.contrib import admin
from .models import Position, Candidate, Voter, VotingToken, Vote, AuditLog, ElectionConfig

# Standard Model Registrations
admin.site.register(Position)
admin.site.register(Candidate)
admin.site.register(Voter)
admin.site.register(VotingToken)
admin.site.register(Vote)
admin.site.register(AuditLog)

@admin.register(ElectionConfig)
class ElectionConfigAdmin(admin.ModelAdmin):
    """
    Singleton Admin: Ensures only one Election Configuration can exist.
    This keeps the Developer and Commissioner in perfect sync.
    """
    list_display = ('title', 'start_time', 'end_time', 'results_certified', 'certified_at')
    
    def has_add_permission(self, request):
        # If a configuration already exists, hide the 'Add' button
        if ElectionConfig.objects.exists():
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion to avoid system-wide crashes
        return False

    # Optional: Make results_certified read-only in admin so it must be done via the front-end process
    readonly_fields = ('certified_at',)