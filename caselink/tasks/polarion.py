import re
import difflib
import datetime
import suds
import pytz
import sys

from django.conf import settings
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from caselink import models
from caselink.utils.jira import create_update_request, issue_updated
from celery import shared_task
from . import update_task_info

if sys.version_info >= (3, 0):
    from html.parser import HTMLParser
else:
    import HTMLParser

PYLARION_INSTALLED = True
try:
    from pylarion.document import Document
    from pylarion.work_item import _WorkItem
except ImportError:
    PYLARION_INSTALLED = False

PROJECT = settings.CASELINK_POLARION['PROJECT']
SPACES = settings.CASELINK_POLARION['SPACES']
POLARION_URL = settings.CASELINK_POLARION['URL']
DEFAULT_COMPONENT = 'n/a'

try:
    literal = unicode
except NameError:
    literal = str


def all_documents(project, spaces):
    """
    Load all documents, return list
    """
    utc = pytz.UTC
    for idx, space in enumerate(spaces):
        update_task_info('Fetching Space %s, (%s/%s)' % (space, idx, len(spaces)))
        docs = Document.get_documents(
            project, space, fields=['document_id', 'title', 'type', 'updated', 'project_id'])
        for doc in docs:
            update_task_info('Fetching document %s, (%s/%s)' % (literal(doc.title), idx, len(docs)))
            yield {
                'space': space,
                'title': literal(doc.title),
                'type': literal(doc.type),
                'id': literal(doc.document_id),
                'project': project,
                'updated': utc.localize(doc.updated or datetime.datetime.now()),
                'workitems': doc.get_work_items(None, True, fields=['work_item_id', 'type', 'title', 'updated'])
            }


def all_workitems(doc):
    """
    Load all Workitems with given doc, return a dictionary,
    keys are workitem id, values are dicts presenting workitem attributes.
    return generator, each yield element is a dict stands for a WorkItem
    """
    utc = pytz.UTC
    space = doc['space']
    project = doc['project']
    for wi_idx, wi in enumerate(doc['workitems']):
        update_task_info('Updating Workitem "%s" (%s/%s)' %
                         (wi.work_item_id, wi_idx, len(doc['workitems'])))
        if wi is None or wi.title is None or wi.type is None or wi.updated is None:
            print("Invalid workitem %s" % wi)
            continue
        yield {
            'id': wi.work_item_id,
            'title': literal(wi.title),
            'type': literal(wi.type),
            'project': project,
            'space': space,
            'updated': utc.localize(wi.updated or datetime.datetime.now()),
            'document': doc
        }


def get_recent_changes(wi_id, service=None, start_time=None):
    """
    Get changes after start_time, return a list of dict.
    """
    def suds_2_object(suds_obj):
        dict_ = {}
        if not hasattr(suds_obj, '__dict__'):
            print("ERROR: Suds object without __dict__ attribute: {}".format(suds_obj))
        else:
            for key, value in suds_obj.__dict__.items():
                if key.startswith('_'):
                    continue
                if isinstance(value, suds.sax.text.Text):
                    value = literal(value.strip())
                elif isinstance(value, (bool, int, datetime.date, datetime.datetime)):
                    pass
                elif value is None:
                    pass
                elif isinstance(value, list):
                    value = [suds_2_object(elem) for elem in value]
                elif hasattr(value, '__dict__'):
                    value = suds_2_object(value)
                else:
                    print('Unhandled value type: %s' % type(value))
                dict_[key] = value
        return dict_
    utc = pytz.UTC
    uri = 'subterra:data-service:objects:/default/%s${WorkItem}%s' % (PROJECT, wi_id)
    service = _WorkItem.session.tracker_client.service if service is None else service
    changes = service.generateHistory(uri)
    return [suds_2_object(change) for change in changes if not start_time or utc.localize(change.date) > start_time]


