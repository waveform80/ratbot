"""Administration Forms"""

from tw.forms import TableForm, CalendarDatePicker, CalendarDateTimePicker, Spacer, SingleSelectField, TextField, TextArea, FileField, HiddenField, PasswordField, MultipleSelectField
from tw.forms.validators import Int, NotEmpty, DateConverter, DateTimeConverter
from tg import url

__all__ = ['new_user_form', 'new_group_form', 'new_permission_form', 'alter_user_form', 'alter_group_form', 'alter_permission_form']

class UserForm(TableForm):
    show_errors = True
    hover_help = True
    fields = [
        HiddenField('old_id'),
        TextField('user_name', size=20, validator=NotEmpty, label_text='Username', help_text='Specify a unique name for the user'),
        Spacer(),
        TextField('email_address', size=50, validator=NotEmpty, label_text='E-mail', help_text='Specify a unique e-mail address for the user'),
        TextField('display_name', size=50, validator=NotEmpty, label_text='Full name', help_text='Specify the full name of the user'),
        PasswordField('password', size=20, label_text='Password', help_text="Reset the user's password"),
        MultipleSelectField('group_names', size=5, label_text='Groups', help_text='Select the groups this user belongs to'),
    ]

class GroupForm(TableForm):
    show_errors = True
    hover_help = True
    fields = [
        HiddenField('old_id'),
        TextField('group_name', size=20, validator=NotEmpty, label_text='Group name', help_text='Specify a unique name for the group'),
        Spacer(),
        TextField('display_name', size=50, validator=NotEmpty, label_text='Display name', help_text='Specify a display name for the group'),
        MultipleSelectField('user_names', size=5, label_text='Users', help_text='Select the users that belong to this group'),
        MultipleSelectField('permission_names', size=5, label_text='Permissions', help_text='Select the permissions associated with this group'),
    ]

class PermissionForm(TableForm):
    show_errors = True
    hover_help = True
    fields = [
        HiddenField('old_id'),
        TextField('permission_name', size=20, validator=NotEmpty, label_text='Permission name', help_text='Specify a unique name for the permission'),
        Spacer(),
        TextField('description', size=50, validator=NotEmpty, label_text='Description', help_text='Specify a description for the permission'),
        MultipleSelectField('group_names', size=5, label_text='Groups', help_text='Select the groups that are associated with this permission'),
    ]

new_user_form = UserForm('new_user_form', action=url('/admin/insert_user'))
new_group_form = GroupForm('new_group_form', action=url('/admin/insert_group'))
new_permission_form = PermissionForm('new_permission_form', action=url('/admin/insert_permission'))
alter_user_form = UserForm('alter_user_form', action=url('/admin/update_user'))
alter_group_form = GroupForm('alter_group_form', action=url('/admin/update_group'))
alter_permission_form = PermissionForm('alter_permission_form', action=url('/admin/update_permission'))
