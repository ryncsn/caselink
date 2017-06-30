from django.db import transaction
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from .models import (
    WorkItem, AutoCase, Linkage, Bug, BlackListEntry, AutoCaseFailure,
    Framework, Component, Arch, Project, Document, Error)
from .error import ErrorCheckModel


def _set_skip_signal(instance, value=True):
    """
    Set a skip signal sign, to avoid signal recursion
    """
    if hasattr(instance, '__skip_signal'):
        return instance.__skip_signal
    setattr(instance, '__skip_signal', value)


__all__ = [
    'WorkItem', 'AutoCase', 'Linkage', 'Bug', 'BlackListEntry', 'AutoCaseFailure',
    'Framework', 'Component', 'Arch', 'Project', 'Document',
    'Error']


@receiver(post_save)
def save_error_check_handler(sender, instance, created, raw, **kwargs):
    # Returns false if 'sender' is NOT a subclass of AbstractModel
    if _set_skip_signal(instance):
        return
    with transaction.atomic():
        if hasattr(sender, 'autolink'):
            instance.autolink()
            instance.save()
        if issubclass(sender, ErrorCheckModel):
            instance.error_check(depth=1)
            instance.save()
    _set_skip_signal(instance, False)


@receiver(post_delete)
def delete_error_check_handler(sender, instance, **kwargs):
    # Returns false if 'sender' is NOT a subclass of AbstractModel
    if _set_skip_signal(instance):
        return
    if issubclass(sender, ErrorCheckModel):
        with transaction.atomic():
            instances = instance.get_error_related()
            instance.delete()
            for instance_ in instances:
                with transaction.atomic():
                    instance_.error_check(depth=0)
                    instance_.save()
    _set_skip_signal(instance, False)
