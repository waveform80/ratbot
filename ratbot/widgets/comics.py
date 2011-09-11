# -*- coding: utf-8 -*-
"""Comic Forms"""

from tw.forms import TableForm, CalendarDatePicker, CalendarDateTimePicker, Spacer, SingleSelectField, TextField, TextArea, FileField, HiddenField
from tw.forms.validators import Int, NotEmpty, DateConverter, DateTimeConverter
from tg import url

__all__ = ['new_page_form', 'new_comic_form', 'alter_comic_form']

class ComicForm(TableForm):
    show_errors = True
    fields = [
        HiddenField('old_id'),
        TextField('id', validator=NotEmpty, label_text='ID', help_text='Specify a unique ID for the comic'),
        TextField('title', validator=NotEmpty, label_text='Title', help_text='Specify the title for the comic'),
        Spacer(),
        TextArea('description', validator=NotEmpty, label_text='Description', help_text='Specify the description for the comic'),
    ]

class NewPageForm(TableForm):
    show_errors = True
    fields = [
        SingleSelectField('comic_id', validator=NotEmpty, label_text='Comic', help_text='Please select a comic'),
        TextField('issue_number', validator=Int, label_text='Issue #', help_text='Please enter an issue number'),
        TextField('number', validator=Int, label_text='Page #', help_text='Please enter a page number'),
        Spacer(),
        CalendarDateTimePicker('published', validator=DateTimeConverter, help_text='Please enter the date to publish the page'),
        Spacer(),
        FileField('vector', help_text='Please specify the filename of the vector (SVG) variant of the page'),
        FileField('bitmap', help_text='Please specify the filename of the bitmap (PNG) variant of the page'),
    ]

new_comic_form = ComicForm('new_comic_form', action=url('/comics/create_comic'))
alter_comic_form = ComicForm('alter_comic_form', action=url('/comics/update_comic'))
new_page_form = NewPageForm('new_page_form', action=url('/comics/create_page'))
