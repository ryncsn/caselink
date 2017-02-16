# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-02-17 07:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caselink', '0014_auto_20170214_0740'),
    ]

    operations = [
        migrations.AlterField(
            model_name='autocasefailure',
            name='errors',
            field=models.ManyToManyField(blank=True, related_name='autocase_failures', to='caselink.Error'),
        ),
    ]
