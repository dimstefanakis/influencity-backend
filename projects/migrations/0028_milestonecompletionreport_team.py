# Generated by Django 3.1 on 2021-03-31 19:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0027_milestonecompletionreport_video_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='milestonecompletionreport',
            name='team',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='projects.team'),
        ),
    ]