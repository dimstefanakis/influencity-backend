# Generated by Django 3.1 on 2022-01-25 17:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qa', '0003_auto_20220125_1542'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='answer_needed_now',
            field=models.BooleanField(default=False),
        ),
    ]
