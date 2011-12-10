# -*- coding: utf-8 -*-
"""Comic Forms"""

from tw.forms import TableForm, CalendarDatePicker, CalendarDateTimePicker, Spacer, SingleSelectField, TextField, TextArea, FileField, HiddenField
from tw.forms.validators import Int, NotEmpty, DateConverter, DateTimeConverter
from tg import url

__all__ = ['new_page_form', 'alter_page_form', 'new_comic_form', 'alter_comic_form', 'new_issue_form', 'alter_issue_form']


class NewsForm(TableForm):
    show_errors = True
    hover_help = True
    fields = [
        HiddenField('id'),
        TextField('title', size=20, validator=NotEmpty, label_text='Title', help_text='Specify a title for the entry'),
        Spacer(),
        CalendarDateTimePicker('published', validator=DateTimeConverter, help_text='Specify the date and time to publish the entry'),
        TextArea('content', validator=NotEmpty, label_text='Content (HTML)', help_text='Specify the content of the entry - you may use HTML here'),
    ]

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
        Spacer(),
        FileField('archive', label_text='Archive', help_text='Select the file containing the archive of the issue (optional - will be generated from page bitmaps if unspecified'),
        FileField('pdf', label_text='PDF', help_text='Select the PDF file of the issue (optional - will be generated from the page vectors if unspecified'),
    ]

class PageForm(TableForm):
    show_errors = True
    hover_help = True
    fields = [
        SingleSelectField('comic_id', validator=NotEmpty, label_text='Comic', help_text='Select the comic the page belongs to'),
        TextField('issue_number', size=4, validator=Int, label_text='Issue #', help_text='Specify the issue number the page belongs to'),
        TextField('number', size=4, validator=Int, label_text='Page #', help_text='Specify the page number'),
        Spacer(),
        CalendarDateTimePicker('published', validator=DateTimeConverter, help_text='Select the date and time to publish the page'),
        Spacer(),
        FileField('vector', label_text='Vector Image', help_text='Select the file containing the vector (SVG) image of the page'),
        FileField('bitmap', label_text='Bitmap Image', help_text='Select the file containing the bitmap (PNG) image of the page (optional - will be generated from the vector if unspecified'),
        FileField('thumbnail', label_text='Thumbnail Image', help_text='Select the file containing the thumbnail (PNG) image of the page (optional - will be generated from the bitmap if unspecified'),
    ]

new_news_form = NewsForm('new_news_form', action=url('/admin/insert_news'))
new_comic_form = ComicForm('new_comic_form', action=url('/admin/insert_comic'))
new_issue_form = IssueForm('new_issue_form', action=url('/admin/insert_issue'))
new_page_form = PageForm('new_page_form', action=url('/admin/insert_page'))
alter_news_form = NewsForm('alter_news_form', action=url('/admin/update_news'))
alter_comic_form = ComicForm('alter_comic_form', action=url('/admin/update_comic'))
alter_issue_form = IssueForm('alter_issue_form', action=url('/admin/update_issue'))
alter_page_form = PageForm('alter_page_form', action=url('/admin/update_page'))
