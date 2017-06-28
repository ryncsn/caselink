from django.core.management.base import BaseCommand
from caselink.tasks.common import init_linkage, init_error_checking


class Command(BaseCommand):
    help = 'Manually initialize database, create linkage and mark error.'

    def handle(self, *args, **options):
        print("Initializing Linkage...")
        init_linkage()
        print("Checking for error...")
        init_error_checking()
