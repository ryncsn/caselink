from django.conf import settings


def settings_inject(request):
    return {
        'POLARION_DEFAULT_PROJECT': settings.CASELINK_POLARION['PROJECT'],
        'POLARION_URL': settings.CASELINK_POLARION['URL'],
        'MAITAI_URL': settings.CASELINK_MAITAI['SERVER'],
        'JIRA_URL': settings.CASELINK_JIRA['SERVER'],
        'CASELINK_MEMBERS': settings.CASELINK_MEMBERS,
        'CASELINK_DEFAULT_ASSIGNEE': settings.CASELINK_DEFAULT_ASSIGNEE,
    }
