# TODO: Rename this file
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from caselink import models
from caselink.utils.jira import Jira
from caselink.utils.polarion import (
    all_documents, all_workitems, get_automation_of_wi, filter_step_changes, get_recent_changes,
    set_automation_of_wi, PYLARION_INSTALLED, literal)
from celery import shared_task
from . import update_task_info


PROJECT = settings.CASELINK_POLARION['PROJECT']
SPACES = settings.CASELINK_POLARION['SPACES']
POLARION_URL = settings.CASELINK_POLARION['URL']
DEFAULT_COMPONENT = 'n/a'


def create_workitem(wi):
    with transaction.atomic():
        workitem = models.WorkItem(
            id=wi['id'],
            title=wi['title'],
            type=wi['type'],
            updated=wi['updated'],
            automation=get_automation_of_wi(PROJECT, wi['id']) or 'notautomated'
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
        workitem.automation = get_automation_of_wi(PROJECT, wi['id']) or workitem.automation
        workitem.save()

    workitem_changes, authors = filter_step_changes(get_recent_changes(PROJECT, wi['id'], start_time=workitem.updated))
    if workitem_changes:
        try:
            print("Workitem steps changed, makring it notautomated")
            set_automation_of_wi(PROJECT, wi['id'], 'notautomated')
            if workitem.jira_id:
                print("Reopenning a old issue %s for %s, and adding comments" % (workitem.jira_id, workitem.id))
                Jira().update_issue(workitem.jira_id, workitem_changes)
            else:
                print("Creating a new issue for %s, assign to %s" % (workitem.id, authors[-1] if len(authors) > 0 else None))
                if not workitem.automation == 'notautomated':
                    print("In progress workitem %s don't have a JIRA issue " % workitem.id)
                issue = Jira().create_update_request(workitem.id, workitem.title,
                                                     ("%s/polarion/#/project/%s/workitem?id=%s"
                                                      % (POLARION_URL, PROJECT, workitem.id)),
                                                     # Assign to the last one who edited this workitem
                                                     workitem_changes, authors[-1] if len(authors) > 0 else None)
                if issue:
                    print("Issued created %s" % issue.key)
                    workitem.jira_id = issue.key  # TODO: jira_id should be jira_key
                    workitem.jira_type = 'UPDATE'
                else:
                    raise RuntimeError("Failed creating issue")
            print("Done")
        except Exception as error:
            # Faied, record the change for later use
            # TODO: record user as well
            print("Failed creating/updating jira issue for %s" % wi['id'])
            print(error)
            workitem.changes = workitem_changes
        else:
            workitem.comfirmed = workitem.updated
            workitem.updated = wi['updated']
            workitem.save()
    else:
        workitem.comfirmed = workitem.updated
        workitem.updated = wi['updated']
        workitem.save()
    return True


def delete_workitem(wi_id):
    wi = models.WorkItem.objects.get(id=wi_id)
    if not any([getattr(wi, data) for data in wi._user_data]):
        if not wi.linkages.exists():
            related_wis = wi.error_related.all()
            wi.delete()
            for wi_r in related_wis:
                wi_r.error_check()
            return
    wi.mark_deleted()
    wi.save()


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
    created_wi_ids = set()
    failed_wi_ids = set()
    all_caselink_wi_ids = set(models.WorkItem.objects.all().values_list('id', flat=True))

    try:
        update_task_info('Starting Polarion sync, fetching workspaces...')
        for doc in all_documents(PROJECT, SPACES):
            update_task_info('Fetching document %s' % (literal(doc['title'])))
            document, created = models.Document.objects.get_or_create(id=doc['id'])
            if created:
                document.title = doc['id']
                document.component = models.Component.objects.get_or_create(name=DEFAULT_COMPONENT)
            document.save()
            document_wi_ids = set()

            for wi in all_workitems(doc):
                update_task_info('Updating Workitem "%s"' % (wi['id']))
                document_wi_ids.add(wi['id'])
                try:
                    if not update_workitem(wi):
                        skipped_wi_ids.add(wi['id'])
                    else:
                        updated_wi_ids.add(wi['id'])
                except ObjectDoesNotExist:
                    create_workitem(wi)
                    created_wi_ids.add(wi['id'])
                except Exception as error:
                    print("Failed retriving data for workitem %s" % wi['id'])
                    print(error)
                    failed_wi_ids.add(wi['id'])

            update_task_info('Updating document relationship...')
            with transaction.atomic():
                document.workitems.clear()
                for wi_id in document_wi_ids:
                    document.workitems.add(wi_id)
                document.save()

    except Exception as error:
        # Critical Error, can't fetch full workitem list, hence deleting is skipped, and already updated workitem is perserved
        raise
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
        for wi_id in deleted_wi_ids:
            delete_workitem(wi_id)

    return (
        "Created: " + ', '.join(created_wi_ids) + "\n" +
        "Deleted: " + ', '.join(deleted_wi_ids) + "\n" +
        "Updated: " + ', '.join(updated_wi_ids) + "\n" +
        "Failed: " + ', '.join(failed_wi_ids)
    )


def handle_automation_result(workitem, result, jira):
    if result['cases']:
        print("Worktiem %s, issue %s is updated" % (workitem.id, workitem.jira_id))
        for case_pattern in result['cases']:
            linkage, _ = models.Linkage.objects.get_or_create(workitem=workitem, autocase_pattern=case_pattern)
            linkage.save()
            workitem.linkages.add(linkage)
        set_automation_of_wi(PROJECT, workitem.id, 'automated')
        workitem.automation = 'automated'
        workitem.jira_id = None
        workitem.save()
    else:
        print("Worktiem %s, issue %s Not in a acceptable status" % (workitem.id, workitem.jira_id))
        jira.update_issue(workitem.jira_id)


@shared_task
def sync_with_jira():
    jira = Jira()
    for workitem in models.WorkItem.objects.filter(jira_id__isnull=False):
        update_task_info('Updating Workitem "%s", jira task "%s"' % (workitem.id, workitem.jira_id))
        print('Updating Workitem "%s", jira task "%s"' % (workitem.id, workitem.jira_id))
        if workitem.jira_type == 'UPDATE':
            result = jira.get_issue_feedback(workitem.jira_id)
            if result and result['status'] == 'Done':
                if result['resolution'] in ["Fixed", "Done"]:
                    handle_automation_result(workitem, result, jira)
                else:
                    print('Workitem %s, issue %s don\'t need update, mark automated again and remove issue' % (workitem.id, workitem.jira_id))
                    set_automation_of_wi(PROJECT, workitem.id, 'automated')
                    workitem.automation = 'automated'
                    workitem.jira_id = None
                    workitem.save()
            if result and result['status'] == 'Rejected':
                print('Workitem %s, issue %s can\'t be updated, mark automated again and remove issue' % (workitem.id, workitem.jira_id))
                set_automation_of_wi(PROJECT, workitem.id, 'automated')
                workitem.automation = 'automated'
                workitem.jira_id = None
                workitem.save()

        elif workitem.jira_type == 'AUTOMATION':
            result = jira.get_issue_feedback(workitem.jira_id)
            if result and result['status'] == 'Done':
                handle_automation_result(workitem, result, jira)
            elif result['status'] == 'Rejected':
                print("Worktiem %s, issue %s is NOT automatable" % (workitem.id, workitem.jira_id))
                set_automation_of_wi(PROJECT, workitem.id, 'manualonly')
                workitem.automation = 'manualonly'
                workitem.jira_id = None
                workitem.save()

        else:
            print("Workflow 1 not usable yet")
