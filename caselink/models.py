from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.db import transaction, models


def _test_pattern_match(pattern, casename):
    """
    Test if a autocase match with the name pattern.
    """
    segments = pattern.split('..')
    items = casename.split('.')
    idx = 0
    for segment in segments:
        seg_items = segment.split('.')
        try:
            while True:
                idx = items.index(seg_items[0])
                if items[idx:len(seg_items)] == seg_items:
                    items = items[len(seg_items):]
                    break
                else:
                    del items[0]
        except ValueError:
            return False
    return True


class Error(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    message = models.CharField(max_length=65535, blank=True)
    _min_dump = ('id', 'message',)
    def __str__(self):
        return self.id + ":" + self.message



class Arch(models.Model):
    name = models.CharField(max_length=255, primary_key=True)
    _min_dump = ('name')
    def __str__(self):
        return self.name


class Component(models.Model):
    name = models.CharField(max_length=255, primary_key=True)
    _min_dump = ('name',)
    def __str__(self):
        return self.name


class Framework(models.Model):
    name = models.CharField(max_length=255, primary_key=True)
    _min_dump = ('name', )
    def __str__(self):
        return self.name


class Project(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255)
    _min_dump = ('id', 'name',)
    def __str__(self):
        return self.name


class Document(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    components = models.ManyToManyField(Component, blank=True)
    title = models.CharField(max_length=65535)
    _min_dump = ('id', 'component', 'title', )
    def __str__(self):
        return self.id


class WorkItem(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    type = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=65535, blank=True)
    automation = models.CharField(max_length=255, default='notautomated', blank=True)
    commit = models.CharField(max_length=255, blank=True)
    project = models.ForeignKey(Project, blank=True, null=True, related_name='workitems')
    archs = models.ManyToManyField(Arch, blank=True, related_name='workitems')
    documents = models.ManyToManyField(Document, blank=True, related_name='workitems')
    errors = models.ManyToManyField(Error, blank=True, related_name='workitems')

    comment = models.CharField(max_length=65565, blank=True, null=True)
    need_automation = models.BooleanField(default=False)
    maitai_id = models.CharField(max_length=65535, blank=True)
    jira_id = models.CharField(max_length=65535, blank=True, null=True)
    updated = models.DateTimeField(blank=False, auto_now_add=True)

    changes = models.TextField(blank=True, null=True)
    confirmed = models.DateTimeField(blank=True, null=True)

    #Field used to perform runtime error checking
    error_related = models.ManyToManyField('self', blank=True)

    _user_data = ('comment', 'need_automation', 'maitai_id', 'jira_id', )

    _min_dump = ('id', 'type', 'title', 'automation', 'commit', 'project', 'archs',
                 'documents', 'maitai_id', 'jira_id', 'updated', 'errors', 'comment', 'changes', 'confirmed') #TODO: some errors can be ignored

    def __str__(self):
        return self.id

    def get_related(self):
        """Get related objects for error cheking"""
        return (
            list(self.error_related.all()) +
            list(self.caselinks.all())
        )

    def mark_deleted(self):
        self.errors.add("WORKITEM_DELETED")
        self.save()

    def mark_notdeleted(self):
        self.errors.remove("WORKITEM_DELETED")
        self.save()

    @transaction.atomic
    def error_check(self, depth=1):
        if depth > 0:
            # error_related may change, so check it first
            for item in self.error_related.all():
                item.error_check(depth - 1)

        self.error_related.clear()

        deleted = False
        if self.errors.filter(id="WORKITEM_DELETED").exists():
            deleted = True

        self.errors.clear()

        cases_duplicate = WorkItem.objects.filter(title=self.title)
        if len(cases_duplicate) > 1:
            self.errors.add("WORKITEM_TITLE_DUPLICATE")
            for case in cases_duplicate:
                if case == self:
                    continue
                self.error_related.add(case)

        links = Linkage.objects.filter(workitem=self)

        if len(links) > 1:
            self.errors.add("WORKITEM_MULTI_PATTERN")

        if len(links) == 0:
            if self.automation not in ['notautomated', 'manualonly']:
                self.errors.add("WORKITEM_AUTOMATED_NO_LINKAGE")
        else:
            if self.automation != 'automated':
                self.errors.add("WORKITEM_NOTAUTOMATED_WITH_LINKAGE")

        if self.comment:
            self.errors.add("WORKITEM_HAS_COMMENT")

        if self.changes:
            self.errors.add("WORKITEM_CHANGED")

        if deleted:
            self.errors.add("WORKITEM_DELETED")
        if depth > 0:
            for item in self.get_related():
                item.error_check(depth - 1)

        self.save()


class AutoCase(models.Model):
    id = models.CharField(max_length=65535, primary_key=True)
    archs = models.ManyToManyField(Arch, blank=True, related_name='autocases')
    components = models.ManyToManyField(Component, related_name='autocases', blank=True)
    framework = models.ForeignKey(Framework, null=True, on_delete=models.PROTECT,
                                  related_name='autocases')
    start_commit = models.CharField(max_length=255, blank=True, null=True)
    end_commit = models.CharField(max_length=255, blank=True, null=True)
    pr = models.CharField(max_length=255, blank=True, null=True)
    errors = models.ManyToManyField(Error, blank=True, related_name='autocases')

    #Field used to perform runtime error checking
    #error_related = models.ManyToManyField('self', blank=True)
    _min_dump = ('id', 'archs', 'framework', 'start_commit', 'end_commit', 'components',
                 'pr', 'errors')

    def get_related(self):
        """Get related objects for error cheking"""
        return (
            list(self.caselinks.all())
        )

    def __str__(self):
        return self.id

    def autolink(self):
        for link in Linkage.objects.all():
            if link.test_match(self):
                link.autocases.add(self)
                link.save()
        for link in AutoCaseFailure.objects.all():
            if link.test_match(self):
                link.autocases.add(self)
                link.save()

    @transaction.atomic
    def error_check(self, depth=1):
        #TODO: Use external errors list for prevent certain error from being cleaned.
        add_in_pr = self.errors.filter(id="AUTOCASE_PR_NOT_MERGED").exists()
        deleted_in_pr = self.errors.filter(id="AUTOCASE_DELETED_IN_PR").exists()

        self.errors.clear()

        if len(self.caselinks.all()) < 1:
            self.errors.add("NO_LINKAGE")

        if len(self.caselinks.all()) > 1:
            self.errors.add("MULTIPLE_WORKITEM")

        if depth > 0:
            for item in self.get_related():
                item.error_check(depth - 1)

        if add_in_pr:
            self.errors.add("AUTOCASE_PR_NOT_MERGED")
        if deleted_in_pr:
            self.errors.add("AUTOCASE_DELETED_IN_PR")

        self.save()


class Linkage(models.Model):
    workitem = models.ForeignKey(WorkItem, on_delete=models.PROTECT, null=True, related_name='caselinks')
    autocases = models.ManyToManyField(AutoCase, blank=True, related_name='caselinks')
    autocase_pattern = models.CharField(max_length=65535)
    framework = models.ForeignKey(Framework, on_delete=models.PROTECT, null=True,
                                  related_name='caselinks')
    errors = models.ManyToManyField(Error, blank=True, related_name='caselinks')

    #Field used to perform runtime error checking
    error_related = models.ManyToManyField('self', blank=True)

    _min_dump = ('workitem', 'autocase_pattern', 'framework', )

    def __str__(self):
        return str(self.workitem) + " - " + str(self.autocase_pattern)

    class Meta:
        unique_together = ("workitem", "autocase_pattern",)

    def test_match(self, auto_case):
        """
        Test if a autocase match with the name pattern.
        """
        return _test_pattern_match(self.autocase_pattern, auto_case.id)

    def autolink(self):
        for case in AutoCase.objects.all():
            if self.test_match(case):
                self.autocases.add(case)
        self.save()

    def get_related(self):
        """Get related objects for error cheking"""
        return (
            list(self.error_related.all()) +
            list([self.workitem]) +
            list(self.autocases.all())
        )

    @transaction.atomic
    def error_check(self, depth=1):
        if depth > 0:
            for item in self.error_related.all():
                item.error_check(depth - 1)
        self.error_related.clear()
        self.errors.clear()

        links_duplicate = Linkage.objects.filter(autocase_pattern=self.autocase_pattern)

        if len(self.autocases.all()) < 1:
            self.errors.add("PATTERN_INVALID")

        if len(links_duplicate) > 1:
            self.errors.add("PATTERN_DUPLICATE")
            for link in links_duplicate:
                if link == self:
                    continue
                self.error_related.add(link)

        if depth > 0:
            for item in self.get_related():
                item.error_check(depth - 1)

        self.save()


class Bug(models.Model):
    """
    Linked with AutoCase through AutoCasesFailure for better autocase failure matching,
    Linked with ManualCase directly.
    """
    id = models.CharField(max_length=255, primary_key=True)

    _min_dump = ('id', )

    def __str__(self):
        return "<Bug %s>" % self.id


class BlackListEntry(models.Model):
    status = models.CharField(max_length=255, null=True)
    description = models.TextField(blank=True)
    bugs = models.ManyToManyField('Bug', blank=True, related_name='black_list_entries')
    manualcases = models.ManyToManyField('WorkItem', blank=True, related_name='black_list_entries')
    autocase_failures = models.ManyToManyField('AutoCaseFailure', related_name='black_list_entries')
    errors = models.ManyToManyField(Error, blank=True, related_name='black_list_entries')

    _min_dump = ('status', 'description', 'bugs', 'manualcases', 'autocase_failures' )

    _types = ['bug', 'bug-skip', 'case-update-skip', 'case-update', ] #TODO
    _bug_types = ['bug', 'bug-skip', 'case-update-skip', 'case-update', ] #TODO

    def clean(self):
        assert(self._bug_types in self._types)
        if self.status not in self._types:
            raise ValidationError(_('Unsupported AutoCase Failure Type' + str(self.type)))
        if self.status in self._bug_types and not self.bugs:
            raise ValidationError(_('Entry\'s bugs attribute can\'t be empty with status %s.' % self.status))

    @property
    def autocases(self):
        cases = []
        for failure in self.autocase_failures.all():
            cases += failure.autocases.all()
        return cases

    @transaction.atomic
    def error_check(self, depth=1):
        # TODO
        pass

    def __str__(self):
        return self.status + self.description


class AutoCaseFailure(models.Model):
    autocases = models.ManyToManyField(AutoCase, related_name="autocase_failures", blank=True)
    framework = models.ForeignKey(Framework, on_delete=models.PROTECT, null=True,
                                  related_name='autocase_failures')
    failure_regex = models.CharField(max_length=65535)
    autocase_pattern = models.CharField(max_length=65535)
    errors = models.ManyToManyField(Error, blank=True, related_name='autocase_failures')

    _min_dump = ('framework', 'failure_regex', 'autocase_pattern', )

    class Meta:
        unique_together = ("failure_regex", "autocase_pattern",)

    def test_match(self, auto_case):
        """
        Test if a autocase match with the name pattern.
        """
        return _test_pattern_match(self.autocase_pattern, auto_case.id)

    def autolink(self):
        for case in AutoCase.objects.all():
            if self.test_match(case):
                self.autocases.add(case)
        self.save()

    @transaction.atomic
    def error_check(self, depth=1):
        # TODO
        pass

    def __str__(self):
        return "<'%s' failing with '%s'>" % (self.autocase_pattern, self.failure_regex)
