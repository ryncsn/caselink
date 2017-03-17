import os
import requests
import time
from django.conf import settings
from caselink.models import WorkItem

import xml.etree.ElementTree as ET


PROJECT = settings.CASELINK_POLARION['PROJECT']
POLARION_URL = settings.CASELINK_POLARION['URL']
DEFAULT_ASSIGNEE = settings.CASELINK_MAITAI['DEFAULT_ASSIGNEE']
DEFAULT_PARENT_ISSUE = settings.CASELINK_MAITAI['PARENT_ISSUE']

MAITAI_PASSWORD = settings.CASELINK_MAITAI['PASSWORD']
MAITAI_USER = settings.CASELINK_MAITAI['USER']
MAITAI_SERVER = settings.CASELINK_MAITAI['SERVER']
MAITAI_DEPLOYMENT = settings.CASELINK_MAITAI['DEPLOYMENT']

PARENT_ISSUE = settings.CASELINK_MAITAI['PARENT_ISSUE']

MAITAI_ENABLE = settings.CASELINK_MAITAI['ENABLE']
MAITAI_REASON = settings.CASELINK_MAITAI['REASON']


class WorkflowDisabledException(Exception):
    pass


class WorkflowException(Exception):
    pass


class Workflow(object):
    def __init__(self):
        self.enable = False
        self.definition = ''
        self.version = ''
        self.params = {}
        self.timeout = 10

    def _gen_url(self):
        return ("%s/business-central/rest/runtime/%s/process/%s"
                % (MAITAI_SERVER, MAITAI_DEPLOYMENT, self.definition))

    def _start(self):
        if not MAITAI_ENABLE:
            reason = (
                MAITAI_REASON or 'Maitai disabled, please contact the admin.')
            raise WorkflowDisabledException(reason)
        if not self.enable:
            raise WorkflowDisabledException("Requested workflow is not enabled.")

        res = requests.post("%s/%s" % (self._gen_url(), 'start'), self.params,
                            auth=(MAITAI_USER, MAITAI_PASSWORD),
                            verify=False)

        if res.status_code != 200:
            raise WorkflowException('Maitai server internal error, detail: %s' % res.text)

        ret = {}
        root = ET.fromstring(res.content)
        for key in ['process-id', 'state', 'id', 'parentProcessInstanceId', 'status']:
            ret[key] = root.find(key).text

        return ret

    def _wait(self):
        return False

    def start(self):
        ret = self._start()
        for i in range(self.timeout + 1):
            if self._wait():
                time.sleep(1)
            else:
                break
            if i >= self.timeout:
                raise WorkflowException("Waiting for condition timed out")

        return ret


class CaseAddWorkflow(Workflow):
    def __init__(self, workitem_id, workitem_title, assignee=None, label=None, parent_issue=None):
        super(CaseAddWorkflow, self).__init__()
        self.workitem_id = workitem_id
        self.enable = settings.CASELINK_MAITAI['CASEADD_ENABLE']
        self.definition = settings.CASELINK_MAITAI['CASEADD_DEFINITION']
        parent_issue = parent_issue or DEFAULT_PARENT_ISSUE
        assignee = assignee or DEFAULT_ASSIGNEE
        label = label or ''
        self.params = {
            "map_polarionId": workitem_id,
            "map_polarionProject": PROJECT,
            "map_polarionUrl": ("%s/polarion/#/project/%s/workitem?id=%s"
                                % (POLARION_URL, PROJECT, workitem_id)),
            "map_polarionTitle": workitem_title,
            "map_issueAssignee": assignee,
            "map_issueLabels": label,
            "map_parentIssueKey": parent_issue,
        }

    def _wait(self):
        workitem = WorkItem.objects.get(id=self.workitem_id)
        return not workitem.jira_id


class CaseUpdateWorkflow(Workflow):
    def __init__(self, workitem_id, workitem_title, assignee=None, label=None, parent_issue=None):
        super(CaseUpdateWorkflow, self).__init__()
        self.enable = settings.CASELINK_MAITAI['CASEUPDATE_ENABLE']
        self.definition = settings.CASELINK_MAITAI['CASEUPDATE_DEFINITION']
        parent_issue = parent_issue or DEFAULT_PARENT_ISSUE
        assignee = assignee or DEFAULT_ASSIGNEE
        label = label or ''
        self.params = {
            "map_polarionId": workitem_id,
            "map_polarionProject": PROJECT,
            "map_polarionUrl": ("%s/polarion/#/project/%s/workitem?id=%s"
                                % (POLARION_URL, PROJECT, workitem_id)),
            "map_polarionTitle": workitem_title,
            "map_issueAssignee": assignee,
            "map_issueLabels": label,
            "map_parentIssueKey": parent_issue,
        }

        self.workitem_id = workitem_id
        self.workitem = WorkItem.objects.get(id=self.workitem_id)
        self.workitem.jira_id = None
        self.workitem.save()

    def _wait(self):
        workitem = WorkItem.objects.get(id=self.workitem_id)
        return not workitem.jira_id


