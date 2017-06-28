"""
Common functions for Celery tasks
"""
from celery import current_task


def update_task_info(state, meta=None):
    """
    If running as task, update the task state, else return directly
    """
    if current_task.request.id is not None:
        current_task.update_state(state=(state[:35] + '..' + state[-10:]) if len(state) > 49 else state,
                                  meta=meta)
