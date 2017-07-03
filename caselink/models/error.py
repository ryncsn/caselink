from django.db import models


class Error(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    message = models.CharField(max_length=65535, blank=True)
    _min_dump = ('id', 'message',)

    def __str__(self):
        return self.id + ":" + self.message


class ErrorCheckModel(object):
    """
    Model inherit this will have a errors m2m relation.
    If error checking related to other object, subclass should have a error_related m2m relation.
    """
    errors = models.ManyToManyField(Error, blank=True, related_name='autocases')

    def get_error_related(self):
        """
        Deleting or updating instance of this model may introduce/fix error for other models,
        then this method should return a list of instances need to be checked.
        """
        return []

    def error_check(self, depth=1):
        """
        Implement a error_check function, to check if there are any
        linkage or metadata error.
        """
        raise NotImplementedError()
