from __future__ import absolute_import
import re

from jira import JIRA
from django.conf import settings

UPDATED_PATTERN_REGEX = (
    ".*?"
    "\s*Pull Requests:(\s*?)\n"
    "(?P<prs>(:?\s*http\S+?\s*?\n)+)"
    "\s*Auto Cases:(\s*?)\n"
    "(?P<cases>(:?\s*[a-zA-Z0-9_\.]+\s*?(\n|$))+)"
    ".*"
)

AUTOMATION_REQUEST_DESCRIPTION = """
Please automate this manual test case:
*[{polarion_wi_id}|{polarion_wi_url}]* {polarion_wi_title}

 ----

When you finished the automation, please comment this issue with following format before marking this issue as *Done*:

{{code:java}}Pull Requests:
https://github.com/autotest/tp-libvirt/pull/831
https://github.com/avocado-framework/avocado-vt/pull/630
Auto Cases:
conf_file.libvirtd_conf.unix_sock
conf_file..disable_bypass_cache
{{code}}

If you think this test case can't be automated, please reject this issue by clicking *Reject* button above.
If only part of this test case can be automated, please discuss with manual members to on whether to change existing case,
or split non-automatable part out to another test case before proceeds.
"""

AUTOMATION_REQUEST_SUMMARY = "Automate {polarion_wi_id}: {polarion_wi_title}"

UPDATE_REQUEST_DESCRIPTION = """
Please check following test step changes:
*[{polarion_wi_id}|{polarion_wi_url}]* {polarion_wi_title}

Test step changes:
{{code:java}}
{polarion_wi_changes}
{{code}}

 ----

When you finished updating the automation, please comment this issue with following format before marking this issue as *Done*:

{{code:java}}Pull Requests:
https://github.com/autotest/tp-libvirt/pull/831
https://github.com/avocado-framework/avocado-vt/pull/630
Auto Cases:
conf_file.libvirtd_conf.unix_sock
conf_file..disable_bypass_cache
{{code}}

If you think there is no need to update corresponding automation script, please reject this issue by clicking *Reject* button above.
If only part of this test case can be automated, please discuss with manual members to on whether to change existing case,
or split non-automatable part out to another test case before proceeds.
"""

UPDATE_REQUEST_SUMMARY = "Update {polarion_wi_id}: {polarion_wi_title}"


def _connect():
    user = settings.CASELINK_JIRA['USER']
    password = settings.CASELINK_JIRA['PASSWORD']
    server = settings.CASELINK_JIRA['SERVER']
    basic_auth = (user, password)
    options = {
        'server': server,
        'verify': False,
    }
    return JIRA(options, basic_auth=basic_auth)


def add_jira_comment(issue, comment, jira_connect=None):
    jira = jira_connect or _connect()
    if not jira:
        return False
    if isinstance(issue, (str, unicode)):
        issue = jira.issue(issue)
    return jira.add_comment(issue, comment)


def transition_issue(issue, status, jira_connect=None):
    jira = jira_connect or _connect()
    if not jira:
        return False
    if isinstance(issue, (str, unicode)):
        issue = jira.issue(issue)
    return jira.transition_issue(issue, status)


def create_jira_issue(issue_dict, jira_connect=None):
    jira = jira_connect or _connect()
    if not jira:
        return False

    dict_ = {
        'project': {
            'key': 'LIBVIRTAT',
        },
        'summary': None,
        'description': None,
        'priority': {
            'name': 'Major',
        },
        'assignee': {
            'name': None
        },
    }

    parent_issue = issue_dict.pop('parent_issue', None) or settings.CASELINK_JIRA['DEFAULT_PARENT_ISSUE']
    assignee = issue_dict.pop('assignee', None) or settings.CASELINK_JIRA['DEFAULT_ASSIGNEE']

    dict_.update({
        'assignee': {
            'name': assignee
        }
    })

    if parent_issue:
        dict_.update({
            'parent': {
                'id': parent_issue
            },
            'issuetype': {
                'name': 'Sub-task'
            }
        })
    else:
        dict_.update({
            'issuetype': {
                'name': 'Task'
            }
        })

    dict_.update(issue_dict)

    return jira.create_issue(dict_)


def update_issue(issue, changes=None):
    jira = _connect()
    transition_id = settings.CASELINK_JIRA['REOPEN_STATUS_ID']
    try:
        transition_issue(issue, transition_id, jira)
    except Exception:
        pass

    if changes:
        add_jira_comment(issue, 'Polarion Workitem Changed: {code}%s{code}'
                         % changes, jira)


def create_update_request(wi_id, wi_title, wi_url, changes, assignee, parent_issue=None):
        description = UPDATE_REQUEST_DESCRIPTION.format(
            polarion_wi_id=wi_id,
            polarion_wi_title=wi_title,
            polarion_wi_url=wi_url,
            polarion_wi_changes=changes
        )
        summary = UPDATE_REQUEST_SUMMARY.format(
            polarion_wi_id=wi_id,
            polarion_wi_title=wi_title
        )
        assignee = assignee
        parent_issue = parent_issue

        return create_jira_issue({
            'summary': summary,
            'description': description,
            'assignee': assignee,
            'parent_issue': parent_issue
        })


def get_issue_feedback(issue_key):
    jira = _connect()
    issue = jira.issue(issue_key)
    status = str(issue.fields.status)
    comments = issue.fields.comment.comments
    if status == 'Resolved' or True:  # DEBUG
        for comment in reversed(comments):
            match = re.match(UPDATED_PATTERN_REGEX, comment.body, re.M)
            if match:
                return {
                    "status": "Resolved",
                    "cases": filter(lambda x: x, map(lambda x: x.strip(), match.groupdict()['cases'].splitlines())),
                    "prs": filter(lambda x: x, map(lambda x: x.strip(), match.groupdict()['prs'].splitlines())),
                }
    return {
        "status": status,
    }
