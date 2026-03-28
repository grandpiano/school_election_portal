import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'udes.settings') # Ensure 'udes' matches your project folder name
django.setup()

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

def setup_udes():
    print("🚀 Starting UDES Role & Permission Setup...")

    groups_config = {
        'Commissioner Head': {
            'models': ['candidate', 'position', 'electionconfig', 'vote', 'auditlog', 'voter'],
            'actions': ['add', 'change', 'delete', 'view']
        },
        'Admin Registrar': {
            'models': ['voter', 'votingtoken', 'auditlog'],
            'actions': ['add', 'change', 'view']
        },
        'Student Director': {
            'models': ['auditlog', 'voter', 'vote', 'candidate'],
            'actions': ['view']
        },
        'Observer': {
            'models': ['vote', 'candidate', 'position', 'electionconfig'],
            'actions': ['view']
        },
        'Kiosk_Stations': {
            'models': [], # Task 4/5: Handled by Middleware and internal Logic
            'actions': []
        }
    }

    for group_name, config in groups_config.items():
        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            print(f"✅ Created Group: {group_name}")
        else:
            print(f"🔄 Group already exists: {group_name}")

        # Clear existing permissions to avoid duplicates during updates
        group.permissions.clear()

        for model_name in config['models']:
            for action in config['actions']:
                codename = f"{action}_{model_name}"
                try:
                    perm = Permission.objects.get(codename=codename)
                    group.permissions.add(perm)
                except Permission.DoesNotExist:
                    print(f"⚠️  Warning: Permission {codename} not found.")

    print("\n✨ UDES Role System is now synchronized and secure.")

if __name__ == "__main__":
    setup_udes()