def filter_changes(changes):
    """
    Filter out irrelevant changes, return a list of dict.
    """
    def _convert_text(text):
        """
        Convert and format HTML into plain text, clean '<br>'s
        """
        lines = re.split(r'\<[bB][rR]/\>', text)
        new_lines = []
        for line in lines:
            line = " ".join(line.split())
            if line:
                line = HTMLParser.HTMLParser().unescape(line)
                new_lines.append(line)
        return '\n'.join(new_lines)

    def diff_test_steps(before, after):
        """
        Will break if steps are not in a two columns table (Step, Result)
        """
        def _get_steps_for_diff(data):
            ret = []
            if not data:
                return ret
            try:
                steps = data.get('steps', {}).get('TestStep', [])
                if not isinstance(steps, list):
                    steps = [steps]
                for idx, raw_step in enumerate(steps):
                    step, result = [
                        _convert_text(text['content'])
                        for text in raw_step['values']['Text']]
                    ret.extend([
                        "Step:",
                        step or "<empty>",
                        "Expected result:",
                        result or "<empty>",
                    ])
            except Exception as error:
                print("ERROR: %s" % error)
            finally:
                return ret
        steps_before, steps_after = _get_steps_for_diff(before), _get_steps_for_diff(after)
        return '\n'.join(difflib.unified_diff(steps_before, steps_after))

    summary = ""
    authors = set()
    for change in changes:
        creation = change['creation']
        date = change['date']
        diffs = change['diffs']
        empty = change['empty']
        # invalid = change['invalid']
        # revision = change['revision']
        user = change['user']

        if creation:
            summary += "User %s create this workitem at %s\n" % (user, date)
            if empty:
                continue

        if diffs:
            for diff in diffs['item']:
                before = diff.get('before', None)
                after = diff.get('after', None)
                field = diff['fieldName']

                # Ignore irrelevant properties changing
                if field not in ['testSteps']:
                    continue

                if field == 'testSteps':
                    summary += "User %s changed test steps at %s:\n%s\n" % (user, date, diff_test_steps(before, after))
                    authors.add(user)
                    continue

                else:
                    def _get_text_content(data):
                        if not data:
                            return None
                        elif not isinstance(data, (str, unicode)):
                            if 'id' in data:  # It'a Enum?
                                data = data['id']
                            elif 'content' in data:  # It's a something else...
                                data = _convert_text(data['content'])
                            else:
                                return None
                        return data

                    before, after = _get_text_content(before), _get_text_content(after)

                    if not before or not after:
                        summary += "User %s changed %s at %s, details not avaliable.\n" % (user, field, date)
                        continue

                    else:
                        detail_diff = ''.join(difflib.unified_diff(before, after))
                        summary += "User %s changed %s at %s:\n%s\n" % (user, field, date, detail_diff)
    return summary, list(authors)


def get_automation_of_wi(wi_id):
    """
    Get the automation status of a workitem.
    """
    polarion_wi = _WorkItem(project_id=PROJECT, work_item_id=wi_id)
    try:
        for custom in polarion_wi._suds_object.customFields.Custom:
            if custom.key == 'caseautomation':
                return literal(custom.value.id)
    except AttributeError:
        pass
    return None


def create_workitem(wi):
    with transaction.atomic():
        workitem = models.WorkItem(
            id=wi['id'],
            title=wi['title'],
            type=wi['type'],
            updated=wi['updated'],
            automation=get_automation_of_wi(wi['id']) or 'notautomated'
        )

        workitem.project, created = models.Project.objects.get_or_create(name=wi['project'])
        workitem.save()

        if 'arch' in wi:
            for arch_name in wi['arch']:
                arch, _ = models.Arch.objects.get_or_create(name=arch_name)
                arch.workitems.add(workitem)
                arch.save()

        if 'errors' in wi:
            for error_message in wi['errors']:
                error, created = models.Error.objects.get_or_create(message=error_message)
                if created:
                    error.id = error_message
                    error.workitems.add(workitem)
                    error.save()
        workitem.error_check()
        workitem.save()
    return True


