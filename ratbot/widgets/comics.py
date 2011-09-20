# -*- coding: utf-8 -*-
"""Comic Forms"""

from tw.forms import TableForm, CalendarDatePicker, CalendarDateTimePicker, Spacer, SingleSelectField, TextField, TextArea, FileField, HiddenField
from tw.forms.validators import Int, NotEmpty, DateConverter, DateTimeConverter
from tg import url

__all__ = ['new_page_form', 'new_comic_form', 'alter_comic_form', 'new_issue_form', 'alter_issue_form']

class ComicForm(TableForm):
    show_errors = True
    hover_help = True
    fields = [
        HiddenField('old_id'),
        TextField('id', size=10, validator=NotEmpty, label_text='ID', help_text='Specify a unique ID for the comic'),
        Spacer(),
        TextField('title', size=50, validator=NotEmpty, label_text='Title', help_text='Specify the title for the comic'),
        TextArea('description', validator=NotEmpty, label_text='Description', help_text='Specify the description for the comic'),
    ]

class IssueForm(TableForm):
    show_errors = True
    hover_help = True
    fields = [
        HiddenField('old_comic'),
        HiddenField('old_number'),
        SingleSelectField('comic_id', validator=NotEmpty, label_text='Comic', help_text='Select the comic the issue belongs to'),
        TextField('number', size=4, validator=Int, label_text='Issue #', help_text='Specify the issue number'),
        Spacer(),
        TextField('title', size=50, validator=NotEmpty, label_text='Title', help_text='Specify the title for the issue'),
        TextArea('description', validator=NotEmpty, label_text='Description', help_text='Specify the description for the issue'),
    ]

class NewPageForm(TableForm):
    show_errors = True
    hover_help = True
    fields = [
        SingleSelectField('comic_id', validator=NotEmpty, label_text='Comic', help_text='Please select a comic'),
        TextField('issue_number', size=4, validator=Int, label_text='Issue #', help_text='Please enter an issue number'),
        TextField('number', size=4, validator=Int, label_text='Page #', help_text='Please enter a page number'),
        Spacer(),
        CalendarDateTimePicker('published', validator=DateTimeConverter, help_text='Please enter the date and time to publish the page'),
        Spacer(),
        FileField('vector', help_text='Please specify the filename of the vector (SVG) variant of the page'),
        FileField('bitmap', help_text='Please specify the filename of the bitmap (PNG) variant of the page'),
    ]

new_comic_form = ComicForm('new_comic_form', action=url('/admin/insert_comic'))
new_issue_form = IssueForm('new_issue_form', action=url('/admin/insert_issue'))
new_page_form = NewPageForm('new_page_form', action=url('/admin/insert_page'))
alter_comic_form = ComicForm('alter_comic_form', action=url('/admin/update_comic'))
alter_issue_form = IssueForm('alter_issue_form', action=url('/admin/update_issue'))
