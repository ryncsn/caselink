import datetime
from django.core import serializers
from django.db import transaction
from celery import shared_task, current_task
from . import update_task_info

# pylint: disable=redefined-builtin
try:
    from builtins import str
except ImportError:
    pass

from caselink.models import (
    Framework, Project, Document, Component, Arch,
    WorkItem, AutoCase, Linkage, Bug, AutoCaseFailure)


BACKUP_DIR = 'caselink/backups'


@transaction.atomic
def init_linkage():
    """Link cases according by pattern"""
    for case in AutoCase.objects.all():
        case.autolink()
        case.save()


@transaction.atomic
def init_error_checking():
    """Check for error."""
    update_workitem_error()
    update_autocase_error()
    update_linkage_error()


@shared_task
@transaction.atomic
def clean_and_restore(filename):
    clean_all_db()
    restore_all_db(filename)
    init_linkage()
    init_error_checking()


@shared_task
def update_linkage_error(links=None):
    """Check for errors in linkage"""
    links = links or Linkage.objects.all()
    for idx, link in enumerate(links):
        link.error_check(depth=0)
        update_task_info('PROGRESS', meta={'current': idx, 'total': len(links)})


@shared_task
def update_workitem_error(cases=None):
    """Check for errors in workitems"""
    cases = cases or WorkItem.objects.all()
    for idx, case in enumerate(cases):
        case.error_check(depth=0)
        update_task_info(state='PROGRESS', meta={'current': idx, 'total': len(cases)})


@shared_task
def update_autocase_error(cases=None):
    """Check for errors in auto cases"""
    cases = cases or AutoCase.objects.all()
    for idx, case in enumerate(cases):
        case.error_check(depth=0)
        update_task_info(state='PROGRESS', meta={'current': idx, 'total': len(cases)})


@shared_task
def backup_all_db():
    """
    Dump all models except Error.
    """
    filename = BACKUP_DIR + "/" + str(datetime.datetime.now().isoformat()) + ".yaml"
    with open(filename, 'w+') as base_fp:
        for model in [Framework, Project, Document, Component, Arch,  # Meta models
                      WorkItem, AutoCase, Linkage, Bug, AutoCaseFailure]:
            base_fp.write(serializers.serialize('yaml', model.objects.all(), fields=model._min_dump))


@shared_task
def restore_all_db(filename):
    with open(filename) as fl:
        data = fl.read()
        for obj in serializers.deserialize("yaml", data):
            obj.save()


@shared_task
def clean_all_db():
    """
    Clean all models except Error.
    """
    for model in [
            Component, Arch, AutoCase, AutoCaseFailure, Bug, Linkage, WorkItem,
            Document, Project, Framework]:
        model.objects.all().delete()
