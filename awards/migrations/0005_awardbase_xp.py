# Generated by Django 3.1 on 2021-09-19 23:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('awards', '0004_auto_20210420_2023'),
    ]

    operations = [
        migrations.AddField(
            model_name='awardbase',
            name='xp',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
