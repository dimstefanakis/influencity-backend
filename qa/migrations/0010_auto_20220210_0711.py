# Generated by Django 3.1 on 2022-02-10 07:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qa', '0009_auto_20220210_0622'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='zoom_link',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='question',
            name='zoom_password',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
