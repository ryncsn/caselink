from __future__ import absolute_import

import yaml
import re
import logging
import difflib
import datetime

from django.core import serializers
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from celery import shared_task, current_task

# pylint: disable=redefined-builtin
try:
    from builtins import str
except ImportError:
    pass

try:
    from html.parser import HTMLParser
except ImportError:
    from HTMLParser import HTMLParser

from caselink.models import *


BASE_DIR = 'caselink/backups'


@transaction.atomic
def init_error_checking():
    """Check for error."""
    update_workitem_error()
    update_autocase_error()
    update_linkage_error()


@transaction.atomic
def init_linkage():
    """Link cases according by pattern"""
    for case in AutoCase.objects.all():
        case.autolink()
        case.save()


@shared_task
def update_linkage_error(link=None):
    """Check for errors in linkage"""
    if not link:
        links = Linkage.objects.all()
    else:
        links = [link]

    current = 0
    total = len(links)
    direct_call = current_task.request.id is None

    for link in links:
        link.error_check(depth=0)

        if not direct_call:
            current += 1
            current_task.update_state(state='PROGRESS',
                                      meta={'current': current, 'total': total})


@shared_task
def update_workitem_error(case=None):
    """Check for errors in workitems"""
    if not case:
        cases = WorkItem.objects.all()
    else:
        cases = [case]

    current = 0
    total = len(cases)
    direct_call = current_task.request.id is None

    for case in cases:
        case.error_check(depth=0)

        if not direct_call:
            current += 1
            current_task.update_state(state='PROGRESS',
                                      meta={'current': current, 'total': total})

@shared_task
def update_autocase_error(case=None):
    """Check for errors in auto cases"""
    if not case:
        cases = AutoCase.objects.all()
    else:
        cases = [case]

    current = 0
    total = len(cases)
    direct_call = current_task.request.id is None

    for case in cases:
        case.error_check(depth=0)

        if not direct_call:
            current += 1
            current_task.update_state(state='PROGRESS',
                                      meta={'current': current, 'total': total})


@shared_task
def dump_all_db():
    """
    Dump all models except Error.
    """
    # TODO: hardcoded BASE_DIR
    filename = BASE_DIR + "/" + str(datetime.datetime.now().isoformat()) + ".yaml"
    with open(filename, 'w+') as base_fp:
        for model in [Framework, Project, Document, Component, Arch, #Meta models
                      WorkItem, AutoCase, Linkage, Bug, AutoCaseFailure]:
            base_fp.write(serializers.serialize('yaml', model.objects.all(), fields=model._min_dump))


@shared_task
@transaction.atomic
def restore_all_db(filename):
    with open(filename) as fl:
        data = fl.read()
        for obj in serializers.deserialize("yaml", data):
            obj.save()


@shared_task
@transaction.atomic
def clean_all_db():
    """
    Clean all models except Error.
    """
    for model in [
            Component, Arch, AutoCase, AutoCaseFailure, Bug, Linkage, WorkItem,
            Document, Project, Framework]:
        model.objects.all().delete()


@shared_task
def clean_and_restore(filename):
    clean_all_db()
    restore_all_db(filename)
    init_linkage()
    init_error_checking()


def _save_db(filename, Model):
    with open(filename, 'w+') as base_fp:
        base_fp.write(serializers.serialize('yaml', Model.objects.all(), fields=Model._min_dump))


def save_error_db(filename):
    _save_db(filename, Error)


def save_framework_db(filename):
    _save_db(filename, Framework)


def save_project_db(filename):
    _save_db(filename, Project)


def save_document_db(filename):
    _save_db(filename, Document)


def save_workitem_db(filename):
    _save_db(filename, WorkItem)


def save_autocase_db(filename):
    _save_db(filename, AutoCase)


def save_caselink_db(filename):
    _save_db(filename, Linkage)


def save_bug_db(filename):
    _save_db(filename, Bug)


def save_failure_db(filename):
    _save_db(filename, AutoCase)


@transaction.atomic
def restore_db(filename):
    with open(filename) as fl:
        data = fl.read()
        for obj in serializers.deserialize("yaml", data):
            obj.save()


def restore_error_db(filename):
    restore_db(filename)


def restore_framework_db(filename):
    restore_db(filename)


def restore_project_db(filename):
    restore_db(filename)


def restore_document_db(filename):
    restore_db(filename)


def restore_workitem_db(filename):
    restore_db(filename)


def restore_autocase_db(filename):
    restore_db(filename)


def restore_caselink_db(filename):
    restore_db(filename)


def restore_bug_db(filename):
    restore_db(filename)


def restore_failure_db(filename):
    restore_db(filename)
