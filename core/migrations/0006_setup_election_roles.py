from django.db import migrations

def create_election_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    
    roles_permissions = {
        'Commissioner Head': [
            'add_candidate', 'change_candidate', 'delete_candidate', 'view_candidate',
            'add_position', 'change_position', 'delete_position', 'view_position',
            'view_voter', 'view_votingtoken'
        ],
        'Admin (Registrar)': [
            'add_voter', 'change_voter', 'view_voter',
            'add_student_id', 'view_student_id'
        ],
        'Student Director': [
            'view_candidate', 'view_position', 
            'add_votingtoken', 'view_votingtoken'
        ],
        'Observer': [
            'view_candidate', 'view_position', 'view_voter'
        ],
    }

    for role_name, perms in roles_permissions.items():
        group, created = Group.objects.get_or_create(name=role_name)
        for perm_code in perms:
            try:
                permission = Permission.objects.get(codename=perm_code)
                group.permissions.add(permission)
            except Permission.DoesNotExist:
                continue

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_remove_candidate_photo_candidate_photo_url'),
    ]

    operations = [
        migrations.RunPython(create_election_roles),
    ]