def update_workitem(wi):
    workitem = models.WorkItem.objects.get(id=wi['id'])
    if workitem.updated >= wi['updated']:
        return False

    print("Workitem %s changed, local version %s, new version %s" % (workitem.id, workitem.updated, wi['updated']))

    with transaction.atomic():
        # In case a old deleted case show up again in polarion.
        workitem.mark_notdeleted()
        workitem.title = wi['title']
        workitem.automation = get_automation_of_wi(wi['id']) or workitem.automation
        workitem.save()

    workitem_changes, authors = filter_changes(get_recent_changes(wi['id'], start_time=workitem.updated))
    if workitem_changes:
        try:
            if workitem.jira_id:
                print("Reopenning a old issue %s for %s" % (workitem.jira_id, workitem.id))
                issue_updated(workitem.jira_id, workitem_changes)
            else:
                print("Creating a new issue for %s, assign to %s" % (workitem.id, authors[-1] if len(authors) > 0 else None))
                if not workitem.automation != 'automated':
                    print("In progress workitem %s don't have a JIRA issue " % workitem.id)
                issue = create_update_request(workitem.id, workitem.title,
                                              ("%s/polarion/#/project/%s/workitem?id=%s"
                                               % (POLARION_URL, PROJECT, workitem.id)),
                                              # Assign to the last one who edited this workitem
                                              workitem_changes, authors[-1] if len(authors) > 0 else None)
                if issue:
                    print("Issued created %s" % issue.key)
                    workitem.jira_id = issue.key  # TODO: jira_id should be jira_key
            print("Done")
        except Exception as error:
            # Faied, record the change for later use
            # TODO: record user as well
            print(error)
            workitem.changes = workitem_changes

    workitem.comfirmed = workitem.updated
    workitem.updated = wi['updated']
    workitem.save()
    return True


@shared_task
def sync_with_polarion():
    """
    Main task, fetch workitems from polarion.
    """
    if not PYLARION_INSTALLED:
        return "Pylarion not installed"
    if not settings.CASELINK_POLARION['ENABLE']:
        return settings.CASELINK_POLARION['REASON']

    deleted_wi_ids = set()
    updated_wi_ids = set()
    skipped_wi_ids = set()
    failed_wi_ids = set()
    created_wi_ids = set()
    all_caselink_wi_ids = set(models.WorkItem.objects.all().values_list('id', flat=True))

    try:
        for doc in all_documents(PROJECT, SPACES):
            document, created = models.Document.objects.get_or_create(id=doc['id'])
            if created:
                document.title = doc['id']
                document.component = models.Component.objects.get_or_create(name=DEFAULT_COMPONENT)
            document.save()
            document_wi_ids = set()

            for wi in all_workitems(doc):
                document_wi_ids.add(wi['id'])
                try:
                    if not update_workitem(wi):
                        skipped_wi_ids.add(wi['id'])
                    else:
                        updated_wi_ids.add(wi['id'])
                except ObjectDoesNotExist:
                    create_workitem(wi)
                    created_wi_ids.add(wi['id'])
                except Exception:
                    print("Failed retriving data for workitem %s" % wi['id'])
                    failed_wi_ids.add(wi['id'])

            update_task_info('Updating document relationship...')
            with transaction.atomic():
                document.workitems.clear()
                for wi_id in document_wi_ids:
                    document.workitems.add(wi_id)
                document.save()
    except Exception as error:
        # Critical Error, can't fetch full workitem list, hence deleting is skipped, and already updated workitem is perserved
        return (
            ("Progress Interrupted Due to critical error %s" % error) +
            "Created: " + ', '.join(created_wi_ids) + "\n" +
            "Deleted: " + ', '.join(deleted_wi_ids) + "\n" +
            "Updated: " + ', '.join(updated_wi_ids) + "\n" +
            "Failed: " + ', '.join(failed_wi_ids)
        )
    else:
        update_task_info('Deleting deleted workitems...')
        deleted_wi_ids = all_caselink_wi_ids - skipped_wi_ids - updated_wi_ids - created_wi_ids - failed_wi_ids
        for wi_id in deleted_wi_ids.copy():
            wi = models.WorkItem.objects.get(id=wi_id)
            related_wis = wi.error_related.all()
            if not any([getattr(wi, data) for data in wi._user_data]):
                if not wi.linkages.exists():
                    wi.delete()
                    for wi_r in related_wis:
                        wi_r.error_check()
                    continue
            wi.mark_deleted()
            wi.save()

    return (
        "Created: " + ', '.join(created_wi_ids) + "\n" +
        "Deleted: " + ', '.join(deleted_wi_ids) + "\n" +
        "Updated: " + ', '.join(updated_wi_ids) + "\n" +
        "Failed: " + ', '.join(failed_wi_ids)
    )
