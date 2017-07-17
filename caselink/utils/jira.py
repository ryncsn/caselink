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


class Jira(object):
    """
    jira operation class
    """
    def __init__(self, **args):
        """
        Init JIRA connection
        """
        self.server = settings.CASELINK_JIRA['SERVER']
        self.username = settings.CASELINK_JIRA['USER']
        self.password = settings.CASELINK_JIRA['PASSWORD']
        self.verify = False  # TODO: move to settings
        self._jira = JIRA(options={
            'server': self.server,
            'verify': self.verify,
        }, basic_auth=(self.username, self.password))

    def search_issues(self, project_name, jql_str, fields=None):
        """
        Search issue under the project and return result
        """
        jql_str = "project = " + project_name + " and " + jql_str
        return self.jira_.search_issues(jql_str, maxResults=-1, fields=fields)

    def add_comment(self, issue, comment):
        """
        Add comments in the issue
        """
        if isinstance(issue, (str, unicode)):
            issue = self._jira.issue(issue)
        return self._jira.add_comment(issue, comment)

    def transition_issue(self, issue, status):
        """
        Transition issue status to another
        """
        self.jira_.transition_issue(issue, status)

    def get_watchers(self, issue):
        """
        Get a watchers Resource from the server for an issue
        """
        watcher_data = self.jira_.watchers(issue)
        return [str(w.key) for w in watcher_data.watchers]

    def add_watcher(self, issue, watchers):
        """
        Append an issue's watchers list
        """
        new_watchers = []
        if isinstance(watchers, str):
            new_watchers.append(watchers)
        elif isinstance(watchers, list):
            new_watchers = watchers
        for watcher in new_watchers:
            self.jira_.add_watcher(issue, watcher)

    def remove_watcher(self, issue, watchers):
        """
        Remove watchers from an issue's watchers list
        """
        del_watchers = []
        if isinstance(watchers, str):
            del_watchers.append(watchers)
        elif isinstance(watchers, list):
            del_watchers = watchers
        for watcher in del_watchers:
            self.jira_.remove_watcher(issue, watcher)

    def create_issue(self, issue_dict):
        """
        Create Issue and apply some default properties
        """
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

        return self._jira.create_issue(dict_)

    # Helper functions
    def update_issue(self, issue, changes=None):
        trans = settings.CASELINK_JIRA['REOPEN_TRANSITION']
        try:
            if isinstance(issue, (str, unicode)):
                issue = self._jira.issue(issue)
            return self._jira.transition_issue(issue, trans)
        except Exception:
            pass

        if changes:
            self.add_comment(issue, 'Polarion Workitem Changed: {code}%s{code}' % changes)

    def create_automation_request(self, wi_id, wi_title, wi_url, changes, assignee, parent_issue=None):
        description = AUTOMATION_REQUEST_DESCRIPTION.format(
            polarion_wi_id=wi_id,
            polarion_wi_title=wi_title,
            polarion_wi_url=wi_url,
        )
        summary = AUTOMATION_REQUEST_SUMMARY.format(
            polarion_wi_id=wi_id,
            polarion_wi_title=wi_title
        )
        assignee = assignee
        parent_issue = parent_issue

        return self.create_issue({
            'summary': summary,
            'description': description,
            'assignee': assignee,
            'parent_issue': parent_issue
        })

    def create_update_request(self, wi_id, wi_title, wi_url, changes, assignee, parent_issue=None):
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

        return self.create_issue({
            'summary': summary,
            'description': description,
            'assignee': assignee,
            'parent_issue': parent_issue
        })

    def get_issue_feedback(self, issue_key):
        issue = self._jira.issue(issue_key)
        status = str(issue.fields.status)
        resolution = str(issue.fields.resolution)
        comments = issue.fields.comment.comments
        if status == 'Done':
            for comment in reversed(comments):
                match = re.match(UPDATED_PATTERN_REGEX, comment.body, re.M)
                if match:
                    return {
                        "status": status,
                        "resolution": resolution,
                        "cases": filter(lambda x: x, map(lambda x: x.strip(), match.groupdict()['cases'].splitlines())),
                        "prs": filter(lambda x: x, map(lambda x: x.strip(), match.groupdict()['prs'].splitlines())),
                    }
        return {
            "status": status,
            "resolution": resolution,
            "cases": None,
            "prs": None,
        }
