# Generated by Django 2.2.4 on 2020-10-22 17:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('instructor', '0014_auto_20201014_2013'),
        ('projects', '0009_project_members'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='coach',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='instructor.Coach'),
        ),
    ]
