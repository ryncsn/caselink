import os
from django.conf import settings

from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.db import IntegrityError, OperationalError, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render_to_response

from caselink.models import (
    WorkItem)
from caselink.tasks.common import (
    backup_all_db, update_workitem_error, update_autocase_error, update_linkage_error, clean_and_restore)
from caselink.tasks.polarion import sync_with_polarion
from caselink.utils.maitai import CaseAddWorkflow, WorkflowDisabledException, WorkflowException

from celery.task.control import inspect
from celery.result import AsyncResult
from djcelery.models import TaskMeta

from caselink.form import MaitaiAutomationRequest

BASE_DIR = settings.BASE_DIR
BACKUP_DIR = BASE_DIR + "/caselink/backups"


def _get_tasks():
    workers = inspect(['celery@localhost']).active()  # TODO: only support local worker
    if workers is None:
        return None
    return workers.items()


def _get_finished_tasks_results(limit):
    ret = []
    task_metas = TaskMeta.objects.order_by('-date_done')
    for i in task_metas[0:limit]:
        ret.append(i.to_dict())
        ret[-1]['result'] = "%s" % ret[-1]['result']
    return ret


def _get_running_tasks_status():
    task_status = []
    _tasks = _get_tasks()
    if not _tasks:
        return {}
    for worker, tasks in _tasks:
        for task in tasks:
            res = AsyncResult(task['id'])
            task_status.append({
                'name': task['name'],
                'id': task['id'],
                'state': res.state,
                'meta': res.info
            })
    return task_status


def _cancel_task(task_id=None):
    task_status = {}
    worker_tasks = _get_tasks()
    if not worker_tasks:
        return {}
    for worker, tasks in worker_tasks:
        for task in tasks:
            res = AsyncResult(task['id'])
            task_status[task['name']] = {
                'state': res.state,
                'meta': res.info
            }
            if not task_id or task_id == task['id']:
                res.revoke(terminate=True)
                task_status[task['name']]['canceled'] = True
    return task_status


def _schedule_task(task_name, async_task=True):
    tasks_map = {
        'linkage_error_check': update_linkage_error,
        'autocase_error_check': update_autocase_error,
        'workitem_error_check': update_workitem_error,
        'dump_all_db': backup_all_db,
        'polarion_sync': sync_with_polarion,
    }
    if task_name in tasks_map:
        task = tasks_map[task_name]
    else:
        return {'message': 'Unknown task'}

    if not async_task:
        try:
            with transaction.atomic():
                task()
        except OperationalError:
            return {'message': 'DB Locked'}
        except IntegrityError:
            return {'message': 'Integrity Check Failed'}
        return {'message': 'done'}
    else:
        task.apply_async()
        return {'message': 'queued'}


def _get_backup_list():
    backup_list = []
    for file in os.listdir(BACKUP_DIR):
        if file.endswith(".yaml"):
            size = os.path.getsize(BACKUP_DIR + "/" + file)
            backup_list.append({
                'file': file,
                'size': size,
            })
    return backup_list


def overview(request):
    return JsonResponse({
        'tasks': _get_running_tasks_status(),
        'results': _get_finished_tasks_results(7),
        'backups': _get_backup_list(),
    })


def task(request):
    return JsonResponse(_get_running_tasks_status())


def trigger(request):
    results = {}

    cancel = True if request.GET.get('cancel', '') == 'true' else False
    async = True if request.GET.get('async', '') == 'true' else False
    tasks = request.GET.getlist('trigger', [])

    if cancel:
        results = _cancel_task()
    elif len(tasks) > 0:
        for task in tasks:
            results[task] = _schedule_task(task, async_task=async)

    return JsonResponse(results)


def backup(request):
    return JsonResponse({
        'message': 'Not implemented'
    })


def backup_instance(request, filename=None):
    delete = True if request.GET.get('delete', '') == 'true' else False
    if delete:
        try:
            os.remove(BACKUP_DIR + "/" + filename)
        except OSError:
            raise HttpResponseServerError()
        else:
            return JsonResponse({'message': 'Done'})

    with open(BACKUP_DIR + "/" + filename) as file:
        data = file.read()
    response = HttpResponse(data, content_type='text/plain')
    response['Content-Length'] = os.path.getsize(BACKUP_DIR + "/" + filename)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


def restore(request, filename=None):
    clean_and_restore.apply_async((BACKUP_DIR + "/" + filename,))
    return JsonResponse({
        'filename': filename,
        'message': 'queued'
    })


def upload(request):
    if request.method == 'POST' and request.FILES['file']:
        i = 0
        while os.path.exists(BACKUP_DIR + "/upload-%s.yaml" % i):
            i += 1
        with open(BACKUP_DIR + "/upload-%s.yaml" % i, "w+") as fl:
            for chunk in request.FILES['file'].chunks():
                fl.write(chunk)
        return render_to_response('caselink/popup.html', {'message': 'Upload successful'})
    else:
        return HttpResponseBadRequest()


def create_maitai_request(request):
    maitai_request = MaitaiAutomationRequest(request.POST)
    if not maitai_request.is_valid():
        return JsonResponse({'message': "Invalid parameters"}, status=400)

    workitem_ids = maitai_request.cleaned_data['workitems'].split()
    # TODO: multiple assignee
    assignee = maitai_request.cleaned_data['assignee'].split().pop()
    labels = maitai_request.cleaned_data['labels']
    parent_issue = maitai_request.cleaned_data['parent_issue']

    ret = {}

    for workitem_id in workitem_ids:
        try:
            wi = WorkItem.objects.get(pk=workitem_id)
        except ObjectDoesNotExist:
            ret.setdefault(workitem_id, {})['message'] = "Workitem doesn't exists."
            continue

        workflow = CaseAddWorkflow(workitem_id, wi.title,
                                   assignee=assignee, label=labels, parent_issue=parent_issue)
        try:
            res = workflow.start()
        except (WorkflowException, WorkflowDisabledException) as error:
            ret.setdefault(workitem_id, {})['message'] = error.message
        else:
            wi = WorkItem.objects.get(pk=workitem_id)
            wi.maitai_id = res['id']
            wi.need_automation = True
            wi.save()

        ret.setdefault(workitem_id, {})['maitai_id'] = wi.maitai_id

    return JsonResponse(ret, status=200)
