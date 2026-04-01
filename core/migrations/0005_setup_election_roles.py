from django.db import migrations

def create_election_roles(apps, schema_editor):
    # We get the models dynamically to ensure they exist during migration
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    
    # Define your roles and the exact permission codenames
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
        # Create the group if it doesn't exist
        group, created = Group.objects.get_or_create(name=role_name)
        
        for perm_code in perms:
            # We look for the permission by codename only
            # This is safer across different database environments
            perm = Permission.objects.filter(codename=perm_code).first()
            if perm:
                group.permissions.add(perm)

class Migration(migrations.Migration):

    dependencies = [
        # FIXED: Points to the actual last file in your folder
        ('core', '0004_alter_position_order'),
    ]

    operations = [
        # We add a second argument: migrations.RunPython.noop 
# This tells Django: "If you need to go backwards, just do nothing."
        # Change the existing line to add the reverse_code part
migrations.RunPython(create_election_roles, reverse_code=migrations.RunPython.noop),
    ]

    