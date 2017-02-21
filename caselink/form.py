from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from .models import WorkItem

def assignee_list():
    assignees = settings.CASELINK_MEMBERS.split()
    for assignee in assignees:
        yield (assignee, assignee)

class MaitaiAutomationRequest(forms.Form):
    """Form for MaitaiAutomationRequest. """
    workitems = forms.CharField(
        label='Manual cases(Workitems)', max_length=1023, required=True)
    assignee = forms.ChoiceField(
        label='Assignee on JIRA', required=True, choices=assignee_list,
        initial=settings.CASELINK_DEFAULT_ASSIGNEE)
    labels = forms.CharField(
        label='Labels on JIRA, split by comma', max_length=1023, required=False,
        initial=settings.CASELINK_MAITAI['DEFAULT_LABEL'])
    parent_issue = forms.CharField(
        label='Parent on JIRA, default is None', max_length=1023, required=False,
        initial=settings.CASELINK_MAITAI['PARENT_ISSUE'])

    def clean(self):
        cleaned_data = super(MaitaiAutomationRequest, self).clean()
        labels = cleaned_data.get("labels")
        workitems = cleaned_data.get("workitems")

        for workitem in workitems.split():
            try:
                wi = WorkItem.objects.get(id=workitem)
                if wi.maitai_id:
                    self.add_error('workitems', '%s already have a pending request' % workitem)
            except ObjectDoesNotExist:
                self.add_error('workitems', '%s is not a valid workitem id' % workitem)


        if " " in labels:
            msg = "Space not allowed in labels."
            self.add_error('labels', msg)
